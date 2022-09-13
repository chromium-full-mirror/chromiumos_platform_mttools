#! /usr/bin/env python
# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from mtedit import MTEdit
from mtlib import Log
from mtreplay import MTReplay
from mtstat import MTStat
from optparse import OptionParser

usage = """Multitouch Statistic Collector

This tool is used to gather statistics on large amounts of touchpad data from
feedback reports. Samples are gathered by parsing the log output of the
gestures library. The gesture library provides the MTStatSample/Set commands to
create samples.

Gestures Library API
--------------------

For example you can extend a decision tree in the gestures library code with
calls to:

MTStatSample("MyDecision", "CaseA");
MTStatSample("MyDecision", "CaseB");
MTStatSample("MyDecision", "CaseC");

Next to string samples you can also sample integers with MTStatSampleInt.
For example you can sample the number of fingers in each hardware state:

MTStatSampleInt("NumFingers", hwstate.num_fingers);

Sometimes you want to only generate one sample per file, for example to
count the number of clicks in each file. Call MTStatUpdate[Int] every time
your value is changed and the last update will be used by MTStat.
For example every time a click is performed you call the following:

static int num_of_clicks = 0;
MTStatUpdateInt("NumClicks", ++num_of_clicks);

Preparing MTStat
----------------

To run on feedback reports you first have to download a bunch of them. MTStat
does this for you, for example by downloading the latest 1000 reports:

$ %prog -d 1000

Sample Histograms
------------------

Running mtstat will then generate statistic on how often each of the logged
cases happened. Optionally you can specify the number of log files to process,
per default it will always run all downloaded reports:

$ %prog [-n 1000]

The output will be presented as a histogram of how often each case appeared.
For integer samples with a lot of different values, a bin-based histogram is
used.

Searching Samples
-----------------

You can then also search for cases and view their activity log to figure out
which user activity lead to this decision. For example:

$ %prog -s "MyDecision == CaseC" [-n 100]

When searching integer samples, unequality operators are supported:

$ %prog -s "NumFingers >= 3" [-n 100]

Of course the same thing works on samples made with MTStatUpdate. For example
to find files with a lot of clicks:

$ %prog -s "NumClicks > 300" [-n 100]

Advanced Search
---------------

You can search the gestures library log output with regular expressions.
For example to see if any ERROR messages happen:

$ %prog -r "ERROR:"

Searching for Changed Gestures
------------------------------

MTStat can also be used to search for changes in the generated gestures
introduced by changes to the code of the gestures library.

In order to do so make local changes to the gestures library without
commiting them. Then run:

$ %prog -c [-n 100]

This command will compare to the HEAD version of gestures and present all
changed gestures.

You can also limit the search to a certain type of gestures:

$ %prog -c -g "ButtonDown" [-n 100]
"""

def main():
  parser = OptionParser(usage=usage)
  parser.add_option('-d', '--download',
                    dest='download', default=None,
                    help='download more log files')
  parser.add_option('-n', '--number',
                    dest='number', default=None,
                    help='number of log files to gather stats on')
  parser.add_option('-p', '--platform',
                    dest='platform', default=None,
                    help='only use log files from specified platform')
  parser.add_option('-s', '--search',
                    dest='search', default=None,
                    help='search for specific tags')
  parser.add_option('-l', '--list',
                    dest='list', action='store_true', default=False,
                    help='just print list, don\'t view search results')
  parser.add_option('-r', '--regex',
                    dest='regex', default=None,
                    help='search log output for regex')
  parser.add_option('-g', '--gestures',
                    dest='gestures', default=None,
                    help='search log for gestures')
  parser.add_option('-b', '--bins',
                    dest='bins', default=10,
                    help='number of bins for histograms')
  parser.add_option('-c', '--changes',
                    dest='changes', action='store_true', default=False,
                    help='search for changes introduced by ' +
                         'local code changes to the gestures library')

  (options, args) = parser.parse_args()

  stat = MTStat()
  if options.download:
    stat.Download(options.download)
    return

  number = None if options.number is None else int(options.number)

  if (options.search or options.regex or options.gestures or
      options.changes):
    if options.changes:
      results = stat.SearchChanges(options.gestures,
                                   number=number, platform=options.platform)
    else:
      results = stat.Search(search=options.search, gestures=options.gestures,
                            regex=options.regex, number=number,
                            platform=options.platform)

    print("Found occurences in %d files" % len(results))
    print("Serving results, press CTRL-C to abort")
    for filename, result in results.items():
      print("%d occurences in %s:" % (len(result.matches), filename))
      for match in result.matches:
        print("    ", match)

      # display link to MTEdit session
      if not options.list:
        MTEdit().View(result.log, result.matches[0].timestamp)
        raw_input("Press Enter to continue...")
    return


  bins = int(options.bins)
  results = stat.GatherStats(number, platform=options.platform, num_bins=bins)
  for key, hist in results.items():
    print("%s:" % key)
    overall_count = sum(hist.values())
    for value, count in hist.items():
      percent = int(round(float(count) / float(overall_count) * 100))
      percent_str = "(" + str(percent) + "%)"
      graph = "=" * int(round(percent / 2))
      print("  {0:>6} {1:<6} {2:6} |{3}".format(
          str(value) + ":", count, percent_str, graph))

if __name__ == '__main__':
  main()
