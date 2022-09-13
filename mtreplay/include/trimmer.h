// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef TRIMMER_H_
#define TRIMMER_H_

#include "replay_device.h"

namespace replay {

// The trimmer class is used to trim event logs.
// As input_event logs are delta compressed, the log cannot be simply
// cut at any position, but the device state has to be tracked and restored
// after a cut.
class Trimmer {
 public:
  // The trimmer requires a ReplayDevice instance to replay and keep track of
  // the event state.
  explicit Trimmer(ReplayDevice* replay);

  // Trim the event log from in and write the result to out.
  // Note: The trim times have to be timestamps of SYN events.
  bool Trim(Stream* in, Stream* out, double from, double to);

 private:
  // Used internally to write events to the output stream that will restore the
  // current event state.
  void WriteCurrentState(Stream* out, struct input_event* syn);

  // Writes a single input event to the output stream
  void WriteEvent(Stream* out, const struct timeval& time, __u16 type,
                  __u16 code, __s32 value);

  ReplayDevice* replay_;
};

}  // namespace replay

#endif  // TRIMMER_H
