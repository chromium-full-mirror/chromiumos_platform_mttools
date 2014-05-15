# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides tools for packaging, installing and testing firmware."""

from mtlib.util import Path, RequiredRegex, Execute, GitRepo
from tempfile import NamedTemporaryFile
import tarfile
import os
import io
import time

src_dir = Path("/mnt/host/source/src/")

class FirmwareException(Exception):
  pass

class FirmwareBinary(object):
  """."""
  def __init__(self, filename, fileobj=None, symlink=None):
    self.hw_version = None
    self.fw_version = None
    self.symlink_name = None

    if not fileobj:
      fileobj = open(filename, "rb")
    self.data = fileobj.read()

    if symlink:
      self.symlink_name = symlink

    name_regex = RequiredRegex("([0-9.a-zA-Z]+)_([0-9.a-zA-Z]+)\\.bin")
    match = name_regex.Match(filename, must_succeed=False)
    if match:
      self.hw_version = match.group(1)
      self.fw_version = match.group(2)

    self.filename = filename
    self.device_file = Path("/opt/google/touch/firmware", filename)

  def UpdateName(self, hw_version, fw_version):
    name = "{}_{}.bin".format(hw_version, fw_version)
    os.rename(self.filename, name)
    self.filename = name

  def ForceUpdate(self, device, remote):
    remote.RemountWriteable()

    symlink = Path("/lib/firmware", device.symlink)
    symlink_bak = Path(str(symlink) + ".bak")

    target = Path("/opt/google/touch/firmware/force_update.fw")
    device.symlink = symlink.basename

    remote.Write(str(target), self.data)
    try:
      remote.SafeExecute(["mv", str(symlink), str(symlink_bak)])
      try:
        remote.SafeExecute(["ln", "-s", str(target), str(symlink)])
        device.ForceFirmwareUpdate(remote)
      finally:
        remote.SafeExecute(["mv", str(symlink_bak), str(symlink)])
    finally:
      remote.SafeExecute(["rm", str(target)])

  def __str__(self):
    symlink = "Unknown"
    if self.symlink_name:
      symlink = "/lib/firmware/" + self.symlink_name
    return "%s @%s" % (self.filename, symlink)

  def __repr__(self):
    return str(self)


