// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef REPLAY_DEVICE_H_
#define REPLAY_DEVICE_H_

#include <cstdarg>

#include <string>
#include <vector>

#include <gestures/gestures.h>

#include "evdev_gestures.h"
#include "evemu_device.h"
#include "libevdev_mock.h"
#include "prop_provider.h"
#include "stream.h"

namespace replay {

// This structure contains all external configuration for the replay
// device. Including properties and all input/output streams for logs and
// settings.
struct ReplayDeviceConfig {
  // Enumeration of the different logs created by the simulation.
  enum LogCategory {
    // log created by libevdev
    kLogEvdev = 0,
    // log created by the gestures library
    kLogGestures,
    // json activity log generated at the end of a replay
    kLogActivity,
    // number of log categories.
    kLogCategoryCount
  };

  // The device class used for replay
  GestureInterpreterDeviceClass device_class;

  // Array containing all streams for log files
  Stream log[ReplayDeviceConfig::kLogCategoryCount];

  // json string containing properties
  std::string properties;

  // File pointer to the device data file
  Stream device;
};

// The main class for replaying event logs. It can only be instantiated with a
// ReplayDeviceConfig instance that contains valid streams. It allows
// to replay events and observe the current state of the multitouch stack.
// It also contains an interface for the libevdev and gestures mock to
// handle functionality like timers and callbacks.
class ReplayDevice {
 public:
  // All instances are tracked and accessible via GetDevice to allow mock
  // methods to access instances without having a pointer to them.
  explicit ReplayDevice(ReplayDeviceConfig* config);

  // Unregisters this instance automatically and it will no longer be accessible
  // via GetDevice.
  virtual ~ReplayDevice();

  // Replays all events from stream until the stream is empty.
  void ReplayEvents(Stream* stream);

  // Replay a single input event.
  void ReplayEvent(const struct input_event& event);

  // Access to the current timestamp of libevdev.
  double GetCurrentTime() const {
    return current_time_;
  }

  // Log a message to specified category.
  void Log(ReplayDeviceConfig::LogCategory category,
           const char* message, ...);

  // Log a message to specified category using a va_list.
  // Useful when mocking log methods.
  void VLog(ReplayDeviceConfig::LogCategory category,
           const char* format, va_list args);

  // The gestures library does have any means of identifying different devices
  // in the log method. It will use VLogAll to log to all open instances of
  // ReplayDevice.
  static void VLogAll(ReplayDeviceConfig::LogCategory category,
                     const char* format, va_list args);

  // This method is to be called by libevdev when a syn event is processed.
  void SynCallback(EventStatePtr, struct timeval*);

  // This method is called by the gestures library when a new gesture is ready.
  void GestureCallback(const struct Gesture*);

  // This method is used by the gestures library to set timers. The replay
  // device will make sure that the callback is invoked at an appropriate time.
  void SetFakeTimer(stime_t time, GesturesTimerCallback callback,
                    void* callback_udata);

  // Plays through the fake timer 0 or more times (maybe > 1 b/c a timer
  // callback may request another callback) until there are no more timer
  // requests or they advance to next_event or further.
  // current_time_ will be updated as timer events happen.
  void RunTimer(stime_t next_event);

  // Static method to access a device of a specific ID.
  static ReplayDevice* GetDevice(size_t id);

  EventStatePtr current_state() const {
    return current_state_;
  }

  Evdev_* evdev_device() const {
    return evdev_device_;
  }

  bool has_device_data() const {
    return has_device_data_;
  }

  EvemuDevice* evdev_file() const {
    return evdev_file_;
  }

 private:
  // Reference to the configuration for accessing the streams.
  ReplayDeviceConfig* config_;

  // Property provider to load properties for the gestures library
  PropProvider properties_;

  // The id of this device, as used by GetDevice.
  int id_;

  // True if device data has been loaded from file
  bool has_device_data_;

  // The EvemuDevice is used to read event/device files.
  EvemuDevice* evdev_file_;

  // Instances to the actual multitouch stack
  Evdev_* evdev_device_;
  EvdevGesture* evdev_gesture_;
  GestureInterpreter* interpreter_;
  // The current state of the multitouch stack
  EventStatePtr current_state_;
  stime_t current_time_;

  // Variables to track a timer and it:s callback.
  stime_t timer_target_time_;
  GesturesTimerCallback timer_callback_;
  void* timer_callback_udata_;

  // Array containing all instances of ReplayDevice.
  static std::vector<ReplayDevice*> devices_;

  DISALLOW_COPY_AND_ASSIGN(ReplayDevice);
};

}  // namespace replay

#endif  // REPLAY_DEVICE_H_
