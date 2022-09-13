#! /usr/bin/env python
# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from mtedit import MTEdit
from mtlib import Log
from mtlib.feedback import FeedbackDownloader
from optparse import OptionParser
import sys


usage = """Multitouch Editor Usage Examples:

Viewing logs:
$ %prog filename.log (from file)
$ %prog 172.22.75.0 (from device ip address)
$ %prog http://feedback.google.com/... (from feedback report url)

Edit log and save result into output.log:
$ %prog log -o output.log

Download log and save without editing:
$ %prog log -d -o output.log"""


def main(argv):
  parser = OptionParser(usage=usage)
  parser.add_option('-o',
                    dest='out', default=None,
                    help='set target filename for storing results',
                    metavar='output.log')
  parser.add_option('-d', '--download',
                    dest='download', action='store_true', default=False,
                    help='download file only, don\'t edit.')
  parser.add_option('-e', '--evdev',
                    dest='evdev', default=None,
                    help='path to local evdev log file')
  parser.add_option('-n', '--new',
                    dest='new', action='store_true', default=False,
                    help='Create new device logs before downloading. '+
                         '[Default: False]')
  parser.add_option('-p', '--persistent',
                    dest='persistent', action='store_true', default=False,
                    help='Keep server alive until killed in the terminal '+
                         'via CTRL-C [Default: False]')
  parser.add_option('-s', '--serve',
                    dest='serve', action='store_true', default=False,
                    help='Serve a standalone MTEdit.')
  parser.add_option('-c', '--screenshot',
                    dest='screenshot', action='store_true', default=False,
                    help='Force an attempt to find and download a screenshot.')
  parser.add_option('--login',
                    dest='login', action='store_true', default=False,
                    help='Force (re-)login to feedback.corp.google.com')
  (options, args) = parser.parse_args()

  editor = MTEdit(persistent=options.persistent)

  if options.serve:
    editor.Serve()
    return

  if options.login:
    FeedbackDownloader(force_login=True)

  if len(args) != 1:
    parser.print_help()
    exit(-1)

  log = Log(args[0], options)

  if options.download:
    if not options.out:
      print('--download requires -o to be set.')
      exit(-1)
    log.SaveAs(options.out)
  else:
    if options.out is None:
      editor.View(log)
    else:
      log = editor.Edit(log)
      if log:
        log.SaveAs(options.out)

  log.CleanUp()


if __name__ == '__main__':
  main(sys.argv)