class FirmwarePackage(object):
  """Helper class to deal with firmware installation on devices."""
  name = "firmware"

  def __init__(self, board, variant):
    self.board = board
    self.variant = variant
    self.binaries = {}

    # determine path and name of touch firmware ebuild file
    if variant:
      overlay_name = "overlay-variant-{}-{}-private".format(
          board, variant)
    else:
      overlay_name = "overlay-{}-private".format(board)
    self.overlay = src_dir / "private-overlays" / overlay_name

    self.ebuild_name = "chromeos-touch-firmware-{}".format(board)
    self.ebuild_dir = self.overlay / "chromeos-base" / self.ebuild_name
    self.ebuild_repo = GitRepo(self.ebuild_dir)

    self.ebuild_file = self.ebuild_dir / "{}-0.0.1.ebuild".format(
        self.ebuild_name)

    # look for symlink to ebuild file
    self.ebuild_symlink = None
    for symlink in self.ebuild_dir.ListDir():
      if symlink.is_link and symlink.basename.startswith(self.ebuild_name):
        self.ebuild_symlink = symlink

    if not self.ebuild_symlink:
      msg = "Cannot find version symlink in {}"
      raise Exception(msg.format(self.ebuild_dir))

    # extract ebuild version from symlink name
    regex = "{}-([0-9a-zA-Z_\\-\\.]*).ebuild"
    regex = RequiredRegex(.format(self.ebuild_name))
    match = regex.Search(self.ebuild_symlink.basename)
    self.ebuild_version = match.group(1)

    bcsname = self.overlay.basename.replace("overlay-", "bcs-")
    url = "gs://chromeos-binaries/HOME/{}/{}/chromeos-base/{}/{}-{}.tbz2"
    self.bcs_url = url.format(bcsname, self.overlay.basename,
                              self.ebuild_name, self.ebuild_name,
                              self.ebuild_version)

  def _ExtractSymlinkfromEbuild(self, firmware):
    ebuild = open(str(self.ebuild_file), "r").read()
    regex = "dosym \"{}\" \"/lib/firmware/([a-zA-Z0-9_\\-.]+)\""
    regex = RequiredRegex(regex.format(firmware.device_file))
    match = regex.Search(ebuild, must_succeed=False)
    if match:
      return match.group(1)
    else:
      return None

  def GetExistingBinaries(self):
    tar_file = NamedTemporaryFile("rb")
    res = Execute(["gsutil", "cp", self.bcs_url, tar_file.name])
    if not res:
      return
    tar_file.seek(0)
    tar = tarfile.open(fileobj=tar_file)

    for member in tar.getmembers():
      if not member.isfile():
        continue
      name = os.path.basename(member.name)
      fileobj = tar.extractfile(member)
      binary = FirmwareBinary(name, fileobj)
      binary.symlink_name = self._ExtractSymlinkfromEbuild(binary)
      yield binary

  def AddBinary(self, binary):
    self.binaries[binary.hw_version] = binary

  def GenerateBCSPackage(self, version):
    tar_name = "chromeos-touch-firmware-{}-{}".format(self.board, version)
    tar_file = "{}.tbz2".format(tar_name)

    tar = tarfile.open(tar_file, "w:bz2")
    for binary in self.binaries.values():
      data = io.BytesIO(binary.data)
      path = tar_name + str(binary.device_file)
      info = tarfile.TarInfo(path)
      info.size = len(binary.data)
      info.mode = 0755
      info.uid = 0
      info.gid = 0
      info.mtime = time.time()
      info.uname = "root"
      info.gname = "root"
      tar.addfile(info, data)
    return Path(tar_file)

  def UpdateVersionSymlink(self, version):
    new_symlink = self.ebuild_dir / "{}-{}.ebuild".format(
        self.ebuild_name, version)

    old_symlink = self.ebuild_symlink
    if new_symlink != old_symlink:
      self.ebuild_repo.Move(old_symlink, new_symlink)

  def UpdateBinarySymlinks(self, remote):
    device_info = remote.GetDeviceInfo()
    devices = device_info.touch_devices
    for firmware in self.binaries.values():
      if firmware.symlink_name:
        continue
      if firmware.hw_version not in devices:
        msg = "Cannot find device for binary {}"
        raise Exception(msg.format(firmware))
      device = devices[firmware.hw_version]
      firmware.symlink_name = device.symlink

    symlink_names = [b.symlink_name for b in self.binaries.values()]
    if len(set(symlink_names)) != len(symlink_names):
      raise Exception("Duplicate symlink names for firmwares found")

  def UpdateEbuildFile(self, remote):
    self.UpdateBinarySymlinks(remote)

    ebuild = self.ebuild_file.Read()

    install_idx = ebuild.find("src_install")
    begin = ebuild.find("{", install_idx)

    # find closing bracket
    brackets = 0
    end = len(ebuild)
    for end in range(begin, len(ebuild)):
      if ebuild[end] == "{":
        brackets = brackets + 1
      elif ebuild[end] == "}":
        brackets = brackets - 1
      if brackets == 0:
        end = end + 1
        break

    # write ebuild with new src_install method
    out = self.ebuild_file.Open("w")
    out.write(ebuild[:begin])
    out.write("{\n")
    out.write("\t# automatically generated by mtbringup.\n")
    out.write("\tcros-binary_src_install\n\n")

    for firmware in self.binaries.values():
      line = "\tdosym \"%s\" \"/lib/firmware/%s\"\n"
      out.write(line % (firmware.device_file, firmware.symlink_name))

    out.write("}\n")
    out.write(ebuild[end:].strip())
    out.close()

  def VerifySymlinks(self, remote):
    valid = True

    for firmware in self.binaries.values():
      cmd = "readlink -f /lib/firmware/{}".format(firmware.symlink)
      target = remote.Execute(cmd)

      if not target:
        msg = "Symlink for firmware '{}' does not exist on device"
        print msg.format(firmware)
        valid = False

      target = Path(target)
      if target.basename != firmware.file.basename:
        msg = "Symlink for firmware '{}' does not point to the right file"
        print msg.format(firmware)
        valid = False

      cmd = "ls {}".format(firmware.device_file)
      if remote.Execute(cmd) is False:
        msg = "Firmware file {} does not exist on device"
        print msg.format(firmware.device_file)
        valid = False

    return valid

  def VerifyFirmwareVersions(self, remote):
    device_info = remote.GetDeviceInfo(refresh=True)

    valid = True
    for device in device_info.touch_devices.values():
      if device.hw_version not in self.binaries:
        continue
      firmware = self.binaries[device.hw_version]
      if firmware.fw_version != device.fw_version:
        print "Device {} did not update correctly:".format(device.hw_version)
        print "Device version {} != firmware version {}".format(
            device.fw_version, firmware.fw_version)
        valid = False
    return valid

  def __str__(self):
    res = "  firmwares:\n"
    for firmware in self.firmwares.values():
      res += "    {}".format(firmware)
    return res
