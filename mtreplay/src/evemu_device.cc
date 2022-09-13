// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "evemu_device.h"

#include <cstdio>

namespace replay {

EvemuDevice::EvemuDevice() {
  evemu_ = evemu_new(NULL);
}

EvemuDevice::~EvemuDevice() {
  evemu_delete(evemu_);
}

bool EvemuDevice::ReadDeviceFile(FILE* fp) {
  return evemu_read(evemu_, fp);
}

const std::string EvemuDevice::GetName() {
  return std::string(evemu_get_name(evemu_));
}

const unsigned char* EvemuDevice::GetPropMask() {
  return evemu_get_prop_mask(evemu_);
}

const unsigned char* EvemuDevice::GetMask(const size_t& key) {
  return evemu_get_mask(evemu_, key);
}

const struct input_absinfo& EvemuDevice::GetAbsinfo(const size_t& key) {
  return *reinterpret_cast<const struct input_absinfo*>(
      evemu_get_abs(evemu_, key));
}

}  // namespace evemu
