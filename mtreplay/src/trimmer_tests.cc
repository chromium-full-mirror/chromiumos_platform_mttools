// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <limits>

#include <gtest/gtest.h>

#include "prop_provider.h"
#include "replay_device.h"
#include "trimmer.h"

// Event log for testing trimming.
// The log contains the following movements.
// 1 finger up/down movement.
// 2 finger up/down movement.
// 3 finger up/down movement.
// 2 finger up/down movement.
// 1 finger up/down movement.
// The fingers are not all removed from the touchpad between the movements.
// After these movements the same set is repeated with a thumb keeping the
// phyiscal button pressed.
extern const char* trimmer_tests_events;

// A copy of lumpy's device properties file.
extern const char* trimmer_tests_device;

namespace replay {

// The main goal of these tests is to see if trimming will trim at the right
// position in the events log and to see if the device state is completely
// restored at the beginning of the trimmed log no matter what the state is.
class TrimmerTests : public ::testing::Test {
 protected:
  // Perform a trim using the Trimmer class and return the result as a
  // string.
  std::string Trim(const char* in, double from, double to) {
    ReplayDeviceConfig config;
    config.device.OpenReadBuffer(trimmer_tests_device);
    ReplayDevice device(&config);
    Trimmer trimmer(&device);

    Stream events;
    events.OpenReadBuffer(in);

    // buffer for output of trimming.
    // At least as big as the input, but to be save give some extra
    // space in case the output is formated a little different.
    size_t buffer_size = strlen(in) * 1.2;
    Stream out;
    out.OpenWriteBuffer(buffer_size);

    trimmer.Trim(&events, &out, from, to);

    return std::string(out.GetBuffer());
  }

  // Create new instances for all replay devices
  void SetUp() {
    replay_config_trimmed_ = new ReplayDeviceConfig();
    replay_config_trimmed_->device.OpenReadBuffer(trimmer_tests_device);
    replay_trimmed_ = new ReplayDevice(replay_config_trimmed_);

    replay_config_original_ = new ReplayDeviceConfig();
    replay_config_original_->device.OpenReadBuffer(trimmer_tests_device);
    replay_original_ = new ReplayDevice(replay_config_original_);
  }

  // clean up instances
  void TearDown() {
    delete replay_trimmed_;
    delete replay_config_trimmed_;
    delete replay_original_;
    delete replay_config_original_;
  }

  // replay until the next SYN event is received
  bool NextSyn(ReplayDevice* device, Stream* events) {
    input_event event;

    while (EvdevReadEventFromFile(events->GetFP(), &event)) {
      device->ReplayEvent(event);
      if (event.type == EV_SYN) {
        return true;
      }
    }
    return false;
  }

  // replay until the SYN event with the requested timestamp is found.
  bool FindMatchingSyn(ReplayDevice* device, Stream* events,
                       double timestamp) {
    while (timestamp > device->GetCurrentTime()) {
      if (!NextSyn(device, events)) {
        ADD_FAILURE() << "End of file reached while searching for matching syn";
        return false;
      }
      double delta = timestamp - device->GetCurrentTime();
      delta = delta > 0.0 ? delta : - delta;
      if (delta < 1.0e-10) {
        return true;
      }
    }
    ADD_FAILURE() << "No syn with matching timestamp found";
    return false;
  }

