#! /usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from optparse import OptionParser
from mtstat import MTStat

usage = """Multitouch Statistic Collector

Download latest N feedback reports
$ %prog -d N
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
  (options, args) = parser.parse_args()

  stat = MTStat()
  if options.download:
    stat.Download(options.download, options.offset)
    return

  number = None if options.number is None else int(options.number)
  results = stat.GatherStats(number)
  for key, value in results.items():
    print key, '=', value

if __name__ == '__main__':
  main()