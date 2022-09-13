# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module defines a class for remotely accessing a Chromebook."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from .cros_info import CrOSDeviceInfo
from mtlib.util import Execute, SafeExecute, AskUser
import os
from six import string_types
import tempfile


identity_message = """\
In order to remotely access devices, you need to have password-less
auth for chromebooks set up.
Would you like tptool to run the following command for you?
$ %s
"""


class CrOSRemote(object):
  """This class allows remote access to Chromebooks.

  For every operation this class will call out to a subprocess running ssh
  or scp.
  """

  def __init__(self, ip):
    self.id_path = os.path.expanduser('~/.ssh/id_rsa')
    if not os.path.exists(self.id_path):
      self._SetupIdentity()
    self.ip = ip
    self.info = None

  def RemountWriteable(self):
    self.SafeExecute("mount -oremount,rw /")

  def GetDeviceInfo(self, refresh=False):
    if refresh or not self.info:
      self.info = CrOSDeviceInfo(self)
    return self.info

  def Execute(self, command, cwd=None, verbose=False, interactive=False):
    cmd = self._BuildCommand(command, cwd)
    return Execute(cmd, None, verbose, interactive)

  def SafeExecute(self, command, cwd=None, verbose=False, interactive=False):
    cmd = self._BuildCommand(command, cwd)
    return SafeExecute(cmd, None, verbose, interactive)

  def Read(self, filename, target_file=None):
    temp = None
    if not target_file:
      temp = tempfile.NamedTemporaryFile('r')
      target_file = temp.name

    cmd = ('scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' +
           '-q root@%s:%s %s')
    cmd = cmd % (self.ip, filename, target_file)
    SafeExecute(cmd)
    if temp:
      temp.seek(0)
      return temp.read()
    return None

  def Write(self, filename, content=None, source_file=None):
    if content:
      temp = tempfile.NamedTemporaryFile('wb')
      temp.write(content)
      temp.flush()
      temp.seek(0)
      source_file = temp.name
    if not source_file:
      raise Exception("specify either content or source_file")

    cmd = ('scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' +
           '-q %s root@%s:%s')
    cmd = cmd % (source_file, self.ip, filename)
    SafeExecute(cmd.split())

  def _BuildCommand(self, command, cwd=None):
    if not isinstance(command, string_types):
      command = " ".join(command)
    if cwd:
      command = "cd \"%s\" && %s" % (cwd, command)
    cmd = ('ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' +
           '-q -t root@%s') % (self.ip)
    cmd = cmd.split()
    cmd.append(command)
    return cmd

  def _SetupIdentity(self):
    source = os.path.expanduser('~/trunk/chromite/ssh_keys/testing_rsa')
    command = 'cp %s %s && chmod 600 %s' % (source, self.id_path, self.id_path)
    if AskUser.YesNo(identity_message % command, default=False):
      SafeExecute(command, verbose=True)
