# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Classes to extract information about chromebooks and their touch devices."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import re

def EnumerateI2CDevices(remote, path):
  items = remote.Execute("ls " + path)
  if items is False:
    return []

  device_regex = "[0-9a-z]+-[0-9a-fA-Z:]+"
  devices = []
  for item in re.finditer(device_regex, items):
    devices.append(item.group(0))
  return devices

class DeviceInfo(object):
  """Describes a chromebook's touch device."""
  vendor = None

  def __init__(self, remote, device_id):
    self.id = device_id
    self.path = os.path.join("/sys/bus/i2c/devices", device_id)
    self.kernel_device = None
    self.name = str(self.vendor) + " Touch Device"
    self.hw_version = None
    self.fw_version = None
    self.symlink = None

    self.fw_version = self.ReadDeviceFile(
        remote, ["fw_version", "firmware_version"])
    self.hw_version = self.ReadDeviceFile(
        remote, ["hw_version", "product_id"])

    self.hw_name = self.ReadDeviceFile(remote, "name")

    input_path = os.path.join(self.path, "input")
    input_name = remote.Execute("ls {}".format(input_path))
    if input_name:
      if len(input_name.splitlines()) > 1:
        raise Exception("Multiple kernel devices found")

      input_id = int(input_name[-1:])
      self.kernel_device = "/dev/input/event{}".format(input_id)

      name_path = os.path.join(input_path, input_name, "name")
      self.name = remote.SafeExecute("cat {}".format(name_path))

  def Refresh(self, remote):
    self.__init__(remote, self.id)

  def ReadDeviceFile(self, remote, names):
    if isinstance(names, str):
      names = [names]
    for name in names:
      path = os.path.join(self.path, name)
      res = remote.Execute("cat " + path)
      if res:
        return res.strip()
    raise Exception("Cannot read any of the remote files: {}".format(names))

  def ForceFirmwareUpdate(self, remote):
    update_path = os.path.join(self.path, "update_fw")
    remote.SafeExecute("echo 1 > " + update_path, verbose=True)

  def __str__(self):
    return "{} {}/{} /lib/firmware/{} @{}".format(
        self.name, self.hw_version, self.fw_version, self.symlink, self.path)
  def __repr__(self):
    return self.__str__()


class AtmelDeviceInfo(DeviceInfo):
  """Implementation of DeviceInfo for Atmel maXTouch devices."""
  vendor = "Atmel"

  def __init__(self, remote, device_id):
    DeviceInfo.__init__(self, remote, device_id)

    if self.hw_name == "atmel_mxt_ts":
      self.symlink = "maxtouch_ts.fw"
    elif self.hw_name == "atmel_mxt_tp":
      self.symlink = "maxtouch_tp.fw"
    elif "Touchscreen" in self.name:
      self.symlink = "maxtouch_ts.fw"
    elif "Touchpad" in self.name:
      self.symlink = "maxtouch_tp.fw"
    else:
      raise Exception("Cannot determine Atmel symlink name")

  def ForceFirmwareUpdate(self, remote):
    file_path = os.path.join(self.path, "fw_file")
    remote.SafeExecute("echo {} > {}".format(self.symlink, file_path),
                       verbose=True)
    return DeviceInfo.ForceFirmwareUpdate(self, remote)

  @staticmethod
  def DiscoverAll(remote):
    def Discover(driver):
      devices = EnumerateI2CDevices(remote, "/sys/bus/i2c/drivers/%s/" % driver)
      return [AtmelDeviceInfo(remote, d) for d in devices]
    return Discover("atmel_mxt_ts") + Discover("atmel_mxt_tp")


class ElanDeviceInfo(DeviceInfo):
  """Implementation of DeviceInfo for Elan touch devices."""
  vendor = "Elan"

  def __init__(self, remote, device_id, symlink):
    DeviceInfo.__init__(self, remote, device_id)
    self.symlink = symlink

  def Refresh(self, remote):
    self.__init__(remote, self.id, self.symlink)

  @staticmethod
  def DiscoverAll(remote):
    tp_devices = EnumerateI2CDevices(remote, "/sys/bus/i2c/drivers/elan_i2c/")
    ts_devices = EnumerateI2CDevices(remote, "/sys/bus/i2c/drivers/elants_i2c/")
    return ([ElanDeviceInfo(remote, d, "elan_i2c.bin") for d in tp_devices] +
            [ElanDeviceInfo(remote, d, "elants_i2c.bin") for d in ts_devices])

class CypressDeviceInfo(DeviceInfo):
  """Implementation of DeviceInfo for Cypress touch devices."""
  vendor = "Cypress"

  def __init__(self, remote, device_id):
    DeviceInfo.__init__(self, remote, device_id)
    self.symlink = "cyapa.bin"

  @staticmethod
  def DiscoverAll(remote):
    devices = EnumerateI2CDevices(remote, "/sys/bus/i2c/drivers/cyapa/")
    return [CypressDeviceInfo(remote, d) for d in devices]


class CrOSDeviceInfo(object):
  """CrOSDeviceInfo extracts device information from chromebook.

  The information is extracted via an SSH remote connection. It will
  determine which board the device is running and enumerate all touch
  devices.
  """

  def __init__(self, remote):
    self.remote = remote
    self.ip = remote.ip
    self.arch = remote.SafeExecute("arch")

    # read board_variant from device
    info = self.remote.Read("/etc/lsb-release")
    board_regex = "CHROMEOS_RELEASE_BOARD=([a-zA-Z0-9_-]*)"
    self.board_variant = re.search(board_regex, info).group(1)

    # split into board and variant
    parts = self.board_variant.split("_")
    self.board = parts[0]
    self.variant = parts[1] if len(parts) > 1 else None

    # discover all touch devices that are present
    device_list = []
    device_list.extend(AtmelDeviceInfo.DiscoverAll(remote))
    device_list.extend(ElanDeviceInfo.DiscoverAll(remote))
    device_list.extend(CypressDeviceInfo.DiscoverAll(remote))

    self.touch_devices = {}
    for device in device_list:
      self.touch_devices[device.hw_version] = device
