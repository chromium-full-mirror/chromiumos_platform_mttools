// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <generic_stream.h>

#include <ext/stdio_filebuf.h>
#include <sstream>

#include <util.h>

namespace replay {

using __gnu_cxx::stdio_filebuf;

template<typename StreamType>
GenericStream<StreamType>::GenericStream()
    : buffer_(NULL), stream_(NULL), stream_owner_(false) {
}

template<typename StreamType>
GenericStream<StreamType>::GenericStream(const std::string& target)
    : buffer_(NULL), stream_(NULL), stream_owner_(false) {
  Open(target);
}

template<typename StreamType>
GenericStream<StreamType>::GenericStream(StreamType* target)
    : buffer_(NULL), stream_(NULL), stream_owner_(false) {
  Open(target);
}

template<typename StreamType>
bool GenericStream<StreamType>::Open(const std::string& target) {
  if (target == "stdio") {
    // access stdio stream
    stream_ = stdio_stream_;
  } else {
    if (target.compare(0, 3, "fd:") == 0) {
      // access file descriptor
      int fd = lexical_cast<int>(target.substr(3));
      buffer_ = new stdio_filebuf<char>(fd,
                                        GenericStream<StreamType>::openmode_);
    } else {
      // access file
      buffer_ = new std::filebuf();
      buffer_->open(target.c_str(), GenericStream<StreamType>::openmode_);
    }
    stream_ = new StreamType(buffer_);
    stream_owner_ = true;
  }
  return Good();
}

template<typename StreamType>
inline bool GenericStream<StreamType>::Open(StreamType* target) {
  stream_ = target;
  return Good();
}

template<typename StreamType>
bool GenericStream<StreamType>::OpenBuffer(const char* buffer) {
  stream_ = new std::stringstream(buffer, GenericStream<StreamType>::openmode_);
  stream_owner_ = true;
  return Good();
}


template<typename StreamType>
GenericStream<StreamType>::~GenericStream() {
  if (!stream_owner_)
    return;

  if (buffer_ != NULL) {
    delete buffer_;
    buffer_ = NULL;
  }
  if (stream_ != NULL && stream_ != stdio_stream_) {
    delete stream_;
    stream_ = NULL;
  }
}

template<typename StreamType>
bool GenericStream<StreamType>::Good() {
  return stream_ != NULL && stream_->good();
}

template<typename StreamType>
StreamType* GenericStream<StreamType>::GetStream() {
  return stream_;
}

// force code generation for istream and ostream.
template class GenericStream<std::istream>;
template class GenericStream<std::ostream>;

// specialize template to assign stdio stream
template<>
std::istream* GenericStream<std::istream>::stdio_stream_ = &std::cin;

template<>
std::ostream* GenericStream<std::ostream>::stdio_stream_ = &std::cout;

// specialize template to assign openmode
template<>
std::ios_base::openmode GenericStream<std::istream>::openmode_ = std::ios::in;

template<>
std::ios_base::openmode GenericStream<std::ostream>::openmode_ = std::ios::out;

}  // namespace replay