  // Compare the two device states and return test failures if there
  // are mismatches.
  void ExpectEqualState(ReplayDevice* device_trimmed,
                        ReplayDevice* device_original) {
    EventStatePtr state_trimmed = device_trimmed->current_state();
    EventStatePtr state_original = device_original->current_state();

    ASSERT_DOUBLE_EQ(device_original->GetCurrentTime(),
                     device_trimmed->GetCurrentTime());
    EXPECT_EQ(state_trimmed->slot_min, state_original->slot_min);
    EXPECT_EQ(state_trimmed->slot_count, state_original->slot_count);

    // check slots
    for (int i = 0; i < state_trimmed->slot_count; i++) {
      MtSlotPtr slot_trimmed = &state_trimmed->slots[i];
      MtSlotPtr slot_original = &state_original->slots[i];

      // only check if one of the devices treats this slot as tracked.
      if (slot_original->tracking_id >= 0 || slot_trimmed->tracking_id >= 0) {
        EXPECT_EQ(slot_original->tracking_id, slot_trimmed->tracking_id);
        if (slot_original->tracking_id >= 0 && slot_trimmed->tracking_id >= 0) {
          EXPECT_EQ(slot_original->touch_major, slot_trimmed->touch_major);
          EXPECT_EQ(slot_original->touch_minor, slot_trimmed->touch_minor);
          EXPECT_EQ(slot_original->width_major, slot_trimmed->width_major);
          EXPECT_EQ(slot_original->width_minor, slot_trimmed->width_minor);
          EXPECT_EQ(slot_original->orientation, slot_trimmed->orientation);
          EXPECT_EQ(slot_original->position_x,  slot_trimmed->position_x );
          EXPECT_EQ(slot_original->position_y,  slot_trimmed->position_y );
          EXPECT_EQ(slot_original->tool_type,   slot_trimmed->tool_type  );
          EXPECT_EQ(slot_original->blob_id,     slot_trimmed->blob_id    );
          EXPECT_EQ(slot_original->pressure,    slot_trimmed->pressure   );
          EXPECT_EQ(slot_original->distance,    slot_trimmed->distance   );
        }
      }
    }

    // check keys
    for (size_t i = 0; i < NLONGS(KEY_CNT); ++i) {
      EXPECT_EQ(device_trimmed->evdev_device()->key_state_bitmask[i],
                device_original->evdev_device()->key_state_bitmask[i]);
    }
  }
  // Checks if the replay left the device clean
  void ExpectClean() {
    EventStatePtr state_trimmed = replay_trimmed_->current_state();

    // check if all fingers are removed
    for (int i = 0; i < state_trimmed->slot_count; i++) {
      MtSlotPtr slot_trimmed = &state_trimmed->slots[i];
      EXPECT_EQ(slot_trimmed->tracking_id, -1);
    }
  }
  // Replay both devices and check the event state at each SYN event.
  void ExpectEqualReplay() {
    ExpectEqualState(replay_trimmed_, replay_original_);

    while (NextSyn(replay_trimmed_, &trimmed_)) {
      if (!NextSyn(replay_original_, &original_)) {
        ADD_FAILURE() << "original file ends before trimmed file";
        return;
      }
      ExpectEqualState(replay_trimmed_, replay_original_);
    }
  }

  // Execute trim and store trim result inside a stream
  void TrimEvents(double trimFrom, double trimTo) {
    original_.OpenReadBuffer(trimmer_tests_events);
    std::string result = Trim(trimmer_tests_events, trimFrom, trimTo);
    trimmed_.OpenReadBuffer(result.c_str());
  }

  void StripHeader(Stream* stream) {
    // strip the header information
    EvdevInfo info;
    EvdevReadInfoFromFile(stream->GetFP(), &info);
  }

  // Test if both devices replay cover the same timestamps
  // and if the resulting states are the same.
  void ExpectNoTrimming() {
    StripHeader(&trimmed_);
    // select first SYN for both
    EXPECT_TRUE(NextSyn(replay_trimmed_, &trimmed_));
    EXPECT_TRUE(NextSyn(replay_original_, &original_));

    ExpectEqualReplay();

    // expect both streams to have no events left
    EXPECT_LE(fscanf(trimmed_.GetFP(), "E:"), 0);
    EXPECT_LE(fscanf(original_.GetFP(), "E:"), 0);
  }

  // Test if both devices replay the same states.
  // But allow the trimmed device to cover only a part of the
  // original log.
  void ExpectTrimmedReplayIsEqual() {
    StripHeader(&trimmed_);
    // select first SYN from trimmed replay
    EXPECT_TRUE(NextSyn(replay_trimmed_, &trimmed_));
    // find matching SYN in original replay
    EXPECT_TRUE(FindMatchingSyn(replay_original_, &original_,
                                replay_trimmed_->GetCurrentTime()));

    ExpectEqualReplay();

    // expect both streams to be consumed completely
    EXPECT_LE(fscanf(trimmed_.GetFP(), "E:"), 0);
    EXPECT_LE(fscanf(original_.GetFP(), "E:"), 0);
  }

 protected:
  ReplayDeviceConfig* replay_config_trimmed_;
  ReplayDeviceConfig* replay_config_original_;
  ReplayDevice* replay_trimmed_;
  ReplayDevice* replay_original_;

  Stream original_;
  Stream trimmed_;
};

TEST_F(TrimmerTests, TestNoTrimming) {
  double inf = std::numeric_limits<double>::infinity();
  TrimEvents(-inf, inf);
  ExpectNoTrimming();
  ExpectClean();
}

TEST_F(TrimmerTests, TestFirstLastSynTrimming) {
  // first and last SYN timestamp
  TrimEvents(37716.042789, 38257.473632);
  ExpectNoTrimming();
  ExpectClean();
}

TEST_F(TrimmerTests, TestTrimWhileFingersTouching) {
  // start: in middle of 2 finger up/down movement
  // end: after 3 finger up/down movement
  TrimEvents(38242.311957, 38244.058656);
  ExpectTrimmedReplayIsEqual();
  ExpectClean();
}

TEST_F(TrimmerTests, TestTrimWhileButtonPressed) {
  // start: in middle of 2 finger up/down movement. With button pressed.
  // end: after 3 finger up/down movement. With button still pressed.
  TrimEvents(38242.209067, 38253.411325);
  ExpectTrimmedReplayIsEqual();
  ExpectClean();
}

}  // namespace replay
