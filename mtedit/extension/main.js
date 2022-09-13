// Copyright 2013 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

var finger_view_controller;
var current_layer = 0;
var json_obj;

var use_server = false;
var logname = undefined;

var LOG_SCREEN = 'screen';
var LOG_PAD = 'pad';

function getScreenshotUrl(reportUrl) {
  var findId = /id=([0-9]+)/;
  var id = findId.exec(reportUrl)[1];
  return 'https://feedback.corp.googleusercontent.com/screenshot?id=' + id;
}

function startLoading() {
  // Do something more visually interesting later.
  $('#loading').show();
}

function doneLoading() {
  $('#loading').hide();
}

function parseWindowHash() {
  var args = {};
  var hash = window.location.hash.substr(1);
  if (hash.length > 0) {
    var params = hash.split('&');
    for (var i = 0; i < params.length; i++) {
      var param = params[i].split('=', 2);
      args[param[0]] = param.length > 0 ? param[1] : true;
    }
  }
  return args;
}

function updateWindowHash(newArgs) {
  var args = parseWindowHash();
  for (name in newArgs) {
    // Only if newArgs specifically sets an undefined key do we delete from
    // args. Otherwise only add/update key/value pairs in newArgs.
    if (newArgs[name] === undefined) {
      delete args[name];
    } else {
      args[name] = newArgs[name];
    }
  }

  // Replace flags in window hash with current flags
  var flags = finger_view_controller.getTouchFlags();
  for (var name in args) {
    if (name.substring(0, 5) === 'flag.') {
      delete args[name];
    }
  }
  for (var name in flags) {
    args['flag.' + name] = flags[name].join('.');
  }

  var argValues = [];
  for (var name in args) {
    argValues.push(name + '=' + args[name]);
  }
  var newHash = '#' + argValues.join('&');

  // Set a flag so this hash change does not trigger processArguments
  window.ignoreNextHashChange = true;
  window.location.hash = newHash;
  return newHash;
}


function processArguments(args) {
  var file = args.file || args.f;
  var reportUrl = args.reportUrl;
  var startTime = args.startTime;
  var endTime = args.endTime;
  var logType = args.logType;
  var logName = args.logName;

  // We need to set the flags from the original hash before processing the file
  // as file processing triggers updating the hash from existing flags in
  // the FingerViewController.
  var processBeforeLoading = function () {
    var overrideFlags = false;
    var flags = {};
    for (var name in args) {
      if (name.substring(0, 5) === 'flag.') {
        overrideFlags = true;
        flags[name.substring(5)] = args[name].split('.');
      }
    }
    if (overrideFlags) {
      finger_view_controller.setTouchFlags(flags);
    }
  };

  // This range selection only matters after we load a file.
  var processAfterLoading = function() {
    // Fast forward to the range defined by startTime and endTime
    var beginIndex = 0;
    var endIndex = finger_view_controller.entries.length;
    if (startTime) {
      beginIndex =
          finger_view_controller.getHardwareStateGETimestamp(startTime);
    }
    if (endTime) {
      endIndex =
          finger_view_controller.getHardwareStateLETimestamp(endTime);
    }
    finger_view_controller.setRange(beginIndex, endIndex);
    finger_view_controller.resetZooms();
    $('#slider').slider('option', 'values', [beginIndex, endIndex]);
  };

  var loadFileAndScreenshot = function(requestUrl, screenshotUrl, error) {
    startLoading();
    var request = new XMLHttpRequest();
    request.responseType = 'arraybuffer';
    request.addEventListener('load', function() {
      var loadFileAfterImage = function() {
        processBeforeLoading();
        loadFileContent(request.response, logType, logName);
        processAfterLoading();
        doneLoading();
      };
      $('#screenshot').prop('src', screenshotUrl)
          .load(loadFileAfterImage).error(loadFileAfterImage);
    });
    request.addEventListener('error', function() {
      console.error(error);
      doneLoading();
    });
    request.open('GET', requestUrl);
    request.send();
  };

  // Load file from feedback report or local server
  if (reportUrl) {
    reportUrl = decodeURIComponent(reportUrl);
    loadFileAndScreenshot(
        reportUrl,
        getScreenshotUrl(reportUrl),
        'Failed to load system logs for report url ' + reportUrl + '.');
  } else if (file) {
    var path = window.location.href;
    path = path.substr(0, path.indexOf('#'));
    path = path.substr(0, path.lastIndexOf('/') + 1);
    var screenshotFileName;
    var extension = file.substring(file.length - 4);
    // Strip .zip and .bz2 for screenshots to align with mtlib conventions.
    if (extension === '.zip' || extension === '.bz2') {
      screenshotFileName = file.substring(0, file.length - 4);
    } else {
      screenshotFileName = file;
    }
    loadFileAndScreenshot(
        path + file,
        path + screenshotFileName + '.jpg',
        'Failed to load ' + file + ' locally.');
  }
  if (args.start) {
    setBeginTimestampValue(parseFloat(args.start));
  }
  if (args.end) {
    setEndTimestampValue(parseFloat(args.end));
  }
}

