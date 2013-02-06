// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef EVDEV_GESTURES_H_
#define EVDEV_GESTURES_H_

extern "C" {
#include <libevdev/libevdev.h>
}

#include <base/basictypes.h>
#include <gestures/gestures.h>

namespace replay {

// class wrapping the GestureInterpreter. It allows the GestureInterpreter
// to be used with structures provided by libevdev.
class EvdevGesture {
 public:
  EvdevGesture(EvdevPtr evdev,
               GestureInterpreter* interpreter);
  virtual ~EvdevGesture();

  // Initialize a HardwareProperties structure with data read from an evdev
  // device.
  void InitHardwareProperties(struct HardwareProperties*);

  // Push an libevdev event state to the GestureInterpreter.
  void PushEventState(EventStatePtr, struct timeval* tv);

 private:
  DISALLOW_COPY_AND_ASSIGN(EvdevGesture);

  GestureInterpreter* interpreter_;
  EvdevPtr evdev_;
  struct FingerState* fingers_;
};

}  // namespace replay

#endif  // EVDEV_GESTURES_H_
