# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime
import time
import getpass
import imghdr
import math
import os
import os.path
import re
import subprocess
import sys
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import multiprocessing
import random
import errno

# path to current script directory
script_dir = os.path.dirname(os.path.realpath(__file__))
cache_dir = os.path.realpath(os.path.join(script_dir, "..", "cache"))
if not os.path.exists(cache_dir):
  os.mkdir(cache_dir)

# path to the cookies file used for storing the login cookies.
rpc_cred_file = os.path.join(cache_dir, "rpc_cred")

# path to folder where downloaded reports are cached
log_cache_dir = os.path.join(cache_dir, "reports")
if not os.path.exists(log_cache_dir):
  os.mkdir(log_cache_dir)

class FeedbackDownloader():
  # Stubby command to download a feedback log:
  #   field_id - determines what data to download:
  #              1: feedback log ID #
  #              7: screenshot
  #              8: system log
  #   resource_id - feedback log ID #
  STUBBY_FILE_CMD = 'stubby --rpc_creds_file=' + rpc_cred_file + \
                    ' call blade:feedback-export-api-prod ' \
                    'ReportService.Get ' \
                    '\'result_mask <field <id:{field_id}>>, ' \
                    'resource_id: "{resource_id}"\''
  # Stubby command to download a list of feedback log IDs:
  #   product_id - 208 refers to ChromeOS
  #   submission_time_[start|end]_time_ms - feedback submission time range
  #   max_results - number of IDs to download
  #   token - page token
  STUBBY_LIST_CMD = 'stubby --rpc_creds_file=' + rpc_cred_file + \
                    ' call blade:feedback-export-api-prod ' \
                    'ReportService.List --proto2 ' \
                    '\'result_mask <field <id:1>>, ' \
                    'product_id: "208", ' \
                    'submission_time_start_ms: 0, ' \
                    'submission_time_end_ms: {end_time}, ' \
                    'page_selection {{ max_results: {max_results} ' \
                    'token: "{token}" }}\''
  # Refer to go/touch-feedback-download for information on getting permission
  # to download feedback logs.
  GAIA_CMD = '/google/data/ro/projects/gaiamint/bin/get_mint --type=loas ' \
             '--text --scopes=40700 --endusercreds > ' + rpc_cred_file
  SYSTEM_LOG_FIELD = 7
  SCREENSHOT_FIELD = 8
  sleep_sec = 4.0
  auth_lock = multiprocessing.Lock()

  def __init__(self, force_authenticate=False):
    if force_authenticate:
      self._Authenticate()

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

  def _AuthenticateWithLock(self):
    is_owner = self.auth_lock.acquire(False)
    if is_owner:
      self._Authenticate()
      self.auth_lock.release()
    else:
      self.auth_lock.acquire()
      self.auth_lock.release()

  def _StubbyCall(self, cmd):
    if not os.path.exists(rpc_cred_file):
      try:
        os.mkdir(cache_dir)
      except OSError as ex:
        if ex.errno != errno.EEXIST:
          raise
        pass
      self._AuthenticateWithLock()
    while True:
      process = subprocess.Popen(cmd, shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 universal_newlines=True)

      output, errors = process.communicate()
      errorcode = process.returncode

      if ('AUTH_FAIL' in errors or
          'CredentialsExpiredException' in output or
          'FORBIDDEN' in output):
        self._AuthenticateWithLock()
        continue
      elif ('exceeds rate limit' in errors or
            'WaitUntilNonEmpty' in errors):
        self._AuthenticateWithLock()

        sleep_time = self.sleep_sec + random.uniform(0.0, self.sleep_sec * 2)
        time.sleep(sleep_time)
        continue
      elif errorcode != 0:
        print(errors)
        print("default error")
        print("An error (%d) occurred while downloading" % errorcode)
        sys.exit(errorcode)
      return output

  def _DownloadAttachedFile(self, id, field):
    cmd = FeedbackDownloader.STUBBY_FILE_CMD.format(
        field_id=field, resource_id=id)
    output = self._StubbyCall(cmd)
    return output

  def _Authenticate(self):
    cmd = FeedbackDownloader.GAIA_CMD
    process = subprocess.Popen(cmd, shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               universal_newlines=True)
    print("Authenticating...")
    output, errors = process.communicate()
    errorcode = process.returncode

    if errorcode != 0:
      print(errors)
      print("An error (%d) occurred while authenticating" % errorcode)
      if errorcode == 126:
        print("You may need to run prodaccess")
        sys.exit(errorcode)
      return None
    print("Done Authenticating")

  def DownloadIDs(self, num, end_time_ms=None, page_token=''):
    if not end_time_ms:
      dt = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
      end_time_ms = (((dt.days * 24 * 60 * 60 + dt.seconds) * 1000) +
                     math.ceil(dt.microseconds / 10))

    cmd = FeedbackDownloader.STUBBY_LIST_CMD.format(
        end_time=int(end_time_ms), max_results=num, token=page_token)
    output = self._StubbyCall(cmd)

    lines = output.split('\n')
    page_token = list(filter(lambda x: 'next_page_token' in x, lines))[0]
    page_token = page_token.split(" ")[-1][1:-1]
    ids = filter(lambda x: 'id' in x, lines)
    ids = [x[7:-1] for x in ids]
    return page_token, ids

  def DownloadSystemLog(self, id):
    report = self._DownloadAttachedFile(id,
                                        FeedbackDownloader.SYSTEM_LOG_FIELD)
    sleep_time = self.sleep_sec + random.uniform(0.0, self.sleep_sec * 2)
    time.sleep(sleep_time)
    data_line = None
    system_log = None
    for count, line in enumerate(StringIO(report)):
      if 'name: "system_logs.zip"' in line:
        data_line = count + 2
      elif data_line and data_line == count:
        system_log = re.search('data: "(.*)"\s*', line).group(1)

    if not system_log or (system_log[0:2] != "BZ" and system_log[0:2] != "PK"):
      print("Report " + id + " does not seem to include include log files...")
      return None

    return self._OctetStreamToBinary(system_log)

  def DownloadScreenshot(self, id):
    print("Downloading screenshot from %s..." % id)
    report = self._DownloadAttachedFile(id,
                                        FeedbackDownloader.SCREENSHOT_FIELD)
    data_line = None
    screenshot = None
    for count, line in enumerate(StringIO(report)):
      if 'screenshot <' in line:
        data_line = count + 2
      elif data_line and data_line == count:
        screenshot = re.search('content: "(.*)"\s*', line).group(1)

    if not screenshot:
      print("Report does not seem to include include a screenshot...")
      return None

    return self._OctetStreamToBinary(screenshot)
