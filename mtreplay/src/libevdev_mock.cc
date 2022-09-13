// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <cstdarg>

#include "libevdev_mock.h"
#include "replay_device.h"
#include "util.h"

using replay::EvemuDevice;
using replay::ReplayDevice;
using replay::ReplayDeviceConfig;
using replay::TestBit;

extern "C" {

// Implements the log method used by libevdev. Passes all logs to ReplayDevice.
static void EvdevLog(void* udata, int level, const char* format, ...) {
  ReplayDevice* device = reinterpret_cast<ReplayDevice*>(udata);
  va_list args;
  va_start(args, format);
  device->VLog(ReplayDeviceConfig::kLogEvdev, format, args);
  va_end(args);
}

// Wrapper callback to pass the syn callback to ReplayDevice
static void EvdevSynCallback(void* udata, EventStatePtr evstate,
                             struct timeval* timeval) {
  ReplayDevice* device = reinterpret_cast<ReplayDevice*>(udata);
  device->SynCallback(evstate, timeval);
}

// Do nothing, there is no kernel device.
int EvdevOpen(EvdevPtr evdev, const char* device) {
  return Success;
}

// Do nothing, there is no kernel device.
int EvdevClose(EvdevPtr evdev) {
  return Success;
}

// Do nothing, there is no kernel device.
int EvdevRead(EvdevPtr evdev) {
  return Success;
}

// This method usually queries the kernel for device information using ioctls.
// We fake this by copying data from the evemu device.
int EvdevProbe(EvdevPtr device) {
  // find replay device instance by file descriptor
  EvemuDevice* evemu = ReplayDevice::GetDevice(device->fd)->evdev_file();

  // copy device information
  strcpy(device->info.name, evemu->GetName().c_str());
  memcpy(device->info.prop_bitmask, evemu->GetPropMask(),
         sizeof(device->info.prop_bitmask));

  memcpy(device->info.bitmask, evemu->GetMask(0),
         sizeof(device->info.bitmask));
  memcpy(device->info.key_bitmask, evemu->GetMask(EV_KEY),
         sizeof(device->info.key_bitmask));
  memcpy(device->info.led_bitmask, evemu->GetMask(EV_LED),
         sizeof(device->info.led_bitmask));
  memcpy(device->info.rel_bitmask, evemu->GetMask(EV_REL),
         sizeof(device->info.rel_bitmask));
  memcpy(device->info.abs_bitmask, evemu->GetMask(EV_ABS),
         sizeof(device->info.abs_bitmask));

  for (size_t i = 0; i < ABS_CNT; ++i) {
    memcpy(&device->info.absinfo[i], &evemu->GetAbsinfo(i),
           sizeof(device->info.absinfo[i]));
  }
  const EvdevInfo& info = device->info;
  if ((info.absinfo[ABS_X].maximum > 0 &&
       info.absinfo[ABS_X].resolution <= 0) ||
      (info.absinfo[ABS_Y].maximum > 0 &&
       info.absinfo[ABS_Y].resolution <= 0) ||
      (info.absinfo[ABS_MT_POSITION_X].maximum > 0 &&
       info.absinfo[ABS_MT_POSITION_X].resolution <= 0) ||
      (info.absinfo[ABS_MT_POSITION_Y].maximum > 0 &&
       info.absinfo[ABS_MT_POSITION_Y].resolution <= 0)) {
    std::cerr << "Missing resolution field in device file" << std::endl;
    exit(1);
  }

  return Success;
}

// Only used during resync. Not supported by this mock.
int EvdevProbeAbsinfo(EvdevPtr device, size_t key) {
  return Success;
}

int EvdevIsSinglePressureDevice(EvdevPtr device) {
    EvdevInfoPtr info = &device->info;

    return (!TestBit(ABS_MT_PRESSURE, info->abs_bitmask) &&
            TestBit(ABS_PRESSURE, info->abs_bitmask));
}

// This method usually queries the kernel for the current MTSlot state.
// We fake this by returning 'no fingers' as the current state.
int EvdevProbeMTSlot(EvdevPtr device, MTSlotInfoPtr req) {
  for (int i = 0; i < ABS_CNT; ++i) {
    if (req->code == ABS_MT_TRACKING_ID)
      req->values[i] = -1;
    else
      req->values[i] = 0;
  }
  return Success;
}

// Only used during resync. Not supported by this mock.
int EvdevProbeKeyState(EvdevPtr device) {
  return Success;
}

// This mock device always allows monotonic timers.
int EvdevEnableMonotonic(EvdevPtr device) {
  return Success;
}

}  // extern "C"

namespace replay {

Evdev* NewEvdevMock(int id) {
  // create new evdev instance. Store the ReplayDevice ID as file descriptor
  Evdev* evdev = new Evdev();
  evdev->fd = id;

  // setup event state
  EventStatePtr evstate = new EventStateRec();
  evstate->debug_buf_tail = 0;
  evdev->evstate = evstate;

  // setup method callbacks
  evdev->log = &EvdevLog;
  evdev->log_udata = ReplayDevice::GetDevice(evdev->fd);
  evdev->syn_report = &EvdevSynCallback;
  evdev->syn_report_udata = ReplayDevice::GetDevice(evdev->fd);

  // allow libevdev to init.
  if (Event_Init(evdev) != Success) {
    DeleteEvdevMock(evdev);
    return NULL;
  }

  // Per default we start with the MT slot 0
  MT_Slot_Set(evdev, 0);

  return evdev;
}

void DeleteEvdevMock(Evdev* evdev) {
  delete evdev->evstate;
  evdev->evstate = NULL;

  delete evdev;
  evdev = NULL;
}

}  // namespace replay
