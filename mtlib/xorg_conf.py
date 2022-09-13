# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import math
import numpy as np
import re
from six import string_types
import sys
import time
from mtlib.util import RequiredRegex, SafeExecute, Execute, Path
from remote import ChromeOSTouchDevice

# locate required folders in chroot enviornment
src_dir = Path("/mnt/host/source/src/")
touch_firmware_test_dir = src_dir / "platform/touch_firmware_test"
scripts_dir = src_dir / "scripts"
autotest_dir = src_dir / "third_party/autotest/files"
pressure_calib_dir = autotest_dir / "client/site_tests/firmware_TouchMTB"

xorg_conf_template = """\
Section "InputClass"
    Identifier      "touchpad {board} {vendor_lower}"
    MatchIsTouchpad "on"
    MatchDevicePath "/dev/input/event*"
    MatchProduct    "{vendor}"
    Option          "Integrated Touchpad" "1"
    Option          "Touchpad Stack Version" "2"
{comment}
    Option          "Pressure Calibration Offset" "{intercept}"
    Option          "Pressure Calibration Slope" "{slope}"
EndSection\
"""

class XorgConfBuilder(object):
  def __init__(self, info, conf_file, touchpad):
    self.board_variant = info.board_variant
    self.xorg_conf = conf_file
    self.touchpad = touchpad
    self.sheet_name = self.board_variant + " " + self.touchpad.fw_version

  def GetCalibrationResults(self):
    cmd = "python spreadsheet.py --print-info -n \"{}\""
    cmd = cmd.format(self.sheet_name)

    res = Execute(cmd, cwd=pressure_calib_dir, verbose=True)
    if not res:
      return False

    slope_regex = RequiredRegex("slope=([0-9.\\-]+)")
    slope = slope_regex.Search(res).group(1)
    intercept_regex = RequiredRegex("intercept=([0-9.\\-]+)")
    intercept = intercept_regex.Search(res).group(1)
    return (float(slope), float(intercept))

  def RunCalibration(self, remote, use_existing=True):
    if use_existing:
      existing = remote.Execute("readlink /var/tmp/touch_firmware_test/latest")
    else:
      existing = False

    if not existing:
      print("Installing firmware_TouchMTB on device")
      cmd = ("sh test_that --autotest_dir {} " +
             "{} firmware_TouchMTBSetup")
      cmd = cmd.format(autotest_dir, remote.ip)
      SafeExecute(cmd, cwd=scripts_dir, verbose=True)

      print("Executing Pressure Calibration.")
      print("Follow instructions on device")
      remote.SafeExecute("XAUTHORITY=\"/home/chronos/.Xauthority\" DISPLAY=:0" +
                         " python main.py -m calibration",
                         cwd="/usr/local/autotest/tests/firmware_TouchMTB",
                         verbose=True)

    print("Uploading data to spreadsheet. This can take a minute.")
    cmd = ["python", "spreadsheet.py", "-v", "-d", remote.ip,
           "--result-dir=latest", "-n", self.sheet_name]
    SafeExecute(cmd, cwd=pressure_calib_dir, verbose=True, interactive=True)

  def UpdateXorgConf(self, calib):
    conf = xorg_conf_template.format(
        board=self.board_variant,
        vendor=self.touchpad.vendor,
        vendor_lower=self.touchpad.vendor.lower(),
        slope=calib[0],
        intercept=calib[1])
    if self.xorg_conf.exists:
      current = self.xorg_conf.Read()
      match_regex = RequiredRegex("MatchProduct\s+\"{}\"".format(
          self.touchpad.vendor))
      match = match_regex.Search(current, safe=False)
      if match:
        begin = current.rindex("Section", 0, match.start())
        end = current.index("EndSection", match.end()) + len("EndSection")
        new = current[:begin] + conf + current[end:]
      else:
        new = current + "\n" + conf
    else:
      new = conf
    self.xorg_conf.Write(new)

