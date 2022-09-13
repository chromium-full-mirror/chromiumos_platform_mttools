// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "stream.h"

#include <assert.h>
#include <cstdio>
#include <cstring>

#include "util.h"

namespace replay {

Stream::Stream() : fp_(NULL), buffer_(NULL) {}

Stream::Stream(FILE* target) : fp_(NULL), buffer_(NULL) {
  Open(target);
}

Stream::Stream(const std::string& filename, const char* mode)
  : fp_(NULL), buffer_(NULL) {
  OpenFile(filename, mode);
}

Stream::~Stream() {
  Close();
}

void Stream::Close() {
  if (fp_) {
    fclose(fp_);
    fp_ = NULL;
  }
  if (buffer_) {
    delete[] buffer_;
    buffer_ = NULL;
  }
}

bool Stream::Open(FILE* target) {
  if (fp_)
    Close();
  fp_ = target;
  return Good();
}

bool Stream::OpenFile(const std::string& filename, const char* mode) {
  if (fp_)
    Close();
  fp_ = fopen(filename.c_str(), mode);
  return Good();
}

bool Stream::OpenReadBuffer(const char* contents) {
  if (fp_)
    Close();

  // add \0 terminator to size
  size_t size = strlen(contents) + 1;

  // copy string to buffer_
  buffer_ = new char[size];
  strcpy(buffer_, contents);

  // open buffer_ as FILE
  fp_ = fmemopen(buffer_, size, "r");

  return Good();
}

bool Stream::OpenWriteBuffer(size_t size) {
  if (fp_)
    Close();

  // create empty buffer
  buffer_ = new char[size];
  memset(buffer_, 0, size);

  // open buffer_ as FILE
  fp_ = fmemopen(buffer_, size, "w");

  return Good();
}

bool Stream::Good() {
  return fp_ && !feof(fp_);
}

FILE* Stream::GetFP() {
  return fp_;
}

const char* Stream::GetBuffer() {
  if (fp_)
    fflush(fp_);
  return buffer_;
}

}  // namespace replay
