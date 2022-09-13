// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "libevdev_mock.h"

#include <gtest/gtest.h>

#include "util.h"

namespace replay {
class LibEvDevTests : public ::testing::Test {
};

TEST(LibEvdevTests, SinglePressureDeviceTest) {
    Evdev* evdev = new Evdev();
    EvdevInfoPtr info = &evdev->info;

    /* true if there is only ABS_PRESSURE bit set */
    AssignBit(info->abs_bitmask, ABS_PRESSURE, true);
    EXPECT_TRUE(EvdevIsSinglePressureDevice(evdev));

    /* false if both bits set */
    AssignBit(info->abs_bitmask, ABS_MT_PRESSURE, true);
    EXPECT_FALSE(EvdevIsSinglePressureDevice(evdev));

    /* false if only ABS_MT_PRESSURE bit is set */
    AssignBit(info->abs_bitmask, ABS_PRESSURE, false);
    EXPECT_FALSE(EvdevIsSinglePressureDevice(evdev));
}
}  // namespace replay
