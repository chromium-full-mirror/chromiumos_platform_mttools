// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef EVDEV_GESTURES_H_
#define EVDEV_GESTURES_H_

#include <gestures/gestures.h>
extern "C" {
#include <libevdev/libevdev.h>
}

#include "util.h"

namespace replay {

class PropProvider;

// class wrapping the GestureInterpreter. It allows the GestureInterpreter
// to be used with structures provided by libevdev.
class EvdevGesture {
 public:
  EvdevGesture(EvdevPtr evdev,
               GestureInterpreter* interpreter);
  virtual ~EvdevGesture();

  // Initialize a HardwareProperties structure with data read from an evdev
  // device.
  void InitHardwareProperties(struct HardwareProperties*,
                              PropProvider* properties);

  // Push an libevdev event state to the GestureInterpreter.
  void PushEventState(EventStatePtr, struct timeval* tv);

 private:
  GestureInterpreter* interpreter_;
  EvdevPtr evdev_;
  struct FingerState* fingers_;

  DISALLOW_COPY_AND_ASSIGN(EvdevGesture);
};

}  // namespace replay

#endif  // EVDEV_GESTURES_H_
