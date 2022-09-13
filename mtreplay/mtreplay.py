# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from mtedit import MTEdit
from mtlib.gesture_log import GestureLog
from mtlib.log import Log
from mtlib.platform import PlatformDatabase, PlatformProperties
from subprocess import Popen, PIPE, STDOUT
from tempfile import NamedTemporaryFile
from threading import Thread
import decimal
import json
import logging
import multiprocessing
import os
import sys

default_log = logging.getLogger(__name__)

def _GetAbsPath(path):
  """ Return normalized path relative to this script """
  path = os.path.join(os.path.dirname(__file__), path)
  return os.path.abspath(path)

class ReplayResults(object):
  def __init__(self, replay):
    self.gestures_log = replay.gestures_log
    self.evdev_log = replay.evdev_log
    self.log = Log(activity=replay.activity_log)
    self._gestures = None

  @property
  def gestures(self):
    if not self._gestures:
      self._gestures = GestureLog(self.log.activity)
    return self._gestures

  def View(self, what):
    if what == None:
      what = 'activity-log'
    elif what == 'g':
      what = 'gestures'
    elif what == 'gl':
      what = 'gestures-log'
    elif what == 'el':
      what = 'evdev-log'
    elif what == 'al':
      what = 'activity-log'
    elif what == 'a':
      what = 'activity'
    elif what == 'e':
      what = 'events'

    if what == 'gestures-log':
      print(self.gestures_log)
    elif what == 'evdev-log':
      print(self.evdev_log)
    elif what == 'activity-log':
      print(self.log.activity)
    elif what == 'activity':
      MTEdit().View(self.log)
    elif what == 'gestures':
      for gesture in self.gestures.gestures:
        print(gesture)
    elif what == 'events':
      for event in self.gestures.events:
        print(event)


class MTReplay(object):
  """ New API for replaying log files """
  def __init__(self):
    self._database = None

  @property
  def database(self):
    if not self._database:
      self._database = PlatformDatabase()
    return self._database

  def Recompile(self, head=False):
    def SafeExec(args, cwd):
      default_log.info("Executing: %s", " ".join(args))
      process = Popen(args, cwd=cwd, stdout=PIPE, stderr=STDOUT)
      ret = process.wait()
      default_log.info("Process returned: %d", process.returncode)
      if ret != 0:
        print(process.stdout.read())
        sys.exit(-1)

    gestures_path = _GetAbsPath("../../gestures")

    if head:
      SafeExec(['git', 'stash'], gestures_path)

    print("Recompiling gestures/libevdev/replay...")
    SafeExec(["make", "-j", str(multiprocessing.cpu_count()),
                    "in-place"], _GetAbsPath("../"))

    if head:
      SafeExec(['git', 'stash', 'pop'], gestures_path)

  def PlatformOf(self, log, debug=False):
    return self.database.FindMatching(log, debug=debug)

  def Replay(self, log, override_properties=None, force_platform=None,
             gdb=False, dbg_log=None):
    dbg_log = dbg_log or default_log
    if force_platform:
      dbg_log.info("Forced platform: %s", force_platform)
      platform = PlatformProperties(force_platform)
    else:
      dbg_log.info("Matching platforms...")
      platform = self.PlatformOf(log)
    if not platform:
      dbg_log.info("Unable to find platform")
      return None
    dbg_log.info("Platform found: %s", platform.name)

    replay = RawReplay(platform.hwprops_file, platform.device_class)

    events = NamedTemporaryFile('w', delete=True)
    events.write(log.evdev)
    events.flush()

    properties = {}
    properties.update(platform.properties)
    if override_properties:
      properties.update(override_properties)

    replay.Replay(events.name, json.dumps(properties),
                  debug=True, gdb_mode=gdb, dbg_log=dbg_log)
    return ReplayResults(replay)

  def TrimEvdev(self, log, force_platform=None, gdb=False, dbg_log=None):
    """ Trim evdev log to cover same range as activity log. """
    dbg_log = dbg_log or default_log
    if force_platform:
      dbg_log.info("Forced platform: %s", force_platform)
      platform = PlatformProperties(force_platform)
    else:
      dbg_log.info("Matching platforms...")
      platform = self.PlatformOf(log, False)
    if not platform:
      dbg_log.info("Unable to find platform")
      return None
    dbg_log.info("Platform found: %s", platform.name)

    replay = RawReplay(platform.hwprops_file, platform.device_class)

    # parse activity_log
    decimal.setcontext(decimal.Context(prec=8))
    activity = json.loads(log.activity, parse_float=decimal.Decimal)

    # extract from/to times from activity log
    hwstates = list(filter(lambda e: e["type"] == "hardwareState",
                           activity["entries"]))
    if not hwstates:
      dbg_log.warning("No HardwareStates generated")
      return None
    trim_from = hwstates[0]["timestamp"]
    trim_to = hwstates[-1]["timestamp"]
    dbg_log.info("Trimming from %f to %f", trim_from, trim_to)

    events = NamedTemporaryFile('w', delete=True)
    events.write(log.evdev)
    events.flush()

    trim_out = NamedTemporaryFile('r', delete=True)

    replay.Trim(events.name, trim_out.name,
                trim_from=trim_from, trim_to=trim_to,
                gdb_mode=gdb, dbg_log=dbg_log)
    log.evdev = trim_out.read()
    return log


