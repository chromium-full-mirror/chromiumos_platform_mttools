#! /usr/bin/env python
# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Common command line options for mtbringup tools."""

from __future__ import print_function

from mtlib import CrOSRemote
from mtlib.util import Path, GitRepo, AskUser, Emerge
from argparse import ArgumentParser

src_dir = Path("/mnt/host/source/src/")

class MTBringupToolArgs(object):
  def __init__(self, args=None):
    self.device = None
    self.board = None
    self.remote = None
    self.verbose = None
    if args:
      self.device = args.device
      self.board = args.board
      self.remote = args.remote
      self.verbose = args.verbose

class MTBringupTool(object):
  def __init__(self, args):
    self.args = args
    self.verbose = args.verbose
    self.board_variant = None

    self._remote = None
    self._device_info = None

    if args.remote:
      self._remote = CrOSRemote(args.remote)
      self._device_info = self._remote.GetDeviceInfo()
      self.board_variant = self._device_info.board_variant
    if args.board:
      self.board_variant = args.board

    if not self.board_variant:
      raise Exception("Specify either --remote or --board")

    parts = self.board_variant.split("_")
    self.board = parts[0]
    self.variant = parts[1] if len(parts) > 1 else None

    self.branch_name = "{}_bringup".format(self.board_variant)
    self.emerge = Emerge(self.board_variant)

  @property
  def has_remote(self):
    return self._remote is not None

  @property
  def remote(self):
    if self._remote:
      return self._remote
    raise Exception("This operation requires --remote to be specified.")

  @property
  def device_info(self):
    if self._device_info:
      return self._device_info
    raise Exception("This operation requires --remote to be specified.")

  def FindDevice(self, device_match):
    for device in self.device_info.touch_devices.values():
      if device_match in device.id:
        return device
      if device_match in device.hw_name:
        return device
      if device_match in device.name:
        return device
    raise Exception("Cannot find device matching '{}'".format(device_match))

  def AskForDevice(self, question):
    if self.args.device:
      return self.FindDevice(self.args.device)
    devices = self.device_info.touch_devices
    if len(devices) == 1:
      return devices.values()[0]
    selection = AskUser.Select(devices.values(), question)
    return devices.values()[selection]

  def GitRepoPrepared(self, path):
    if not path.exists:
      path.MakeDirs()
    repo = GitRepo(path)
    if repo.active_branch != self.branch_name:
      raise Exception("Git repository is not prepared.")

  def PrepareGit(self, path):
    path.MakeDirs()
    repo = GitRepo(path)

    if not repo.path.exists:
      raise Exception("Cannot find git repo at {}".format(repo.path))

    if repo.active_branch == self.branch_name:
      return

    if repo.working_directory_dirty:
      print("There are local changes in {}".format(repo.path))
      if AskUser.YesNo("Would you like to stash the changes?", default=False):
        repo.Stash()
      elif AskUser.YesNo("Would you like to discard the changes?",
                         default=False):
        repo.Checkout("m/main", force=True)
      else:
        msg = "Cannot continue with local changes in {}"
        raise Exception(msg.format(repo.path))

    branch_name = self.branch_name
    if branch_name in repo.branches:
      print("Checking out {} in {}".format(branch_name, repo.path))
      repo.Checkout(branch_name)
    else:
      print("Creating branch {} in {}".format(branch_name, repo.path))
      repo.CreateBranch(branch_name, "m/main")

  def CleanGit(self, path):
    repo = GitRepo(path)
    if self.branch_name in repo.branches:
      print("Deleting branch {} in {}".format(self.branch_name, repo.path))
      repo.DeleteBranch(self.branch_name)

  def Upload(self, repo):
    review_url = repo.Upload()
    if not review_url:
      review_url = "Not uploaded. Change is up to date."
    print("Review URL:\n\t", review_url, "\n")

  def Status(self):
    pass

  def Prepare(self):
    pass

  def Verify(self):
    pass

  def Commit(self, bug_id):
    pass

  def Clean(self):
    pass


def MTBringupArgumentParser(usage):
  parser = ArgumentParser(usage=usage)
  parser.add_argument('-r', '--remote',
                      dest='remote', default=None,
                      help='remote ip address of chromebook')
  parser.add_argument('-b', '--board',
                      dest='board', default=None,
                      help='board name to use for process')
  parser.add_argument('-v', '--verbose',
                      dest='verbose', default=False, action="store_true",
                      help='show executed commands and their outputs')
  parser.add_argument('-d', '--device',
                      dest='device', default=None,
                      help='I2C device match to use for operations. Can be ' +
                           'part of device name, driver name or I2C id.')
  parser.add_argument('--bug',
                      dest='bug', default=None,
                      help='id of bug report tracking this device bringup.')
  return parser

def ExecuteCommonCommands(args, tool):
  if args.prepare:
    tool.Prepare()
  elif args.verify:
    tool.Verify()
  elif args.commit:
    bug = args.bug
    if not bug:
      bug = AskUser.Text("What is the bug id tracking this device bringup?")
    tool.Commit(bug)
  elif args.clean:
    tool.Clean()
  else:
    tool.Status()
