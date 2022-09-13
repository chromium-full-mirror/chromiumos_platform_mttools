# Copyright 2012 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

include common.mk

# global flags
CPPFLAGS += -I$(SRC)/include -fvisibility=default $(PC_CFLAGS)
LDLIBS += -ljsoncpp -levdev-cros -lutouch-evemu -lgestures \
	 $(PC_LIBS)

common_OBJS = src/evdev_gestures.o \
	src/evemu_device.o \
	src/gestures_mock.o \
	src/libevdev_mock.o \
	src/prop_provider.o \
	src/replay_device.o \
	src/stream.o \
	src/trimmer.o

# replay tool
replay_OBJS = src/main.o \
	$(common_OBJS)

CXX_BINARY(replay): $(replay_OBJS)
CXX_BINARY(replay): LDLIBS += $(replay_LIBS)
CXX_BINARY(replay): CPPFLAGS += $(replay_FLAGS)
clean: CLEAN(replay)

# unit tests
tests_LIBS = -lgtest
tests_OBJS = src/test_main.o \
	src/libevdev_mock_tests.o \
	src/prop_provider_tests.o \
	src/trimmer_tests.o \
	src/trimmer_tests_data.o \
	$(common_OBJS)

CXX_BINARY(tests): $(tests_OBJS)
CXX_BINARY(tests): LDLIBS += $(tests_LIBS)
CXX_BINARY(tests): CPPFLAGS += $(tests_FLAGS)
clean: CLEAN(tests)
tests: TEST(CXX_BINARY(tests))
