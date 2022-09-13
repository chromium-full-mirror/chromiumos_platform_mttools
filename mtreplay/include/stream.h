// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef STREAM_H_
#define STREAM_H_

#include <iostream>
#include <string>

#include "util.h"

namespace replay {

// Class for wrapping C FILE* objects to allow RAII and provide
// helper methods for reading/writing from/to strings.
class Stream {
 public:
  // create an uninitialized stream
  Stream();

  // open a new stream. See open() for details.
  explicit Stream(FILE* target);

  // open a new stream. See open() for details.
  Stream(const std::string& filename, const char* mode);

  // closes the stream
  virtual ~Stream();

  // wrap an existing FILE pointer into this instance
  bool Open(FILE* target);

  // open stream to file
  bool OpenFile(const std::string& filename, const char* mode);

  // open a stream to read contents.
  // The content is copied to the internal buffer
  bool OpenReadBuffer(const char* contents);

  // open stream to write to a buffer of size
  bool OpenWriteBuffer(size_t size);

  // true if the stream is opened and ready for IO
  bool Good();

  // returns the file object accessing the stream
  FILE* GetFP();

  // closes the steam and frees all memort
  void Close();

  // returns the buffer contents if the stream was opened with OpenWriteBuffer.
  // otherwise returns NULL
  const char* GetBuffer();

 protected:
  // underlying FILE object
  FILE* fp_;

  // underlying string when using a buffer
  char* buffer_;

 private:
  DISALLOW_COPY_AND_ASSIGN(Stream);
};

}  // namespace replay

#endif  // GENERIC_STREAM_H_
