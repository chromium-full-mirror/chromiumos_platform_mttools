#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Common command line options for mtbringup tools."""

from common import (MTBringupTool,
                    MTBringupArgumentParser,
                    ExecuteCommonCommands,
                    MTBringupToolArgs)
from mtlib.xorg_conf import XorgConfBuilder
from mtlib.util import GitRepo, Path

xorg_commit_tpl = """\
xorg configuration for {board}

This configuration uses the v2 touchpad stack and includes pressure
calibration for the integrated touchpad of {board}

BUG={bug}
TEST=To automatically verify if the config is correctly applied run:
     $ mtbringup-xorg -r device_ip --verify
"""

src_dir = Path("/mnt/host/source/src/")
xorg_conf_dir = src_dir / "platform/xorg-conf"

class XorgTool(MTBringupTool):
  def __init__(self, args):
    MTBringupTool.__init__(self, args)
    info = self.device_info
    if info.variant:
      conf_name = "60-touchpad-cmt-{}.conf".format(info.board_variant)
    else:
      conf_name = "50-touchpad-cmt-{}.conf".format(info.board)
    self.conf_file = xorg_conf_dir / conf_name

  def Calibrate(self, device):
    xorg_builder = XorgConfBuilder(self.device_info, self.conf_file, device)
    xorg_builder.RunCalibration(self.remote, False)

  def GenerateXorgConf(self, device):
    xorg_builder = XorgConfBuilder(self.device_info, self.conf_file, device)
    calib = xorg_builder.GetCalibrationResults()
    if not calib:
      raise Exception("No calibration found for this board.")
    xorg_builder.UpdateXorgConf(calib)

  def Verify(self):
    self.emerge.Deploy("xorg-conf", self.remote)
    print "todo(denniskempin): Verify xorg-conf properties on device"

  def Prepare(self):
    self.PrepareGit(xorg_conf_dir)

  def Clean(self):
    self.CleanGit(xorg_conf_dir)

  def Commit(self, bug_id):
    message = xorg_commit_tpl.format(
        board=self.board,
        bug=bug_id)
    xorg_repo = GitRepo(xorg_conf_dir)
    xorg_repo.Add(self.conf_file)
    xorg_repo.Commit(message, all_changes=True,
                     ammend_if_diverged=True)
    self.Upload(xorg_repo)

def main():
  usage = "Xorg config bringup tool"

  parser = MTBringupArgumentParser(usage)
  parser.add_argument("--prepare",
                      dest="prepare", default=False, action="store_true",
                      help="prepare xorg_conf git repo.")
  parser.add_argument("--verify",
                      dest="verify", default=False, action="store_true",
                      help="Install config and check properties")
  parser.add_argument("--commit",
                      dest="commit", default=False, action="store_true",
                      help="upload xorg config for review.")
  parser.add_argument("--clean",
                      dest="clean", default=False, action="store_true",
                      help="cleanup xorg_conf git repo.")
  parser.add_argument("--calibrate",
                      dest="calibrate", default=False, action="store_true",
                      help="run pressure calibration on remote device")
  parser.add_argument("--conf",
                      dest="conf", default=False, action="store_true",
                      help="generate xorg configuration file")

  args = parser.parse_args()
  tool = XorgTool(MTBringupToolArgs(args))

  if args.conf or args.calibrate:
    device = tool.AskForDevice("Which device is the integrated touchpad?")
    if args.conf:
      tool.GenerateXorgConf(device)
    elif args.calibrate:
      tool.Calibrate(device)
  else:
    ExecuteCommonCommands(args, tool)

if __name__ == '__main__':
  main()

