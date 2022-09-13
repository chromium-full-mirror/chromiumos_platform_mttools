// Copyright 2012 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

function GraphController(canvas_elt) {
  this.canvas = canvas_elt[0];
  canvas_elt.bind('mousewheel', [this], function(evt, intDelta) {
    evt.data[0].zoomBy(intDelta);
    evt.stopPropagation();
    evt.preventDefault();
  });
  canvas_elt.bind('mousemove', [this], function(evt) {
    evt.data[0].mouseMove(evt.offsetX, evt.offsetY);
  });
  var docMouseMove = function(evt) {
    evt.stopPropagation();
    evt.preventDefault();
    var offset = evt.data[1].offset();
    evt.data[0].dragMove(evt.pageX - offset.left, evt.pageY - offset.top);
  };
  var docMouseUp = function(evt) {
    evt.stopPropagation();
    evt.preventDefault();
    var offset = evt.data[1].offset();
    evt.data[0].mouseUp(evt.pageX, evt.pageY, offset.left, offset.top);
    $(document).unbind('mousemove', docMouseMove);
    $(document).unbind('mouseup', docMouseUp);
  }
  canvas_elt.bind('mousedown', [this, canvas_elt], function(evt) {
    evt.stopPropagation();
    evt.preventDefault();
    $(document).bind('mousemove', [evt.data[0], evt.data[1]], docMouseMove);
    $(document).bind('mouseup', [evt.data[0], evt.data[1]], docMouseUp);
    evt.data[0].mouseDown(evt.offsetX, evt.offsetY);
  });
  this.selected = null;
  this.mouseX = this.mouseY = 0;
  this.dragging = false;
  this.dragStart = null;
  this.segs = [];
  var halfWidth = (this.canvas.width / 2) | 0;
  this.defaultXMin = -halfWidth;
  this.defaultXMax = halfWidth;
  var halfHeight = (this.canvas.height / 2) | 0;
  this.defaultYMin = -halfHeight;
  this.defaultYMax = halfHeight;
  this.highlightSelected = false;
  this.resetCoordinatesAndZoom();
};

GraphController.LINE = 1;
GraphController.CIRCLE = 2;
GraphController.IMAGE = 3;

