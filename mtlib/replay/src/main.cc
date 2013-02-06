// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <iostream>
#include <limits>

#include <getopt.h>

#include <replay_device.h>
#include <trimmer.h>

// this function will open a stream.
// In case the stream cannot be opened an error message will be printed
// and the program will be forced to exit.
template<typename StreamType>
void SafeOpen(StreamType& stream, const std::string& filename) {
  stream.Open(filename);
  if (!stream.Good()) {
    std::cerr << "Cannot open stream to '" << filename << "'" << std::endl;
    exit(-1);
  }
}

int main(int argc, char** argv) {
  replay::ReplayDeviceConfig config;
  replay::GenericStream<std::istream> events;
  replay::GenericStream<std::ostream> trim_out;

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
      SafeOpen(config.log[replay::ReplayDeviceConfig::kLogEvdev], optarg);
      break;
    // gestures-log
    case 'g':
      SafeOpen(config.log[replay::ReplayDeviceConfig::kLogGestures], optarg);
      break;
    // activity-log
    case 'a':
      SafeOpen(config.log[replay::ReplayDeviceConfig::kLogActivity], optarg);
      break;
    // device
    case 'd':
      SafeOpen(config.device, optarg);
      break;
    // events
    case 'e':
      SafeOpen(events, optarg);
      break;
    // properties
    case 'p':
      SafeOpen(config.properties, optarg);
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
      SafeOpen(trim_out, optarg);
      break;
    case '?':
      return -1;
    }
  }

  // check if device/events file are present
  if (!config.device.Good()) {
    std::cerr << "device file is required" << std::endl;
    return -1;
  }

  if (!events.Good()) {
    std::cerr << "events file is required" << std::endl;
    return -1;
  }

  // execute: replay or trim
  replay::ReplayDevice device(&config);
  if (trim_enabled) {
    if(!trim_out.Good()) {
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
