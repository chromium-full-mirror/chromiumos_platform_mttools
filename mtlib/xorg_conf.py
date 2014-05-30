# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import re
from mtlib.util import RequiredRegex, SafeExecute, Execute, Path

# locate required folders in chroot enviornment
src_dir = Path("/mnt/host/source/src/")
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
      print "Installing firmware_TouchMTB on device"
      cmd = ("sh run_remote_tests.sh --autotest_dir {} " +
             "--remote={} firmware_TouchMTBSetup")
      cmd = cmd.format(autotest_dir, remote.ip)
      SafeExecute(cmd, cwd=scripts_dir, verbose=True)

      print "Executing Pressure Calibration."
      print "Follow instructions on device"
      remote.SafeExecute("XAUTHORITY=\"/home/chronos/.Xauthority\" DISPLAY=:0" +
                         " python main.py -m calibration",
                         cwd="/usr/local/autotest/tests/firmware_TouchMTB",
                         verbose=True)

    print "Uploading data to spreadsheet. This can take a minute."
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
      if isinstance(file, basestring):
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

