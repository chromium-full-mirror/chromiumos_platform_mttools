// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

function FingerViewController(inGraph, outGraph, inText, popup, outLockHead) {
  this.entries = [];
  this.fingerFlags = [];
  this.hardwareProperties = [];
  this.begin = -1;
  this.end = -1;
  this.gestureHead = null;

  this.gs_graph = outGraph;
  this.inGraph = inGraph;
  this.inText = inText;
  this.popup = popup;
  this.outLockHead = outLockHead[0];
  this.background = null;
  this.drawStyle = FingerViewController.prototype.style.PAINT;
};

FingerViewController.prototype = {
  style: {
    STANDARD: 'STANDARD',
    PAINT: 'Paint',
  },
  flag: {
    NONE: '',
    GOOD: 'good',
    NOISE: 'noise',
    FILTER: 'filter',
  },
  setEntriesLog: function(log, layer) {
    var tmp = log;
    for (var i = 0; i < layer; i++)
      tmp = tmp.nextLayer;
    this.entries = tmp.entries;
    this.log = log;

    // Update input default zoom
    this.hardwareProperties = tmp.hardwareProperties;
    var hwprops = tmp.hardwareProperties;
    var xRes = hwprops.xResolution;
    var yRes = hwprops.yResolution;
    var left = hwprops.left / xRes;
    var right = hwprops.right / xRes;
    var top = hwprops.top / yRes;
    var bottom = hwprops.bottom / yRes;

    var height = bottom - top;
    var width = right - left;
    var borderHeight = height / 20;
    var borderWidth = width / 20;
    this.inGraph.setDefaultZoom(left - borderWidth,
                                top - borderHeight,
                                right + borderWidth,
                                bottom + borderHeight);
  },
  resetZooms: function() {
    this.inGraph.resetCoordinatesAndZoom();
    this.gs_graph.resetCoordinatesAndZoom();
  },
  prevHardwareState: function(start) {
    for (var i = start - 1; i >= 0; i--)
      if (this.entries[i].type == 'hardwareState')
        return i;
    return -1;
  },
  nextHardwareState: function(start) {
    for (var i = start + 1; i < this.entries.length; i++)
      if (this.entries[i].type == 'hardwareState')
        return i;
    return -1;
  },
  setEndPoint: function(index) {
    this.end = index;
    this.redraw();
  },
  getHardwareStateLETimestamp: function(timestamp) {
    for (var i = this.entries.length - 1; i >= 0; i--) {
      if (this.entries[i].type == 'hardwareState' &&
          this.entries[i].timestamp <= timestamp) {
        return i;
      }
    }
    return -1;
  },
  getHardwareStateGETimestamp: function(timestamp) {
    for (var i = 0; i < this.entries.length; i++) {
      if (this.entries[i].type == 'hardwareState' &&
          this.entries[i].timestamp >= timestamp) {
        return i;
      }
    }
    return -1;
  },
  getLETimestamp: function(end) {
    end = this.prevHardwareState(end + 1);
    if (end == -1)
      return -1;
    else
      return this.entries[end].timestamp;
  },
  getGETimestamp: function(begin) {
    begin = this.nextHardwareState(begin - 1);
    if (begin == -1)
      return -1;
    else
      return this.entries[begin].timestamp;
  },
  getTimestamp: function(index) {
    if (this.entries[index].type == 'hardwareState' &&
        index >= 0 && index < this.entries.length) {
      return this.entries[index].timestamp;
    }
    return -1;
  },
  getPreviousHardwareStateTimestamp: function(index) {
    if (index < 0 && index >= this.entries.length)
      return -1;
    for (var i = index; i >= 0; i--) {
      if (this.entries[i].type == 'hardwareState')
        return this.entries[i].timestamp;
    }
    return -1;
  },
  lastEntryIndex: function() {
    return this.entries.length - 1;
  },
  isFirstFTS: function(index) {
    return index <= this.fts[0][1];
  },
  isLastFTS: function(index) {
    return index >= this.fts[this.fts.length - 1][0];
  },
  getNextNon0TouchCountHardwareState: function(index) {
    for (var i = index; i < this.entries.length; i++) {
      var e = this.entries[i];
      if (e.type == 'hardwareState' && e.touchCount > 0)
        return i;
    }
    return -1;
  },
  getNext0TouchCountHardwareState: function(index) {
    for (var i = index; i < this.entries.length; i++) {
      var e = this.entries[i];
      if (e.type == 'hardwareState' && e.touchCount == 0)
        return i;
    }
    return -1;
  },
  // Every FTS begins with a hwstate with non-0 touchCount, and ends at
  // any entry just preceding the next FTS. If the FTS is the last one, it
  // ends at whatever the very last entry is.
  initFTS: function() {
    this.fts = [];
    var beginEntry;
    var endEntry = -1;
    var hwstate;
    while (1) {
      beginEntry = this.getNextNon0TouchCountHardwareState(endEntry + 1);
      if (beginEntry == -1)
        break;
      hwstate = this.getNext0TouchCountHardwareState(beginEntry);
      if (hwstate == -1) {
        this.fts.push([beginEntry, this.lastEntryIndex()]);
        break;
      }
      hwstate = this.getNextNon0TouchCountHardwareState(hwstate);
      endEntry = (hwstate == -1) ? this.lastEntryIndex() : (hwstate - 1);
      this.fts.push([beginEntry, endEntry]);
    }
  },
  getNumFTS: function() {
    return this.fts.length;
  },
  getFTSIndex: function(value) {
    for (var i = 0; i < this.fts.length; i++) {
      if (value >= this.fts[i][0] && value <= this.fts[i][1])
        return i;
    }
    return 0;
  },
  // Get the first Finger Touch Section
  getFirstFTS: function() {
    return this.fts[0];
  },
  // Get the last Finger Touch Section
  getLastFTS: function() {
    return this.fts[this.fts.length - 1];
  },
  // Get previous Finger Touch Section
  getPrevFTS: function(indexes) {
    // If it is the whole range, or the indexes are in the first FTS,
    // return the first FTS.
    if (this.isFirstFTS(indexes[0]))
      return this.getFirstFTS();
    return this.fts[this.getFTSIndex(indexes[0]) -1];
  },
  // Get next Finger Touch Section
  getNextFTS: function(indexes) {
    // If it is the whole range, or the indexes are in the last FTS,
    // return the last FTS.
    if (this.isLastFTS(indexes[1]))
      return this.getLastFTS();
    return this.fts[this.getFTSIndex(indexes[1]) + 1];
  },
  // Get all entries
  getAllEntries: function() {
    return [0, this.lastEntryIndex()];
  },
  setRange: function(begin, end) {
    this.begin = begin;
    this.end = end;
    this.redraw();
  },
  setTouchFlags: function(flagDictionary) {
    this.fingerFlags = [];
    // Set annoted 'good' / 'noise' flags last as these are more correct than
    // automatic results and should be preserved.
    var importantFlags = [
      FingerViewController.prototype.flag.GOOD,
      FingerViewController.prototype.flag.NOISE
    ];
    for (var flag in flagDictionary) {
      var trackingIds = flagDictionary[flag];
      if (importantFlags.indexOf(flag) === -1) {
        for (var trackingId in trackingIds) {
          this.fingerFlags[trackingId] = flag;
        }
      }
    }
    for (var index in importantFlags) {
      var flag = importantFlags[index];
      var trackingIds = flagDictionary[flag];
      if (trackingIds) {
        for (var trackingId in trackingIds) {
          this.fingerFlags[trackingId] = flag;
        }
      }
    }
  },
  getTouchFlags: function() {
    var flagDictionary = {};
    for (var trackingId in this.fingerFlags) {
      var flag = this.fingerFlags[trackingId];
      if (!flagDictionary[flag]) {
        flagDictionary[flag] = [];
      }
      flagDictionary[flag].push(trackingId);
    }
    return flagDictionary;
  },
  flagTouchPoints: function(value) {
    var lastEntry = null;
    for (var i = this.nextHardwareState(this.begin - 1);
         i < this.end && i !== -1;
         i = this.nextHardwareState(i)) {
      var entry = this.entries[i];
      if (entry.fingers) {
        for (var j = 0; j < entry.fingers.length; j++) {
          var isNew = true;
          var trackingId = entry.fingers[j].trackingId;
          if (lastEntry !== null) {
            for (var k = 0; k < lastEntry.fingers.length; k++) {
              if (lastEntry.fingers[k].trackingId === trackingId) {
                isNew = false;
                break;
              }
            }
          }
          if (isNew) {
            if (value) {
              this.fingerFlags[trackingId] = value;
            } else {
              delete this.fingerFlags[trackingId];
            }
          }
        }
      }
      lastEntry = entry;
    }
  },
  jumpToNextNoise: function() {
    var self = this;
    var isNoise = function(hardwareState) {
      if (hardwareState.fingers) {
        for (var i = 0; i < hardwareState.fingers.length; i++) {
          var flag = self.fingerFlags[hardwareState.fingers[i].trackingId];
          if (flag === FingerViewController.prototype.flag.NOISE ||
              flag === FingerViewController.prototype.flag.FILTER) {
            return true;
          }
        }
      }
      return false;
    };
    var testForNoise = function(value, startIndex) {
      var currentIndex = startIndex;
      do {
        if (isNoise(self.entries[currentIndex]) === value) {
          return currentIndex;
        }
        currentIndex = self.nextHardwareState(currentIndex);
        if (currentIndex === -1) {
          currentIndex = self.nextHardwareState(0);
        }
      } while (currentIndex !== startIndex);
      return null;
    };
    // Find the next noise
    var start = testForNoise(true, this.nextHardwareState(this.begin - 1));
    if (start === null) {  // No noise found.
      return null;
    }
    // Find the next non-noise
    var end = testForNoise(false, this.nextHardwareState(start));
    if (end === null) {  // No non-noise found
      return [0, this.entries.length - 1];
    }
    return [start, end];
  },
  setHighlightPopup: function(on) {
    this.inGraph.setHighlightSelected(on);
  },
  setBackground: function(image) {
    this.background = image;
  },
  getEvent: function(index) {
    if (index < 0 || index >= this.entries.length)
      return 'N/A';
    return JSON.stringify(this.entries[index], null, 2);
  },
  getSnippet: function(begin, end) {
    var snippet = {};
    for (var key in this.log) {
      if (!this.log.hasOwnProperty(key)) {
        continue;
      }
      snippet[key] = this.log[key];
    }
    snippet.entries = snippet.entries.slice(begin, end + 1);
    return snippet;
  },
  getUnitTest: function(begin, end, interpreterName, testName) {
    var hp = this.log.hardwareProperties;
    var hardwareStates = '';
    var fingerStates = '';
    var fingerIndex = 0;
    var hwstateIndex = 0;
    for (var i = begin; i <= end; i++) {
      if (this.entries[i].type != 'hardwareState') {
        continue;
      }
      var hwstate = this.entries[i];
      var fingers = hwstate.fingers;
      for (var j = 0; j < fingers.length; j++) {
        var fingerFields = [
          fingers[j].touchMajor,
          fingers[j].touchMinor,
          fingers[j].widthMajor,
          fingers[j].widthMinor,
          fingers[j].pressure,
          fingers[j].orientation,
          fingers[j].positionX,
          fingers[j].positionY,
          fingers[j].trackingId,
          fingers[j].flags
        ].join(', ');
        var index = j ? '' : '  // ' + fingerIndex;
        fingerStates += [ '    { ', fingerFields, ' },', index, '\n' ].join('');
      }

      var hwstateFields = [
        hwstate.timestamp,
        hwstate.buttonsDown,
        fingers.length,
        hwstate.touchCount,
        fingers.length ? '&fs[' + fingerIndex + ']' : 'NULL'
      ].join(', ');

      hardwareStates += [
        '    { ', hwstateFields, ' },  // ', hwstateIndex, '\n'
      ].join('');

      fingerIndex += fingers.length;
      hwstateIndex += 1;
    }

    // Declarations
    unittest =
        'TEST(' + interpreterName + 'Test, ' + testName + 'Test) {\n' +
        '  ' + interpreterName + 'TestInterpreter* base_interpreter =\n' +
        '      new ' + interpreterName + 'TestInterpreter;\n' +
        '  ' + interpreterName + ' interpreter(NULL, base_interpreter);\n\n';

    //  Finger States
    unittest +=
        '  FingerState fs[] = {\n' +
        '    // TM, Tm, WM, Wm, Press, Orientation, X, Y, TrID, flags\n';
    unittest += fingerStates;
    unittest += '  };\n\n';

    //  Hardware States
    unittest +=
        '  HardwareState hs[] = {\n' +
        '    // time, buttons, finger count, touch count, fingers\n';
    unittest += hardwareStates;
    unittest += '  };\n\n';

    // Hardware properties
    unittest +=
        '  HardwareProperties hwprops = {\n' +
        '    ' + [hp.left, hp.top, hp.right, hp.bottom].join(', ') +
        ',  // left, top, right, bottom\n' +
        '    ' + [hp.xResolution, hp.yResolution, hp.xDpi, hp.yDpi].join(', ') +
        ',  // x res, y res, x DPI, y DPI\n' +
        '    ' + [hp.maxFingerCount, hp.maxTouchCount].join(', ') +
        ',  // max_fingers, max_touch\n' +
        '    ' + [hp.supportsT5R2, hp.semiMt, hp.isButtonPad].join(', ') +
        '  // t5r2, semi_mt, is_button_pad\n' +
        '  };\n\n' +
        '  interpreter.SetHardwareProperties(hwprops);\n\n';

    // Interpreter loop
    unittest +=
        '  for (size_t i = 0; i < arraysize(hs); i++)\n' +
        '    interpreter.SyncInterpret(&hs[i], NULL);\n' +
        '}\n';

    return unittest;
  },
  getContentForEntry: function(entry, lastEntry) {
    var dist = 'N/A';
    var hp = this.hardwareProperties;
    var xRes = hp.xResolution;
    var yRes = hp.yResolution;
    var rel = '';
    if (entry.relX !== 0 || entry.relY !== 0) {
      rel = '<br/> rel: (' + entry.relX + ', ' + entry.relY + ')';
    }
    if (entry.fingers.length == 2) {
      var dx = (entry.fingers[1].positionX -
                entry.fingers[0].positionX) / xRes;
      var dy = (entry.fingers[1].positionY -
                entry.fingers[0].positionY) / yRes;
      dist = Math.sqrt(dx * dx + dy * dy) + 'mm';
    }
    var fingerStrings = [];
    for (var i = 0; i < entry.fingers.length; i++) {
      var stringEntry = '' + entry.fingers[i].trackingId;
      var fingerState = entry.fingers[i];
      var outPressure = fingerState.pressure *
          this.log.properties['Pressure Calibration Slope'] +
          this.log.properties['Pressure Calibration Offset'];
      var xPos = fingerState.positionX / xRes;
      var yPos = fingerState.positionY / yRes;
      stringEntry += ' (' + xPos.toFixed(2) + ', ' + yPos.toFixed(2) + ')';
      stringEntry += ' pr: ' + outPressure.toFixed(2);
      if (lastEntry) {
        var dt = lastEntry.timestamp - entry.timestamp;
        var angles = [];
        for (var j = 0; j < lastEntry.fingers.length; j++) {
          if (lastEntry.fingers[j].trackingId ==
              entry.fingers[i].trackingId) {
            var dx = entry.fingers[i].positionX -
                lastEntry.fingers[j].positionX;
            var dy = entry.fingers[i].positionY -
                lastEntry.fingers[j].positionY;
            dx /= xRes;
            dy /= yRes;
            stringEntry += ' (dx/dt: ' + (dx/dt).toFixed(2) + ', dy/dt: ' +
                (dy/dt).toFixed(2) + ' flags: ' + entry.fingers[i].flags + ')';
          }
        }
      }
      fingerStrings.push(stringEntry);
    }
    var fingerString = ': ' + fingerStrings.join(', ');
    return 'timestamp: ' + entry.timestamp +
        '<br/>' + 'fingerCount: ' + entry.fingers.length + fingerString +
        '<br/>' + 'touchCount: ' + entry.touchCount +
        '<br/>' + 'button: ' + (entry.buttonsDown ? 'DOWN' : 'UP') +
        '<br/>' + 'dist: ' + dist + rel;
  },
  handleEntrySelected: function(entry, lastEntry, pageX, pageY) {
    var offsetX = 20;
    var offsetY = 10;
    this.popup.show().css('left', pageX + offsetX).css('top', pageY + offsetY)
        .html(this.getContentForEntry(entry, lastEntry));
  },
  handleEntryDeselected: function() {
    this.popup.hide();
  },
  updateInput: function() {
    var lastPosDict = {};
    var segs = [];
    var lastPoints = [];
    var lastLines = [];
    // draw border
    var hp = this.hardwareProperties;
    var xRes = hp.xResolution;
    var yRes = hp.yResolution;
    var upLeft = {'xPos': hp.left / xRes,
                  'yPos': hp.top / yRes};
    var upRight = {'xPos': hp.right / xRes,
                   'yPos': hp.top / yRes};
    var botLeft = {'xPos': hp.left / xRes,
                   'yPos': hp.bottom / yRes};
    var botRight = {'xPos': hp.right / xRes,
                    'yPos': hp.bottom / yRes};
    segs.push({'start': upLeft,
               'end': upRight,
               'type': GraphController.LINE,
               'color': '#ccc'});
    segs.push({'start': upRight,
              'end': botRight,
              'type': GraphController.LINE,
              'color': '#ccc'});
    segs.push({'start': botRight,
               'end': botLeft,
               'type': GraphController.LINE,
               'color': '#ccc'});
    segs.push({'start': botLeft,
              'end': upLeft,
              'type': GraphController.LINE,
              'color': '#ccc'});
    if (this.background && this.background.width !== 0) {
      var start = {'xPos': upLeft.xPos,
                   'yPos': upLeft.yPos};
      var end = {'xPos': botRight.xPos,
                 'yPos': botRight.yPos};
      // If set, hp.bezels has properties (in hardware touchscreen pixels):
      //     left, right, top, bottom
      if (hp.bezels) {
        start.xPos += hp.bezels.left / xRes;
        start.yPos += hp.bezels.top / yRes;
        end.xPos -= hp.bezels.right / xRes;
        end.yPos -= hp.bezels.bottom / yRes;
      }
      segs.push({'start': start,
                 'end': end,
                 'type': GraphController.IMAGE,
                 'image': this.background});
    }
    var lastEntry = null;
    var prevLastEntry = null;

    var timeLimit = 1.0;  // seconds
    // Compute final timestamp
    var finalTimestamp = 0.0;
    var end = Math.min(this.end + 1, this.entries.length);
    for (var i = (end - 1); i >= this.begin; i--) {
      var entry = this.entries[i];
      if (entry.type != 'hardwareState')
        continue;
      finalTimestamp = entry.timestamp;
      break;
    }
    for (var i = this.begin; i < end; i++) {
      var entry = this.entries[i];
      var prevEntry = lastEntry;
      if (entry.type != 'hardwareState') {
        continue;
      }
      if (finalTimestamp && entry.timestamp < (finalTimestamp - timeLimit)) {
        continue;
      }
      var intensity = (finalTimestamp - entry.timestamp) / timeLimit;
      var buttonDown = !!entry.buttonsDown;
      var newLast = {};
      var lines = [];
      var points = [];
      for (var f = 0; f < entry.fingers.length; f++) {
        var fingerState = entry.fingers[f];
        var lastFingerState = null;
        if (lastEntry) {
          for (var lastf = 0; lastf < lastEntry.fingers.length; lastf++) {
            if (lastEntry.fingers[lastf].trackingId == fingerState.trackingId) {
              lastFingerState = lastEntry.fingers[lastf];
              break;
            }
          }
        }
        var trId = fingerState.trackingId;
        var pt = {'xPos': fingerState.positionX / xRes,
                  'yPos': fingerState.positionY / yRes};
        var touchType = 'start';
        if (trId in lastPosDict) {
          // Draw line from previous point to here
          var i255 = finalTimestamp ? parseInt(intensity * 255) : 0;
          var line = {'start': lastPosDict[trId],
                      'end': pt,
                      'type': GraphController.LINE,
                      'color':
                      ['rgb(', i255, ',', i255, ',', i255, ')'].join('') };
          segs.push(line);
          lines.push(line);
          touchType = 'move';
        }
        newLast[trId] = pt;
        var color = '#ccc';
        var fillColor = '';
        if (finalTimestamp) {
          var i192 = parseInt(intensity * 192);
          color = ['rgb(', i192, ',', i192, ',', i192, ')'].join('');
        }
        var outPressure = fingerState.pressure *
            this.log.properties['Pressure Calibration Slope'] +
            this.log.properties['Pressure Calibration Offset'];
        var radius;
        var label = fingerState.trackingId + ';' + outPressure.toFixed(2);
        if (this.drawStyle === FingerViewController.prototype.style.PAINT) {
          var hue = (fingerState.trackingId * 30) % 256;
          var lum = Math.round(outPressure * 0.8 + 20);
          label = '';
          fillColor = 'hsla(' + hue + ', 100%, ' + lum + '%, 0.1)';
          if (touchType === 'move') {
            color = '';
          } else {
            color = '#000';
          }
          radius = 0.5 * fingerState.touchMajor / Math.max(xRes, yRes);
          if (!radius) {
            radius = outPressure;
          }
          if (!radius || radius < 5) {
            radius = 5;
          }
        }
        var thickness = 1;
        var flag = this.fingerFlags[fingerState.trackingId];
        if (flag && touchType !== 'move') {
          thickness = 3;
          if (flag === FingerViewController.prototype.flag.GOOD) {
            color = 'green';
          } else if (flag === FingerViewController.prototype.flag.NOISE) {
            color = 'red';
          } else if (flag === FingerViewController.prototype.flag.FILTER) {
            color = 'blue';
          }
        }
        var self = this;
        var circle = {'type': GraphController.CIRCLE,
                      'center': pt,
                      'color': color,
                      'fillColor': fillColor,
                      'radius': radius,
                      'label': label,
                      'thickness': thickness,
                      'onSelected': function(pageX, pageY) {
                        self.handleEntrySelected(
                            entry, prevEntry, pageX, pageY);
                      },
                      'onDeselected': function() {
                        self.handleEntryDeselected();
                      }};
        segs.push(circle);
        points.push(circle);
      }
      lastPosDict = newLast;
      lastPoints = points;
      lastLines = lines;
      prevLastEntry = lastEntry;
      lastEntry = entry;
    }
    for (var i = 0; i < lastPoints.length; i++) {
      lastPoints[i].color = '#f99';
    }
    for (var i = 0; i < lastLines.length; i++) {
      lastLines[i].color = '#f99';
    }
    this.inGraph.setLineSegments(segs);
    if (lastEntry) {
      this.inText[0].innerHTML = this.getContentForEntry(
          lastEntry, prevLastEntry);
    }
  },
  updateGs: function() {
    var xPos = 0;
    var yPos = 0;
    var buttonsDx = 5;
    var buttonsDy = 10;
    var xMin = Number.POSITIVE_INFINITY;
    var yMin = Number.POSITIVE_INFINITY;
    var xMax = Number.NEGATIVE_INFINITY;
    var yMax = Number.NEGATIVE_INFINITY;
    var segs = [];
    var end = Math.min(this.end + 1, this.entries.length);
    for (var i = this.begin; i < end; i++) {
      var entry = this.entries[i];
      var prevEntry = null;
      if (i > this.begin)
        prevEntry = this.entries[i - 1];
      if (entry.type == 'gesture') {
        if (entry.gestureType == 'scroll' || entry.gestureType == 'move' ||
            entry.gestureType == 'fling' || entry.gestureType == 'swipe') {
          if (entry.gestureType == 'scroll' || entry.gestureType == 'move' ||
              entry.gestureType == 'swipe') {
            var dx = entry.dx;
            var dy = entry.dy;
          } else {
            var dt = entry.endTime - entry.startTime;
            var dx = entry.vx * dt;
            var dy = entry.vy * dt;
          }
          if (entry.gestureType == 'scroll' || entry.gestureType == 'swipe') {
            if (dy != 0 && dx == 0)
              dx = 1;
            if (dy == 0 && dx != 0)
              dy = 1;
          }
          var colors = {'scroll': '#00f', 'move': '#f00', 'fling': '#ff832c',
                        'swipe': '#0080ff'};
          var endPt = {'xPos': (xPos + dx), 'yPos': (yPos + dy)};
          segs.push({'start': {'xPos': xPos, 'yPos': yPos},
                     'end': endPt,
                     'type': GraphController.LINE,
                     'color': colors[entry.gestureType]});
          xPos += dx;
          yPos += dy;
        } else if (entry.gestureType == 'buttonsChange') {
          var colors = ['#0f0', '#0a0', '#050'];
          for (var bt = 0; bt < 3; bt++) {
            var mask = 1 << bt;
            var color = colors[bt];
            if (entry.down & mask) {
              segs.push({'type': GraphController.LINE,
                         'start': {'xPos': xPos, 'yPos': yPos},
                         'end': {'xPos': (xPos + buttonsDx),
                                 'yPos': (yPos + buttonsDy)},
                         'color': color});
              xPos += buttonsDx;
              yPos += buttonsDy;
              xMin = Math.min(xMin, xPos);
              xMax = Math.max(xMax, xPos);
              yMin = Math.min(yMin, yPos);
              yMax = Math.max(yMax, yPos);
            }
            if (entry.up & mask) {
              segs.push({'type': GraphController.LINE,
                         'start': {'xPos': xPos, 'yPos': yPos},
                         'end': {'xPos': (xPos + buttonsDx),
                                 'yPos': (yPos - buttonsDy)},
                         'color': color});
              xPos += buttonsDx;
              yPos -= buttonsDy;
            }
            xMin = Math.min(xMin, xPos);
            xMax = Math.max(xMax, xPos);
            yMin = Math.min(yMin, yPos);
            yMax = Math.max(yMax, yPos);
          }
        } else if (entry.gestureType == 'swipeLift') {
          segs.push({'type': GraphController.LINE,
                     'start': {'xPos': xPos, 'yPos': yPos},
                     'end': {'xPos': (xPos + buttonsDx),
                             'yPos': (yPos - buttonsDy)},
                     'color': '#660066'});
          xPos += buttonsDx;
          yPos -= buttonsDy;
          xMin = Math.min(xMin, xPos);
          xMax = Math.max(xMax, xPos);
          yMin = Math.min(yMin, yPos);
          yMax = Math.max(yMax, yPos);
        }
        var self = this;
        segs.push({'type': GraphController.CIRCLE,
                   'center': {'xPos': xPos, 'yPos': yPos},
                   'color': '#ccc',
                   'onSelected': function(pageX, pageY) {
                     self.handleEntrySelected(entry, prevEntry, pageX, pageY);
                   },
                   'onDeselected': function() {
                     self.handleEntryDeselected();
                   }});
      }
      xMin = Math.min(xMin, xPos);
      xMax = Math.max(xMax, xPos);
      yMin = Math.min(yMin, yPos);
      yMax = Math.max(yMax, yPos);
    }
    if (xMin < Number.POSITIVE_INFINITY) {
      yBorder = (yMax - yMin) / 20;
      xBorder = (xMax - xMin) / 20;
      this.gs_graph.setDefaultZoom(xMin - xBorder,
                                   yMin - yBorder,
                                   xMax + xBorder,
                                   yMax + yBorder);
      if (this.outLockHead.checked && this.gestureHead) {
        var dx = this.gestureHead.xPos - xPos;
        var dy = this.gestureHead.yPos - yPos;
        this.gs_graph.moveBy(dx, dy);
      }
      this.gestureHead = {'xPos': xPos, 'yPos': yPos};
    }
    this.gs_graph.setLineSegments(segs);
  },
  redraw: function() {
    this.updateInput();
    this.updateGs();
  },
  colorForGesture: function(gs) {
    if (gs.gestureType == 'scroll')
      return 'rgb(255, 0, 0)';
    if (gs.gestureType == 'move')
      return 'rgb(0, 0, 255)';
    if (gs.gestureType == 'buttons')
      return 'rgb(0, 255, 0)';
  }
};
