// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <fstream>
#include <getopt.h>
#include <iostream>
#include <limits>

#include "replay_device.h"
#include "stream.h"
#include "trimmer.h"

// this function will open a stream.
// In case the stream cannot be opened an error message will be printed
// and the program will be forced to exit.
void SafeOpen(replay::Stream* stream, const char* filename, const char* mode) {
  stream->OpenFile(filename, mode);
  if (!stream->Good()) {
    std::cerr << "Cannot open stream to '" << filename << "'" << std::endl;
    exit(-1);
  }
}

int main(int argc, char** argv) {
  replay::ReplayDeviceConfig config;
  replay::Stream events;
  replay::Stream trim_out;
  std::ifstream props;

  config.device_class = GESTURES_DEVCLASS_TOUCHPAD;

  bool trim_enabled = false;
  double trim_from = -std::numeric_limits<double>::infinity();
  double trim_to = std::numeric_limits<double>::infinity();

  while (1) {
    static struct option long_options[] = {
      { "evdev-log", required_argument, 0, 'v' },
      { "gestures-log", required_argument, 0, 'g' },
      { "activity-log", required_argument, 0, 'a' },
      { "device",  required_argument, 0, 'd'},
      { "events",  required_argument, 0, 'e'},
      { "properties",  required_argument, 0, 'p'},
      { "trim-from",  required_argument, 0, 'b'},
      { "trim-to",  required_argument, 0, 's'},
      { "trim-out",  required_argument, 0, 't'},
      { "class",  required_argument, 0, 'c'},
      { 0, 0, 0, 0 }
    };

    int option_index = 0;
    int c = getopt_long(argc, argv, "", long_options, &option_index);

    // end of options
    if (c == -1)
      break;

    switch (c) {
    // evdev-log
    case 'v':
      SafeOpen(&config.log[replay::ReplayDeviceConfig::kLogEvdev],
               optarg, "w");
      break;
    // gestures-log
    case 'g':
      SafeOpen(&config.log[replay::ReplayDeviceConfig::kLogGestures],
               optarg, "w");
      break;
    // activity-log
    case 'a':
      SafeOpen(&config.log[replay::ReplayDeviceConfig::kLogActivity],
               optarg, "w");
      break;
    // device
    case 'd':
      SafeOpen(&config.device, optarg, "r");
      break;
    // events
    case 'e':
      SafeOpen(&events, optarg, "r");
      break;
    // properties
    case 'p':
      props.open(optarg);
      if (!props.good()) {
        std::cerr << "Cannot open stream to '" << optarg << "'" << std::endl;
        exit(-1);
      }
      config.properties = std::string((std::istreambuf_iterator<char>(props)),
                                      std::istreambuf_iterator<char>());;
      break;
    // trim-from
    case 'b':
      trim_enabled = true;
      trim_from = atof(optarg);
      break;
     // trim-to
    case 's':
      trim_enabled = true;
      trim_to = atof(optarg);
      break;
    // trim-out
    case 't':
      trim_enabled = true;
      SafeOpen(&trim_out, optarg, "w");
      break;
    // class
    case 'c':
      if (strcmp(optarg, "touchpad") == 0)
        config.device_class = GESTURES_DEVCLASS_TOUCHPAD;
      else if (strcmp(optarg, "mouse") == 0)
        config.device_class = GESTURES_DEVCLASS_MOUSE;
      else if (strcmp(optarg, "multitouch_mouse") == 0)
        config.device_class = GESTURES_DEVCLASS_MULTITOUCH_MOUSE;
      else {
        std::cerr << "--class should be touchpad, mouse or multitouch_mouse"
                  << std::endl;
        return -1;
      }
      break;
    case '?':
      return -1;
    }
  }

  if (!events.Good()) {
    std::cerr << "events file is required" << std::endl;
    return -1;
  }

  // execute: replay or trim
  replay::ReplayDevice device(&config);
  if (trim_enabled) {
    if (!trim_out.Good()) {
      std::cerr << "--trim-out is required for trimming" << std::endl;
      return -1;
    }
    replay::Trimmer trimmer(&device);
    trimmer.Trim(&events, &trim_out, trim_from, trim_to);
  } else {
    device.ReplayEvents(&events);
  }

  return 0;
}
