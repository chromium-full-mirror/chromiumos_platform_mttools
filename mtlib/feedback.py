# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cookielib
import getpass
import imghdr
import os
import os.path
import re
import subprocess
import sys
import urllib
import urllib2

# path to current script directory
script_dir = os.path.dirname(os.path.realpath(__file__))
cache_dir = os.path.realpath(os.path.join(script_dir, "..", "cache"))
if not os.path.exists(cache_dir):
  os.mkdir(cache_dir)

# path to the cookies file used for storing the login cookies.
cookies_file = os.path.join(cache_dir, "cookies")

# path to folder where downloaded reports are cached
log_cache_dir = os.path.join(cache_dir, "reports")
if not os.path.exists(log_cache_dir):
  os.mkdir(log_cache_dir)

class FeedbackDownloader():
  STUBBY_CMD = 'stubby --security_protocol=loas --binary_output=0 \
                       call blade:feedback-export-api-prod \
                       ReportService.Get \'resource_id: "{}"\''
  BINARY_DATA_FILTER = '| grep -A 2 \'name: "system_logs.zip"\' | tail -n 1 \
                        | sed \'s/.*data: "\(.*\)"\s*/\\1/\''
  SCREENSHOT_FILTER = '| grep -A 2 \'screenshot <\' | tail -n 1 \
                       | sed \'s/.*content: "\(.*\)"\s*/\\1/\''

  def __init__(self, force_login=False):
    if force_login and os.path.exists(cookies_file):
      os.remove(cookies_file)
      self._SetupCookies()

  def _SetupCookies(self):
    # setup cookies file and url opener
    self.cookies = cookielib.MozillaCookieJar(cookies_file)
    if os.path.exists(cookies_file):
      self.cookies.load()
    cookie_processor = urllib2.HTTPCookieProcessor(self.cookies)
    self.opener = urllib2.build_opener(cookie_processor)
    self._Login()

  def _Login(self):
    username = getpass.getuser()

    # check if already logged in
    url = "https://feedback.corp.google.com"
    data = self.opener.open(url).read()
    if "loginForm" not in data:
      return

    # ask for credentials
    print "Login to corp.google.com:"
    password = getpass.getpass()
    sys.stdout.write("OTP: ")
    otp = sys.stdin.readline().strip()

    values = {
      'u': username,
      'pw': password,
      'otp': otp
    }

    # extract hidden form values
    regex = ("<input type=\"hidden\" id=\"([^\"]*)\" " +
             "name=\"([^\"]*)\" value=\"([^\"]*)\"/>")
    for match in re.finditer(regex, data):
      values[match.group(2)] = match.group(3)

    # execute login by posting userdata to login.corp.google.com
    query = urllib.urlencode(values)
    url = ("https://login.corp.google.com/login")
    result = self.opener.open(url, query).read()
    # check if the result displays error
    if "error" in result >= 0:
      print "Login failed"
      exit(-1)

    # login was successful. save cookies to file to be reused later.
    self.cookies.save()

  def DownloadFile(self, url):
    self._SetupCookies()
    try:
      return self.opener.open(url).read()
    except urllib2.URLError:
      return None

  def _OctetStreamToBinary(self, octetStream):
    """ The zip files are returned in an octet-stream format that must
    be decoded back into a binary.  This function scans through the stream
    and unescapes the special characters
    """
    binary = ''
    i = 0
    while i < len(octetStream):
      if ord(octetStream[i]) is ord('\\'):
        if re.match('\d\d\d', octetStream[i + 1:i + 4]):
          binary += chr(int(octetStream[i + 1:i + 4], 8))
          i += 4
        else:
          binary += octetStream[i:i + 2].decode("string-escape")
          i += 2
      else:
        binary += octetStream[i]
        i += 1
    return binary

  def _DownloadAttachedFile(self, id, filter_cmd):
    cmd = FeedbackDownloader.STUBBY_CMD.format(id) + filter_cmd
    print cmd
    process = subprocess.Popen(cmd, shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    output, errors = process.communicate()
    errorcode = process.returncode
    if errorcode != 0:
        print "An error (%d) occurred while downloading the logs" % errorcode
        return None

    return self._OctetStreamToBinary(output)

  def DownloadSystemLog(self, id):
    report = self._DownloadAttachedFile(id,
                                FeedbackDownloader.BINARY_DATA_FILTER)

    if not report or (report[0:2] != "BZ" and report[0:2] != "PK"):
      print "Report does not seem to include include log files..."
      print "Do you need to run 'prodaccess' perhaps?"
      return None

    return report

  def DownloadScreenshot(self, id):
    return self._DownloadAttachedFile(id, FeedbackDownloader.SCREENSHOT_FILTER)
