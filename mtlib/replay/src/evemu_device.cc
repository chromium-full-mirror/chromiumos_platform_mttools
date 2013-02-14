// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "evemu_device.h"

#include <cstdio>

namespace evemu {

EvemuDevice::EvemuDevice() {
  evemu_ = evemu_new(NULL);
}

EvemuDevice::~EvemuDevice() {
  evemu_delete(evemu_);
}

bool EvemuDevice::ReadDeviceFile(FILE* fp) {
  return evemu_read(evemu_, fp);
}

bool EvemuDevice::ReadEvent(FILE* fp, struct input_event* event) {
  struct input_event tmp;
  int ret = evemu_read_event(fp, &tmp);
  if (ret > 0) {
    *event = tmp;
    return true;
  }
  return false;
}

bool EvemuDevice::WriteEvent(FILE* fp,
                             const struct input_event& event) {
  return evemu_write_event(fp, &event) > 0;
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
