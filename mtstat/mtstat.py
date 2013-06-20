#! /usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from mtlib.log import Log, FeedbackDownloader, FeedbackLog
from mtreplay import MTReplay
import json
import multiprocessing
import os
import random
import re
import urllib

script_dir = os.path.dirname(os.path.realpath(__file__))
log_dir = os.path.join(script_dir, '../cache/logs/')
if not os.path.exists(log_dir):
  os.mkdir(log_dir)


def MTStatSubprocess(filename):
  return MTStat().GatherStatsFromFile(filename)

def MTStatDownloadSubprocess(id):
  return MTStat().DownloadFile(id)

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
    except:
      print 'Invalid report %s' % id
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

  def GatherStatsFromFile(self, filename):
    """ Gathers statistics on a log file

    Replays a logfile and searched for MTStat log entries.
    The return value is a list of all log entries found.
    """
    TAG = 'MTStat:'

    log = Log(filename)
    replay = MTReplay()
    platform = replay.PlatformOf(log)
    if not platform:
      print 'No platform for %s' % os.path.basename(filename)
      return ([], 0)
    print 'Replaying %s on platform %s' % (os.path.basename(filename),
                                           platform.name)

    # count the number of syn reports in log file
    num_syn = len(tuple(re.finditer("0000 0000 0", log.evdev)))

    result = replay.Replay(log)
    stats = []
    for line in result.gestures_log.splitlines():
      if TAG in line:
        stats.append(line[line.find(TAG) + len(TAG):])
    return (stats, num_syn)

  def GatherStats(self, number=None, parallel=True):
    """ Gathers stats on feedback reports.

    number: optional number of random reports to use
    parallel: use parallel processing

    returns a dictionary representing the histogram of all
    MTStat log entries.
    """
    files = [os.path.join(log_dir, f) for f in os.listdir(log_dir)
                                      if f.isdigit()]

    if number is not None:
      files = random.sample(files, number)

    if parallel:
      pool = multiprocessing.Pool()
      results = pool.map(MTStatSubprocess, files)
      pool.terminate()
    else:
      results = map(MTStatSubprocess, files)

    # build histogram of stat lines
    stats = {}
    num_syn = 0
    for stat_lines, log_syn in results:
      num_syn = num_syn + log_syn
      for line in stat_lines:
        if line not in stats:
          stats[line] = 0
        stats[line] = stats[line] + 1

    # syn reports are coming at 30 Hz on most platforms
    syn_per_second = 60.0
    hours = num_syn / syn_per_second / 60.0 / 60.0

    print "Processed %.2f hours of interaction)" % hours
    return stats
