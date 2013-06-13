# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

include common.mk

all: CXX_BINARY(replay)
clean: CLEAN(replay)
tests: CXX_BINARY(tests)
install:
	install -D -m 0755 $(OUT)/replay $(DESTDIR)/replay

setup-in-place:
clean-in-place: CLEAN(replay)
in-place: CXX_BINARY(replay)

in-place: CPPFLAGS += -I$(SRC)/../../gestures/in-place
in-place: CPPFLAGS += -I$(SRC)/../../libevdev/in-place
in-place: LDFLAGS += -L$(SRC)/../../gestures/in-place
in-place: LDFLAGS += -L$(SRC)/../../libevdev/in-place