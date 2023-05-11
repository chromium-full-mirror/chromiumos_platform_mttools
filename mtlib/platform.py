# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
""" This module manages the platform properties in mttools/platforms. """

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import namedtuple
import json
import os
import re
import sys

from .cros_remote import CrOSRemote
from .util import AskUser, ExecuteException
from .xorg_conf import XorgInputClassParser
from functools import reduce

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

AbsInfo = namedtuple("AbsInfo", ("min", "max", "res"))

class PlatformProperties(object):
  """ A class containing hardware and xorg properties for a platform.

  The class can be created from an activity log or by providing
  the name of the platform. Information will then be read from the
  'platforms_dir' directory.
  """
  def __init__(self, platform=None, log=None):
    self.absinfos = {}
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
    elif log:
      self.name = ''
      if log.evdev:
        self._ParseEvdevLog(log.evdev)

  def _ParseEvdevLog(self, evdev_data):
    # Look for embedded hwproperties in header. Format:
    # absinfo: axis min max 0 0 res
    values_regex = 6 * ' ([-0-9]+)'
    abs_regex = re.compile('# absinfo:' + values_regex)
    for match in abs_regex.finditer(evdev_data):
      axis = int(match.group(1))
      info = AbsInfo(min=int(match.group(2)), max=int(match.group(3)),
                     res=int(match.group(6)))
      self.absinfos[axis] = info

  def _ParseHWProperties(self, data):
    """Parse x and y dimensions and resolution from hwprops file."""
    values_regex = 6 * ' ([0-9\\-a-fA-F]+)'
    abs_regex = re.compile('A:' + values_regex)
    for match in abs_regex.finditer(data):
      axis = int(match.group(1), 16)
      info = AbsInfo(min=int(match.group(2)), max=int(match.group(3)),
                     res=int(match.group(6)))
      self.absinfos[axis] = info

  def _ParseProperties(self, data):
    """ Parse properties from file. """
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

    self._ParseXorgConfig(data)

    for prop in self.ignore_properties:
      if prop in self.properties:
        del self.properties[prop]

  def _ParseXorgConfig(self, data):
    """ Locate and parse the Xorg configuration. """
    if 'xorg' not in data or 'file' not in data['xorg']:
      return

    xorg = data['xorg']
    src_root = os.environ.get('CROS_WORKON_SRCROOT')
    if src_root:
      # Running in the chroot.
      #if 'conf_directory' in xorg:
      #  # Look wherever the config specifies (probably in an overlay).
      #  project_path = xorg['conf_directory']
      #else:
      #  # Look in the xorg-conf repository.
      #  project_path = xorg_conf_project_path
      project_path = (
              xorg['conf_directory'] if 'conf_directory' in xorg
              else xorg_conf_project_path)

      xorg_conf_path = os.path.join(src_root, project_path)
      base_touchpad_conf_path = os.path.join(src_root, xorg_conf_project_path)
    else:
      # Running on Chrome OS, so look in the normal installed location.
      xorg_conf_path = '/etc/gesture'
      base_touchpad_conf_path = '/etc/gesture'
      if not os.path.exists(xorg_conf_path):
        xorg_conf_path = '/etc/X11/xorg.conf.d'

    if self.device_class == 'touchpad':
      base_touchpad_filename = os.path.join(base_touchpad_conf_path,
                                             '40-touchpad-cmt.conf')
      self._AddPropertiesFromFile(base_touchpad_filename, xorg['identifiers'])

    filename = os.path.join(xorg_conf_path, xorg['file'])
    self._AddPropertiesFromFile(filename, xorg['identifiers'])

  def _AddPropertiesFromFile(self, filename, identifiers):
      input_classes = self.xorg_parser.Parse(file=filename)
      for identifier in identifiers:
        if identifier in input_classes:
          properties = input_classes[identifier]
          self.properties.update(properties)

  def Match(self, other, loose, debug=False):
    """ Compare properties and return similarity.

    Compare these properties to another PlatformProperties instance.
    The return value is a score between 1. 0 meaning there is a big mismatch
    and 1 meaning the properties match completely.
    Only a selected range of properties are compared in order to
    prevent property adjustments to cause platforms to be mismatched.
    """
    scores = []
    def compare_absinfo_prop(a, b, field):
      a_value = float(getattr(a, field)) if a else None
      b_value = float(getattr(b, field)) if b else None

      score = 0.0
      if a_value is not None and b_value is not None:
        delta = abs(float(a_value) - float(b_value))
        if delta > 0:
          score = 1.0 - min(1.0, delta / max(abs(a_value), abs(b_value)))
        else:
          score = 1.0
      scores.append(score)

      a_str = str(a_value) if a_value is not None else "N/A"
      b_str = str(b_value) if b_value is not None else "N/A"
      if debug:
        print("  %s: %.2f (%s == %s)" % (field, score, a_str, b_str))

    for axis in set().union(self.absinfos.keys(), other.absinfos.keys()):
      if debug:
        print("axis %d:" % axis)
      self_absinfo = self.absinfos.get(axis, None)
      other_absinfo = other.absinfos.get(axis, None)
      compare_absinfo_prop(self_absinfo, other_absinfo, "min")
      compare_absinfo_prop(self_absinfo, other_absinfo, "max")
      compare_absinfo_prop(self_absinfo, other_absinfo, "res")

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
        print("-" * 30, name)
      score = platform.Match(properties, loose, debug)
      if debug:
        print(name, "score =", score)
      if score > 0.96:
        if result:
          if loose:
            if debug:
              print("-" * 10, "Multiple matches. Try strict")
            return self.FindMatching(log, False, debug)
          print(("multiple matching platforms:", result.name,
                 "and", platform.name))
          return None
        result = platform
    if not result:
      print("cannot find matching platform")
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
       event_devices = remote.SafeExecute(
                        "ls /dev/input/ | grep event",
                        verbose=True)
       event_devices = event_devices.splitlines()
       devices = []
       for d in event_devices:
           device_desc_evemu = remote.SafeExecute(
                                      "evemu-describe /dev/input/%s |grep N:" % d,
                                      verbose=False)
           event_number = int((d.split("event", 1))[1])
           device_desc_evemu = device_desc_evemu.split("N:",1)[1]

           devices.append([event_number, device_desc_evemu])

       idx = AskUser.Select([t[1] for t in devices],
                            "Which device would you like to register?")
       device_id = devices[idx][0]
       hwprops = remote.SafeExecute(
                        "evemu-describe /dev/input/event%s" % devices[idx][0],
                        verbose=True)
    if not hwprops:
       print("Please update your device to latest canary or:")
       print(" emerge-${BOARD} inputcontrol")
       print(" cros deploy $DEVICE_IP inputcontrol")
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
      print("Selecting Xorg identifiers from", xorg_file)
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
      print("Please configure the platform properties manually")
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

    print("Created files: ")
    print(" ", hwprops_file)
    print(" ", props_file)

    return platform_name
