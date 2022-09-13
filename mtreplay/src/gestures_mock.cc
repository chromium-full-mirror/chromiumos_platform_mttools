// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "gestures_mock.h"

#include <cstdarg>

#include <gestures/gestures.h>

#include "replay_device.h"

using replay::ReplayDeviceConfig;
using replay::ReplayDevice;

extern "C" {

void gestures_log(int level, const char* format, ...) {
  va_list args;
  va_start(args, format);
  ReplayDevice::VLogAll(ReplayDeviceConfig::kLogGestures, format, args);
  va_end(args);
}

// Declared in gestures library. Empty definition here.
struct GesturesTimer {
  char __dummy; // http://crbug.com/341508
};

}  // extern "C"

namespace replay {

GesturesTimer* TimerCreate(void*) {
  return new GesturesTimer();
}

void TimerSet(void* udata, GesturesTimer* timer, stime_t time,
              GesturesTimerCallback callback, void* callback_udata) {
  ReplayDevice* device = reinterpret_cast<ReplayDevice*>(udata);
  device->SetFakeTimer(time, callback, callback_udata);
}

void TimerCancel(void* udata, GesturesTimer* timer) {
  ReplayDevice* device = reinterpret_cast<ReplayDevice*>(udata);
  device->SetFakeTimer(0, NULL, NULL);
}

void TimerFree(void*, GesturesTimer* timer) {
  delete timer;
}

void GestureCallback(void* udata, const struct Gesture* gesture) {
  ReplayDevice* device = reinterpret_cast<ReplayDevice*>(udata);
  device->GestureCallback(gesture);
}

GestureInterpreter* NewGestureInterpreterMock(int id) {
  GestureInterpreter* interpreter = new GestureInterpreter(1);
  interpreter->set_callback(&GestureCallback, ReplayDevice::GetDevice(id));

  static GesturesTimerProvider timerProvider = { TimerCreate, TimerSet,
                                                 TimerCancel, TimerFree };
  interpreter->SetTimerProvider(&timerProvider, ReplayDevice::GetDevice(id));
  return interpreter;
}

void DeleteGestureInterpreterMock(GestureInterpreter* interpreter) {
  delete interpreter;
}

}  // namespace replay
