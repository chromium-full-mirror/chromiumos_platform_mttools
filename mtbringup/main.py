#! /usr/bin/env python
# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Command line interface for MTBringup."""

from __future__ import print_function

from common import MTBringupTool, MTBringupArgumentParser, ExecuteCommonCommands
from main_firmware import FirmwareTool
from main_xorg import XorgTool

class DiscoverTool(MTBringupTool):
  name = "Discovery"

  def __init__(self, args):
    MTBringupTool.__init__(self, args)

  def Status(self):
    print("Board: {}".format(self.board_variant))
    if not self.has_remote:
      return

    print("Device IP: {}".format(self.remote.ip))
    print("Touch devices:")
    for device in self.device_info.touch_devices.values():
      print(" - {}:".format(device.name))
      print("     Device Name: {}".format(device.hw_name))
      print("     Hardware Version: {}".format(device.hw_version))
      print("     Firmware Version: {}".format(device.fw_version))
      print("     I2C Path: {}".format(device.path))
      if device.kernel_device:
        print("     Kernel Device: {}".format(device.kernel_device))

def main():
  usage = "Touch device bringup tools"
  parser = MTBringupArgumentParser(usage)
  parser.add_argument("--prepare",
                      dest="prepare", default=False, action="store_true",
                      help="prepare all mtbringup tools incl git repos.")
  parser.add_argument("--verify",
                      dest="verify", default=False, action="store_true",
                      help="Run verification of all mtbringup tools.")
  parser.add_argument("--commit",
                      dest="commit", default=False, action="store_true",
                      help="upload changes of all mtbringup tools.")
  parser.add_argument("--clean",
                      dest="clean", default=False, action="store_true",
                      help="cleanup all mtbringup tools incl git repos.")
  args = parser.parse_args()

  tools = [
      DiscoverTool(args),
      FirmwareTool(args),
      XorgTool(args)
  ]

  for tool in tools:
    ExecuteCommonCommands(args, tool)

if __name__ == "__main__":
  main()
