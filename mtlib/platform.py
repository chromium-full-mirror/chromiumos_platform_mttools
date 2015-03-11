# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
""" This module manages the platform properties in mttools/platforms. """
from cros_remote import CrOSRemote
from util import AskUser
from xorg_conf import XorgInputClassParser
from util import ExecuteException
import json
import os
import re
import sys

# path to current script directory
script_dir = os.path.dirname(os.path.realpath(__file__))
platforms_dir = os.path.realpath(os.path.join(script_dir, '..', 'platforms'))
xorg_conf_project_path = 'src/platform/xorg-conf'

props_template = """\
{
  "gestures": {
  },
  "xorg": {
    "file": "%s",
    "identifiers": %s
  },
  "ignore": [
  ]
}"""

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
    self.properties = {}
    self.ignore_properties = []
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
      if log.evdev:
        self._ParseEvdevLog(log.evdev)
      self._ParseActivityLog(log.activity)


  def _ParseActivityLog(self, activity_data):
    """ Parse property information from an activity log."""
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
    # Look for embedded hwproperties in header. Format:
    # absinfo: axis min max 0 0 res
    abs_regex = 5 * ' ([-0-9]+)'
    xregex = re.compile('# absinfo: 53' + abs_regex)
    xmatch = xregex.search(evdev_data)
    self.x_min = int(xmatch.group(1))
    self.x_max = int(xmatch.group(2))
    self.x_res = int(xmatch.group(5))

    yregex = re.compile('# absinfo: 54' + abs_regex)
    ymatch = yregex.search(evdev_data)
    self.y_min = int(ymatch.group(1))
    self.y_max = int(ymatch.group(2))
    self.y_res = int(ymatch.group(5))

    axis_regex = re.compile('# absinfo: ([0-9]+)')
    for match in axis_regex.finditer(evdev_data):
      self.has_axis.append(int(match.group(1)))

    # look for axes used in the log itself.
    # The format of ABS (0003) reports is:
    # timestamp 0003 axis value
    report_regex = re.compile(' 0003 ([0-9a-f]{4}) ([0-9a-f]+)')
    for match in report_regex.finditer(evdev_data):
      axis = int(match.group(1), 16)
      if axis not in self.required_axis:
        self.required_axis.append(axis)


  def _ParseHWProperties(self, data):
    """Parse x and y dimensions and resolution from hwprops file."""
    abs_regex = 5 * ' ([0-9\\-]+)'
    xregex = re.compile('A: 35' + abs_regex)
    xmatch = xregex.search(data)
    self.x_min = int(xmatch.group(1))
    self.x_max = int(xmatch.group(2))
    self.x_res = int(xmatch.group(5))

    yregex = re.compile('A: 36' + abs_regex)
    ymatch = yregex.search(data)
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

    # Sanity check: Make sure it is not used inside ebuild.
    if os.environ.get('PN') and os.environ.get('S'):
      raise Exception("Should not be executed inside ebuild")

    # If run on a Chromebook device, access xorg-conf files from their normal
    # installed location. If run from inside chroot, access xorg-conf files
    # from the xorg-conf project repository.
    src_root = os.environ.get('CROS_WORKON_SRCROOT')
    if src_root:
      xorg_conf_path = os.path.join(src_root, xorg_conf_project_path)
    else:
      xorg_conf_path = '/etc/gesture'
      if not os.path.exists(xorg_conf_path):
        xorg_conf_path = '/etc/X11/xorg.conf.d'

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

    return reduce(lambda x, y: (x * y), scores)

