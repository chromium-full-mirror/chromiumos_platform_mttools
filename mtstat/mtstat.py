#! /usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from mtlib.log import Log, FeedbackDownloader, FeedbackLog
from mtreplay import MTReplay
import collections
import json
import multiprocessing
import os
import random
import re
import traceback
import urllib

script_dir = os.path.dirname(os.path.realpath(__file__))
log_dir = os.path.join(script_dir, '../cache/logs/')
if not os.path.exists(log_dir):
  os.mkdir(log_dir)


def SortedDict(dict):
  return collections.OrderedDict(sorted(dict.items(), key=lambda t: t[0]))


def MTStatSearchSubprocess(params):
  return MTStat().FindMatchesInFile(params[0], params[1])


def MTStatDownloadSubprocess(id):
  return MTStat().DownloadFile(id)


class SearchMatch(object):
  # Example: MTStat:124.321:Key=Value
  mtstat_regex = re.compile('MTStat:([0-9]+\.[0-9]+):(\w+)([=:])(\w+)')

  def __init__(self, line, file):
    self.line = line
    self.file = file

    self.key = None
    self.value = None
    self.operator = None
    self.timestamp = None
    self.ismtstat = False

    match = SearchMatch.mtstat_regex.search(self.line)
    if match:
      self.timestamp = float(match.group(1))
      self.key = match.group(2)
      self.operator = match.group(3)
      self.value = match.group(4)
      self.ismtstat = True


