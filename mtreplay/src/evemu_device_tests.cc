// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "evemu_device.h"

#include <sstream>

#include <gtest/gtest.h>

namespace evemu {
class EvemuDeviceTests : public ::testing::Test {
};

std::string lumpy_dat = "N: cyapa\n"
                        "I: 0018 0000 0000 0001\n"
                        "P: 05 00 00 00 00 00 00 00\n"
                        "B: 00 0b 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 01 00 00 00 00 00\n"
                        "B: 01 20 e5 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 01 00 00 00 00 00 00 00 00\n"
                        "B: 02 00 00 00 00 00 00 00 00\n"
                        "B: 03 03 00 00 01 00 80 60 06\n"
                        "B: 04 00 00 00 00 00 00 00 00\n"
                        "B: 05 00 00 00 00 00 00 00 00\n"
                        "B: 11 00 00 00 00 00 00 00 00\n"
                        "B: 12 00 00 00 00 00 00 00 00\n"
                        "B: 15 00 00 00 00 00 00 00 00\n"
                        "B: 15 00 00 00 00 00 00 00 00\n"
                        "A: 00 0 1280 0 0 12\n"
                        "A: 01 0 680 0 0 10\n"
                        "A: 18 0 255 0 0 0\n"
                        "A: 2f 0 14 0 0\n"
                        "A: 35 0 1280 0 0 12\n"
                        "A: 36 0 680 0 0 10\n"
                        "A: 39 0 65535 0 0 0\n"
                        "A: 3a 0 255 0 0 0";

TEST(EvemuDeviceTests, ReadDeviceFileTest) {
  EvemuDevice device;
  std::stringstream stream(lumpy_dat);

  ASSERT_TRUE(device.ReadDeviceFile(&stream));

  // test if arbitrary samples from lumpy_dat are read correctly
  EXPECT_EQ(device.GetName(), "cyapa");
  EXPECT_EQ(device.GetPropMask()[0], 0x05);
  EXPECT_EQ(device.GetMask(0x00)[0], 0x0b);
  EXPECT_EQ(device.GetMask(0x03)[0], 0x03);
  EXPECT_EQ(device.GetAbsinfo(0x00).maximum, 1280);
}

TEST(EvemuDeviceTests, ReadEventDecodingTest) {
  EvemuDevice device;
  std::stringstream stream(
      "E: 1335424966.811225 0003 003a 44\n"
  );

  struct input_event event;
  ASSERT_TRUE(device.ReadEvent(&stream, &event));
  EXPECT_EQ(event.time.tv_sec, 1335424966);
  EXPECT_EQ(event.time.tv_usec, 811225);
  EXPECT_EQ(event.type, 0x0003);
  EXPECT_EQ(event.code, 0x003a);
  EXPECT_EQ(event.value, 44);
}

TEST(EvemuDeviceTests, ReadEventNewlineTest) {
  EvemuDevice device;
  std::stringstream stream1(
      "E: 0.0 0000 0000 00\n"
      "E: 0.0 0000 0000 00"
  );
  std::stringstream stream2(
      "E: 0.0 0000 0000 00\n"
      "E: 0.0 0000 0000 00\n"
  );

  struct input_event event;
  ASSERT_TRUE(device.ReadEvent(&stream1, &event));
  ASSERT_TRUE(device.ReadEvent(&stream1, &event));
  ASSERT_FALSE(device.ReadEvent(&stream1, &event));

  ASSERT_TRUE(device.ReadEvent(&stream2, &event));
  ASSERT_TRUE(device.ReadEvent(&stream2, &event));
  ASSERT_FALSE(device.ReadEvent(&stream2, &event));
}
}  // namespace evemu
