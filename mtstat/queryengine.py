#! /usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from mtlib.log import FeedbackDownloader, FeedbackLog, Log
from mtreplay import MTReplay
import json
import multiprocessing
import os
import random
import re
import traceback
import urllib


# prepare folder for log files
script_dir = os.path.dirname(os.path.realpath(__file__))
log_dir = os.path.join(script_dir, '../cache/logs/')
if not os.path.exists(log_dir):
  os.mkdir(log_dir)


class Query(object):
  """ Abstract class for queries.

  These objects are applied to files by the QueryEngine, which
  calls FindMatches to execute the search on the replay results.

  capture_logs can be set to true to direct the QueryEngine to return
  the Log object in the QueryResults.
  """
  def __init__(self):
    self.capture_logs = False

  def FindMatches(self, replay_results, filename):
    """ Returns a list of QueryMatch objects """
    return []


class QueryMatch(object):
  """ Describes a match and contains information on how to locate it """
  def __init__(self, filename, timestamp, line):
    self.filename = filename
    self.timestamp = timestamp
    self.line = line

  def __str__(self):
    if self.timestamp:
      return str(self.timestamp) + ": " + self.line
    else:
      return self.line

  def __repr__(self):
    return str(self)


class QueryResult(object):
  """ Describes the results of a query on a file.

  This includes all matches found in this file, the number of
  SYN reports processed and optionally the activity Log object,
  if requested by the Query."""
  def __init__(self, filename):
    self.filename = filename
    self.syn_count = 0
    self.matches = []
    self.log = None


class QueryEngine(object):
  """ This class allows queries to be executed on a large number of log files.

  It managed a pool of log files, allows more log files to be downloaded and
  can execute queries in parallel on this pool of log files.
  """

  def ExecuteSingle(self, filename, query):
    """ Executes a query on a single log file """
    log = Log(filename)
    replay = MTReplay()
    result = QueryResult(filename)

    # find platform for file
    platform = replay.PlatformOf(log)
    if not platform:
      print 'No platform for %s' % os.path.basename(filename)
      return result

    # count the number of syn reports in log file
    result.syn_count = len(tuple(re.finditer("0000 0000 0", log.evdev)))

    # run replay
    try:
      replay_result = replay.Replay(log)
    except:
      return result

    result.matches = query.FindMatches(replay_result, filename)
    if result.matches:
      result.log = replay_result.log

    return result

  def Execute(self, filenames, queries, parallel=True):
    """ Executes a query on a list of log files.

    filenames: list of filenames to execute
    queries: either a single query object for all files,
             or a dictionary mapping filenames to query objects.
    parallel: set to False to execute sequentially.
    """

    print "Processing %d log files" % len(filenames)

    if hasattr(queries, 'FindMatches'):
      queries = dict([(filename, queries) for filename in filenames])

    # arguments for QuerySubprocess
    parameters = [(name, queries[name])
                  for name in filenames if name in queries]

    # process all files either in parallel or sequential
    if parallel:
      pool = multiprocessing.Pool()
      results = pool.map(ExecuteSingleSubprocess, parameters)
      pool.terminate()
    else:
      results = map(ExecuteSingleSubprocess, parameters)

    # count syn reports
    syn_count = sum([result.syn_count for result in results])

    # create dict of results by filename
    result_dict = dict([(result.filename, result)
                        for result in results
                        if result.matches])

    # syn reports are coming at approx 60 Hz on most platforms
    syn_per_second = 60.0
    hours = syn_count / syn_per_second / 60.0 / 60.0
    print "Processed ~%.2f hours of interaction" % hours

    return result_dict

  def SelectFiles(self, number):
    """ Returns a random selection of files from the pool """
    # list all log files
    files = [os.path.abspath(os.path.join(log_dir, f))
             for f in os.listdir(log_dir)
             if f.isdigit()]

    # randomly select subset of files
    if number is not None:
      files = random.sample(files, number)
    return files

  def DownloadFile(self, id):
    """Download one feedback log into the pool."""
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
    """Download 'num' new feedback logs into the pool."""
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
      results = pool.map(DownloadFileSubprocess, report_ids)
      pool.terminate()
    else:
      results = map(DownloadFileSubprocess, report_ids)


def ExecuteSingleSubprocess(args):
  """ Wrapper for subprocesses to run ExecuteSingle """
  try:
    return QueryEngine().ExecuteSingle(args[0], args[1])
  except Exception, e:
    traceback.print_exc()
    raise e


def DownloadFileSubprocess(id):
  """ Wrapper for subprocesses to run DownloadFile """
  try:
    return QueryEngine().DownloadFile(id)
  except Exception, e:
    traceback.print_exc()
    raise e