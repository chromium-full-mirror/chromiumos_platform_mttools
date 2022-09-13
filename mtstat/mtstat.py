#! /usr/bin/env python
# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import Counter, defaultdict, namedtuple, OrderedDict
from itertools import chain
from mtreplay import MTReplay
from .queryengine import Query, QueryEngine, QueryMatch, QueryResult
import re


class MTStatQuery(Query):
  """ Searches for MTStat lines.

  An MTStat line looks like 'MTStat:124.321:Key=Value' and is used
  for generating statistics and searching of numeric values.
  """
  line_regex = re.compile('MTStat:([0-9]+\.[0-9]+):(\w+)([=:])(\w+)')
  line_match = namedtuple("LineMatch", "timestamp key operator value")

  @classmethod
  def MatchLine(cls, line):
    match = cls.line_regex.match(line)
    if match:
      return cls.line_match(
        timestamp=match.group(1),
        key=match.group(2),
        operator=match.group(3),
        value=match.group(4)
      )
    return None

  # supported operators for queries
  search_operators = {
    ">": lambda a, b: float(a) > float(b),
    ">=": lambda a, b: float(a) >= float(b),
    "<": lambda a, b: float(a) < float(b),
    "<=": lambda a, b: float(a) <= float(b),
    "=": lambda a, b: str(a) == str(b),
    "==": lambda a, b: str(a) == str(b),
    "!=": lambda a, b: str(a) != str(b)
  }

  def __init__(self, query=None, capture_logs=False):
    self.query = query
    self.capture_logs = capture_logs
    # parse search query
    if self.query:
      # example: Key >= 32
      query_regex = re.compile('\s*(\w+)\s*([<>=!]+)\s*([0-9a-zA-Z]+)\s*')
      match = query_regex.match(query)
      if not match:
        raise ValueError(query, " is not a valid query")
      self.key = match.group(1)
      self.op = match.group(2)
      self.value = match.group(3)

  def FindMatches(self, replay_results, filename):
    # find MTStat lines in log
    lines = replay_results.gestures_log.splitlines()
    lines = filter(lambda line: MTStatQuery.MatchLine(line), lines)
    all_matches = map(lambda line: MTStatMatch(line, filename), lines)

    # samples are denoted by the : operator, all of them are returned.
    samples = filter(lambda match: match.operator == ":", all_matches)

    # updates are denoted by the = operator and force only the last
    # update to be returned.
    updates = filter(lambda match: match.operator == "=", all_matches)
    last_updates = dict([(update.key, update) for update in updates])

    matches = samples + last_updates.values()

    # filter by search query if requested
    if self.query:
      matches = filter(self.Match, matches)
    return matches

  def Match(self, match):
    op = MTStatQuery.search_operators[self.op]
    return (match.key == self.key and
            op(match.value, self.value))


class MTStatMatch(QueryMatch):
  def __init__(self, line, file):
    match = MTStatQuery.MatchLine(line)
    QueryMatch.__init__(self, file, float(match.timestamp), line)
    self.key = match.key
    self.operator = match.operator
    self.value = match.value


class RegexQuery(Query):
  """ Searches the raw gestures log with a regular expression """
  def __init__(self, query):
    self.regex = re.compile(query)
    self.capture_logs = True

  def FindMatches(self, replay_results, filename):
    lines = replay_results.gestures_log.splitlines()
    lines = filter(lambda line: self.regex.match(line), lines)
    matches = map(lambda line: QueryMatch(filename, None, line), lines)
    return matches


class GesturesQuery(Query):
  """ Searches for gestures with matching type """
  def __init__(self, type, capture_logs):
    self.type = type
    self.capture_logs = capture_logs

  def FindMatches(self, replay_results, filename):
    gestures = replay_results.gestures.gestures
    if self.type:
      gestures = filter(lambda g: g.type == self.type, gestures)
    return map(lambda g: GesturesMatch(filename, g), gestures)


class GesturesMatch(QueryMatch):
  def __init__(self, filename, gesture):
    QueryMatch.__init__(self, filename, gesture.start, str(gesture))
    self.gesture = gesture


class GesturesDiffQuery(GesturesQuery):
  """ Compare gestures to 'original' QueryResult and search for changes """
  def __init__(self, type, original):
    self.type = type
    self.original = original
    self.capture_logs = True

  def FindMatches(self, replay_results, filename):
    self_matches = GesturesQuery.FindMatches(self, replay_results, filename)
    original_matches = self.original.matches

    size = min(len(original_matches), len(self_matches))
    matches = []
    for i in range(size):
      if str(self_matches[i].gesture) != str(original_matches[i].gesture):
        match = GesturesDiffMatch(filename, self_matches[i].gesture,
                                  original_matches[i].gesture)
        matches.append(match)
    return matches


class GesturesDiffMatch(GesturesMatch):
  def __init__(self, filename, new, original):
    GesturesMatch.__init__(self, filename, new)
    self.original = original

  def __str__(self):
    return "%f: %s != %s" % (self.timestamp, str(self.gesture),
                             str(self.original))


class MTStat(object):
  def SearchChanges(self, type=None, number=None, platform=None, parallel=True):
    """ Search for changed gestures.

    This command will compare the gestures output of the HEAD version of
    the gestures library with the local version.
    Optionally the type of gestures to look at can be specified by 'type'
    """
    engine = QueryEngine()
    files = engine.SelectFiles(number, platform)

    MTReplay().Recompile(head=True)
    gestures_query = GesturesQuery(type, False)
    original_results = engine.Execute(files, gestures_query, parallel=parallel)

    MTReplay().Recompile()
    diff_queries =dict([
      (file, GesturesDiffQuery(type, original_results[file]))
      for file in files if file in original_results])
    return engine.Execute(files, diff_queries, parallel=parallel)

  def Search(self, search=None, gestures=None, regex=None,
             number=None, platform=None, parallel=True):
    """ Search for occurences of a specific tag or regex.

    Specify either a 'search' or a 'regex'. Search queries are formatted
    in a simple "key operator value" format. For example:
    "MyKey > 5" will return all matches where MyKey has a value
    of greater than 5.
    Supported operators are: >, <, >=, <=, =, !=

    number: optional number of random reports to use
    parallel: use parallel processing

    returns a dictionary of lists containing the matches
    for each file.
    """
    engine = QueryEngine()
    files = engine.SelectFiles(number, platform)

    if search:
      query = MTStatQuery(search, True)
    elif regex:
      query = RegexQuery(regex)
    elif gestures:
      query = GesturesQuery(gestures, True)
    else:
      return None

    return engine.Execute(files, query, parallel=parallel)

  def GatherStats(self, number=None, platform=None, parallel=True, num_bins=10):
    """ Gathers stats on feedback reports.

    Returns a dictionary with a histogram for each recorded key.
    """
    engine = QueryEngine()
    files = engine.SelectFiles(number, platform)
    results = engine.Execute(files, MTStatQuery(), parallel=parallel)

    # gather values for each key in a list
    all_matches = chain(*[result.matches for result in results.values()])
    value_collection = defaultdict(list)
    for match in all_matches:
      value_collection[match.key].append(match.value)

    # build histograms
    histograms = {}
    for key, values in value_collection.items():
      histograms[key] = self._Histogram(values, num_bins)
    return OrderedDict(sorted(histograms.items(), key=lambda t: t[0]))

  def Download(self, num, parallel=True):
    QueryEngine().Download(num, parallel)

  def _Histogram(self, values, num_bins):
    def RawHistogram(values):
      return OrderedDict(Counter(values))

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
    histogram = OrderedDict()
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
