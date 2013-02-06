// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <evdev_gestures.h>

namespace replay {

EvdevGesture::EvdevGesture(EvdevPtr evdev,
                                  GestureInterpreter* interpreter) {
  evdev_ = evdev;
  interpreter_ = interpreter;
  fingers_ = new FingerState[Event_Get_Slot_Count(evdev)];
}

EvdevGesture::~EvdevGesture() {
  delete[] fingers_;
  fingers_ = NULL;
}

void EvdevGesture::InitHardwareProperties(struct HardwareProperties* hwprops) {
  hwprops->left = Event_Get_Left(evdev_);
  hwprops->top = Event_Get_Top(evdev_);
  hwprops->right = Event_Get_Right(evdev_);
  hwprops->bottom = Event_Get_Bottom(evdev_);
  hwprops->res_x = Event_Get_Res_X(evdev_);
  hwprops->res_y = Event_Get_Res_Y(evdev_);
  hwprops->screen_x_dpi = 133;
  hwprops->screen_y_dpi = 133;
  hwprops->orientation_minimum = Event_Get_Orientation_Minimum(evdev_);
  hwprops->orientation_maximum = Event_Get_Orientation_Maximum(evdev_);
  hwprops->max_finger_cnt = Event_Get_Slot_Count(evdev_);
  hwprops->max_touch_cnt = Event_Get_Touch_Count_Max(evdev_);
  hwprops->supports_t5r2 = Event_Get_T5R2(evdev_);
  hwprops->support_semi_mt = Event_Get_Semi_MT(evdev_);
  hwprops->is_button_pad = Event_Get_Button_Pad(evdev_);
}

void EvdevGesture::PushEventState(EventStatePtr evstate, struct timeval* tv) {
  struct HardwareState hwstate;
  memset(&hwstate, 0, sizeof(hwstate));
  // zero initialize all FingerStates to clear out previous state.
  memset(fingers_, 0, Event_Get_Slot_Count(evdev_) * sizeof(fingers_[0]));

  int current = 0;
  for (int i = 0; i < evstate->slot_count; i++) {
    MtSlotPtr slot = &evstate->slots[i];
    if (slot->tracking_id == -1)
      continue;
    fingers_[current].touch_major = static_cast<float>(slot->touch_major);
    fingers_[current].touch_minor = static_cast<float>(slot->touch_minor);
    fingers_[current].width_major = static_cast<float>(slot->width_major);
    fingers_[current].width_minor = static_cast<float>(slot->width_minor);
    fingers_[current].pressure    = static_cast<float>(slot->pressure);
    fingers_[current].orientation = static_cast<float>(slot->orientation);
    fingers_[current].position_x  = static_cast<float>(slot->position_x);
    fingers_[current].position_y  = static_cast<float>(slot->position_y);
    fingers_[current].tracking_id = slot->tracking_id;
    current++;
  }
  hwstate.timestamp = StimeFromTimeval(tv);
  if (Event_Get_Button_Left(evdev_))
    hwstate.buttons_down |= GESTURES_BUTTON_LEFT;
  if (Event_Get_Button_Middle(evdev_))
    hwstate.buttons_down |= GESTURES_BUTTON_MIDDLE;
  if (Event_Get_Button_Right(evdev_))
    hwstate.buttons_down |= GESTURES_BUTTON_RIGHT;
  hwstate.touch_cnt = Event_Get_Touch_Count(evdev_);
  hwstate.finger_cnt = current;
  hwstate.fingers = fingers_;
  hwstate.rel_x = evstate->rel_x;
  hwstate.rel_y = evstate->rel_y;
  hwstate.rel_wheel = evstate->rel_wheel;
  hwstate.rel_hwheel = evstate->rel_hwheel;
  GestureInterpreterPushHardwareState(interpreter_, &hwstate);
}

}  // namespace replay
