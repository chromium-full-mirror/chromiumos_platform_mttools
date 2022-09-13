// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <replay_device.h>

#include <assert.h>
#include <cmath>

#include "gestures_mock.h"
#include "libevdev_mock.h"

namespace replay {

std::vector<ReplayDevice*> ReplayDevice::devices_;

ReplayDevice::ReplayDevice(ReplayDeviceConfig* config)
    : config_(config), has_device_data_(false), evdev_file_(NULL),
      evdev_gesture_(NULL), interpreter_(NULL), current_state_(NULL),
      current_time_(0), timer_target_time_(0), timer_callback_(NULL),
      timer_callback_udata_(NULL) {
  id_ = devices_.size();
  devices_.push_back(this);

  // read device file into evemu
  evdev_file_ = new EvemuDevice();
  if (config_->device.Good()) {
    evdev_file_->ReadDeviceFile(config_->device.GetFP());
    has_device_data_ = true;
  }
  // load properties from properties file
  if (!config->properties.empty()) {
    if (!properties_.Load(config->properties)) {
      std::cerr << "Failed loading properties file" << std::endl;
      exit(-1);
    }
  }

  // create libevdev mock
  evdev_device_ = NewEvdevMock(id_);
  interpreter_ = replay::NewGestureInterpreterMock(id_);
  interpreter_->SetPropProvider(&CPropProvider, &properties_);
  evdev_gesture_ = new EvdevGesture(evdev_device_, interpreter_);

  interpreter_->Initialize(config_->device_class);

  // init fake device hardware properties
  struct HardwareProperties hwprops;
  evdev_gesture_->InitHardwareProperties(&hwprops, &properties_);

  // this property is unused but xorg conf file sets it
  int accel_profile = 0;
  properties_.GetPropValue("AccelerationProfile", &accel_profile);

  if (!properties_.CheckIntegrity()) {
    std::cerr << "Property Integrity Error" << std::endl;
    exit(-1);
  }

  interpreter_->SetHardwareProperties(hwprops);
}

ReplayDevice::~ReplayDevice() {
  devices_[id_] = NULL;
}

void ReplayDevice::ReplayEvents(Stream* stream) {
  // Try to read device info from log file. If it exists it will
  // override any device info read from the device file.
  int ret = EvdevReadInfoFromFile(stream->GetFP(), &evdev_device_->info);
  if (!has_device_data_ && ret <= 0) {
    std::cerr << "device file or device header in log is required" << std::endl;
    exit(-1);
  }

  struct input_event event;
  while (EvdevReadEventFromFile(stream->GetFP(), &event) > 0) {
    ReplayEvent(event);
  }

  // handle remaining timers.
  RunTimer(INFINITY);
  std::string activity = interpreter_->EncodeActivityLog();
  Log(ReplayDeviceConfig::kLogActivity, activity.c_str());
}

void ReplayDevice::ReplayEvent(const struct input_event& event) {
  // Passing to C API. Drop const qualifier.
  Event_Process(evdev_device_, const_cast<struct input_event*>(&event));
}

void ReplayDevice::VLog(ReplayDeviceConfig::LogCategory category,
                       const char* format, va_list args) {
  Stream& stream = config_->log[category];
  if (stream.Good()) {
    // Disable warning: format string is not a string literal.
    // https://crbug.com/684114
    #pragma GCC diagnostic push
    #pragma GCC diagnostic ignored "-Wformat-nonliteral"
    vfprintf(stream.GetFP(), format, args);
    #pragma GCC diagnostic pop
  }
}

void ReplayDevice::Log(ReplayDeviceConfig::LogCategory category,
                       const char* format, ...) {
  Stream& stream = config_->log[category];
  if (stream.Good()) {
    va_list args;
    va_start(args, format);
    VLog(category, format, args);
    va_end(args);
  }
}

void ReplayDevice::VLogAll(ReplayDeviceConfig::LogCategory category,
                          const char* format, va_list args) {
  for (size_t i = 0; i < devices_.size(); ++i) {
    if (devices_[i]) {
      devices_[i]->VLog(category, format, args);
    }
  }
}

void ReplayDevice::SynCallback(EventStatePtr evstate, struct timeval* timeval) {
  current_state_ = evstate;
  stime_t next_event = StimeFromTimeval(timeval);
  RunTimer(next_event);
  current_time_ = next_event;
  evdev_gesture_->PushEventState(evstate, timeval);
}

void ReplayDevice::GestureCallback(const struct Gesture* gesture) {
  const char* separator = "----------------------------------------"
                          "----------------------------------------\n";

  Stream& stream = config_->log[ReplayDeviceConfig::kLogGestures];
  if (stream.Good()) {
    FILE* fp = stream.GetFP();
    fprintf(fp, "%s", separator);
    fprintf(fp, "%f.6 - ", current_time_);

    switch (gesture->type) {
    case kGestureTypeContactInitiated:
      fprintf(fp, "Contact Initiated");
      break;
    case kGestureTypeMove:
      fprintf(fp, "Move (%d, %d)",
              static_cast<int>(gesture->details.move.dx),
              static_cast<int>(gesture->details.move.dy));
      break;
    case kGestureTypeScroll:
      fprintf(fp, "Scroll (%d, %d)",
              static_cast<int>(gesture->details.scroll.dx),
              static_cast<int>(gesture->details.scroll.dy));
      break;
    case kGestureTypeMouseWheel:
      fprintf(fp, "Mouse Wheel (%d, %d) [%d, %d]",
              static_cast<int>(gesture->details.wheel.dx),
              static_cast<int>(gesture->details.wheel.dy),
              gesture->details.wheel.tick_120ths_dx,
              gesture->details.wheel.tick_120ths_dy);
      break;
    case kGestureTypeButtonsChange:
      fprintf(fp, "Buttons Change up=%d, down=%d",
              gesture->details.buttons.up,
              gesture->details.buttons.up);
      break;
    case kGestureTypeFling:
      fprintf(fp, "Fling state=%d (%d, %d)",
              gesture->details.fling.fling_state,
              static_cast<int>(gesture->details.fling.vx),
              static_cast<int>(gesture->details.fling.vy));
      break;
    case kGestureTypeSwipe:
      fprintf(fp, "Swipe dx=%d", static_cast<int>(gesture->details.swipe.dx));
      break;
    case kGestureTypeFourFingerSwipe:
      fprintf(fp, "Four Finger Swipe dx=%d",
              static_cast<int>(gesture->details.four_finger_swipe.dx));
      break;
    case kGestureTypePinch:
      fprintf(fp, "Pinch dz=%d", static_cast<int>(gesture->details.pinch.dz));
      break;
    case kGestureTypeSwipeLift:
      fprintf(fp, "Swipe Lift");
      break;
    case kGestureTypeFourFingerSwipeLift:
      fprintf(fp, "Four Finger Swipe Lift");
      break;
    case kGestureTypeMetrics:
      fprintf(fp, "Metrics type=%d (%f, %f)",
              gesture->details.metrics.type,
              gesture->details.metrics.data[0],
              gesture->details.metrics.data[1]);
      break;
    }
    fprintf(fp, "\n%s", separator);
  }
}
void ReplayDevice::SetFakeTimer(stime_t time, GesturesTimerCallback callback,
                                void* callback_udata) {
  timer_target_time_ = current_time_ + time;
  timer_callback_ = callback;
  timer_callback_udata_ = callback_udata;
}

void ReplayDevice::RunTimer(stime_t next_event) {
  while (timer_callback_ && (timer_target_time_ < next_event)) {
    current_time_ = timer_target_time_;
    GesturesTimerCallback callback = timer_callback_;
    timer_callback_ = NULL;

    // the callback might re-set timer_callback
    stime_t next = callback(timer_target_time_, timer_callback_udata_);
    if (next >= 0.0)
      SetFakeTimer(next, callback, timer_callback_udata_);
  }
}

ReplayDevice* ReplayDevice::GetDevice(size_t id) {
  assert(id < devices_.size());
  assert(devices_[id] != NULL);
  return devices_[id];
}

}  // namespace replay