class OzoneConfBuilder(object):
  """Xorg/Ozone configuration file builder.

  Generates the xorg/ozone configuration file. It updates an existing or creates
  a new xorg config for the correct platform and fills it with a config
  template.
  Part of the config is a pressure calibration which is executed by this class
  before the config is written.
  """
  num_samples = 300
  probe_diameters = np.asarray([3.9, 5.7, 7.7, 9.9, 11.7, 13.9, 17.8])

  def __init__(self, info, conf_file, touchpad):
    self.board_variant = info.board_variant
    self.xorg_conf = conf_file
    self.touchpad = touchpad
    self.average_list = []

  def ProbeName(self, probe):
    minmax = ""
    if probe == 0:
      minmax = ", smallest"
    if probe == len(self.probe_diameters) - 1:
      minmax = ", largest"
    return "#%d (diameter=%.2fmm%s)" % (probe + 1,
                                        self.probe_diameters[probe],
                                        minmax)

  def RunCalibration(self, remote, use_existing=True):
    remote_touch = ChromeOSTouchDevice(remote.ip, is_touchscreen=False)

    average_list = []
    for i, diameter in enumerate(self.probe_diameters):
      pressures = self.ReadProbePressure(remote_touch, i)
      if i + 1 < len(self.probe_diameters):
        time.sleep(2)
      average = float(sum(pressures)) / float(len(pressures))
      average_list.append(average)
    self.average_list = average_list

  def CalculateSlopeIntercept(self, average_list, expected_list):
    # only do the calculation on the first 5 probes, as we find that
    # the larger ones can introduce errors and are less representative
    # of typical real fingers.
    average_list = average_list[0:5]
    expected_list = expected_list[0:5]
    slope = np.cov(average_list, expected_list)[0][1] / np.var(average_list)
    inter = np.mean(expected_list) - slope * np.mean(average_list)
    return (slope, inter)

  def ReadProbePressure(self, remote_touch, probe):
    probe_name = self.ProbeName(probe)
    print("Move probe %s in circles over the touchpad:" % probe_name)

    pressures = []
    remote_touch.FlushSnapshotBuffer()
    while len(pressures) < self.num_samples:
      state = remote_touch.NextSnapshot()
      if len(state.fingers) == 1:
        pressures.append(state.fingers[0].pressure)
      sys.stdout.write("\r%d/%d" % (len(pressures), self.num_samples))
      sys.stdout.flush()
    print()
    return pressures

  def GenerateComment(self, average, expected):
    slope, intercept = self.CalculateSlopeIntercept(average, expected)
    calibrated = intercept + slope * average

    lines = []

    header_format = "    # {:<5} {:<10} {:<10} {:<10} {:}"
    line_format = "    # {:<5} {:<10.2f} {:<10.2f} {:<10.2f} {:.2f}"
    lines.append("    # Pressure calibration results:")
    lines.append(header_format.format("Probe", "Diameter", "Measured",
                                      "Expected", "Calibrated"))
    for i in range(len(self.probe_diameters)):
      lines.append(line_format.format(i, self.probe_diameters[i],
                                      average[i], expected[i], calibrated[i]))
    return "\n".join(lines)

  def UpdateXorgConf(self):
    expected = math.pi * ((self.probe_diameters / 2.0) ** 2)
    average = np.asarray(self.average_list)

    slope, intercept = self.CalculateSlopeIntercept(average, expected)
    comment = self.GenerateComment(average, expected)

    conf = xorg_conf_template.format(
        board=self.board_variant,
        vendor=self.touchpad.vendor,
        vendor_lower=self.touchpad.vendor.lower(),
        slope=slope,
        intercept=intercept,
        comment=comment)

    if self.xorg_conf.exists:
      current = self.xorg_conf.Read()
      match_regex = RequiredRegex("MatchProduct\s+\"{}\"".format(
          self.touchpad.vendor))
      match = match_regex.Search(current, must_succeed=False)
      if match:
        begin = current.rindex("Section", 0, match.start())
        end = current.index("EndSection", match.end()) + len("EndSection")
        new = current[:begin] + conf + current[end:]
      else:
        new = current + "\n" + conf
    else:
      new = conf
    self.xorg_conf.Write(new)

class XorgInputClassParser(object):
  """ Parser for xorg input config files.

  This class is used to parse xorg config files for input class options.
  Only input class sections with a valid Identifier line are parsed.
  """

  def Parse(self, file=None, string=None):
    """ Parse xorg file and return dictionary of input classes.

    Provide either a filename or file-like object to the file parameters
    or a string containing the configuration to the string parameter.
    The return value is a dictionary of all InputClasses, with the
    Identifier as a key. The value is another dictionary containing
    all options set for this input class.
    """
    if file:
      if isinstance(file, string_types):
        return self._ParseString(open(file).read())
      elif hasattr(file, 'read'):
        return self._ParseString(file.read())
      else:
        raise ValueError
    elif string:
      return self._ParseString(string)
    else:
      raise ValueError

  def _ParseString(self, string):
    lines = string.splitlines()
    lines = map(lambda l: l.strip(), lines)

    section_regex = re.compile('Section\\s+\"([^\"]+)\"')
    id_regex = re.compile('Identifier\\s+\"([^\"]+)\"')
    option_regex = re.compile('Option\\s+\"([^\"]+)\"\\s+\"([^\"]+)\"')

    classes = {}
    current_options = None
    current_id = None

    for line in lines:
      if current_options is None:
        # Outside of sections
        section_match = section_regex.match(line)
        if section_match and section_match.group(1) == 'InputClass':
          current_options = {}
          continue
      else:
        # Inside of a section
        if line == 'EndSection':
          if current_id:
            # if class had an id, save in results
            classes[current_id] = current_options
          current_options = None
          continue

        # look for identifier line
        id_match = id_regex.match(line)
        if id_match:
          current_id = id_match.group(1)
          continue

        # store options in current_options
        option_match = option_regex.match(line)
        if option_match:
          key = option_match.group(1)
          value = option_match.group(2)
          current_options[key] = value
    return classes
