# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gzip import GzipFile
from StringIO import StringIO
import base64
import bz2
import cookielib
import getpass
import os
import os.path
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib2
import zipfile

# path to current script directory
script_dir = os.path.dirname(os.path.realpath(__file__))

# path to the cookies file used for storing the login cookies.
cookies_file = os.path.join(script_dir, "mtedit.cookies")

log_cache_dir = os.path.join(script_dir, "reports")

def Log(source, options):
  """
    Returns a log object containg activity, evdev and system logs.
    source can be either an ip address to a device from which to
    download, a url pointing to a feedback report to pull or a filename.
  """
  if os.path.exists(source):
    if source.endswith(".zip") or source.endswith(".bz2"):
      return FeedbackLog(source, options)
    return FileLog(source, options)
  else:
    match = re.search("Report/([0-9]+)", source)
    if match:
      return FeedbackLog(match.group(1), options)
    else:
      # todo add regex and error message
      return DeviceLog(source, options)


class AbstractLog(object):
  """
    A log file consists of the activity log, the evdev log, a system log, and
    possibly a screenshot, which can be saved to disk all together.
  """
  def SaveAs(self, filename):
    open(filename, "w").write(self.activity)
    if self.evdev:
      open(filename + ".evdev", "w").write(self.evdev)
    if self.system:
      open(filename + ".system", "w").write(self.system)
    if self.image:
      open(filename + ".jpg", "w").write(self.image)

  def CleanUp(self):
    if os.path.exists("screenshot.jpg"):
      os.remove("screenshot.jpg")


class FileLog(AbstractLog):
  """
    Loads log from file. Does not contain evdev or system logs.
  """
  def __init__(self, filename, options):
    self.activity = open(filename).read()
    self.evdev = ""
    self.system = ""
    self.image = None
    if options.evdev:
      self.evdev = open(options.evdev).read()
    elif os.path.exists(filename + ".evdev"):
      self.evdev = open(filename + ".evdev").read()
    if os.path.exists(filename + ".system"):
      self.system = open(filename + ".system").read()
    if os.path.exists(filename + ".jpg"):
      self.image = open(filename + ".jpg").read()
      file("screenshot.jpg", "w").write(self.image)


