# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from gzip import GzipFile
from mtlib.feedback import FeedbackDownloader
from io import BytesIO
from .cros_remote import CrOSRemote
import base64
import bz2
import os
import os.path
import re
import sys
import tarfile
import zipfile

# path for temporary screenshot
screenshot_filepath = 'extension/screenshot.jpg'

class Options:
  def __init__(self, download=False, new=False, screenshot=False,
               evdev=None):
    self.download = download
    self.new = new
    self.screenshot = screenshot
    self.evdev = evdev

def Log(source=None, options=None, activity=None, evdev=None):
  """ Load log from feedback url, device ip or local file path.

  Returns a log object containg activity, evdev and system logs.
  source can be either an ip address to a device from which to
  download, a url pointing to a feedback report to pull or a filename.
  """
  if not options:
    options = Options()

  if source:
    if os.path.exists(source):
      if source.endswith('.zip') or source.endswith('.bz2'):
        return FeedbackLog(source)
      return FileLog(source, options.evdev)
    else:
      match = re.search('Report/([0-9]+)', source)
      if match:
        return FeedbackLog(match.group(1), options.screenshot,
                           options.download)
      else:
        # todo add regex and error message
        return DeviceLog(source, options.new)

  if activity or evdev:
    log = AbstractLog()
    if activity:
      if os.path.exists(activity):
        log.activity = open(activity).read()
      else:
        log.activity = activity
    if evdev:
      if os.path.exists(evdev):
        log.evdev = open(evdev).read()
      else:
        log.evdev = evdev
    return log


class AbstractLog(object):
  """ Common functions for log files

  A log file consists of the activity log, the evdev log, a system log, and
  possibly a screenshot, which can be saved to disk all together.
  """
  def __init__(self):
    self.activity = ''
    self.evdev = ''
    self.system = ''
    self.image = None

  def SaveAs(self, filename):
    open(filename, 'w').write(self.activity)
    if self.evdev:
      open(filename + '.evdev', 'w').write(self.evdev)
    if self.system:
      open(filename + '.system', 'wb').write(
              self.system.encode('utf-8', 'strict'))
    if self.image:
      open(filename + '.jpg', 'w').write(self.image)

  def CleanUp(self):
    if os.path.exists(screenshot_filepath):
      os.remove(screenshot_filepath)


class FileLog(AbstractLog):
  """ Loads log from file.

  evdev or system logs are optional.
  """
  def __init__(self, filename, evdev=None):
    AbstractLog.__init__(self)

    self.activity = open(filename).read()
    if evdev:
      self.evdev = open(evdev).read()
    elif os.path.exists(filename + '.evdev'):
      self.evdev = open(filename + '.evdev').read()
    if os.path.exists(filename + '.system'):
      self.system = open(filename + '.system').read()
    if os.path.exists(filename + '.jpg'):
      self.image = open(filename + '.jpg').read()
      file(screenshot_filepath, 'w').write(self.image)


