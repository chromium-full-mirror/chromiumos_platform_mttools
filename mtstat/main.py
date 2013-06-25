#! /usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from mtedit import MTEdit
from mtlib import Log
from mtreplay import MTReplay
from mtstat import MTStat
from optparse import OptionParser

usage = """Multitouch Statistic Collector

Download latest N feedback reports
$ %prog -d N

Run and print statistics
$ %prog

Randomly select N logs and run
$ %prog -n N

Search all (or -n N) logs for occurence of TAG and
serve the search results in MTEdit
$ %prog -s TAG
"""

def main():
  parser = OptionParser(usage=usage)
  parser.add_option('-d',
                    dest='download', default=None,
                    help='download more log files')
  parser.add_option('-o',
                    dest='offset', default=0,
                    help='offset for downloading log files')
  parser.add_option('-n',
                    dest='number', default=None,
                    help='number of log files to gather stats on')
  parser.add_option('-s',
                    dest='search', default=None,
                    help='search for specific tags')
  (options, args) = parser.parse_args()

  stat = MTStat()
  if options.download:
    stat.Download(options.download, options.offset)
    return

  number = None if options.number is None else int(options.number)

  if options.search:
    results = stat.Search(options.search, number)
    print "Found occurences in %d files" % len(results)
    print "Serving results, press CTRL-C to abort"
    for filename, entries in results.items():
      print "%d occurences in %s:" % (len(entries), filename)
      for entry in entries:
        print "    %f" % entry.timestamp
      first = entries[0]

      replay_results = MTReplay().Replay(Log(first.id))
      editor = MTEdit()
      editor.View(replay_results.log, first.timestamp)
      raw_input("Press Enter to continue...")
    return

  results = stat.GatherStats(number)
  for key, (count, ratio) in results.items():
    print key, '=', count, "(%d%%)" % (ratio * 100)

if __name__ == '__main__':
  main()