# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This module provides an interface to the replay tool.
from subprocess import Popen
import os
from threading import Thread
from tempfile import NamedTemporaryFile


def _GetAbsPath(path):
  """
    Helper method to return the normalized path of a path
    relative to this script file
  """
  path = os.path.join(os.path.dirname(__file__), path)
  return os.path.normpath(path)


class Replay(object):
  """
  This class provides a high level interface to invoke a replay tool process.
  It provides access to both the replay and the trim feature.
  """

  # default path for executable
  _default_executable_path = os.path.join(os.path.dirname(__file__),
                                          "replay/replay")

  def __init__(self, platform_file, device_class=None,
               path_to_exe=_default_executable_path):
    """
    Create a new instance of the replay tool. The platform_file has to
    point to a file that contains the simulated's device data.
    """
    self._exe = path_to_exe

    # setup LD_LIBRARY_PATH for in-place installs
    libevdev_path = _GetAbsPath("../../libevdev/in-place")
    gestures_path = _GetAbsPath("../../gestures/in-place")
    self._env = os.environ.copy()
    self._env["LD_LIBRARY_PATH"] = "%s;%s" % (libevdev_path, gestures_path)

    self._platform_file = platform_file
    self._device_class = device_class
    self.evdev_log = None
    self.gestures_log = None
    self.activity_log = None

  def Trim(self, events_file, trim_out, trim_from=None, trim_to=None):
    """
    Shorthand for _execute. Stores trimed version of events_file
    in trim_out.
    """
    self._Execute(events_file, None, False, False, False,
           trim_out, trim_from, trim_to)

  def Replay(self, events_file, properties=None, debug=False):
    """
    Shorthand for _execute. debug=True/False enables or disables extra logs.
    This method always returns the activity log as a string.
    """
    self._Execute(events_file, properties, debug, debug, True)
    return self.activity_log

  def _Execute(self, events_file, properties=None,
         log_evdev=True, log_gestures=True, log_activity=True,
         trim_out=None, trim_from=None, trim_to=None):
    """
    executes a replay process. The method arguments are translated to
    command line arguments for the process.
    This method throws an exception if the replay process returns and error.

    events_file: filename of file containing the event data
    properties: string containing properties as a JSON object
    log_evdev: enable logging of libevev. stored in self.evdev_log
    log_gestures: enable logging of gestures. stored in self.gestures_log
    log_evdev: enable generation of activity log in self.activity_log
    trim_out: filename where to store result of trim operation
    trim_from: timestamp of first SYN report to include
    trim_to: timestamp of last SYN report to include
    """
    # temporary files for program output
    evdev_log_file = None
    gestures_log_file = None
    activity_log_file = None
    working_dir = os.path.dirname(events_file)

    # translate arguments to command line parameters
    parameters = [self._exe]
    parameters.extend(["--device", self._platform_file ])
    parameters.extend(["--events", events_file])

    if self._device_class:
      parameters.extend(["--class", self._device_class])

    if log_evdev:
      evdev_log_file = NamedTemporaryFile("r", delete=True)
      parameters.extend(["--evdev-log", evdev_log_file.name])

    if log_gestures:
      gestures_log_file = NamedTemporaryFile("r", delete=True)
      parameters.extend(["--gestures-log", gestures_log_file.name])

    if log_activity:
      activity_log_file = NamedTemporaryFile("r", delete=True)
      parameters.extend(["--activity-log", activity_log_file.name])

    if properties:
      properties_file = NamedTemporaryFile("w", delete=True)
      properties_file.write(properties)
      properties_file.flush()
      parameters.extend(["--properties", properties_file.name])

    if trim_out:
      parameters.extend(["--trim-out", trim_out])

    if trim_from:
      parameters.extend(["--trim-from", str(trim_from)])

    if trim_to:
      parameters.extend(["--trim-to", str(trim_to)])

    # execute
    process = Popen(parameters, env=self._env, cwd=working_dir)
    process.wait()

    # close temporary files
    if log_evdev:
      self.evdev_log = evdev_log_file.read()
      evdev_log_file.close()

    if log_gestures:
      self.gestures_log = gestures_log_file.read()
      gestures_log_file.close()

    if log_activity:
      self.activity_log = activity_log_file.read()
      activity_log_file.close()

    if properties:
      properties_file.close()

    if process.returncode != 0:
      raise Exception("Process error: ", " ".join(parameters))