GraphController.prototype = {
  setLineSegments: function(segs) {
    this.segs = segs;
    this.draw();
  },
  setHighlightSelected: function(on) {
    this.highlightSelected = on;
  },
  setDefaultZoom: function(left, top, right, bottom) {
    var viewHeight = bottom - top;
    var viewWidth = right - left;

    var cHeight = this.canvas.height;
    var cWidth = this.canvas.width;

    if (viewHeight / viewWidth > cHeight / cWidth) {
      this.defaultYMin = top;
      this.defaultYMax = bottom;

      var newViewWidth = viewHeight * cWidth / cHeight;
      var extraEdge = (newViewWidth - viewWidth) / 2;
      this.defaultXMin = left - extraEdge;
      this.defaultXMax = right + extraEdge;
    } else {
      this.defaultXMin = left;
      this.defaultXMax = right;

      var newViewHeight = viewWidth * cHeight / cWidth;
      var extraEdge = (newViewHeight - viewHeight) / 2;
      this.defaultYMin = top - extraEdge;
      this.defaultYMax = bottom + extraEdge;
    }
  },
  resetCoordinatesAndZoom: function() {
    this.xMin = this.defaultXMin;
    this.xMax = this.defaultXMax;
    this.yMin = this.defaultYMin;
    this.yMax = this.defaultYMax;
    this.draw();
  },
  stepAnimResetZoom: function(timestamp) {
    if (timestamp >= this.animStop) {
      this.resetCoordinatesAndZoom();
      return;
    }
    var linX = (timestamp - this.animStart) / (this.animStop - this.animStart);
    var easedX = 0.5 - 0.5 * Math.cos(Math.PI * linX);
    this.xMin = this.animXMin * (1 - easedX) + this.defaultXMin * easedX;
    this.xMax = this.animXMax * (1 - easedX) + this.defaultXMax * easedX;
    this.yMin = this.animYMin * (1 - easedX) + this.defaultYMin * easedX;
    this.yMax = this.animYMax * (1 - easedX) + this.defaultYMax * easedX;
    this.draw();
    var self = this;
    window.requestAnimationFrame(function(timestamp) {
      self.stepAnimResetZoom(timestamp);
    })
  },
  animResetZoom: function() {
    this.animStart = window.performance.now ? performance.now() : Date.now();
    this.animStop = this.animStart + 200;
    this.animXMin = this.xMin;
    this.animXMax = this.xMax;
    this.animYMin = this.yMin;
    this.animYMax = this.yMax;
    var self = this;
    window.requestAnimationFrame(function(timestamp) {
      self.stepAnimResetZoom(timestamp);
    })
  },
  mouseDown: function(xPos, yPos) {
    this.dragStart = { 'xPos': xPos, 'yPos': yPos };
    if (this.highlightSelected && this.selected !== null) {
      this.selected.onDeselected();
      this.selected = null;
      this.draw();
    }
  },
  moveBy: function(dx, dy) {
    this.xMin -= dx;
    this.xMax -= dx;
    this.yMin -= dy;
    this.yMax -= dy;
  },
  dragMove: function(xPos, yPos) {
    var viewPt = { 'xPos': xPos, 'yPos': yPos };
    var viewDx = viewPt.xPos - this.dragStart.xPos;
    var viewDy = viewPt.yPos - this.dragStart.yPos;
    var dx = viewDx * (this.xMax - this.xMin) / this.canvas.width;
    var dy = viewDy * (this.yMax - this.yMin) / this.canvas.height;
    this.moveBy(dx, dy);
    this.dragStart = viewPt;
    this.draw();
  },
  mouseMove: function(xPos, yPos) {
    this.mouseX = xPos;
    this.mouseY = yPos;
  },
  distSquared: function(item, xPos, yPos) {
    var point = this.pointToView(item.center);
    return (point.xPos - xPos) * (point.xPos - xPos) +
        (point.yPos - yPos) * (point.yPos - yPos);
  },
  // evtX, evtY are the absolute page coordinates for the mouseUp event.
  // offsetX, offsetY are the absolute page coordinates for the canvas element.
  // Taking their difference we get the relative coordinates for the event in
  // the canvas (xPos and yPos).
  mouseUp: function(evtX, evtY, offsetX, offsetY) {
    this.dragStart = null;
    if (this.highlightSelected) {
      var xPos = evtX - offsetX, yPos = evtY - offsetY;
      var index = null, best_distance = Infinity;
      for (var i = 0; i < this.segs.length; i++) {
        var item = this.segs[i];
        if (item.type == GraphController.CIRCLE) {
          var distSquared = this.distSquared(item, xPos, yPos);
          if (distSquared <= (5.0 * 5.0) && distSquared < best_distance) {
            best_distance = distSquared;
            index = i;
          }
        }
      }
      if (index !== null) {
        this.selected = this.segs[index];
        this.selected.onSelected(evtX, evtY);
        this.draw();
      }
    }
  },
  zoomBy: function(amount) {
    var scaleFactor = Math.pow(2, -amount / 16);
    var start = [this.xMin, this.yMin];
    var stop = [this.xMax, this.yMax];
    var pt = this.pointFromView({ 'xPos': this.mouseX, 'yPos': this.mouseY });
    pt = [pt.xPos, pt.yPos];
    for (var i = 0; i < 2; i++) {
      var oldLength = stop[i] - start[i];
      start[i] = pt[i] - (pt[i] - start[i]) * scaleFactor;
      stop[i] = pt[i] + (stop[i] - pt[i]) * scaleFactor;
    }
    this.xMin = start[0];
    this.yMin = start[1];
    this.xMax = stop[0];
    this.yMax = stop[1];
    this.draw();
  },
  draw: function() {
    var ctx = this.canvas.getContext('2d');
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    for (var i = 0; i < this.segs.length; i++) {
      var item = this.segs[i];
      if (item.type == GraphController.LINE) {
        this.drawLineSegment(ctx, item);
      } else if (item.type == GraphController.CIRCLE) {
        this.drawCircle(ctx, item);
      } else if (item.type == GraphController.IMAGE) {
        this.drawImage(ctx, item);
      }
    }
  },
  drawLineSegment: function(ctx, seg) {
    var start = this.pointToView(seg.start);
    var end = this.pointToView(seg.end);
    ctx.beginPath();
    ctx.strokeStyle = seg.color;
    ctx.moveTo(start.xPos, start.yPos);
    ctx.lineTo(end.xPos, end.yPos);
    ctx.stroke();
  },
  drawCircle: function(ctx, item) {
    var pt = this.pointToView(item.center)
    var radius = 3;
    if (item.radius) {
      radius = Math.max(this.radiusToView(item.radius), 3);
    }
    var fillColor = item.fillColor;
    if (this.highlightSelected && item === this.selected) {
      fillColor = 'red';
    }
    ctx.beginPath();
    ctx.strokeStyle = item.color;
    ctx.arc(pt.xPos, pt.yPos, radius, 0, Math.PI * 2.0, true);
    ctx.closePath();
    if (fillColor) {
      ctx.fillStyle = fillColor;
      ctx.fill();
    }
    if (item.color) {
      if (item.thickness) {
        ctx.lineWidth = item.thickness;
      }
      ctx.strokeStyle = item.color;
      ctx.stroke();
    }
    if (item.label) {
      ctx.fillStyle = item.labelColor || item.color;
      ctx.fillText(item.label, pt.xPos, pt.yPos);
    }
  },
  drawImage: function(ctx, item) {
    var start = this.pointToView(item.start);
    var end = this.pointToView(item.end);
    var width = end.xPos - start.xPos;
    var height = end.yPos - start.yPos;
    ctx.drawImage(item.image, start.xPos, start.yPos, width, height);
  },
  radiusToView: function(radius) {
    return radius * Math.min(
        this.canvas.width / (this.xMax - this.xMin),
        this.canvas.height / (this.yMax - this.yMin));
  },
  pointToView: function(pt) {
    var arr = [pt.xPos, pt.yPos];
    var fromMin = [this.xMin, this.yMin];
    var fromMax = [this.xMax, this.yMax];
    var toMax = [this.canvas.width, this.canvas.height];
    for (var i = 0; i < 2; i++) {
      arr[i] = (arr[i] - fromMin[i]) * toMax[i] / (fromMax[i] - fromMin[i]);
    }
    return {'xPos': arr[0], 'yPos': arr[1]};
  },
  pointFromView: function(pt) {
    return {
      'xPos': this.xMin + (this.xMax - this.xMin) * pt.xPos/this.canvas.width,
      'yPos': this.yMin + (this.yMax - this.yMin) * pt.yPos/this.canvas.height};
  }
};
