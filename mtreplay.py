#! /usr/bin/env python
# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from mtreplay import MTReplay
from mtlib import Log, PlatformDatabase
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
  parser.add_option('--gdb',
                    dest='gdb', action='store_true', default=False,
                    help='setup gdb session to run replay')
  parser.add_option('--force', '-f',
                    dest='force', default=None,
                    help='force platform for replay')
  parser.add_option('--add-platform', '-a',
                    dest='add', default=None,
                    help='add platform of device to database')
  (options, args) = parser.parse_args()

  if options.add:
    PlatformDatabase.RegisterPlatformFromDevice(options.add)
    return

  replay = MTReplay()
  replay.Recompile()

  if len(args) != 1:
    parser.print_help()
    exit(-1)

  log = Log(args[0])

  if options.platform:
    platform = replay.PlatformOf(log, True)
    if platform:
      print(platform.name)
    return

  results = replay.Replay(log, force_platform=options.force, gdb=options.gdb)
  if results:
    results.View(options.view)


if __name__ == '__main__':
  main(sys.argv)
