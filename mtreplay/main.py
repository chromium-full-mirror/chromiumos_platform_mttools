#! /usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from mtreplay import MTReplay
from mtlib import Log
from optparse import OptionParser
import sys


usage = """Multitouch Replay Usage Examples:

Replaying logs and print activity_log:
$ %prog filename.log (from file)
$ %prog 172.22.75.0 (from device ip address)
$ %prog http://feedback.google.com/... (from feedback report url)

Print which platform this log is replayed on:
$ %prog log -p

View gestures log
$ %prog log -v gestures-log
$ %prog log -vgl

View evdev log
$ %prog log -v evdev-log
$ %prog log -vel

View activity in MTEdit:
$ %prog log -v activity
$ %prog log -va"""


def main(argv):
  parser = OptionParser(usage=usage)
  parser.add_option('-p', '--platform',
                    dest='platform', action='store_true', default=False,
                    help='print platform this log is replayed on')
  parser.add_option('-v', '--view',
                    dest='view', default=None,
                    help='select output of relay to view')
  (options, args) = parser.parse_args()

  replay = MTReplay()

  if len(args) != 1:
    parser.print_help()
    exit(-1)

  log = Log(args[0])

  if options.platform:
    print replay.PlatformOf(log).name
    return

  replay.Replay(log).View(options.view)


if __name__ == '__main__':
  main(sys.argv)
