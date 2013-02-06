// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <evemu_device.h>

#include <cstdio>

namespace evemu {

EvemuDevice::EvemuDevice() {
  evemu_ = evemu_new(NULL);
}

EvemuDevice::~EvemuDevice() {
   evemu_delete(evemu_);
}

bool EvemuDevice::ReadDeviceFile(std::istream* stream) {
  std::string data((std::istreambuf_iterator<char>(*stream)),
                   std::istreambuf_iterator<char>());
  // fmemopen requires non-const pointer, but does not modify in "r" mode
  FILE* file = fmemopen(const_cast<char*>(data.c_str()), data.length(), "r");
  bool result = evemu_read(evemu_, file);
  fclose(file);
  return result;
}

bool EvemuDevice::ReadEvent(std::istream* stream, struct input_event* event) {
  std::string line;
  std::getline(*stream, line);
  if (line.length() == 0)
    return false;

  // fmemopen requires non-const pointer, but does not modify in "r" mode
  FILE* file = fmemopen(const_cast<char*>(line.c_str()), line.length(), "r");

  bool result = evemu_read_event(file, event) > 0;
  fclose(file);
  return result;
}

bool EvemuDevice::WriteEvent(std::ostream* stream,
                             const struct input_event& event) {
  char buffer[128] = {0};

  // fmemopen requires non-const pointer, but does not modify in "r" mode
  FILE* file = fmemopen(buffer, 1024, "w");

  bool result = evemu_write_event(file, &event) > 0;
  fclose(file);
  (*stream) << const_cast<const char*>(buffer);
  return result;
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
