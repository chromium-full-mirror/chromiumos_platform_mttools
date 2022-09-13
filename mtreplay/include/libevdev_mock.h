// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef LIBEVDEV_MOCK_H_
#define LIBEVDEV_MOCK_H_

extern "C" {
#include <libevdev/libevdev.h>
}

namespace replay {

  // create a new mock instance of the evdev device. It will call SynCallback
  // of the associated ReplayDevice. It will read all hardware properties from
  // the ReplayDevice and fake the device setup to be able to run without
  // a kernel device.
  Evdev* NewEvdevMock(int id);

  // Free all resources associated with this device.
  void DeleteEvdevMock(Evdev* device);

}  // namespace replay

#endif  // LIBEVDEV_MOCK_H_