class PlatformDatabase(object):
  """ Class for managing platforms.

  This class reads all available platforms from the platforms_dir and allows
  to search for matching platforms to an activity log file.
  """
  def __init__(self):
    platform_files = [f for f in os.listdir(platforms_dir)
                      if f.endswith('.hwprops')]
    self.platforms = {}
    for filename in platform_files:
      name = filename.replace('.hwprops', '')
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
      if score > 0.96:
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

  @staticmethod
  def RegisterPlatformFromDevice(ip):
    # get list of multitouch devices
    remote = CrOSRemote(ip)
    inputcontrolexist = True
    try:
       devices = remote.SafeExecute(
           "/opt/google/input/inputcontrol -t multitouch --names",
           verbose=True)
    except ExecuteException:
       inputcontrolexist = False
    if inputcontrolexist:
       # Each line has the format:
       # id: Device Name
       # devices[*][0] will have the id
       # devices[*][1] will have the name
       devices = devices.splitlines()
       devices = [l.split(":", 1) for l in devices]

       # select one device from list
       idx = AskUser.Select([d[1] for d in devices],
                            "Which device would you like to register?")
       device_id = devices[idx][0]

       # read hardware properties
       hwprops = remote.SafeExecute(
           "/opt/google/input/inputcontrol --id %s --hwprops" % device_id,
           verbose=True)
    else:
       devices = remote.SafeExecute(
                        "ls /dev/input/ | grep event",
                        verbose=True)
       devices = devices.splitlines()
       touchdevices = []
       for d in devices:
           device_desc_evemu = remote.SafeExecute(
                                      "evemu-describe /dev/input/%s |grep N:" % d,
                                      verbose=False)
           event_number = (d.split("event", 1))[1]
           device_desc_evemu = device_desc_evemu.split("N:",1)[1]   
           if "Touchpad" in device_desc_evemu:
               touchdevices.append([event_number, device_desc_evemu])
       
       idx = AskUser.Select([t[1] for t in touchdevices],
                            "Which device would you like to register?")
       device_id = touchdevices[idx][0]
       hwprops = remote.SafeExecute(
                        "evemu-describe /dev/input/event%s" % touchdevices[idx][0],
                        verbose=True)
    if not hwprops:
       print "Please update your device to latest canary or:"
       print " emerge-${BOARD} inputcontrol"
       print " cros deploy $DEVICE_IP inputcontrol"
       return None
      

    xorg_files = [
        "/etc/X11/xorg.conf.d/60-touchpad-cmt-*.conf",
        "/etc/X11/xorg.conf.d/50-touchpad-cmt-*.conf",
        "/etc/X11/xorg.conf.d/40-touchpad-cmt.conf",
        "/etc/gesture/60-touchpad-cmt-*.conf",
        "/etc/gesture/50-touchpad-cmt-*.conf",
        "/etc/gesture/40-touchpad-cmt.conf"
    ]

    for pattern in xorg_files:
      # find filename of xorg configuration file
      xorg_file = remote.Execute("ls " + pattern, verbose=False)
      if not xorg_file:
        continue
      xorg_file = xorg_file.strip()

      # extract identifiers
      print "Selecting Xorg identifiers from", xorg_file
      conf = remote.Read(xorg_file)
      all_ids = []
      for match in re.finditer("Identifier\\s+\"([a-zA-Z0-9-_ ]+)\"", conf):
        all_ids.append(match.group(1))

      # ask user to select
      idxs = AskUser.SelectMulti(
          all_ids, "Which xorg identifiers apply to this device?",
          allow_none=True)
      ids = [all_ids[i] for i in idxs]
      if ids:
        break

    if not ids:
      print "Please configure the platform properties manually"
      xorg_file = "todo: add correct xorg conf file"
      ids = ["todo: add correct xorg identifier"]

    ids_string = "[" + ", ".join(["\"%s\"" % i for i in ids]) + "]"
    xorg_file = os.path.basename(xorg_file)

    sys.stdout.write("Please name this platform: ")
    sys.stdout.flush()
    platform_name = sys.stdin.readline().strip()

    # write platform info to files
    hwprops_file = os.path.join(platforms_dir, platform_name + ".hwprops")
    props_file = os.path.join(platforms_dir, platform_name + ".props")

    open(hwprops_file, "w").write(hwprops)
    open(props_file, "w").write(props_template % (xorg_file, ids_string))

    print "Created files: "
    print " ", hwprops_file
    print " ", props_file

    return platform_name
