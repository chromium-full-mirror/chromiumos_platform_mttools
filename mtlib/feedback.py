# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cookielib
import getpass
import imghdr
import os
import os.path
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
  def __init__(self):
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
    url = "https://login.corp.google.com/"
    data = self.opener.open(url).read()
    if username in data:
      return

    # ask for credentials
    print "Login to corp.google.com:"
    password = getpass.getpass()
    sys.stdout.write("OTP: ")
    otp = sys.stdin.readline().strip()

    # execute login by posting userdata to login.corp.google.com
    values = {'u': username, 'pw': password, 'otp': otp}
    query = urllib.urlencode(values)
    url = "https://login.corp.google.com/login?ssoformat=CORP_SSO"
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