class MTStat(object):

  search_operators = {
    ">": lambda a, b: float(a) > float(b),
    ">=": lambda a, b: float(a) >= float(b),
    "<": lambda a, b: float(a) < float(b),
    "<=": lambda a, b: float(a) <= float(b),
    "=": lambda a, b: str(a) == str(b),
    "==": lambda a, b: str(a) == str(b),
    "!=": lambda a, b: str(a) != str(b)
  }

  def FindMatchesInFile(self, filename, regex_str=None):
    """ Searchs all MTStat entries from a log file

    Replays a logfile and searched for MTStat log entries.
    Returns two values, a list of SearchMarches and the number of
    SYN reports that has been processed.
    """
    try:
      log = Log(filename)

      # find platform for file
      replay = MTReplay()
      platform = replay.PlatformOf(log)
      if not platform:
        print 'No platform for %s' % os.path.basename(filename)
        return ([], 0)

      # count the number of syn reports in log file
      num_syn = len(tuple(re.finditer("0000 0000 0", log.evdev)))

      # run replay
      result = replay.Replay(log)

      # per default we search for MTStat lines
      if regex_str:
        regex = re.compile(regex_str)
      else:
        regex = SearchMatch.mtstat_regex

      # find all lines matching the regex
      stats = []
      for line in result.gestures_log.splitlines():
        if regex.search(line):
          stats.append(SearchMatch(line, filename))
      return (stats, num_syn)
    except:
      print filename, traceback.format_exc()
      return ([], 0)

  def _FindAllMatches(self, number, parallel, search_regex=None):
    # make sure the replay binaries are up to date
    MTReplay().Recompile()

    # list all log files
    files = [os.path.abspath(os.path.join(log_dir, f))
             for f in os.listdir(log_dir)
             if f.isdigit()]

    # randomly select subset of files
    if number is not None:
      files = random.sample(files, number)

    # arguments for MTStatSearchSubprocess
    parameters = [(file, search_regex) for file in files]

    print "Processing %d log files" % len(files)

    # process all files either in parallel or sequential
    if parallel:
      pool = multiprocessing.Pool()
      pool_results = pool.map(MTStatSearchSubprocess, parameters)
      pool.terminate()
    else:
      pool_results = map(MTStatSearchSubprocess, parameters)

    # merge results of each file into one big list
    entries = []
    syn_count = 0
    for file_entries, file_syn_count in pool_results:
      syn_count = syn_count + file_syn_count

      # the = operator is used to make only the latest
      # entry of each file count.
      file_uniques = {}
      for entry in file_entries:
        if entry.operator == '=':
          file_uniques[entry.key] = entry
        else:
          entries.append(entry)

      # add the last value of each unique entry
      for value in file_uniques.values():
        entries.append(value)

    # syn reports are coming at approx 60 Hz on most platforms
    syn_per_second = 60.0
    hours = syn_count / syn_per_second / 60.0 / 60.0

    print "Processed ~%.2f hours of interaction" % hours

    return entries

  def Search(self, query=None, regex=None, number=None, parallel=True):
    """ Search for occurences of a specific tag or regex.

    Specify either a 'query' or a 'regex'. Queries are formatted
    in a simple "key operator value" format. For example:
    "MyKey > 5" will return all matches where MyKey has a value
    of greater than 5.
    Supported operators are: >, <, >=, <=, =, !=

    number: optional number of random reports to use
    parallel: use parallel processing

    returns a dictionary of lists containing the matches
    for each file.
    """
    entries = self._FindAllMatches(number, parallel, search_regex=regex)

    if query:
      match = re.match("\s*(\w+)\s*([<>=!]+)\s*([0-9a-zA-Z]+)\s*", query)
      if not match:
        print query, " is not a valid query"
        return {}
      search_key = match.group(1)
      search_op = MTStat.search_operators[match.group(2)]
      search_value = match.group(3)

    entries_by_file = collections.defaultdict(list)
    for entry in entries:
      if query is None or (entry.key == search_key and
                           search_op(entry.value, search_value)):
        entries_by_file[entry.file].append(entry)
    return entries_by_file

  def GatherStats(self, number=None, parallel=True, num_bins=10):
    """ Gathers stats on feedback reports.

    Returns a dictionary with a histogram for each recorded key.
    """
    entries = self._FindAllMatches(number, parallel)

    # gather values for each key in a list
    value_collection = collections.defaultdict(list)
    for entry in entries:
      value_collection[entry.key].append(entry.value)

    # build histograms
    histograms = {}
    for key, values in value_collection.items():
      histograms[key] = self._Histogram(values, num_bins)
    return SortedDict(histograms)

  def _Histogram(self, values, num_bins):
    def RawHistogram(values):
      return SortedDict(collections.Counter(values))

    # convert all items to integers.
    integers = []
    for value in values:
      try:
        integers.append(int(value))
      except:
        # not an integer.
        return RawHistogram(values)

    # don't condense lists that are already small enough
    if len(set(integers)) <= num_bins:
      return RawHistogram(integers)

    # all integer values, use bins for histogram
    histogram = collections.OrderedDict()
    integers = sorted(integers)

    # calculate bin size (append one at the end to include last value)
    begin = integers[0]
    end = integers[-1] + 1
    bin_size = float(end - begin) / float(num_bins)

    # remove each bins integers from the list and count them.
    for i in range(num_bins):
      high_v = round((i + 1) * bin_size) + begin

      filtered = filter(lambda i: i >= high_v, integers)
      histogram["<%d" % high_v] = len(integers) - len(filtered)
      integers = filtered
    return histogram

  def DownloadFile(self, id):
    """Download one feedback log into cache."""
    downloader = FeedbackDownloader()

    filename = os.path.join(log_dir, id)
    if os.path.exists(filename):
      print 'Skipping existing report', id
      return

    print 'Downloading new report', id
    try:
      # might throw IO/Tar/Zip/etc exceptions
      report = FeedbackLog(id, force_latest='pad')
      # Test parse. Will throw exception on malformed log
      json.loads(report.activity)
    except:
      print 'Invalid report %s' % id
      return

    # check if report contains logs and actual events
    if report.activity and report.evdev and 'E:' in report.evdev:
      report.SaveAs(filename)
    else:
      print 'Invalid report %s' % id

  def Download(self, num, offset=0, parallel=True):
    """Download 'num' new feedback logs into cache."""
    downloader = FeedbackDownloader()

    # download list of feedback report id's
    params = {
      '$limit': str(num),
      '$offset': str(offset),
      'mapping': ':list',
      'productId': '208'  # ChromeOS
    }
    url = ('https://feedback.corp.google.com/resty/ReportSearch?' +
           urllib.urlencode(params))
    data = downloader.DownloadFile(url)
    data = data[data.find('{'):]  # strip garbage before json data

    reports_json = json.loads(data)
    report_ids = [item['id'] for item in reports_json['results']]

    # Download and check each report
    if parallel:
      pool = multiprocessing.Pool()
      results = pool.map(MTStatDownloadSubprocess, report_ids)
      pool.terminate()
    else:
      results = map(MTStatDownloadSubprocess, report_ids)