function update_range(event, ui) {
  finger_view_controller.setRange(ui.values[0], ui.values[1]);
  var begin_event = finger_view_controller.getEvent(ui.values[0]);
  $('#begin_event').val(begin_event);
  if ((beginTimestamp = finger_view_controller.getTimestamp(ui.values[0])) > 0)
    $('#input_begin_time').val(beginTimestamp);
  var end_event = finger_view_controller.getEvent(ui.values[1]);
  $('#end_event').val(end_event);
  endTimestamp = finger_view_controller.getPreviousHardwareStateTimestamp(
      ui.values[1]);
  if (endTimestamp > 0)
    $('#input_end_time').val(endTimestamp);
  var values = $('#slider').slider('option', 'values');
  $('#num_fts').text('Finger Touch Section (' +
                     finger_view_controller.getFTSIndex(values[1]) + ' / ' +
                     '0 ~ ' + (finger_view_controller.getNumFTS() - 1) + '): ');
}

function loadLogObj(obj, isNew) {
  if (!isNew) {
    var values = $('#slider').slider('option', 'values');
    var beginTime = finger_view_controller.getGETimestamp(values[0]);
    var endTime = finger_view_controller.getLETimestamp(values[1]);
  }
  finger_view_controller.setEntriesLog(obj, current_layer);
  if (obj.flags) {
    finger_view_controller.setTouchFlags(obj.flags);
  }
  finger_view_controller.initFTS();
  var MAX_SIZE = 30000;
  var min = Math.max(0, finger_view_controller.entries.length - MAX_SIZE);
  var max = finger_view_controller.entries.length - 1;
  if (isNew) {
    var values = [min, max];
  } else {
    values[0] = finger_view_controller.getHardwareStateGETimestamp(beginTime);
    values[1] = finger_view_controller.getHardwareStateLETimestamp(endTime);
  }
  $('#slider').slider({
    min: min,
    max: max,
    values: values,
    range: true,
    slide: update_range,
    change: update_range
  });
  update_range(null, { values: values });
  finger_view_controller.resetZooms();
  var args = parseWindowHash();
  if (args.start) {
    setBeginTimestampValue(parseFloat(args.start));
  }
  if (args.end) {
    setEndTimestampValue(parseFloat(args.end));
  }
}

/**
 * Converts raw input event stream from evdev input to the entries structure
 * expected by finger_view_controller.js.
 * @param {string} data The raw log file data in the following format:
 *     # Metadata in comment lines.
 *     # absinfo: [event_type] [min] [max] [fuzz] [flat] [resolution]
 *     E: [timestamp] [event_type] [event_code] [event_value] [slot]
 * @return {Object} Event structure expected by loadLogObj.
 */
