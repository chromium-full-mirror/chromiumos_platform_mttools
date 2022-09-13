#! /usr/bin/env python
# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Common command line options for mtbringup tools."""

from __future__ import print_function

from common import (MTBringupTool,
                    MTBringupArgumentParser,
                    ExecuteCommonCommands,
                    MTBringupToolArgs)
from mtlib.util import AskUser, Path
from mtlib.firmware import FirmwarePackage, FirmwareBinary

src_dir = Path("/mnt/host/source/src/")

firmware_commit_tpl = """\
Touchpad firmware revision {version}

This commit contains the following firmware binaries:
{binaries}

BUG={bug}
TEST=To automatically verify if the firmware is correctly installed, run:
     $ mtbringup-firmware -r device_ip --verify
"""


class FirmwareTool(MTBringupTool):
  def __init__(self, args):
    MTBringupTool.__init__(self, args)
    self.package = FirmwarePackage(self.board, self.variant)

  def ForceUpdate(self, device, binary):
    binary.ForceUpdate(device, self.remote)

    device.Refresh(self.remote)
    print("Updated device information:")
    print(device)

  def DownloadBinaries(self):
    binaries = self.package.GetExistingBinaries()
    for binary in binaries:
      open(binary.filename, "w").write(binary.data)

  def PrepareBinary(self, device, binary):
    self.ForceUpdate(device, binary)
    binary.UpdateName(device.hw_version, device.fw_version)
    print("Renamed binary to: {}".format(binary.filename))

  def GenerateEbuildPackage(self, new_version, binaries, clean):
    for binary in binaries:
      if not binary.fw_version or not binary.hw_version:
        msg = "Prepare {} with --prepare-binary"
        raise Exception(msg.format(binary.filename))
      self.package.AddBinary(binary)

    self.GitRepoPrepared(self.package.ebuild_dir)

    existing = self.package.GetExistingBinaries()
    firmwares = self.package.binaries
    legacy_binaries = [b for b in existing if b.hw_version not in firmwares]
    for binary in legacy_binaries:
      msg = "Do you want to keep the firmware '{}' in the package?"
      if not AskUser.YesNo(msg.format(binary), default=True):
        continue
      if not binary.symlink_name:
        touch_devices = self.device_info.touch_devices
        if binary.hw_version in touch_devices:
          binary.symlink_name = touch_devices[binary.hw_version].symlink
        else:
          msg = "What is the symlink name for this device?"
          binary.symlink_name = AskUser.Text(msg)
      self.package.AddBinary(binary)

    self.package.UpdateVersionSymlink(new_version)
    self.package.UpdateEbuildFile(self.remote, regenerate=clean)

    tar_file = self.package.GenerateBCSPackage(new_version)
    print("Upload the package", tar_file.basename, "to the following URL:")
    print("  https://www.google.com/chromeos/partner/fe/#bcUpload:type=PRIVATE")
    print("Using the following values:")
    print("  Overlay:", self.package.overlay.basename)
    print("  Relative path: chromeos-base/" + self.package.ebuild_name)

  def Status(self):
    print("Firmware Ebuild Status:")
    print("  Ebuild: {}".format(self.package.ebuild_file))
    if not self.package.ebuild_file.exists:
      print("  Ebuild does not exist.")
      return
    print("  Ebuild version: {}".format(self.package.ebuild_version))
    print("  GIT branch: {}".format(self.package.ebuild_repo.active_branch))
    print("  GIT status: {}".format(self.package.ebuild_repo.status))
    print("  Firmware binaries:")
    existing = self.package.GetExistingBinaries()
    for binary in existing:
      print("    {}".format(binary))
    print("  BCS URL: {}".format(self.package.bcs_url))

  def Verify(self):
    self.emerge.Deploy(self.package.ebuild_name, self.remote)
    print("Verifying firmware symlinks and binaries")
    self.package.VerifySymlinks(self.remote)
    print("Forcing firmware updates")
    for device in self.device_info.touch_devices.values():
      device.ForceFirmwareUpdate(self.remote)
    print("Checking firmware version numbers")
    self.package.VerifyFirmwareVersions(self.remote)

  def Prepare(self):
    self.PrepareGit(self.package.overlay)

  def Clean(self):
    self.CleanGit(self.package.overlay)

  def Commit(self, bug_id):
    existing = self.package.GetExistingBinaries()
    lines = []
    for firmware in existing:
      lines.append(" - Firmware {} for device {}".format(
          firmware.fw_version, firmware.hw_version))

    message = firmware_commit_tpl.format(
        version=self.package.ebuild_version,
        binaries="\n".join(lines),
        bug=bug_id)
    self.package.ebuild_repo.Add(self.package.ebuild_file)
    self.package.ebuild_repo.Add(self.package.ebuild_symlink)
    self.package.ebuild_repo.Commit(message, all_changes=True,
                                    ammend_if_diverged=True)
    self.Upload(self.package.ebuild_repo)

usage = "Touch firmware bringup tool"

def main():
  parser = MTBringupArgumentParser(usage)
  parser.add_argument("--prepare",
                      dest="prepare", default=False, action="store_true",
                      help="prepare overlay git repo.")
  parser.add_argument("--verify",
                      dest="verify", default=False, action="store_true",
                      help="Install firmware and verify update process.")
  parser.add_argument("--commit",
                      dest="commit", default=False, action="store_true",
                      help="upload ebuild file for review.")
  parser.add_argument("--clean",
                      dest="clean", default=False, action="store_true",
                      help="cleanup overlay git repo.")
  parser.add_argument("--force-update",
                      dest="force_update", default=None,
                      help="force update to firmware binary on a device")
  parser.add_argument("--prepare-binary",
                      dest="prepare_binary", default=None,
                      help="rename binary to hwver_fwver.bin.")
  parser.add_argument("--ebuild",
                      dest="ebuild", default=None, nargs="*",
                      help="Generate firmware package and ebuild file.")
  parser.add_argument("--version",
                      dest="version", default=None,
                      help="Specify new version of generated ebuild package")
  parser.add_argument("--clean-ebuild",
                      dest="clean_ebuild", default=None, nargs="*",
                      help="Generate firmware package and ebuild file " +
                           "from scratch")
  parser.add_argument("--download",
                      dest="download", default=False, action="store_true",
                      help="download all firmware binaries to cwd")

  args = parser.parse_args()
  tool = FirmwareTool(MTBringupToolArgs(args))

  if args.prepare_binary or args.force_update:
    device = tool.AskForDevice("Which device does this firmware apply to?")
    binary = FirmwareBinary(args.prepare_binary or args.force_update)

    if args.prepare_binary:
      tool.PrepareBinary(device, binary)
    elif args.force_update:
      tool.ForceUpdate(device, binary)
  elif args.download:
    tool.DownloadBinaries()
  elif args.ebuild is not None or args.clean_ebuild is not None:
    files = args.ebuild or args.clean_ebuild
    new_version = args.version
    if not new_version:
      print("Enter the new version number of this ebuild:")
      current_version = tool.package.ebuild_version
      if current_version:
        print("(The current version is: {})".format(current_version))
        # todo(denniskempin): automatically increment x.x or x.x-rx version
      new_version = AskUser.Text()
      if not new_version:
        exit(-1)
    binaries = [FirmwareBinary(b) for b in files]
    tool.GenerateEbuildPackage(new_version, binaries,
                               args.clean_ebuild is not None)

  else:
    ExecuteCommonCommands(args, tool)

if __name__ == '__main__':
  main()
