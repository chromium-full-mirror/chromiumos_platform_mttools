// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef EVEMU_DEVICE_H_
#define EVEMU_DEVICE_H_

#include <linux/input.h>

#include <iostream>

extern "C" {
#include <evemu.h>
}
#include <base/basictypes.h>

namespace evemu {

// This class wraps the utouch-evemu library and allows it to be used with
// C++ streams instead of the C FILE* API.
class EvemuDevice {
 public:
  // Create new device without association to an kernel device.
  EvemuDevice();
  virtual ~EvemuDevice();

  // Read a device file from stream
  bool ReadDeviceFile(std::istream* stream);

  // Read a single event from stream. Returns true if reading was successful.
  static bool ReadEvent(std::istream* stream, struct input_event* event);

  // Write a single event to a stream. Returns true if writing was successful.
  static bool WriteEvent(std::ostream* stream, const struct input_event& event);

  // Access information provided by the device file. See utouch-evemu
  // for information on these methods.
  const std::string GetName();
  const unsigned char* GetPropMask();
  const unsigned char* GetMask(const size_t& key);
  const struct input_absinfo& GetAbsinfo(const size_t& key);

 private:
  DISALLOW_COPY_AND_ASSIGN(EvemuDevice);

  // pointer to underlying C API device.
  evemu_device* evemu_;
};

}  // namespace evemu

#endif  // EVEMU_DEVICE_H_
