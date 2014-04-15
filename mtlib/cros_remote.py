# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module defines a class wrapping around SSH and SCP commands to connect
to chromebooks and run remote commands, download or upload files.
"""

import os
import subprocess
import sys
import tempfile

identity_message = """\
In order to access devices in TPTool, you need to have password-less
auth for chromebooks set up.
Would you like tptool to run the following command for you?
$ %s
Yes/No? (Default: No)"""

class CrOSRemote(object):
  def __init__(self, ip):
    self.id_path = os.path.expanduser('~/.ssh/id_rsa')
    if not os.path.exists(self.id_path):
      self._SetupIdentity()
    self.ip = ip

  def Execute(self, command, cwd=None, verbose=False):
    cmd = self._BuildCommand(command, cwd)
    return self._Exec(cmd, verbose)

  def ReadCommand(self, command, cwd=None, verbose=False):
    cmd = self._BuildCommand(command, cwd)
    return self._GetCommandOutput(cmd, verbose)

  def Read(self, filename):
    temp = tempfile.NamedTemporaryFile('r')
    cmd = ('scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' +
           '-q root@%s:%s %s')
    cmd = cmd % (self.ip, filename, temp.name)
    self._Exec(cmd.split())
    temp.seek(0)
    return temp.read()

  def Write(self, filename, content):
    temp = tempfile.NamedTemporaryFile('w')
    temp.write(content)
    temp.flush()
    temp.seek(0)

    cmd = ('scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' +
           '-q %s root@%s:%s')
    cmd = cmd % (self.ip, temp.name, filename)
    self._Exec(cmd.split())

  def _BuildCommand(self, command, cwd=None):
    if cwd:
      command = "cd \"%s\" && %s" % (cwd, command)
    cmd = ('ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' +
           '-q -t root@%s') % (self.ip)
    cmd = cmd.split()
    cmd.append(command)
    return cmd

  def _Exec(self, command, verbose=False):
    if verbose:
      process = subprocess.Popen(command)
    else:
      process = subprocess.Popen(command, stdout=subprocess.PIPE)
    ret = process.wait()
    if ret:
      if verbose:
        print "Command returned %d: %s" % (ret, " ".join(command))
      return False
    return True

  def _GetCommandOutput(self, command, verbose=False):
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    ret = process.wait()
    if ret:
      if verbose:
        print process.stdout.read()
        print "Command returned %d: %s" % (ret, " ".join(command))
      return False
    return process.stdout.read()

  def _SetupIdentity(self):
    source = os.path.expanduser('~/trunk/chromite/ssh_keys/testing_rsa')
    command = 'cp %s %s && chmod 600 %s' % (source, self.id_path, self.id_path)
    print identity_message % command
    response = sys.stdin.readline().strip()
    if response in ('Yes', 'yes', 'Y', 'y'):
      print command
      os.system(command)
