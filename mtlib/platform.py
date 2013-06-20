# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
""" This module manages the platform properties in mttools/platforms """
import json
import os
import re
import sys
from xorg_conf import XorgInputClassParser

# path to current script directory
script_dir = os.path.dirname(os.path.realpath(__file__))
platforms_dir = os.path.realpath(os.path.join(script_dir, '..', 'platforms'))
xorg_conf_path = os.path.realpath(os.path.join(script_dir, '..',
                                               '..', 'xorg-conf'))

class PlatformProperties(object):
  """ A class containing hardware and xorg properties for a platform.

  The class can be created from an activity log or by providing
  the name of the platform. Information will then be read from the
  'platforms_dir' directory.
  """
  def __init__(self, platform=None, log=None):
    self.required_axis = []
    self.has_axis = []
    self.device_class = "touchpad"
    if platform:
      basename = os.path.join(platforms_dir, platform)
      self.name = platform
      self.hwprops_file = basename + '.hwprops'
      self.props_file = basename + '.props'
      self.xorg_parser = XorgInputClassParser()
      self._ParseHWProperties(open(self.hwprops_file).read())
      self._ParseProperties(open(self.props_file).read())
      self._UpdateDimensions()
    elif log:
      self.name = ''
      self._ParseActivityLog(log.activity)
      if log.evdev:
        self._ParseEvdevLog(log.evdev)

  def _ParseActivityLog(self, activity_data):
    """ Parse property information from an activity log """
    activity = json.loads(activity_data)
    self.properties = activity['properties']

    hwprops = activity['hardwareProperties']
    self.x_min = int(hwprops['left'])
    self.x_max = int(hwprops['right'])
    self.x_res = int(hwprops['xResolution'])
    self.y_min = int(hwprops['top'])
    self.y_max = int(hwprops['bottom'])
    self.y_res = int(hwprops['yResolution'])

  def _ParseEvdevLog(self, evdev_data):
    # The format of ABS (0003) reports is:
    # timestamp 0003 axis value
    report_regex = re.compile(' 0003 ([0-9a-f]{4}) ([0-9a-f]+)')
    for match in report_regex.finditer(evdev_data):
      axis = int(match.group(1), 16)
      if axis not in self.required_axis:
        self.required_axis.append(axis)

  def _ParseHWProperties(self, data):
    """ Parse x and y dimensions and resolution from hwprops file """
    xregex = re.compile('A: 35 ([0-9\-]+) ([0-9\-]+) ([0-9\-]+) ' +
                        '([0-9\-]+) ([0-9\-]+)')
    xmatch = xregex.search(data);
    self.x_min = int(xmatch.group(1))
    self.x_max = int(xmatch.group(2))
    self.x_res = int(xmatch.group(5))

    yregex = re.compile('A: 36 ([0-9\-]+) ([0-9\-]+) ([0-9\-]+) ' +
                        '([0-9\-]+) ([0-9\-]+)')
    ymatch = yregex.search(data);
    self.y_min = int(ymatch.group(1))
    self.y_max = int(ymatch.group(2))
    self.y_res = int(ymatch.group(5))

    axis_regex = re.compile('A: ([0-9a-f]+)')
    for match in axis_regex.finditer(data):
      self.has_axis.append(int(match.group(1), 16))

  def _ParseProperties(self, data):
    """ Parse properties from file and inject xorg properties. """
    self.properties = {}
    self.ignore_properties = []
    data = json.loads(data)

    if 'gestures' in data:
      self.properties.update(data['gestures'])

    if 'device_class' in data:
      self.device_class = data['device_class']

    if 'ignore' in data:
      self.ignore_properties.extend(data['ignore'])

    if xorg_conf_path and 'xorg' in data and 'file' in data['xorg']:
      filename = os.path.join(xorg_conf_path, data['xorg']['file'])
      input_classes = self.xorg_parser.Parse(file=filename)
      if 'identifier' in data['xorg']:
        properties = input_classes[data['xorg']['identifier']]
        self.properties.update(properties)
      if 'identifiers' in data['xorg']:
        for identifier in data['xorg']['identifiers']:
          properties = input_classes[identifier]
          self.properties.update(properties)

    for prop in self.ignore_properties:
      if prop in self.properties:
        del self.properties[prop]

  def _UpdateDimensions(self):
    """ Update x/y min/max with xorg properties.

    CMT allows hardware properties to be overwritten by xorg properties.
    Do the same in this class.
    """
    if 'Active Area Left' in self.properties:
      self.x_min = int(self.properties['Active Area Left'])
    if 'Active Area Right' in self.properties:
      self.x_max = int(self.properties['Active Area Right'])
    if 'Active Area Top' in self.properties:
      self.y_min = int(self.properties['Active Area Top'])
    if 'Active Area Bottom' in self.properties:
      self.y_max = int(self.properties['Active Area Bottom'])

    if 'Horizontal Resolution' in self.properties:
      self.x_res = int(self.properties['Horizontal Resolution'])
    if 'Vertical Resolution' in self.properties:
      self.y_res = int(self.properties['Vertical Resolution'])

    if 'SemiMT Non Linear Area Left' in self.properties:
      self.x_min = int(self.properties['SemiMT Non Linear Area Left'])
    if 'SemiMT Non Linear Area Right' in self.properties:
      self.x_max = int(self.properties['SemiMT Non Linear Area Right'])
    if 'SemiMT Non Linear Area Top' in self.properties:
      self.y_min = int(self.properties['SemiMT Non Linear Area Top'])
    if 'SemiMT Non Linear Area Bottom' in self.properties:
      self.y_max = int(self.properties['SemiMT Non Linear Area Bottom'])


  def Match(self, other, loose, debug=False):
    """ Compare properties and return similarity.

    Compare these properties to another PlatformProperties instance.
    The return value is a score between 1. 0 meaning there is a big mismatch
    and 1 meaning the properties match completely.
    Only a selected range of properties are compared in order to
    prevent property adjustments to cause platforms to be mismatched.
    """
    scores = []
    def compare(a, b, what):
      value = abs(float(a) - float(b))
      if value > 0:
        value = min(1, value / max(abs(float(a)), abs(float(b))))
      scores.append(1-value)
      if debug:
        print "%s: %s == %s" % (what, str(a), str(b))
    def compare_attr(what):
      compare(getattr(self, what), getattr(other, what), what)
    def compare_prop(what):
      if what not in self.properties or what not in other.properties:
        scores.append(0)
      else:
        compare(self.properties[what], other.properties[what], what)
    def check_axis(required, available):
      for axis in required:
        if axis not in available:
          scores.append(0)
          return

    compare_attr('x_min')
    compare_attr('x_max')
    compare_attr('x_res')
    compare_attr('y_min')
    compare_attr('y_max')
    compare_attr('y_res')
    if not loose:
      compare_prop('Pressure Calibration Offset')

    if self.required_axis:
      if debug:
        print "axis:", self.required_axis, "in", other.has_axis
      check_axis(self.required_axis, other.has_axis)

    if other.required_axis:
      if debug:
        print "axis:", other.required_axis, "in", self.has_axis
      check_axis(other.required_axis, self.has_axis)

    return reduce(lambda x,y: (x * y), scores)

class PlatformDatabase(object):
  """ Class for managing platforms.

  This class reads all available platforms from the platforms_dir and allows
  to search for matching platforms to an activity log file.
  """
  def __init__(self):
    platform_files = [ f for f in os.listdir(platforms_dir)
                         if f.endswith('.hwprops') ]
    self.platforms = {}
    for file in platform_files:
      name = file.replace('.hwprops', '')
      self.platforms[name] = PlatformProperties(platform=name)

  def FindMatching(self, log, loose=True, debug=False):
    """ Find platform matching activity_data.

    Returns the PlatformProperties instance of the platform matching
    the activity log data. This method might terminate the program in
    case no match can be made, or the match is ambiguous.
    """
    result = None
    properties = PlatformProperties(log=log)
    for name, platform in self.platforms.items():
      if debug:
        print "#" * 10, name
      score = platform.Match(properties, loose, debug)
      if debug:
        print name, "score =", score
      if score > 0.9:
        if result:
          if loose:
            if debug:
              print "-" * 10, "Multiple matches. Try strict"
            return self.FindMatching(log, False, debug)
          print ('multiple matching platforms:', result.name,
                 'and', platform.name)
          return None
        result = platform
    if not result:
      print 'cannot find matching platform'
      return None
    return result