class FeedbackLog(AbstractLog):
  """ Download log from feedback url.

  Downloads logs and (possibly) screenshot from a feedback id or file name
  """
  def __init__(self, id_or_filename, screenshot=False, download=False,
               force_latest=None, downloader=None):
    AbstractLog.__init__(self)
    self.force_latest = force_latest
    self.try_screenshot = screenshot
    self.report = None
    self.downloader = downloader

    if id_or_filename.endswith('.zip') or id_or_filename.endswith('.bz2'):
      self.report = open(id_or_filename, 'rb').read()
      screenshot_filename = id_or_filename[:-4] + '.jpg'
      try:
        self.image = open(screenshot_filename).read()
      except IOError:
        # No corresponding screenshot available.
        pass
    else:
      if not self.downloader:
        self.downloader = FeedbackDownloader()
      self.report = self.downloader.DownloadSystemLog(id_or_filename)
      if self.try_screenshot:
        self.image = self.downloader.DownloadScreenshot(id_or_filename)

    if self.report:
      self._ExtractSystemLog()
    if self.system:
      self._ExtractLogFiles()

    # Only write to screenshot.jpg if we will be viewing the screenshot
    if not download and self.image:
      file(screenshot_filepath, 'w').write(self.image)

  def _GetLatestFile(self, match, tar):
    # find file name containing match with latest timestamp
    names = filter(lambda n: n.find(match) >= 0, tar.getnames())
    names.sort()
    if not names:
      print('Cannot find files named %s in tar file' % match)
      print('Tar file contents:', tar.getnames())
      sys.exit(-1)
    return tar.extractfile(names[-1])

  def _ExtractSystemLog(self):
    if self.report[0:2] == b'BZ':
      system_log = bz2.decompress(self.report)
    elif self.report[0:2] == b'PK':
      bytes_io = BytesIO(self.report)
      zip = zipfile.ZipFile(bytes_io, 'r')
      system_log = zip.read(zip.namelist()[0])
      zip.extractall('./')
    else:
      print('Cannot download logs file')
      sys.exit(-1)

    self.system = system_log.decode('utf-8', 'strict')

  def _ExtractLogFiles(self):
    # Find embedded and uuencoded activity.tar in system log

    def ExtractByInterface(interface):
      assert interface == 'pad' or interface == 'screen'

      log_index = [
        (('hack-33025-touch{0}_activity=\"\"\"\n' +
          'begin-base64 644 touch{0}_activity_log.tar\n').format(interface),
          '"""'),
        (('touch{0}_activity=\"\"\"\n' +
          'begin-base64 644 touch{0}_activity_log.tar\n').format(interface),
          '"""'),
        (('hack-33025-touch{0}_activity=<multiline>\n' +
          '---------- START ----------\n' +
          'begin-base64 644 touch{0}_activity_log.tar\n').format(interface),
          '---------- END ----------'),
      ]

      start_index = end_index = None
      for start, end in log_index:
        if start in self.system:
          start_index = self.system.index(start) + len(start)
          end_index = self.system.index(end, start_index)
          break

      if start_index is None:
        return []

      activity_tar_enc = self.system[start_index:end_index]

      # base64 decode
      activity_tar_data = base64.b64decode(activity_tar_enc)

      if activity_tar_data == b'':
        print('touch{0}_activity_log.tar found, but empty'.format(interface))
        return []

      # untar
      activity_tar_file = tarfile.open(fileobj=BytesIO(activity_tar_data))

      def ExtractPadFiles(name):
        # find matching evdev file
        evdev_name = name.replace('touchpad_activity', 'cmt_input_events')

        activity_gz = activity_tar_file.extractfile(name)
        evdev_gz = activity_tar_file.extractfile(evdev_name)

        # decompress log files
        return (GzipFile(fileobj=activity_gz).read(),
            GzipFile(fileobj=evdev_gz).read())

      def ExtractScreenFiles(name):
        # Always try for a screenshot with touchscreen view
        self.try_screenshot = True

        evdev = activity_tar_file.extractfile(name)
        return (evdev.read(), None)

      extract_func = {
        'pad': ExtractPadFiles,
        'screen': ExtractScreenFiles,
      }

      # return latest log files, we don't include cmt files
      return [(filename, extract_func[interface])
          for filename in activity_tar_file.getnames()
              if filename.find('cmt') == -1]

    if self.force_latest == 'pad':
      logs = ExtractByInterface('pad')
      idx = 0
    elif self.force_latest == 'screen':
      logs = ExtractByInterface('screen')
      idx = 0
    else:
      logs = ExtractByInterface('pad') + ExtractByInterface('screen')
      if not logs:
        print('Cannot find touchpad_activity_log.tar or '
            'touchscreen_activity_log.tar in systems log file.')
        sys.exit(-1)

      if len(logs) == 1:
        idx = 0
      else:
        while True:
          print('Which log file would you like to use?')
          for i, (name, extract_func) in enumerate(logs):
            if name.startswith('evdev'):
              name = 'touchscreen log - ' + name
            print(i, name)
          print('>')
          selection = sys.stdin.readline()
          try:
            idx = int(selection)
            if idx < 0 or idx >= len(logs):
              print('Number out of range')
            else:
              break
          except:
            print('Not a number')

    name, extract_func = logs[idx]
    activity, evdev = extract_func(name)
    self.activity = activity.decode('utf-8', 'strict')
    self.evdev = evdev.decode('utf-8', 'strict')


identity_message = """\
In order to access devices in TPTool, you need to have password-less
auth for chromebooks set up.
Would you like tptool to run the following command for you?
$ %s
Yes/No? (Default: No)"""

class DeviceLog(AbstractLog):
  """ Downloads logs from a running chromebook via scp. """
  def __init__(self, ip, new=False):
    AbstractLog.__init__(self)
    self.remote = CrOSRemote(ip)

    if new:
      self.remote.SafeExecute('/opt/google/input/inputcontrol -t touchpad' +
                              ' --log')
    self.activity = self.remote.Read('/var/log/xorg/touchpad_activity_log.txt')
    self.evdev = self.remote.Read('/var/log/xorg/cmt_input_events.dat')
