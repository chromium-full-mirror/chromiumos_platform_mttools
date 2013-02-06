// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef GESTURES_MOCK_H_
#define GESTURES_MOCK_H_

#include <gestures/gestures.h>

namespace replay {

// Creates a new gesture interpreter with callbacks that are handled
// by ReplayDevice instead of a real device
GestureInterpreter* NewGestureInterpreterMock(int id);

// Free all associated resources
void DeleteGestureInterpreterMock(GestureInterpreter* interpreter);

}  // namespace replay

#endif  // GESTURES_MOCK_H_