class FeedbackLog(AbstractLog):
  """
    Downloads logs and (possibly) screenshot from a feedback id or file name
  """
  def __init__(self, id_or_filename, options):
    if id_or_filename.endswith(".zip") or id_or_filename.endswith(".bz2"):
      self.report = open(id_or_filename).read()
    else:
      # See if we've already downloaded this
      cached_filename = os.path.join(log_cache_dir, id_or_filename + ".zip")
      try:
        self.report = open(cached_filename).read()
      except IOError:
        # setup cookies file and url opener then download the report archive
        self.cookies = cookielib.MozillaCookieJar(cookies_file)
        if os.path.exists(cookies_file):
          self.cookies.load()
        cookie_processor = urllib2.HTTPCookieProcessor(self.cookies)
        opener = urllib2.build_opener(cookie_processor)
        self._DownloadSystemLog(id_or_filename, opener)
        # Cache the log on disk
        if not os.path.exists(log_cache_dir):
          os.makedirs(log_cache_dir)
        file(cached_filename, "w").write(self.report)
      self.image = None
      if options.screenshot:
        self._DownloadScreenshot(id_or_filename, opener)
      # Only write to screenshot.jpg if we will be viewing the screenshot
      if not options.download and self.image:
        file("screenshot.jpg", "w").write(self.image)

    self._ExtractSystemLog()
    self._ExtractLogFiles()

  def _Login(self, opener):
    print "Login to corp.google.com:"
    username = getpass.getuser()
    password = getpass.getpass()
    sys.stdout.write("OTP: ")
    otp = sys.stdin.readline().strip()

    # execute login by posting userdata to login.corp.google.com
    url = "https://login.corp.google.com/login?ssoformat=CORP_SSO"
    data = "u=%s&pw=%s&otp=%s" % (username, password, otp)
    result = opener.open(url, data).read()

    # check if the result displays error
    if result.find("error") >= 0:
      print "Login failed"
      exit(-1)

    # login was successful. save cookies to file to be reused later.
    self.cookies.save()

  def _GetLatestFile(self, match, tar):
    # find file name containing match with latest timestamp
    names = filter(lambda n: n.find(match) >= 0, tar.getnames())
    names.sort()
    if not names:
      print "Cannot find files named %s in tar file" % match
      print "Tar file contents:", tar.getnames()
      sys.exit(-1)
    return tar.extractfile(names[-1])

  def _DownloadSystemLog(self, id, opener):
    # First download the report.zip file
    logfile = "report-%s-system_logs.zip" % id
    url = ("https://feedback.corp.googleusercontent.com/binarydata/" +
           "%s?id=%s&logIndex=0") % (logfile, id)
    self.report = opener.open(url).read()
    file("test.zip", "w").write(self.report)

    if self.report[0:2] != "BZ" and self.report[0:2] != "PK":
      # not a zip/bzip file. Log in and try again.
      self._Login(opener)
      self.report = opener.open(url).read()

  def _DownloadScreenshot(self, id, opener):
    url = "https://feedback.corp.googleusercontent.com/screenshot?id=%s" % id
    self.image = None
    try:
      self.image = opener.open(url).read()
    except urllib2.URLError:
      print "No screenshots available - %s" % url

  def _ExtractSystemLog(self):
    if self.report[0:2] == "BZ":
      self.system = bz2.decompress(self.report)
    elif self.report[0:2] == "PK":
      io = StringIO(self.report)
      zip = zipfile.ZipFile(io, "r")
      self.system = zip.read(zip.namelist()[0])
      zip.extractall("./")
    else:
      print "Cannot download logs file"
      sys.exit(-1)

  def _ExtractLogFiles(self):
    # find embedded and uuencoded activity.tar in system log
    log_start1 = ("hack-33025-touchpad_activity=\"\"\"\n" +
                 "begin-base64 644 touchpad_activity_log.tar\n")
    log_start2 = ("touchpad_activity=\"\"\"\n" +
                 "begin-base64 644 touchpad_activity_log.tar\n")
    log_start3 = ("hack-33025-touchpad_activity=<multiline>\n" +
                 "---------- START ----------\n" +
                 "begin-base64 644 touchpad_activity_log.tar\n")
    if log_start1 in self.system:
      log_start_index = self.system.index(log_start1) + len(log_start1)
      log_end_index = self.system.index("\"\"\"", log_start_index)
    elif log_start2 in self.system:
      log_start_index = self.system.index(log_start2) + len(log_start2)
      log_end_index = self.system.index("\"\"\"", log_start_index)
    elif log_start3 in self.system:
      log_start_index = self.system.index(log_start3) + len(log_start3)
      log_end_index = self.system.index("---------- END ----------",
                                        log_start_index)
    else:
      print "cannot find touchpad_activity_log.tar in systems log file"
      sys.exit(-1)

    activity_tar_enc = self.system[log_start_index:log_end_index]

    # base64 decode
    activity_tar_data = base64.b64decode(activity_tar_enc)

    # untar
    activity_tar_file = tarfile.open(fileobj=StringIO(activity_tar_data))

    # find latest log files
    logs = filter(lambda n: n.find("touchpad_activity") >= 0,
                  activity_tar_file.getnames())
    if len(logs) == 1:
      idx = 0
    else:
      while True:
        print "Which log file would you like to use?"
        for i, name in enumerate(logs):
          print i, name
        print ">"
        selection = sys.stdin.readline()
        try:
          idx = int(selection)
          if idx < 0 or idx >= len(logs):
            print "Number out of range"
          else:
            break
        except:
          print "Not a number"

    activity_name = logs[idx]

    # find matching evdev file
    evdev_name = logs[idx][0:logs[idx].index("touchpad_activity")]
    evdev_name = evdev_name + "cmt_input_events"

    for name in activity_tar_file.getnames():
      if name.startswith(evdev_name):
        evdev_name = name
        break

    activity_gz = activity_tar_file.extractfile(activity_name)
    evdev_gz = activity_tar_file.extractfile(evdev_name)

    # decompress log files
    self.activity = GzipFile(fileobj=activity_gz).read()
    self.evdev = GzipFile(fileobj=evdev_gz).read()


identity_message = """\
In order to access devices in TPTool, you need to have password-less
auth for chromebooks set up.
Would you like tptool to run the following command for you?
$ %s
Yes/No? (Default: No)"""

class DeviceLog(AbstractLog):
  """
    Downloads logs from a running chromebook via scp.
  """
  def __init__(self, ip, options):
    self.id_path = os.path.expanduser("~/.ssh/identity")
    if not os.path.exists(self.id_path):
      self._SetupIdentity()

    if options.new:
      self._GenerateLogs(ip)

    self.activity = self._Download(ip, "touchpad_activity_log.txt")
    self.evdev = self._Download(ip, "cmt_input_events.dat")
    self.system = ""

  def _GenerateLogs(self, ip):
    cmd = ("ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no " +
           "-q root@%s /opt/google/touchpad/tpcontrol log") % ip
    process = subprocess.Popen(cmd.split())
    process.wait()

  def _Download(self, ip, filename):
    temp = tempfile.NamedTemporaryFile("r")
    cmd = ("scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no " +
           "-q root@%s:/var/log/%s %s")
    cmd = cmd % (ip, filename, temp.name)
    process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    process.wait()
    temp.seek(0)
    return temp.read()

  def _SetupIdentity(self):
    source = os.path.expanduser("~/trunk/chromite/ssh_keys/testing_rsa")
    command = "cp %s %s && chmod 600 %s" % (source, self.id_path, self.id_path)
    print identity_message % command
    response = sys.stdin.readline().strip()
    if response in ("Yes", "yes", "Y", "y"):
      print command
      os.system(command)
