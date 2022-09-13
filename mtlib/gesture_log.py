# Copyright 2013 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import decimal
import json
import math

class GestureLog(object):
  """ Represents the gestures in an activity log.

  The gesture log is a representation of an activity log as it is generated
  by the replay tool or 'tpcontrol log'.
  It converts all gestures into a list of events using the classes below.
  To allow easier processing all events that belong together are merged into
  gestures. For example all scroll events from one scroll motion on the touchpad
  are merged to create a single scroll gesture.
  - self.events will contain the list of events
  - self.gestures the list of gestures.
  """
  def __init__(self, log):
    decimal.setcontext(decimal.Context(prec=8))
    self.raw = json.loads(log, parse_float=decimal.Decimal)
    raw_events = filter(lambda e: e['type'] == 'gesture', self.raw['entries'])
    self.events = self._ParseRawEvents(raw_events)
    self.gestures = self._MergeGestures(self.events)

    self.properties = self.raw['properties']
    self.hwstates = filter(lambda e: e['type'] == 'hardwareState',
                           self.raw['entries'])
    self.hwproperties = self.raw['hardwareProperties']

  def _ParseRawEvents(self, gesture_list):
    events = []

    for gesture in gesture_list:
      start_time = gesture['startTime']
      end_time = gesture['endTime']

      if gesture['gestureType'] == 'move':
        events.append(MotionGesture(gesture['dx'], gesture['dy'], start_time,
                                    end_time))

      elif gesture['gestureType'] == 'buttonsChange':
        if gesture['down'] != 0:
          button = gesture['down']
          events.append(ButtonDownGesture(button, start_time, end_time))
        if gesture['up'] != 0:
          button = gesture['up']
          events.append(ButtonUpGesture(button, start_time, end_time))

      elif gesture['gestureType'] == 'scroll':
        events.append(ScrollGesture(gesture['dx'], gesture['dy'], start_time,
                                    end_time))

      elif gesture['gestureType'] == 'pinch':
        events.append(PinchGesture(gesture['dz'], start_time, end_time))

      elif gesture['gestureType'] == 'swipe':
        events.append(SwipeGesture(gesture['dx'], gesture['dy'], start_time,
                                   end_time))

      elif gesture['gestureType'] == 'swipeLift':
        events.append(SwipeLiftGesture(start_time, end_time))

      elif gesture['gestureType'] == 'fourFingerSwipe':
        events.append(FourFingerSwipeGesture(gesture['dx'], gesture['dy'],
                                             start_time, end_time))

      elif gesture['gestureType'] == 'fourFingerSwipeLift':
        events.append(FourFingerSwipeLiftGesture(start_time, end_time))

      elif gesture['gestureType'] == 'fling':
        if gesture['flingState'] == 1:
          events.append(FlingStopGesture(start_time, end_time))
        else:
          events.append(FlingGesture(gesture['vx'], gesture['vy'], start_time,
                                     end_time))
      elif gesture['gestureType'] == 'metrics':
        # ignore
        pass
      else:
        print('Unknown gesture:', repr(gesture))

    return events

  def _MergeGestures(self, event_list):
    gestures = []
    last_event_of_type = {}

    for event in event_list:
      # merge motion and scroll events into gestures
      if (event.type == 'Motion' or event.type == 'Scroll' or
          event.type == 'Swipe' or event.type == 'Pinch' or
          event.type == 'FourFingerSwipe'):
        if event.type not in last_event_of_type:
          last_event_of_type[event.type] = event
          gestures.append(event)
        else:
          if float(event.start - last_event_of_type[event.type].end) < 0.1:
            last_event_of_type[event.type].Append(event)
          else:
            last_event_of_type[event.type] = event
            gestures.append(event)
      else:
        if event.type == 'ButtonUp' or event.type == 'ButtonDown':
          last_event_of_type = {}
        gestures.append(event)
    return gestures


