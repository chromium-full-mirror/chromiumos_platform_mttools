# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cookielib
import getpass
import imghdr
import os
import os.path
import re
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
  def __init__(self, force_login=False):
    if force_login and os.path.exists(cookies_file):
      os.remove(cookies_file)
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
    try:
      return self.opener.open(url).read()
    except urllib2.URLError:
      return None

  def _GetAndUpdateCachedFile(self, filename, url):
    cached_filename = os.path.join(log_cache_dir, filename)
    try:
      return open(cached_filename).read()
    except IOError:
      data = self.DownloadFile(url)
      if not data:
        return None
      # Cache the data on disk
      file(cached_filename, "w").write(data)
      return data

  def DownloadSystemLog(self, id):
    # First download the report.zip file
    logfile = urllib.quote("report-%s-system_logs.zip" % id)
    query = urllib.urlencode({"id": id, "logIndex": "0"})
    url = ("https://feedback.corp.googleusercontent.com/binarydata/%s?%s" %
           (logfile, query))
    report = self._GetAndUpdateCachedFile(id + ".zip", url)
    if "<html>" in report:
      print "Received a website, you have been logged out."
      print "Please re-login by running:"
      print "   mtedit --login"
      return None
    if not report or (report[0:2] != "BZ" and report[0:2] != "PK"):
      print "Report does not include log files at %s" % url
      return None
    return report

  def DownloadScreenshot(self, id):
    query = urllib.urlencode({"id": id})
    url = "https://feedback.corp.googleusercontent.com/screenshot?%s" % query
    image = self._GetAndUpdateCachedFile(id + ".jpg", url)
    if not image or imghdr.what("", image) != 'jpeg':
      print "No screenshots available at %s" % url
      return None
    return image