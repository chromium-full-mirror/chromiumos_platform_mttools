// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef GENERIC_STREAM_H_
#define GENERIC_STREAM_H_

#include <iostream>
#include <string>

#include <base/basictypes.h>

namespace replay {

// stream class to access a stream to a file, file descriptor
// or a standard io stream. See open() for a description of how to open
// a stream. The StreamType template parameter is used to distinguish between
// std::istream and std::ostream streams.
template<typename StreamType>
class GenericStream {
 public:
  // create an uninitialized stream
  GenericStream();

  // open a new stream. See open() for details.
  GenericStream(const std::string& target);

  // open a new stream. See open() for details.
  GenericStream(StreamType* stream);

  // closes the stream
  virtual ~GenericStream();

  // open a stream to specified target. The target can be:
  // A) "filename" to access a file
  // B) "fd:X" where X is a number to open X as a file descriptor
  // C) "stdio" to read/write to stdin or stdout.
  bool Open(const std::string& target);

  // wrap an existing stream into this instance
  bool Open(StreamType* target);

  // open a stringstream and fill it with 'buffer'
  bool OpenBuffer(const char* buffer);

  // true if the stream is opened and ready for IO
  bool Good();

  // returns a reference to the stream.
  StreamType* GetStream();

 protected:
  DISALLOW_COPY_AND_ASSIGN(GenericStream);

  // the stdio stream associated with this StreamType.
  static StreamType* stdio_stream_;
  // the openmode associated with this StreamType.
  static std::ios_base::openmode openmode_;

  // underlying filebuffer of the std::stream
  std::filebuf* buffer_;
  // instance of the underlying std::stream
  StreamType* stream_;
  // true if this object is owning the stream and buffer
  bool stream_owner_;
};

// code is only generated for these two implementations of GenericStream.
typedef GenericStream<std::istream> GenericIStream;
typedef GenericStream<std::ostream> GenericOStream;

}  // namespace replay

#endif  // GENERIC_STREAM_H_
