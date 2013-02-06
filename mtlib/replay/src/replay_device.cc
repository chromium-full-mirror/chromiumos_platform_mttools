// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <replay_device.h>

#include <cmath>
#include <iomanip>
#include <iostream>

#include <gestures_mock.h>
#include <libevdev_mock.h>

namespace replay {

std::vector<ReplayDevice*> ReplayDevice::devices_;

ReplayDevice::ReplayDevice(ReplayDeviceConfig* config)
    : config_(config), evemu_device_(NULL), evdev_gesture_(NULL),
      interpreter_(NULL), current_state_(NULL), current_time_(0),
      timer_target_time_(0), timer_callback_(NULL),
      timer_callback_udata_(NULL) {
  id_ = devices_.size();
  devices_.push_back(this);

  // read device file into evemu
  evemu_device_ = new evemu::EvemuDevice();
  evemu_device_->ReadDeviceFile(config_->device.GetStream());

  // create libevdev mock
  evdev_device_ = NewEvdevMock(id_);
  interpreter_ = replay::NewGestureInterpreterMock(id_);
  interpreter_->SetPropProvider(&CPropProvider, &properties_);
  evdev_gesture_ = new EvdevGesture(evdev_device_, interpreter_);

  interpreter_->Initialize();

  // load properties from properties file
  if (config->properties.Good()) {
    if (!properties_.Load(&config->properties)) {
      std::cerr << "Failed loading properties file" << std::endl;
      exit(-1);
    }
  }

  // init fake device hardware properties
  struct HardwareProperties hwprops;
  evdev_gesture_->InitHardwareProperties(&hwprops);
  interpreter_->SetHardwareProperties(hwprops);
}

ReplayDevice::~ReplayDevice() {
  devices_[id_] = NULL;
}

void ReplayDevice::ReplayEvents(GenericIStream* stream) {
  struct input_event event;
  while (evemu_device_->ReadEvent(stream->GetStream(), &event) > 0) {
    ReplayEvent(event);
  }

  // handle remaining timers.
  RunTimer(INFINITY);

  Log(ReplayDeviceConfig::kLogActivity, interpreter_->EncodeActivityLog());
}

void ReplayDevice::ReplayEvent(const struct input_event& event) {
  // Passing to C API. Drop const qualifier.
  Event_Process(evdev_device_, const_cast<struct input_event*>(&event));
}

void ReplayDevice::Log(ReplayDeviceConfig::LogCategory category,
                       const std::string& message) {
  GenericStream<std::ostream>& stream = config_->log[category];
  if (stream.Good()) {
    (*stream.GetStream()) << message;
    stream.GetStream()->flush();
  }
}

void ReplayDevice::LogAll(ReplayDeviceConfig::LogCategory category,
                          const std::string& message) {
  for (size_t i = 0; i < devices_.size(); ++i) {
    if (devices_[i]) {
      devices_[i]->Log(category, message);
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
  if (config_->log[ReplayDeviceConfig::kLogGestures].Good()) {

    std::ostream& stream = *(config_->log[ReplayDeviceConfig::kLogGestures]
                             .GetStream());

    stream << "----------------------------------------"
              "----------------------------------------" << std::endl;
    stream << std::setiosflags(std::ios::fixed) << std::setprecision(6)
           << current_time_ << " - ";
    switch (gesture->type) {
    case kGestureTypeContactInitiated:
      stream << "Contact Initiated" << std::endl;
      break;
    case kGestureTypeMove:
      stream << "Move (" << static_cast<int>(gesture->details.move.dx) << ", "
             << static_cast<int>(gesture->details.move.dy) << ")";
      break;
    case kGestureTypeScroll:
      stream << "Scroll (" << static_cast<int>(gesture->details.scroll.dx)
             << ", " << static_cast<int>(gesture->details.scroll.dy) << ")";
      break;
    case kGestureTypeButtonsChange:
      stream << "Buttons Change up=" << gesture->details.buttons.up << ", down="
             << gesture->details.buttons.up;
      break;
    case kGestureTypeFling:
      stream << "Fling state=" << gesture->details.fling.fling_state << " ("
             << gesture->details.fling.vx << ", " << gesture->details.fling.vy
             << ")";
      break;
    case kGestureTypeSwipe:
      stream << "Swipe dx=" << gesture->details.swipe.dx;
      break;
    case kGestureTypePinch:
      stream << "Pinch dz=" << gesture->details.pinch.dz;
      break;
    case kGestureTypeSwipeLift:
      stream << "Swipe Lift";
      break;
    }
    stream << std::endl;
    stream << "----------------------------------------"
              "----------------------------------------" << std::endl;
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