class AxisGesture(object):
  """ Generic gesture class to describe gestures with x/y or z axis. """

  def __init__(self, dx, dy, dz, start, end):
    """ Create a new instance describing a single axis event.

    To describe a list of events that form a gesture use the Append method.
    @param dx: movement in x coords
    @param dy: movement in y coords
    @param dz: movement in z coords
    @param start: start timestamp
    @param end: end timestamp
    """
    self.dx = math.fabs(dx)
    self.dy = math.fabs(dy)
    self.dz = math.fabs(dz)
    self.start = float(start)
    self.end = float(end)
    self.segments = []

    self.distance = math.sqrt(self.dx * self.dx + self.dy * self.dy +
                              self.dz * self.dz)
    self.segments.append(self.distance)

  def Append(self, motion):
    """ Append an motion event to build a gesture. """
    self.dx = self.dx + motion.dx
    self.dy = self.dy + motion.dy
    self.dz = self.dz + motion.dz
    self.distance = self.distance + motion.distance
    self.segments.append(motion.distance)
    self.end = motion.end

  def Distance(self):
    return self.distance

  def Speed(self):
    """ Average speed of motion in mm/s. """
    if self.end > self.start:
      return self.distance / (self.end - self.start)
    else:
      return float('+inf')

  def Roughness(self):
    """ Returns the roughness of this gesture.

    The roughness measures the variability in the movement events. A continuous
    stream of events with similar movement distances is considered to be smooth.
    Choppy movement with a high variation in movement distances on the other
    hand is considered as rough. i.e. a constant series of movement distances is
    considered perfectly smooth and will result in a roughness of 0.
    Whenever there are sudden changes, or very irregular movement distances
    the roughness will increase.
    """
    # Each event in the gesture resulted in a movement distance. These distances
    # are treated as a signal and high pass filtered. This results in a signal
    # containing only high frequency changes in the distance, i.e. the rough
    # parts.
    # The squared average of this signal is used as a measure for the roughness.

    # gaussian filter kernel with sigma=1:
    # The kernel is calculated using this formula (with s=sigma):
    # 1/sqrt(2*pi*s^2)*e^(-x^2/(2*s^2))
    # The array can be recalculated with modified sigma by entering the
    # following equation into http://www.wolframalpha.com/:
    # 1/sqrt(2*pi*s^2)*e^(-[-2, -1, 0, 1, 2]^2/(2*s^2))
    # (Replace s with the desired sigma value)
    gaussian = [0.053991, 0.241971, 0.398942, 0.241971, 0.053991]

    # normalize gaussian filter kernel
    gsum = sum(gaussian)
    gaussian = list(map(lambda g: g / gsum, gaussian))

    # add padding to the front/end of the distances
    segments = []
    segments.append(self.segments[0])
    segments.append(self.segments[0])
    segments.extend(self.segments)
    segments.append(self.segments[-1])
    segments.append(self.segments[-1])

    # low pass filter the distances
    segments_lp = []
    for i in range(2, len(segments) - 2):
      v = segments[i - 2] * gaussian[0]
      v = v + segments[i - 1] * gaussian[1]
      v = v + segments[i  ] * gaussian[2]
      v = v + segments[i + 1] * gaussian[3]
      v = v + segments[i + 2] * gaussian[4]
      segments_lp.append(v)

    # H_HP = 1 - H_LP
    segments_hp = []
    for i in range(0, len(self.segments)):
      segments_hp.append(self.segments[i] - segments_lp[i])
    # square signal and calculate squared average
    segments_hp_sq = map(lambda v:v * v, segments_hp)
    return math.sqrt(sum(segments_hp_sq) / len(segments_hp))

  def __str__(self):
    fstr = '{0} d={1:.4g} x={2:.4g} y={3:.4g} z={4:.4g} r={5:.4g} s={6:.4g}'
    return fstr.format(self.__class__.type, self.distance, self.dx,
                       self.dy, self.dz, self.Roughness(), self.Speed())

  def __repr__(self):
    return str(self)

class MotionGesture(AxisGesture):
  """ The motion gesture is only using the X and Y axis. """
  type = 'Motion'

  def __init__(self, dx, dy, start, end):
    AxisGesture.__init__(self, dx, dy, 0, start, end)

  def __str__(self):
    fstr = '{0} d={1:.4g} x={2:.4g} y={3:.4g} r={4:.4g} s={5:.4g}'
    return fstr.format(self.__class__.type, self.distance, self.dx,
                       self.dy, self.Roughness(), self.Speed())

class ScrollGesture(MotionGesture):
  """ The scroll gesture is functionally the same as the MotionGesture """
  type = 'Scroll'


class PinchGesture(AxisGesture):
  """ The pinch gesture is functionally the same as the MotionGesture.

  However only uses the dz variable to represent the zoom factor.
  """
  type = 'Pinch'

  def __init__(self, dz, start, end):
    AxisGesture.__init__(self, 0, 0, dz, start, end)

  def __str__(self):
    fstr = '{0} dz={1:.4g} r={2:.4g}'
    return fstr.format(self.__class__.type, self.dz, self.Roughness())

  def Append(self, motion):
    self.dx = self.dx + motion.dx
    self.dy = self.dy + motion.dy
    self.dz = self.dz * max(motion.dz, 1 / motion.dz)
    self.distance = self.dz
    self.segments.append(motion.distance)
    self.end = motion.end


class SwipeGesture(MotionGesture):
  """ The swipe gesture is functionally the same as the MotionGesture """
  type = 'Swipe'


class FourFingerSwipeGesture(MotionGesture):
  """ The FourFingerSwipe gesture is functionally the same as the
  MotionGesture """
  type = 'FourFingerSwipe'


class FlingGesture(MotionGesture):
  """ The scroll gesture is functionally the same as the MotionGesture """
  type = 'Fling'


class FlingStopGesture(object):
  """ The FlingStop gesture only contains the start and end timestamp. """
  type = 'FlingStop'

  def __init__(self, start, end):
    self.start = start
    self.end = end

  def __str__(self):
    return self.__class__.type

  def __repr__(self):
    return str(self)


class SwipeLiftGesture(object):
  """ The SwipeLift gesture only contains the start and end timestamp. """
  type = 'SwipeLift'

  def __init__(self, start, end):
    self.start = start
    self.end = end

  def __str__(self):
    return self.__class__.type

  def __repr__(self):
    return str(self)

class FourFingerSwipeLiftGesture(object):
  """ The FourFingerSwipeLift gesture only contains the start and
  end timestamp. """
  type = 'FourFingerSwipeLift'

  def __init__(self, start, end):
    self.start = start
    self.end = end

  def __str__(self):
    return self.__class__.type

  def __repr__(self):
    return str(self)


class AbstractButtonGesture(object):
  """ Abstract gesture for up and down button gestures.

  As both button down and up gestures are functionally identical it has
  been extracted to this class. The AbstractButtonGesture stores a button ID
  next to the start and end time of the gesture.
  """
  type = 'Undefined'

  def __init__(self, button, start, end):
    self.button = button
    self.start = start
    self.end = end

  def __str__(self):
    return self.__class__.type + '(' + str(self.button) + ')'

  def __repr__(self):
    return str(self)


class ButtonDownGesture(AbstractButtonGesture):
  """ Functionally the same as AbstractButtonGesture """
  type = 'ButtonDown'


class ButtonUpGesture(AbstractButtonGesture):
  """ Functionally the same as AbstractButtonGesture """
  type = 'ButtonUp'