function convertEventStreamToEntries(data, bezels) {
  // Clone an object by serializing and parsing it.
  var clone = function(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  // Default hardware properties.
  var obj = {
    'entries': [],
    'hardwareProperties': {
      // TODO(flackr): only add bezel information if touchscreen size matches
      // the size of an output whose name begins with LVDS, eDP or DSI from
      // Xorg.0.log.
      'bezels': bezels,
      'bottom': 1000.0,
      'left': 0.0,
      'right': 2000.0,
      'top': 0.0,
      'xResolution': 1.0,
      'yResolution': 1.0},
    'properties': {
      'Pressure Calibration Offset': 0.0,
      'Pressure Calibration Slope': 1.0,
  }};
  var evt = {
    'fingers': [],
    'timestamp': 0,
    'touchCount': 0,
    'type': 'hardwareState',
  };
  var eventCodes = {
    '002f': 'slot',
    '0030': 'touchMajor',
    '0035': 'positionX',
    '0036': 'positionY',
    '0039': 'trackingId',
    '003a': 'pressure',
  };
  var ignoreCodes = {
    '0000': 'abs_x',
    '0001': 'abs_y',
    '0018': 'abs_pressure',
  };
  var slotDefaults = {
    'flags': 0,
    'trackingId': -1,
  };
  var slots = [];
  var slot = -1;
  var lines = data.split('\n');
  for (var i = 0; i < lines.length; i++) {
    if (lines[i].slice(0, 10) == '# absinfo:') {
      var val = lines[i].split(' ');
      switch (val[2]) {
        case '0':
          obj.hardwareProperties.right = parseInt(val[4]) + 1;
          obj.hardwareProperties.xResolution = parseInt(val[7]);
          break;
        case '1':
          obj.hardwareProperties.bottom = parseInt(val[4]) + 1;
          obj.hardwareProperties.yResolution = parseInt(val[7]);
          break;
        case '47':  // Slot.
          var maxSlot = parseInt(val[4]);
          while (slots.length <= maxSlot)
            slots.push(clone(slotDefaults));
          break;
      }
    } else if (lines[i].slice(0, 3) == 'E: ') {
      var val = lines[i].split(' ');
      switch (val[2]) {  // Event type.
        case '0000':  // EV_SYN: Clone current hardware state and push to list.
          // First copy slots into fingers.
          evt.fingers = [];
          for (var j = 0; j < slots.length; j++) {
            if (slots[j].trackingId >= 0)
              evt.fingers.push(slots[j]);
          }
          evt.touchCount = evt.fingers.length;
          evt.timestamp = parseFloat(val[1]);
          obj.entries.push(clone(evt));
          break;
        case '0003':  // EV_ABS: Update hardware state.
          if (eventCodes[val[3]]) {
            // Parse slot identifier on event info line.
            if (val.length > 5)
              slot = parseInt(val[5]);

            if (eventCodes[val[3]] == 'slot') {
              slot = parseInt(val[4]);
            } else if (slot >= 0) {
              // Initialize the requested slot if not set.
              if (!slots[slot])
                slots[slot] = clone(slotDefaults);

              // Make up tracking ID if we miss the start of a touch.
              if (eventCodes[val[3]] != 'trackingId' &&
                  slots[slot].trackingId == -1)
                slots[slot].trackingId = slot + 1;

              slots[slot][eventCodes[val[3]]] = parseInt(val[4]);
            }
          } else if (!ignoreCodes[val[3]]) {
            console.log('Unrecognized event type ' + val[2] +
                        ' code ' + val[3]);
          }
          break;
      }
    }
  }
  // Add a default empty EV_SYN entry if there are no events as
  // finger_view_controller expects a non-empty obj.entries.
  if (obj.entries.length === 0) {
    obj.entries.push(clone(evt));
  }
  // For touchscreens the absolute value is more useful than the scaled value.
  obj.hardwareProperties.xResolution = 1.0;
  obj.hardwareProperties.yResolution = 1.0;
  return obj;
}

function convertEntriesToEventStream(obj) {
  var lines = [];
  // Hardware properties
  var meta = '# absinfo:';
  var hardwareProperties = obj.hardwareProperties;
  lines.push(meta + ' 0 0 ' + (hardwareProperties.right - 1) + ' 0 0 ' +
      hardwareProperties.xResolution);
  lines.push(meta + ' 1 0 ' + (hardwareProperties.bottom - 1) + ' 0 0 ' +
      hardwareProperties.yResolution);
  lines.push(meta + ' 47 0 ');  // Actual max slot will be filled in later
  var maxSlotIndex = lines.length - 1;
  // Events
  var evt = 'E:';
  var syn = '0000';  // EV_SYN
  var abs = '0003';  // EV_ABS
  var eventCodes = {
    'slot': '002f',
    'touchMajor': '0030',
    'positionX': '0035',
    'positionY': '0036',
    'trackingId': '0039',
    'pressure': '003a',
  };
  var checkEvents = ['positionX', 'positionY', 'pressure', 'touchMajor'];
  var slotMap = {};
  var clearSlots = {};
  var freeSlots = [0];
  var maxSlot = 0;
  for (var i = 0; i < obj.entries.length; i++) {
    var entry = obj.entries[i];
    // Zero clearSlots to mark which trackingIds are still valid
    for (var trackingId in clearSlots) {
      if (clearSlots.hasOwnProperty(trackingId)) {
        clearSlots[trackingId] = true;
      }
    }
    if (entry.fingers !== undefined) {
      for (var j = 0; j < entry.fingers.length; j++) {
        var finger = entry.fingers[j];
        var trackingId = finger.trackingId;
        // If we have not already assigned a slot to this trackingId,
        // find/create one for it
        if (slotMap[trackingId] === undefined) {
          if (freeSlots.length === 0) {
            maxSlot += 1;
            freeSlots.push(maxSlot);
          }
          slotMap[trackingId] = freeSlots.pop();
        }
        var slot = slotMap[trackingId];
        // This trackingId is still valid, do not clear
        clearSlots[trackingId] = false;
        lines.push(evt + ' 0 ' + abs + ' '  + eventCodes.slot + ' ' + slot);
        lines.push(evt + ' 0 ' + abs + ' '  + eventCodes.trackingId + ' ' +
            trackingId);
        // Add all the other properties of the finger, other than trackingId
        // and the slot
        for (var k = 0; k < checkEvents.length; k++) {
          var key = checkEvents[k];
          if (key in finger) {
            lines.push(evt + ' 0 ' + abs + ' ' + eventCodes[key] + ' ' +
                finger[key]);
          }
        }
      }
    }
    for (var trackingId in clearSlots) {
      if (clearSlots.hasOwnProperty(trackingId)) {
        if (clearSlots[trackingId]) {
          // We are done with this particular trackingId, free that slot
          lines.push(evt + ' 0 ' + abs + ' ' + eventCodes.slot + ' ' +
              slotMap[trackingId]);
          lines.push(evt + ' 0 ' + abs + ' ' + eventCodes.trackingId + ' -1 ');
          freeSlots.push(slotMap[trackingId]);
          delete clearSlots[trackingId];
          delete slotMap[trackingId];
        }
      }
    }
    if (entry.timestamp !== undefined) {
      lines.push(evt + ' ' + entry.timestamp + ' ' + syn);
    }
  }
  // Fill in the maximum index slot we needed to use
  lines[maxSlotIndex] += maxSlot
  return lines.join('\n');
}

/**
 * Loads the log frames from json.
 * @param {Object} obj Event structure expected by loadLogObj.
 */
function loadLog(obj) {
  if (!obj) {
    alert('Unrecognized input file');
    return;
  }
  json_obj = obj;
  generateRadioButtons(obj);
  current_layer = 0;
  loadLogObj(obj, true);
  // If obj.isTouchScreen is true, then manually switch to touchscreen mode
  touchscreenToggle(!!obj.isTouchscreen);
}

function convertStrToLog(str, bezels) {
  var obj;
  if (str[0] == '#' || str[0] == 'E') {  // A touchscreen log
    obj = convertEventStreamToEntries(str, bezels);
    obj.isTouchscreen = true;
  } else if (str[0] == '{') {  // A touchpad log
    obj = jQuery.parseJSON(str);
    obj.isTouchscreen = false;
  }
  return obj;
}

function handleFileSelect(evt) {
  $('#text_box').removeClass('text_box_hilight');
  evt.stopPropagation();
  evt.preventDefault();

  var files = evt.dataTransfer.files;  // FileList object.

  var file = files[0];
  var reader = new FileReader();
  reader.onload = function(e) {
    loadLog(convertStrToLog(e.target.result));
  };
  reader.readAsText(file);
}

var count = 0;

function handleDragOver(evt) {
  evt.stopPropagation();
  evt.preventDefault();
}

function handleDragEnter(evt) {
  $('#text_box').addClass('text_box_hilight');
  evt.stopPropagation();
  evt.preventDefault();
}

function handleDragOut(evt) {
  $('#text_box').removeClass('text_box_hilight');
  evt.stopPropagation();
  evt.preventDefault();
}

function setup() {
  var dropZone = document.getElementById('text_box');
  dropZone.addEventListener('dragenter', handleDragEnter, false);
  dropZone.addEventListener('dragleave', handleDragOut, false);
  dropZone.addEventListener('dragover', handleDragOver, false);
  dropZone.addEventListener('drop', handleFileSelect, false);
}

// fix layerX, layerY warnings
(function(){
    // remove layerX and layerY
    var all = $.event.props,
        len = all.length,
        res = [];
    while (len--) {
      var el = all[len];
      if (el != 'layerX' && el != 'layerY') res.push(el);
    }
    $.event.props = res;
}());

function begin_stepBack() {
  var values = $('#slider').slider('option', 'values');
  var minValue = $('#slider').slider('option', 'min');
  if (values[0] > minValue) {
    var newValue = finger_view_controller.prevHardwareState(values[0]);
    if (newValue < 0)
      return;
    values[0] = newValue;
    $('#slider').slider('option', 'values', values);
    $('#input_begin_time').val(finger_view_controller.getTimestamp(newValue));
  }
}

function begin_stepForward() {
  var values = $('#slider').slider('option', 'values');
  if (values[0] < values[1]) {
    var newValue = finger_view_controller.nextHardwareState(values[0]);
    if (newValue < 0)
      return;
    values[0] = newValue;
    $('#slider').slider('option', 'values', values);
    $('#input_begin_time').val(finger_view_controller.getTimestamp(newValue));
  }
}

function end_stepBack() {
  var values = $('#slider').slider('option', 'values');
  if (values[1] > values[0]) {
    var newValue = finger_view_controller.prevHardwareState(values[1]);
    if (newValue < 0)
      return;
    values[1] = newValue;
    $('#slider').slider('option', 'values', values);
    $('#input_end_time').val(finger_view_controller.getTimestamp(newValue));
  }
}

function end_stepForward() {
  var values = $('#slider').slider('option', 'values');
  var maxValue = $('#slider').slider('option', 'max');
  if (values[1] < maxValue) {
    var newValue = finger_view_controller.nextHardwareState(values[1]);
    if (newValue < 0)
      return;
    values[1] = newValue;
    $('#slider').slider('option', 'values', values);
    $('#input_end_time').val(finger_view_controller.getTimestamp(newValue));
  }
}

function setBeginTimestamp() {
  setBeginTimestampValue($('#input_begin_time').val());
}

function setBeginTimestampValue(timestamp) {
  var values = $('#slider').slider('option', 'values');
  var minValue = $('#slider').slider('option', 'min');
  var maxValue = $('#slider').slider('option', 'max');
  var newValue = finger_view_controller.getHardwareStateLETimestamp(timestamp);
  if (newValue >= minValue && newValue <= maxValue) {
    values[0] = (newValue >= values[1] ? values[1] : newValue);
    $('#slider').slider('option', 'values', values);
  }
}

function setEndTimestamp() {
  setEndTimestampValue($('#input_end_time').val());
}

function setEndTimestampValue(timestamp) {
  var values = $('#slider').slider('option', 'values');
  var minValue = $('#slider').slider('option', 'min');
  var maxValue = $('#slider').slider('option', 'max');
  var newValue = finger_view_controller.getHardwareStateGETimestamp(timestamp);
  if (newValue >= minValue && newValue <= maxValue) {
    values[1] = (newValue <= values[0] ? values[0] : newValue);
    $('#slider').slider('option', 'values', values);
  }
}

function gotoPrevFTS() {
  var values = $('#slider').slider('option', 'values');
  var fts = finger_view_controller.getPrevFTS(values);
  $('#slider').slider('option', 'values', fts);
}

function gotoNextFTS() {
  var values = $('#slider').slider('option', 'values');
  var fts = finger_view_controller.getNextFTS(values);
  $('#slider').slider('option', 'values', fts);
}

function gotoFirstFTS() {
  var fts = finger_view_controller.getFirstFTS();
  $('#slider').slider('option', 'values', fts);
}

function gotoLastFTS() {
  var fts = finger_view_controller.getLastFTS();
  $('#slider').slider('option', 'values', fts);
}

function expandAllFTS() {
  var values = finger_view_controller.getAllEntries();
  $('#slider').slider('option', 'values', values);
}

function shrink() {
  var values = $('#slider').slider('option', 'values');
  var snippet = finger_view_controller.getSnippet(values[0], values[1]);
  $('#text_box').val(JSON.stringify(snippet, null, 2));
  loadLogObj(snippet, true);

  if (use_server) {
    $.post('/save/' + logname, JSON.stringify(snippet, null, 2), function () {
      alert('Saved');
    });
  }
}

function play() {
  // Maximum time between touch events
  var maxDelay = 3000;  // ms
  var values = $('#slider').slider('option', 'values');
  var current = values[0];
  var end = values[1];
  var playTimer = null;
  var stop = function() {
    if (playTimer !== null) {
      clearTimeout(playTimer);
      playTimer = null;
      $('#play')[0].firstChild.textContent = 'Play';
      $('#play').unbind('click').click(play);
    }
  };
  $('#play')[0].firstChild.textContent = 'Stop';
  $('#play').unbind('click').click(stop);
  var animate = function() {
    current += 1;
    finger_view_controller.setEndPoint(current);
    values[1] = current;
    $('#slider').slider('option', 'values', values);
    if (current < end) {
      playTimer = setTimeout(animate, Math.min(maxDelay,
            (finger_view_controller.entries[current].timestamp -
             finger_view_controller.entries[current - 1].timestamp) * 1000));
    } else {
      stop();
    }
  };
  animate();
}

function setTextBoxAndSelect(text) {
  $('#text_box').val(text);
  $('#text_box')[0].focus();
  $('#text_box')[0].select();
}

function exportRange() {
  var values = $('#slider').slider('option', 'values');
  var snippet = finger_view_controller.getSnippet(values[0], values[1]);
  setTextBoxAndSelect(convertEntriesToEventStream(snippet));
}

function displayLink() {
  var beginIndex = finger_view_controller.begin;
  var endIndex = finger_view_controller.end;
  if (beginIndex >= 0 && endIndex >= 0) {
    var startTime = finger_view_controller.getGETimestamp(beginIndex);
    var endTime = finger_view_controller.getLETimestamp(endIndex);

    if (startTime < 0) {
      startTime = undefined;
    }
    if (endTime < 0) {
      endTime = undefined;
    }

    updateWindowHash({
      'startTime': startTime,
      'endTime': endTime,
    });
    setTextBoxAndSelect(window.location);
  }
}

function generateRadioButtons(obj) {
  var radioHTML = '<input type="radio" name="viewLayer" value="0" ' +
                  'checked="checked" onclick="radioChange(event)">' +
                  obj.interpreterName + '</input><br/>';
  var layer = 0;
  while (obj.hasOwnProperty('nextLayer')) {
    obj = obj.nextLayer;
    layer++;
    radioHTML += '<input type="radio" name="viewLayer" value="' + layer +
                 '" onclick="radioChange(event)">' + obj.interpreterName +
                 '</input><br/>';
  }
  document.getElementById('button_div').innerHTML = radioHTML;
  if (layer > 1) {
    $('#button_div').css('visibility', 'visible');
  } else {
    $('#button_div').css('visibility', 'hidden');
  }
}

function generateUnittest() {
  var interpreter_name = $('#unittest_interpreter').val();
  var unittest_name = $('#unittest_testname').val();

  var values = $('#slider').slider('option', 'values');
  var unittest = finger_view_controller.getUnitTest(
      values[0], values[1], interpreter_name, unittest_name);
  $('#unittest_box').val(unittest);
}

function radioChange(e) {
  if (e.target.value != current_layer) {
    current_layer = e.target.value;
    loadLogObj(json_obj, false);
  }
}

function paintStyleChange() {
  if ($(this).is(':checked')) {
    finger_view_controller.drawStyle =
        FingerViewController.prototype.style.PAINT;
  } else {
    finger_view_controller.drawStyle =
        FingerViewController.prototype.style.STANDARD;
  }
  finger_view_controller.redraw();
}

function touchscreenToggle(on) {
  var isTouchscreen = false;
  var inputWidth = '';
  var canvasWidth = 480, canvasHeight = 320;
  var canvas;
  var image = null;
  if (on) {
    isTouchscreen = true;
    inputWidth = 1100;
    canvasWidth = 1080;
    canvasHeight = 720;
    image = document.getElementById('screenshot');
  }
  $('.pad').toggle(!isTouchscreen);
  $('.screen').toggle(isTouchscreen);
  $('#inputview').width(inputWidth);
  $('.view-container').width(canvasWidth);
  $('.view-container').height(canvasHeight);
  canvas = document.getElementById('fview');
  canvas.setAttribute('width', canvasWidth);
  canvas.setAttribute('height', canvasHeight);
  finger_view_controller.setHighlightPopup(on);
  finger_view_controller.setBackground(image);
  finger_view_controller.resetZooms();

  // Allow changing paint styles only for touchscreen view, lock to standard
  // paint style for touchpad view.
  if (on) {
    $('#paint-style').change();
  } else {
    finger_view_controller.drawStyle =
        FingerViewController.prototype.style.STANDARD;
    finger_view_controller.redraw();
  }
}

function convertArrayToString(int_array) {
  var char_array = [];
  for (var i = 0; i < int_array.length; i++) {
    char_array.push(String.fromCharCode(int_array[i]));
  }
  return char_array.join('');
}

function setKeyValue(key, value) {
  if (!window.chrome || !chrome.storage)
    return;
  var items = {};
  items[key] = value;
  chrome.storage.sync.set(items);
}

function getValueCallback(key, callback) {
  if (!window.chrome || !chrome.storage) {
    setTimeout(callback, 0);
    return;
  }
  chrome.storage.sync.get(key, function(items) {
    callback(items[key]);
  });
}

// Returns a name-data dictionary object of logs extracted from the tar file.
function extractActivityLog(tar, type) {
  // a tar file is a sequence of 512 byte blocks. Starting with a header block
  // followed by the contents of that file, repeated for as many files
  // as are in the archive. The file contents are padded if zeros to fill up
  // multiples of 512 byte blocks.

  // extracts name from tar file header
  function getName(header_offset) {
    name_array = new Uint8Array(tar.slice(header_offset, header_offset + 100));
    if (name_array[0] == 0) {
      return undefined;
    }
    return String.fromCharCode.apply(null, name_array);
  }

  // extracts length from tar file header
  function getLength(header_offset) {
    start = header_offset + 124;
    length_array = new Uint8Array(tar.slice(start, start + 12));
    length_string = String.fromCharCode.apply(null, length_array);
    return parseInt(length_string, 8);
  }


  // iterate over all files and collect all activity logs
  var header_offset = 0;
  var log_list = new Array();
  var name_pattern = /touchpad_activity_([0-9\-]+)/;
  if (type === LOG_SCREEN) {
    name_pattern = /evdev/;
  }
  while (header_offset + 512 < tar.byteLength) {

    // cannot read a name from the header? -> End of archive.
    var name = getName(header_offset);
    if (name == undefined)
      break;

    var length = getLength(header_offset);

    if (name_pattern.test(name)) {
      // store file info in list
      result = new Object();
      result.name = name;
      result.timestamp = 0;
      var timestamp = name_pattern.exec(name);
      if (timestamp !== null) {
        result.timestamp = timestamp[1];
      }
      if (type === LOG_PAD) {
        // The normal name for touchpad logs is too long, just use the timestamp
        // to distinguish between them.
        result.name = result.timestamp;
      }
      result.offset = header_offset + 512
      result.length = length;
      log_list.push(result)
    }

    // Next header starts after the file on the next 512 byte aligned
    // block.
    header_offset = Math.ceil((header_offset+length) / 512 + 1) * 512;
  }

  // sort by descending timestamps to find latest file
  log_list.sort(function(a, b) {
    return a.timestamp < b.timestamp;
  });
  var extracted_logs = {};
  for (var i = 0; i < log_list.length; i++) {
    var log = log_list[i];
    var name = log.name;
    var log_data =
        new Uint8Array(tar.slice(log.offset, log.offset + log.length));
    var extracted_log;
    if (type === LOG_SCREEN) {
      extracted_log = convertArrayToString(log_data);
    } else {
      extracted_log = (new JXG.Util.Unzip(log_data)).unzip()[0][0];
    }
    extracted_logs[name] = extracted_log;
  }
  return extracted_logs;
}

function extractAndLoadLog(log, logType, logName) {
  // Returns a name=>data dictionary object of logs
  var extractByInterface = function(type) {
    var start_index = [
      'hack-33025-touch' + type + '_activity="""\n' +
      'begin-base64 644 touch' + type + '_activity_log.tar\n',
      'touch' + type + '_activity="""\n' +
      'begin-base64 644 touch' + type + '_activity_log.tar\n',
      'hack-33025-touch' + type + '_activity=<multiline>\n' +
      '---------- START ----------\n' +
      'begin-base64 644 touch' + type + '_activity_log.tar\n',
    ];
    var end_index = [
      '"""',
      '"""',
      '---------- END ----------',
    ];
    // extract matched tar from log
    var start_idx = -1, end_idx;
    for (var i = 0; i < start_index.length; i++) {
      start_idx = log.indexOf(start_index[i]);
      if (start_idx !== -1) {
        start_idx += start_index[i].length;
        end_idx = log.indexOf(end_index[i], start_idx) - 1;
        break;
      }
    }
    if (start_idx === -1) {
      return {};
    }

    var tar_base64 = log.substring(start_idx, end_idx);

    // decode base64
    var tar_file = Base64Binary.decodeArrayBuffer(tar_base64);

    // extract log from tar file
    return extractActivityLog(tar_file, type);
  };

  var logsByType = {};

  logsByType[LOG_PAD] = extractByInterface(LOG_PAD);
  logsByType[LOG_SCREEN] = extractByInterface(LOG_SCREEN);

  var bezels;
  var calibrationFlag = '--touch-calibration=';
  // Find a line that contains /sbin/session_manager and capture the characters
  // between the end of that command and the end of the line to get all the
  // command-line flags passed to the session manager.
  var findSessionManagerFlags = RegExp('\/sbin\/session_manager[^\n]* ' +
                                       '-- \/opt\/google\/chrome\/chrome ?' +
                                       '([^\n]+)\n');
  var sessionManagerMatches = findSessionManagerFlags.exec(log);
  if (sessionManagerMatches) {
    var sessionManagerFlags = sessionManagerMatches[1];
    // Search for the calibration flag only among these command-line flags
    var findCalibrationParameters = /--touch-calibration=([0-9,]*)/;
    var calibrationParameterMatches =
        findCalibrationParameters.exec(sessionManagerFlags);
    if (calibrationParameterMatches) {
      var calibrationParameter = calibrationParameterMatches[1];
      var parsedBezels = calibrationParameter.split(',');
      if (parsedBezels.length === 4) {
        bezels = {
          left: parseInt(parsedBezels[0]),
          right: parseInt(parsedBezels[1]),
          top: parseInt(parsedBezels[2]),
          bottom: parseInt(parsedBezels[3])
        };
      } else {
        console.error('Wrong number of --touch-calibration parameters: ' +
            calibrationParameter);
      }
    }
  }

  var SEPARATOR = ': ';  // Assuming ': ' is a valid separator.
  var LOG_TYPE_KEY = 'preferrerdLogType';
  var select = $('#select');
  select.empty();  // Remove old options
  var numOptions = 0;
  $.each(logsByType, function(type, logs) {
    $.each(logs, function(name, data) {
      var value = type + SEPARATOR + name;
      numOptions += 1;
      select.append($('<option></option>')
                    .prop('value', value)
                    .text(value));
    });
  });

  var loadLogAndUpdateWindowHash = function(type, name) {
    if (type !== undefined &&
        name !== undefined &&
        logsByType[type] !== undefined &&
        logsByType[type][name] !== undefined) {
      // Keep track in the hash arguments which log we are loading.
      updateWindowHash({
        'logType': type,
        'logName': name,
      });
      loadLog(convertStrToLog(logsByType[type][name], bezels));
      select.val(type + SEPARATOR + name);
    }
  }
  select.change(function() {
    var values = $(this).prop('value').split(SEPARATOR);
    var type = values[0], name = values[1];
    loadLogAndUpdateWindowHash(type, name);
    setKeyValue(LOG_TYPE_KEY, type);
  });
  select.toggle(numOptions > 1);  // Only display select if more than 1 option.

  // Load default (first available) log type if no type or name is specified.
  if (logType === undefined || logName === undefined) {
    // When loading the default log, check storage to see if there is a
    // different preferred log type stored, and load that one if available.
    getValueCallback(LOG_TYPE_KEY, function(storedType) {
      var type, name;
      if (storedType !== undefined &&
          logsByType[storedType] !== undefined &&
          Object.keys(logsByType[storedType]).length > 0) {
        var keys = Object.keys(logsByType[storedType]);
        // When a valid type is found, simply load any log of that type.
        type = storedType;
        name = keys[0];
      } else {
        // No valid log of the stored type available or no store, just load the
        // first option in select.
        var values = select.prop('value').split(SEPARATOR);
        type = values[0];
        name = values[1];
      }
      loadLogAndUpdateWindowHash(type, name);
    });
  } else {
    // Load the preselected log.
    loadLogAndUpdateWindowHash(logType, logName);
  }
}

/**
 * Loads from a buffer, either from uploaded file or from feedback report urls.
 * @param {ArrayBuffer} buffer Contains the entire file's contents.
 */
function loadFileContent(buffer, logType, logName) {
  var feedback = '';
  var dataArray = new Uint8Array(buffer);
  var unzipper = new JSUnzip({
    'charCodeAt': function(index) {
      // Hack to trick JSUnzip that we don't use UTF-8 in
      // filenames. This means that filenames with multi-byte chars
      // will be mangled, but that doesn't affect us. We need this b/c
      // without it, JSUnzip refuses to unzip the file at all.
      if (index == 7)
        return 0;
      return dataArray[index];
    },
  });
  // If the file is not a valid zip file, check for bz2, otherwise assume raw
  // file content
  if (unzipper.isZipFile()) {
    unzipper.readEntries();
    feedback = JSInflate.inflate(unzipper.entries[0].data);
  } else {
    var bz2Array = bzip2.array(dataArray);
    // The bzip2.header method in bzip2.simple throws an exception if the array
    // does not represent a valid bz2 file.
    try {
      feedback = bzip2.simple(bz2Array);
    } catch (e) {
      // Not a bz2 file, load as a plain file input
      var rawInput = convertArrayToString(dataArray);
      loadLog(convertStrToLog(rawInput));
      return;
    }
  }
  extractAndLoadLog(feedback, logType, logName);
}

function updateFlags(state) {
  finger_view_controller.flagTouchPoints(state);
  finger_view_controller.redraw();
  var flags = finger_view_controller.getTouchFlags();
  var text = '';
  for (var flag in flags) {
    text += '# flag: ' + flag + ' ' + flags[flag].join(',') + '\n';
  }
  setTextBoxAndSelect(text);
}

function jumpToNextNoise() {
  var values = finger_view_controller.jumpToNextNoise();
  if (values !== null) {
    $('#slider').slider('option', 'values', values);
  }
}

$(document).ready(function() {
  setup();
  $('#playpause').button({
    text: false,
    icons: {
      primary: 'ui-icon-play'
    }
  });
  var gc = new GraphController($('#gview'));
  gc.setLineSegments([{'start': {'xPos': 0.1, 'yPos': 0.1},
                       'end': {'xPos': 0.9, 'yPos': 0.5}}]);
  var inGc = new GraphController($('#fview'));
  finger_view_controller = new FingerViewController(
      inGc, gc, $('#intext'), $('#popup'), $('#out-lock-head'));

  $('#paint-style').change(paintStyleChange);
  $('#out-resetzoom').button({
    icons: {
      primary: 'ui-icon-arrow-4-diag'
    }
  }).click(function() {
    gc.animResetZoom();
  });

  $('#in-resetzoom').button({
    icons: {
      primary: 'ui-icon-arrow-4-diag'
    }
  }).click(function() {
    inGc.animResetZoom();
  });

  $('#begin_stepback').button({
    text: false,
    icons: {
      primary: 'ui-icon-triangle-1-w'
    }
  }).click(begin_stepBack);
  $('#begin_stepforward').button({
    text: false,
    icons: {
      primary: 'ui-icon-triangle-1-e'
    }
  }).click(begin_stepForward);
  $('#end_stepback').button({
    text: false,
    icons: {
      primary: 'ui-icon-triangle-1-w'
    }
  }).click(end_stepBack);
  $('#end_stepforward').button({
    text: false,
    icons: {
      primary: 'ui-icon-triangle-1-e'
    }
  }).click(end_stepForward);

  $('#play').button({
    text: true,
  }).click(play);
  $('#shrink').button({
    text: true,
  }).click(shrink);
  $('#export').button({
    text: true,
  }).click(exportRange);
  $('#link').button({
    text: true,
  }).click(displayLink);
  $('#flag-noise').button({
    text: true,
  }).click(function() {
    updateFlags(FingerViewController.prototype.flag.NOISE);
  });
  $('#flag-good').button({
    text: true,
  }).click(function() {
    updateFlags(FingerViewController.prototype.flag.GOOD);
  });
  $('#flag-unknown').button({
    text: true,
  }).click(function() {
    updateFlags(FingerViewController.prototype.flag.NONE);
  });
  $('#next-noise').button({
    text: true,
  }).click(jumpToNextNoise);
  $('#prev_finger_touch').button({
    text: true,
  }).click(gotoPrevFTS);
  $('#next_finger_touch').button({
    text: true,
  }).click(gotoNextFTS);
  $('#first_finger_touch').button({
    text: true,
  }).click(gotoFirstFTS);
  $('#last_finger_touch').button({
    text: true,
  }).click(gotoLastFTS);
  $('#all_finger_touch').button({
    text: true,
  }).click(expandAllFTS);
  $('#unittest').button({
    text: true,
  }).click(generateUnittest);

  $(window).keypress(function (event) {
    switch (event.keyCode) {
    case 44:  // ','  move the slider to previous fts
      gotoPrevFTS();
      break;
    case 46:  // '.'  move the slider to next fts
      gotoNextFTS();
      break;
    case 109:  // 'm' move the slider to the first fts
      gotoFirstFTS();
      break;
    case 47:  // '/'  move the slider to the last fts
      gotoLastFTS();
      break;
    case 97:  // 'a'  expand the slider to all entries
      expandAllFTS();
      break;
    case 107:  // 'k'
      end_stepBack();
      break;
    case 106:  // 'j'
      end_stepForward();
      break;
    case 103:  // 'g'
      begin_stepBack();
      break;
    case 104:  // 'h'
      begin_stepForward();
      break;
    case 115:  // 's'
      shrink();
      break;
    }
  });

  $('#upload').change(function () {
    // read selected file
    reader = new FileReader();
    startLoading();
    reader.onload = function (event) {
      loadFileContent(event.target.result);
      doneLoading();
    };
    reader.readAsArrayBuffer(document.getElementById('upload').files[0]);
  });

  // The jQuery hashchange event is bound to the window.onhashchange event. This
  // event is fired whenever the part of the url following the # symbol is
  // changed.
  $(window).bind('hashchange', function() {
    if (window.ignoreNextHashChange) {
      window.ignoreNextHashChange = false;
    } else {
      processArguments(parseWindowHash());
    }
  });
  var args = parseWindowHash();
  processArguments(args);
  // Loading feedback report from url or file takes precedence
  if (args.reportId === undefined &&
      args.f === undefined &&
      args.file === undefined) {
    logname = $.url().fparam('id');
    use_server = logname !== '';
    if (use_server) {
      $.get('/load/' + logname, function(data) {
        loadLog(convertStrToLog(data));
      }, 'text');
    } else {
      loadLog(secret_obj);
    }
  }
});
