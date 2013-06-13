// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef EVEMU_DEVICE_H_
#define EVEMU_DEVICE_H_

#include <linux/input.h>
#include <string>

#include <base/basictypes.h>
extern "C" {
#include <evemu.h>
}

namespace evemu {

// This class wraps the utouch-evemu library.
// This class is deprecated and will be replaced by the
// read/write API of libevdev in a follow-up CL.
class EvemuDevice {
 public:
  // Create new device without association to an kernel device.
  EvemuDevice();
  virtual ~EvemuDevice();

  // Read a device file from file
  bool ReadDeviceFile(FILE* fp);

  // Read a single event from file. Returns true if reading was successful.
  static bool ReadEvent(FILE* fp, struct input_event* event);

  // Write a single event to a file. Returns true if writing was successful.
  static bool WriteEvent(FILE* fp, const struct input_event& event);

  // Access information provided by the device file. See utouch-evemu
  // for information on these methods.
  const std::string GetName();
  const unsigned char* GetPropMask();
  const unsigned char* GetMask(const size_t& key);
  const struct input_absinfo& GetAbsinfo(const size_t& key);

 private:
  // pointer to underlying C API device.
  evemu_device* evemu_;

  DISALLOW_COPY_AND_ASSIGN(EvemuDevice);
};

}  // namespace evemu

#endif  // EVEMU_DEVICE_H_