class RawReplay(object):
  """ High level interface to replay tool.

  It provides access to both the replay and the trim feature.
  """

  # default path for executable
  _default_executable_path = _GetAbsPath('replay')

  def __init__(self, platform_file, device_class=None,
               path_to_exe=_default_executable_path):
    """ Create a new instance of the replay tool.

    The platform_file has to point to a file that contains the
    simulated's device data.
    """
    self._exe = path_to_exe

    # setup LD_LIBRARY_PATH for in-place installs
    libevdev_path = _GetAbsPath('../../libevdev/in-place')
    gestures_path = _GetAbsPath('../../gestures/in-place')
    self._env = os.environ.copy()
    self._env['LD_LIBRARY_PATH'] = '%s;%s' % (libevdev_path, gestures_path)

    self._platform_file = platform_file
    self._device_class = device_class
    self.evdev_log = None
    self.gestures_log = None
    self.activity_log = None

  def Trim(self, events_file, trim_out, trim_from=None, trim_to=None,
           gdb_mode=False, dbg_log=None):
    """ Shorthand for _execute for trimming.

    Stores trimed version of events_file in trim_out.
    """
    self._Execute(events_file, None, False, False, False,
           trim_out, trim_from, trim_to, gdb_mode=gdb_mode, dbg_log=dbg_log)

  def Replay(self, events_file, properties=None, debug=False, gdb_mode=False,
             dbg_log=None):
    """ Shorthand for _execute for replaying.

    debug=True/False enables or disables extra logs.
    This method always returns the activity log as a string.
    """
    self._Execute(events_file, properties, debug, debug, True,
                  gdb_mode=gdb_mode, dbg_log=dbg_log)
    return self.activity_log

  def _Execute(self, events_file, properties=None,
         log_evdev=True, log_gestures=True, log_activity=True,
         trim_out=None, trim_from=None, trim_to=None, gdb_mode=False,
         dbg_log=None):
    """ Executes a replay process.

    The method arguments are translated to
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

    dbg_log = dbg_log or default_log

    # translate arguments to command line parameters
    parameters = [self._exe]
    parameters.extend(['--device', self._platform_file ])
    parameters.extend(['--events', events_file])

    if self._device_class:
      parameters.extend(['--class', self._device_class])

    if log_evdev:
      evdev_log_file = NamedTemporaryFile('r', delete=True)
      parameters.extend(['--evdev-log', evdev_log_file.name])

    if log_gestures:
      gestures_log_file = NamedTemporaryFile('r', delete=True)
      parameters.extend(['--gestures-log', gestures_log_file.name])

    if log_activity:
      activity_log_file = NamedTemporaryFile('r', delete=True)
      parameters.extend(['--activity-log', activity_log_file.name])

    if properties:
      properties_file = NamedTemporaryFile('w', delete=True)
      properties_file.write(properties)
      properties_file.flush()
      parameters.extend(['--properties', properties_file.name])

    if trim_out:
      parameters.extend(['--trim-out', trim_out])

    if trim_from:
      parameters.extend(['--trim-from', str(trim_from)])

    if trim_to:
      parameters.extend(['--trim-to', str(trim_to)])

    # execute
    if gdb_mode:
      parameters = ['gdb', '--args'] + parameters

    dbg_log.info("Executing: %s", " ".join(parameters))
    process = Popen(parameters, env=self._env, cwd=working_dir, stderr=PIPE)
    process.wait()
    dbg_log.info("Process returns: %d", process.returncode)

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
      print('Gestures Log: ')
      print(self.gestures_log)
      print('Standard error:')
      print(process.stderr.read().decode(errors='replace'))
      raise Exception('Error {} from process: {}'
              .format(process.returncode, ' '.join(parameters)))
