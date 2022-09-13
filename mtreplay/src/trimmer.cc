// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "trimmer.h"

#include "evemu_device.h"
#include "libevdev_mock.h"
#include "util.h"

namespace replay {

Trimmer::Trimmer(ReplayDevice* replay)
    : replay_(replay) {
}

void Trimmer::WriteEvent(Stream* out, const struct timeval& time, __u16 type,
                         __u16 code, __s32 value) {
  input_event event = { time, type, code, value };
  EvdevWriteEventToFile(out->GetFP(), &event);
}

void Trimmer::WriteCurrentState(Stream* out, struct input_event* syn) {
  EventStatePtr evstate = replay_->current_state();
  Evdev* device = replay_->evdev_device();

  // write slots
  for (int i = evstate->slot_min; i < evstate->slot_min + evstate->slot_count;
       i++) {
    MtSlotPtr slot = &evstate->slots[i - evstate->slot_min];
    if (slot->tracking_id == -1) {
      WriteEvent(out, syn->time, EV_ABS, ABS_MT_SLOT, i);
      WriteEvent(out, syn->time, EV_ABS, ABS_MT_TRACKING_ID, -1);
      continue;
    }
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_SLOT, i);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_TOUCH_MAJOR, slot->touch_major);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_TOUCH_MINOR, slot->touch_minor);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_WIDTH_MAJOR, slot->width_major);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_WIDTH_MINOR, slot->width_minor);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_ORIENTATION, slot->orientation);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_POSITION_X, slot->position_x);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_POSITION_Y, slot->position_y);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_TOOL_TYPE, slot->tool_type);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_BLOB_ID, slot->blob_id);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_TRACKING_ID, slot->tracking_id);
    if (EvdevIsSinglePressureDevice(device))
      WriteEvent(out, syn->time, EV_ABS, ABS_PRESSURE, slot->pressure);
    else
      WriteEvent(out, syn->time, EV_ABS, ABS_MT_PRESSURE, slot->pressure);
    WriteEvent(out, syn->time, EV_ABS, ABS_MT_DISTANCE, slot->distance);
  }

  // activate the currently active slot
  for (int i = evstate->slot_min; i < evstate->slot_min + evstate->slot_count;
       i++) {
    MtSlotPtr slot = &evstate->slots[i - evstate->slot_min];
    if (slot == evstate->slot_current) {
      WriteEvent(out, syn->time, EV_ABS, ABS_MT_SLOT, i);
      break;
    }
  }

  // write key state
  for (int i = 0; i < KEY_CNT; ++i) {
    if (TestBit(i, device->key_state_bitmask)) {
      WriteEvent(out, syn->time, EV_KEY, i, 1);
    }
  }
  EvdevWriteEventToFile(out->GetFP(), syn);
}

bool Trimmer::Trim(Stream* in, Stream* out, double from,
                   double to) {
  EvdevInfoPtr info = &replay_->evdev_device()->info;
  // Try to read device info from log file. If it exists it will
  // override any device info read from the device file.
  int ret = EvdevReadInfoFromFile(in->GetFP(), info);
  if (!replay_->has_device_data() && ret <= 0) {
    std::cerr << "device file or device header in log is required" << std::endl;
    exit(-1);
  }

  // Write device data to output log file
  if (EvdevWriteInfoToFile(out->GetFP(), info) <= 0) {
    std::cerr << "EvdevWriteInfoToFile failed" << std::endl;
    exit(-1);
  }
  input_event event;
  bool trimming = true;

  while (EvdevReadEventFromFile(in->GetFP(), &event) > 0) {
    // check timestamps only on SYN events.
    if (event.type == EV_SYN) {
      // check if we have reached the from timestamp.
      double timestamp = StimeFromTimeval(&event.time);
      if (timestamp >= from && timestamp < to) {
        if (trimming == true) {
          // turn off trimming and start the output
          // stream by writing the current event state.
          trimming = false;
          replay_->ReplayEvent(event);
          WriteCurrentState(out, &event);
          continue;
        }
      } else if (timestamp >= to) {
        // we have reached the 'to' timestamp
        EvdevWriteEventToFile(out->GetFP(), &event);
        break;
      }
    }
    if (trimming) {
      // if we are trimming these events just replay them.
      replay_->ReplayEvent(event);
    } else {
      // write event to output stream
      EvdevWriteEventToFile(out->GetFP(), &event);
    }
  }

  // 0.5 seconds after replay: Add cleanup state
  EventStatePtr evstate = replay_->current_state();
  event.time.tv_usec += 500;
  for (int i = 0; i < evstate->slot_count; i++) {
    WriteEvent(out, event.time, EV_ABS, ABS_MT_SLOT, i);
    WriteEvent(out, event.time, EV_ABS, ABS_MT_TRACKING_ID, -1);
  }

  return true;
}

}  // namespace replay
