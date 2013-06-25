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


def MTStatGatherSubprocess(filename):
  return MTStat().GatherEntriesFromFile(filename)


def MTStatDownloadSubprocess(id):
  return MTStat().DownloadFile(id)


class MTStatEntry(object):
  TAG = 'MTStat:'
  def __init__(self, logline, id):
    self.logline = logline
    self.id = id
    startidx = logline.find(MTStatEntry.TAG) + len(MTStatEntry.TAG)
    self.tagline = logline[startidx:]

  @property
  def timestamp(self):
    match = re.search('([0-9]+\.[0-9]+)\:MTStat', self.logline)
    if match:
      return float(match.group(1))
    return 0.0

class MTStat(object):
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

  def GatherEntriesFromFile(self, filename):
    """ Gathers all MTStat entries from a log file

    Replays a logfile and searched for MTStat log entries.
    The return value is a list of all log entries found.
    """
    try:
      log = Log(filename)
      id = os.path.basename(filename)
      replay = MTReplay()
      platform = replay.PlatformOf(log)
      if not platform:
        print 'No platform for %s' % os.path.basename(filename)
        return ([], 0)

      # count the number of syn reports in log file
      num_syn = len(tuple(re.finditer("0000 0000 0", log.evdev)))

      result = replay.Replay(log)
      stats = []
      for line in result.gestures_log.splitlines():
        if MTStatEntry.TAG in line:
          stats.append(MTStatEntry(line, filename))
      return (stats, num_syn)
    except:
      print filename, traceback.format_exc()
      return ([], 0)

  def _GatherEntries(self, number, parallel):
    files = [os.path.abspath(os.path.join(log_dir, f))
             for f in os.listdir(log_dir)
             if f.isdigit()]

    if number is not None:
      files = random.sample(files, number)

    print "Processing %d log files" % len(files)

    if parallel:
      pool = multiprocessing.Pool()
      pool_results = pool.map(MTStatGatherSubprocess, files)
      pool.terminate()
    else:
      pool_results = map(MTStatGatherSubprocess, files)

    entries = []
    syn_count = 0
    for pool_entries, pool_syn_count in pool_results:
      syn_count = syn_count + pool_syn_count
      entries.extend(pool_entries)

    # syn reports are coming at approx 60 Hz on most platforms
    syn_per_second = 60.0
    hours = syn_count / syn_per_second / 60.0 / 60.0

    print "Processed ~%.2f hours of interaction" % hours

    return entries

  def Search(self, search, number=None, parallel=True):
    """ Search for occurences of a specific tag

    number: optional number of random reports to use
    parallel: use parallel processing

    returns a dictionary of lists containing the matches
    for each file.
    """
    entries = self._GatherEntries(number, parallel)

    entries_by_id = collections.defaultdict(list)
    for entry in entries:
      if entry.tagline == search:
        entries_by_id[entry.id].append(entry)
    return entries_by_id

  def GatherStats(self, number=None, parallel=True):
    """ Gathers stats on feedback reports.

    Each tag is part of a group, with group names separated
    by colons. Each group can also have sub-groups for example:

    GroupA:ValueA
    GroupA:ValueB
    GroupA:Subgroup:ValueA
    GroupA:Subgroup:ValueB

    number: optional number of random reports to use
    parallel: use parallel processing

    returns a dictionary that maps a tag to a tuple of
    it's number of occurences and it's ratio.
    The ratios are calculated within each group (excluding sub-groups)
    """
    entries = self._GatherEntries(number, parallel)

    # build histogram of stat lines
    counts = collections.defaultdict(lambda: 0)
    num_syn = 0
    for entry in entries:
      counts[entry.tagline] = counts[entry.tagline] + 1

    def get_parent(tagline):
      return ":".join(tagline.split(":")[:-1])

    # calculate ratios
    ratios = {}
    for tagline, count in counts.items():
      parent = get_parent(tagline)
      sibling_sum = 0
      for other, other_count in counts.items():
        if get_parent(other) == parent:
          sibling_sum = sibling_sum + other_count
      ratios[tagline] = float(count) / float(sibling_sum)

    stats = {}
    for key in counts.keys():
      stats[key] = (counts[key], ratios[key])

    return collections.OrderedDict(sorted(stats.iteritems()))
