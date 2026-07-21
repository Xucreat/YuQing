import { c as createTextStyle$1, S as SeriesModel, C as ChartView, u as use, i as install, a as install$1, b as installLabelLayout, d as createDimensions, e as SeriesData, Z as ZRText, f as enableHoverEmphasis, r as registerLayout, g as getLayoutRect, l as linearMap, h as registerPreprocessor, j as isArray, k as each, m as capitalFirst, n as init, L as LinearGradient } from './index-C0N1mBNY.js';
import { d as defineComponent, c as createElementBlock, F as Fragment, i as renderList, o as openBlock, n as normalizeClass, t as toDisplayString, _ as _export_sfc, a as createBaseVNode, j as computed, k as normalizeStyle, l as usePermission, m as watch, p as onMounted, q as nextTick, s as onBeforeUnmount, w as withDirectives, e as createTextVNode, x as unref, y as createBlock, z as withCtx, A as createCommentVNode, B as createVNode, r as ref, f as reactive, g as api, E as ElMessage, C as resolveComponent, D as resolveDirective } from './index-Dpnq6Xd3.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-R0-NMbt_.js';

function createTextStyle(textStyleModel, opts) {
  opts = opts || {};
  return createTextStyle$1(textStyleModel, null, null, opts.state !== 'normal');
}

function extendSeriesModel(proto) {
  var Model = SeriesModel.extend(proto);
  SeriesModel.registerClass(Model);
  return Model;
}
function extendChartView(proto) {
  var View = ChartView.extend(proto);
  ChartView.registerClass(View);
  return View;
}

use([install, install$1]);
use(installLabelLayout);

extendSeriesModel({
  type: 'series.wordCloud',

  visualStyleAccessPath: 'textStyle',
  visualStyleMapper: function (model) {
    return {
      fill: model.get('color')
    };
  },
  visualDrawType: 'fill',

  optionUpdated: function () {
    var option = this.option;
    option.gridSize = Math.max(Math.floor(option.gridSize), 4);
  },

  getInitialData: function (option, ecModel) {
    var dimensions = createDimensions(option.data, {
      coordDimensions: ['value']
    });
    var list = new SeriesData(dimensions, this);
    list.initData(option.data);
    return list;
  },

  // Most of options are from https://github.com/timdream/wordcloud2.js/blob/gh-pages/API.md
  defaultOption: {
    maskImage: null,

    // Shape can be 'circle', 'cardioid', 'diamond', 'triangle-forward', 'triangle', 'pentagon', 'star'
    shape: 'circle',
    keepAspect: false,

    left: 'center',

    top: 'center',

    width: '70%',

    height: '80%',

    sizeRange: [12, 60],

    rotationRange: [-90, 90],

    rotationStep: 45,

    gridSize: 8,

    drawOutOfBound: false,
    shrinkToFit: false,

    textStyle: {
      fontWeight: 'normal'
    }
  }
});

extendChartView({
  type: 'wordCloud',

  render: function (seriesModel, ecModel, api) {
    var group = this.group;
    group.removeAll();

    var data = seriesModel.getData();

    var gridSize = seriesModel.get('gridSize');

    seriesModel.layoutInstance.ondraw = function (text, size, dataIdx, drawn) {
      var itemModel = data.getItemModel(dataIdx);
      var textStyleModel = itemModel.getModel('textStyle');

      var textEl = new ZRText({
        style: createTextStyle(textStyleModel),
        scaleX: 1 / drawn.info.mu,
        scaleY: 1 / drawn.info.mu,
        x: (drawn.gx + drawn.info.gw / 2) * gridSize,
        y: (drawn.gy + drawn.info.gh / 2) * gridSize,
        rotation: drawn.rot
      });
      textEl.setStyle({
        x: drawn.info.fillTextOffsetX,
        y: drawn.info.fillTextOffsetY + size * 0.5,
        text: text,
        verticalAlign: 'middle',
        fill: data.getItemVisual(dataIdx, 'style').fill,
        fontSize: size
      });

      group.add(textEl);

      data.setItemGraphicEl(dataIdx, textEl);

      textEl.ensureState('emphasis').style = createTextStyle(
        itemModel.getModel(['emphasis', 'textStyle']),
        {
          state: 'emphasis'
        }
      );
      textEl.ensureState('blur').style = createTextStyle(
        itemModel.getModel(['blur', 'textStyle']),
        {
          state: 'blur'
        }
      );

      enableHoverEmphasis(
        textEl,
        itemModel.get(['emphasis', 'focus']),
        itemModel.get(['emphasis', 'blurScope'])
      );

      textEl.stateTransition = {
        duration: seriesModel.get('animation')
          ? seriesModel.get(['stateAnimation', 'duration'])
          : 0,
        easing: seriesModel.get(['stateAnimation', 'easing'])
      };
      // TODO
      textEl.__highDownDispatcher = true;
    };

    this._model = seriesModel;
  },

  remove: function () {
    this.group.removeAll();

    this._model.layoutInstance.dispose();
  },

  dispose: function () {
    this._model.layoutInstance.dispose();
  }
});

/*!
 * wordcloud2.js
 * http://timdream.org/wordcloud2.js/
 *
 * Copyright 2011 - 2019 Tim Guan-tin Chien and contributors.
 * Released under the MIT license
 */


// setImmediate
if (!window.setImmediate) {
  window.setImmediate = (function setupSetImmediate() {
    return (
      window.msSetImmediate ||
      window.webkitSetImmediate ||
      window.mozSetImmediate ||
      window.oSetImmediate ||
      (function setupSetZeroTimeout() {
        if (!window.postMessage || !window.addEventListener) {
          return null;
        }

        var callbacks = [undefined];
        var message = 'zero-timeout-message';

        // Like setTimeout, but only takes a function argument.  There's
        // no time argument (always zero) and no arguments (you have to
        // use a closure).
        var setZeroTimeout = function setZeroTimeout(callback) {
          var id = callbacks.length;
          callbacks.push(callback);
          window.postMessage(message + id.toString(36), '*');

          return id;
        };

        window.addEventListener(
          'message',
          function setZeroTimeoutMessage(evt) {
            // Skipping checking event source, retarded IE confused this window
            // object with another in the presence of iframe
            if (
              typeof evt.data !== 'string' ||
              evt.data.substr(0, message.length) !== message /* ||
            evt.source !== window */
            ) {
              return;
            }

            evt.stopImmediatePropagation();

            var id = parseInt(evt.data.substr(message.length), 36);
            if (!callbacks[id]) {
              return;
            }

            callbacks[id]();
            callbacks[id] = undefined;
          },
          true
        );

        /* specify clearImmediate() here since we need the scope */
        window.clearImmediate = function clearZeroTimeout(id) {
          if (!callbacks[id]) {
            return;
          }

          callbacks[id] = undefined;
        };

        return setZeroTimeout;
      })() ||
      // fallback
      function setImmediateFallback(fn) {
        window.setTimeout(fn, 0);
      }
    );
  })();
}

if (!window.clearImmediate) {
  window.clearImmediate = (function setupClearImmediate() {
    return (
      window.msClearImmediate ||
      window.webkitClearImmediate ||
      window.mozClearImmediate ||
      window.oClearImmediate ||
      // "clearZeroTimeout" is implement on the previous block ||
      // fallback
      function clearImmediateFallback(timer) {
        window.clearTimeout(timer);
      }
    );
  })();
}

// Check if WordCloud can run on this browser
var isSupported = (function isSupported() {
  var canvas = document.createElement('canvas');
  if (!canvas || !canvas.getContext) {
    return false;
  }

  var ctx = canvas.getContext('2d');
  if (!ctx) {
    return false;
  }
  if (!ctx.getImageData) {
    return false;
  }
  if (!ctx.fillText) {
    return false;
  }

  if (!Array.prototype.some) {
    return false;
  }
  if (!Array.prototype.push) {
    return false;
  }

  return true;
})();

// Find out if the browser impose minium font size by
// drawing small texts on a canvas and measure it's width.
var minFontSize = (function getMinFontSize() {
  if (!isSupported) {
    return;
  }

  var ctx = document.createElement('canvas').getContext('2d');

  // start from 20
  var size = 20;

  // two sizes to measure
  var hanWidth, mWidth;

  while (size) {
    ctx.font = size.toString(10) + 'px sans-serif';
    if (
      ctx.measureText('\uFF37').width === hanWidth &&
      ctx.measureText('m').width === mWidth
    ) {
      return size + 1;
    }

    hanWidth = ctx.measureText('\uFF37').width;
    mWidth = ctx.measureText('m').width;

    size--;
  }

  return 0;
})();

var getItemExtraData = function (item) {
  if (Array.isArray(item)) {
    var itemCopy = item.slice();
    // remove data we already have (word and weight)
    itemCopy.splice(0, 2);
    return itemCopy;
  } else {
    return [];
  }
};

// Based on http://jsfromhell.com/array/shuffle
var shuffleArray = function shuffleArray(arr) {
  for (var j, x, i = arr.length; i; ) {
    j = Math.floor(Math.random() * i);
    x = arr[--i];
    arr[i] = arr[j];
    arr[j] = x;
  }
  return arr;
};

var timer = {};
var WordCloud = function WordCloud(elements, options) {
  if (!isSupported) {
    return;
  }

  var timerId = Math.floor(Math.random() * Date.now());

  if (!Array.isArray(elements)) {
    elements = [elements];
  }

  elements.forEach(function (el, i) {
    if (typeof el === 'string') {
      elements[i] = document.getElementById(el);
      if (!elements[i]) {
        throw new Error('The element id specified is not found.');
      }
    } else if (!el.tagName && !el.appendChild) {
      throw new Error(
        'You must pass valid HTML elements, or ID of the element.'
      );
    }
  });

  /* Default values to be overwritten by options object */
  var settings = {
    list: [],
    fontFamily:
      '"Trebuchet MS", "Heiti TC", "微軟正黑體", ' +
      '"Arial Unicode MS", "Droid Fallback Sans", sans-serif',
    fontWeight: 'normal',
    color: 'random-dark',
    minSize: 0, // 0 to disable
    weightFactor: 1,
    clearCanvas: true,
    backgroundColor: '#fff', // opaque white = rgba(255, 255, 255, 1)

    gridSize: 8,
    drawOutOfBound: false,
    shrinkToFit: false,
    origin: null,

    drawMask: false,
    maskColor: 'rgba(255,0,0,0.3)',
    maskGapWidth: 0.3,

    layoutAnimation: true,

    wait: 0,
    abortThreshold: 0, // disabled
    abort: function noop() {},

    minRotation: -Math.PI / 2,
    maxRotation: Math.PI / 2,
    rotationStep: 0.1,

    shuffle: true,
    rotateRatio: 0.1,

    shape: 'circle',
    ellipticity: 0.65,

    classes: null,

    hover: null,
    click: null
  };

  if (options) {
    for (var key in options) {
      if (key in settings) {
        settings[key] = options[key];
      }
    }
  }

  /* Convert weightFactor into a function */
  if (typeof settings.weightFactor !== 'function') {
    var factor = settings.weightFactor;
    settings.weightFactor = function weightFactor(pt) {
      return pt * factor; // in px
    };
  }

  /* Convert shape into a function */
  if (typeof settings.shape !== 'function') {
    switch (settings.shape) {
      case 'circle':
      /* falls through */
      default:
        // 'circle' is the default and a shortcut in the code loop.
        settings.shape = 'circle';
        break;

      case 'cardioid':
        settings.shape = function shapeCardioid(theta) {
          return 1 - Math.sin(theta);
        };
        break;

      /*
        To work out an X-gon, one has to calculate "m",
        where 1/(cos(2*PI/X)+m*sin(2*PI/X)) = 1/(cos(0)+m*sin(0))
        http://www.wolframalpha.com/input/?i=1%2F%28cos%282*PI%2FX%29%2Bm*sin%28
        2*PI%2FX%29%29+%3D+1%2F%28cos%280%29%2Bm*sin%280%29%29
        Copy the solution into polar equation r = 1/(cos(t') + m*sin(t'))
        where t' equals to mod(t, 2PI/X);
        */

      case 'diamond':
        // http://www.wolframalpha.com/input/?i=plot+r+%3D+1%2F%28cos%28mod+
        // %28t%2C+PI%2F2%29%29%2Bsin%28mod+%28t%2C+PI%2F2%29%29%29%2C+t+%3D
        // +0+..+2*PI
        settings.shape = function shapeSquare(theta) {
          var thetaPrime = theta % ((2 * Math.PI) / 4);
          return 1 / (Math.cos(thetaPrime) + Math.sin(thetaPrime));
        };
        break;

      case 'square':
        // http://www.wolframalpha.com/input/?i=plot+r+%3D+min(1%2Fabs(cos(t
        // )),1%2Fabs(sin(t)))),+t+%3D+0+..+2*PI
        settings.shape = function shapeSquare(theta) {
          return Math.min(
            1 / Math.abs(Math.cos(theta)),
            1 / Math.abs(Math.sin(theta))
          );
        };
        break;

      case 'triangle-forward':
        // http://www.wolframalpha.com/input/?i=plot+r+%3D+1%2F%28cos%28mod+
        // %28t%2C+2*PI%2F3%29%29%2Bsqrt%283%29sin%28mod+%28t%2C+2*PI%2F3%29
        // %29%29%2C+t+%3D+0+..+2*PI
        settings.shape = function shapeTriangle(theta) {
          var thetaPrime = theta % ((2 * Math.PI) / 3);
          return (
            1 / (Math.cos(thetaPrime) + Math.sqrt(3) * Math.sin(thetaPrime))
          );
        };
        break;

      case 'triangle':
      case 'triangle-upright':
        settings.shape = function shapeTriangle(theta) {
          var thetaPrime = (theta + (Math.PI * 3) / 2) % ((2 * Math.PI) / 3);
          return (
            1 / (Math.cos(thetaPrime) + Math.sqrt(3) * Math.sin(thetaPrime))
          );
        };
        break;

      case 'pentagon':
        settings.shape = function shapePentagon(theta) {
          var thetaPrime = (theta + 0.955) % ((2 * Math.PI) / 5);
          return 1 / (Math.cos(thetaPrime) + 0.726543 * Math.sin(thetaPrime));
        };
        break;

      case 'star':
        settings.shape = function shapeStar(theta) {
          var thetaPrime = (theta + 0.955) % ((2 * Math.PI) / 10);
          if (
            ((theta + 0.955) % ((2 * Math.PI) / 5)) - (2 * Math.PI) / 10 >=
            0
          ) {
            return (
              1 /
              (Math.cos((2 * Math.PI) / 10 - thetaPrime) +
                3.07768 * Math.sin((2 * Math.PI) / 10 - thetaPrime))
            );
          } else {
            return 1 / (Math.cos(thetaPrime) + 3.07768 * Math.sin(thetaPrime));
          }
        };
        break;
    }
  }

  /* Make sure gridSize is a whole number and is not smaller than 4px */
  settings.gridSize = Math.max(Math.floor(settings.gridSize), 4);

  /* shorthand */
  var g = settings.gridSize;
  var maskRectWidth = g - settings.maskGapWidth;

  /* normalize rotation settings */
  var rotationRange = Math.abs(settings.maxRotation - settings.minRotation);
  var minRotation = Math.min(settings.maxRotation, settings.minRotation);
  var rotationStep = settings.rotationStep;

  /* information/object available to all functions, set when start() */
  var grid, // 2d array containing filling information
    ngx,
    ngy, // width and height of the grid
    center, // position of the center of the cloud
    maxRadius;

  /* timestamp for measuring each putWord() action */
  var escapeTime;

  /* function for getting the color of the text */
  var getTextColor;
  function randomHslColor(min, max) {
    return (
      'hsl(' +
      (Math.random() * 360).toFixed() +
      ',' +
      (Math.random() * 30 + 70).toFixed() +
      '%,' +
      (Math.random() * (max - min) + min).toFixed() +
      '%)'
    );
  }
  switch (settings.color) {
    case 'random-dark':
      getTextColor = function getRandomDarkColor() {
        return randomHslColor(10, 50);
      };
      break;

    case 'random-light':
      getTextColor = function getRandomLightColor() {
        return randomHslColor(50, 90);
      };
      break;

    default:
      if (typeof settings.color === 'function') {
        getTextColor = settings.color;
      }
      break;
  }

  /* function for getting the font-weight of the text */
  var getTextFontWeight;
  if (typeof settings.fontWeight === 'function') {
    getTextFontWeight = settings.fontWeight;
  }

  /* function for getting the classes of the text */
  var getTextClasses = null;
  if (typeof settings.classes === 'function') {
    getTextClasses = settings.classes;
  }

  /* Interactive */
  var interactive = false;
  var infoGrid = [];
  var hovered;

  var getInfoGridFromMouseTouchEvent = function getInfoGridFromMouseTouchEvent(
    evt
  ) {
    var canvas = evt.currentTarget;
    var rect = canvas.getBoundingClientRect();
    var clientX;
    var clientY;
    /** Detect if touches are available */
    if (evt.touches) {
      clientX = evt.touches[0].clientX;
      clientY = evt.touches[0].clientY;
    } else {
      clientX = evt.clientX;
      clientY = evt.clientY;
    }
    var eventX = clientX - rect.left;
    var eventY = clientY - rect.top;

    var x = Math.floor((eventX * (canvas.width / rect.width || 1)) / g);
    var y = Math.floor((eventY * (canvas.height / rect.height || 1)) / g);

    if (!infoGrid[x]) {
      return null
    }

    return infoGrid[x][y];
  };

  var wordcloudhover = function wordcloudhover(evt) {
    var info = getInfoGridFromMouseTouchEvent(evt);

    if (hovered === info) {
      return;
    }

    hovered = info;
    if (!info) {
      settings.hover(undefined, undefined, evt);

      return;
    }

    settings.hover(info.item, info.dimension, evt);
  };

  var wordcloudclick = function wordcloudclick(evt) {
    var info = getInfoGridFromMouseTouchEvent(evt);
    if (!info) {
      return;
    }

    settings.click(info.item, info.dimension, evt);
    evt.preventDefault();
  };

  /* Get points on the grid for a given radius away from the center */
  var pointsAtRadius = [];
  var getPointsAtRadius = function getPointsAtRadius(radius) {
    if (pointsAtRadius[radius]) {
      return pointsAtRadius[radius];
    }

    // Look for these number of points on each radius
    var T = radius * 8;

    // Getting all the points at this radius
    var t = T;
    var points = [];

    if (radius === 0) {
      points.push([center[0], center[1], 0]);
    }

    while (t--) {
      // distort the radius to put the cloud in shape
      var rx = 1;
      if (settings.shape !== 'circle') {
        rx = settings.shape((t / T) * 2 * Math.PI); // 0 to 1
      }

      // Push [x, y, t]; t is used solely for getTextColor()
      points.push([
        center[0] + radius * rx * Math.cos((-t / T) * 2 * Math.PI),
        center[1] +
          radius * rx * Math.sin((-t / T) * 2 * Math.PI) * settings.ellipticity,
        (t / T) * 2 * Math.PI
      ]);
    }

    pointsAtRadius[radius] = points;
    return points;
  };

  /* Return true if we had spent too much time */
  var exceedTime = function exceedTime() {
    return (
      settings.abortThreshold > 0 &&
      new Date().getTime() - escapeTime > settings.abortThreshold
    );
  };

  /* Get the deg of rotation according to settings, and luck. */
  var getRotateDeg = function getRotateDeg() {
    if (settings.rotateRatio === 0) {
      return 0;
    }

    if (Math.random() > settings.rotateRatio) {
      return 0;
    }

    if (rotationRange === 0) {
      return minRotation;
    }

    return minRotation + Math.round(Math.random() * rotationRange / rotationStep) * rotationStep;
  };

  var getTextInfo = function getTextInfo(
    word,
    weight,
    rotateDeg,
    extraDataArray
  ) {
    var fontSize = settings.weightFactor(weight);
    if (fontSize <= settings.minSize) {
      return false;
    }

    // Scale factor here is to make sure fillText is not limited by
    // the minium font size set by browser.
    // It will always be 1 or 2n.
    var mu = 1;
    if (fontSize < minFontSize) {
      mu = (function calculateScaleFactor() {
        var mu = 2;
        while (mu * fontSize < minFontSize) {
          mu += 2;
        }
        return mu;
      })();
    }

    // Get fontWeight that will be used to set fctx.font
    var fontWeight;
    if (getTextFontWeight) {
      fontWeight = getTextFontWeight(word, weight, fontSize, extraDataArray);
    } else {
      fontWeight = settings.fontWeight;
    }

    var fcanvas = document.createElement('canvas');
    var fctx = fcanvas.getContext('2d', { willReadFrequently: true });

    fctx.font =
      fontWeight +
      ' ' +
      (fontSize * mu).toString(10) +
      'px ' +
      settings.fontFamily;

    // Estimate the dimension of the text with measureText().
    var fw = fctx.measureText(word).width / mu;
    var fh =
      Math.max(
        fontSize * mu,
        fctx.measureText('m').width,
        fctx.measureText('\uFF37').width
      ) / mu;

    // Create a boundary box that is larger than our estimates,
    // so text don't get cut of (it sill might)
    var boxWidth = fw + fh * 2;
    var boxHeight = fh * 3;
    var fgw = Math.ceil(boxWidth / g);
    var fgh = Math.ceil(boxHeight / g);
    boxWidth = fgw * g;
    boxHeight = fgh * g;

    // Calculate the proper offsets to make the text centered at
    // the preferred position.

    // This is simply half of the width.
    var fillTextOffsetX = -fw / 2;
    // Instead of moving the box to the exact middle of the preferred
    // position, for Y-offset we move 0.4 instead, so Latin alphabets look
    // vertical centered.
    var fillTextOffsetY = -fh * 0.4;

    // Calculate the actual dimension of the canvas, considering the rotation.
    var cgh = Math.ceil(
      (boxWidth * Math.abs(Math.sin(rotateDeg)) +
        boxHeight * Math.abs(Math.cos(rotateDeg))) /
        g
    );
    var cgw = Math.ceil(
      (boxWidth * Math.abs(Math.cos(rotateDeg)) +
        boxHeight * Math.abs(Math.sin(rotateDeg))) /
        g
    );
    var width = cgw * g;
    var height = cgh * g;

    fcanvas.setAttribute('width', width);
    fcanvas.setAttribute('height', height);

    // Scale the canvas with |mu|.
    fctx.scale(1 / mu, 1 / mu);
    fctx.translate((width * mu) / 2, (height * mu) / 2);
    fctx.rotate(-rotateDeg);

    // Once the width/height is set, ctx info will be reset.
    // Set it again here.
    fctx.font =
      fontWeight +
      ' ' +
      (fontSize * mu).toString(10) +
      'px ' +
      settings.fontFamily;

    // Fill the text into the fcanvas.
    // XXX: We cannot because textBaseline = 'top' here because
    // Firefox and Chrome uses different default line-height for canvas.
    // Please read https://bugzil.la/737852#c6.
    // Here, we use textBaseline = 'middle' and draw the text at exactly
    // 0.5 * fontSize lower.
    fctx.fillStyle = '#000';
    fctx.textBaseline = 'middle';
    fctx.fillText(
      word,
      fillTextOffsetX * mu,
      (fillTextOffsetY + fontSize * 0.5) * mu
    );

    // Get the pixels of the text
    var imageData = fctx.getImageData(0, 0, width, height).data;

    if (exceedTime()) {
      return false;
    }

    // Read the pixels and save the information to the occupied array
    var occupied = [];
    var gx = cgw;
    var gy, x, y;
    var bounds = [cgh / 2, cgw / 2, cgh / 2, cgw / 2];
    while (gx--) {
      gy = cgh;
      while (gy--) {
        y = g;
        /* eslint no-labels: ['error', { 'allowLoop': true }] */
        singleGridLoop: while (y--) {
          x = g;
          while (x--) {
            if (imageData[((gy * g + y) * width + (gx * g + x)) * 4 + 3]) {
              occupied.push([gx, gy]);

              if (gx < bounds[3]) {
                bounds[3] = gx;
              }
              if (gx > bounds[1]) {
                bounds[1] = gx;
              }
              if (gy < bounds[0]) {
                bounds[0] = gy;
              }
              if (gy > bounds[2]) {
                bounds[2] = gy;
              }
              break singleGridLoop;
            }
          }
        }
      }
    }

    // Return information needed to create the text on the real canvas
    return {
      mu: mu,
      occupied: occupied,
      bounds: bounds,
      gw: cgw,
      gh: cgh,
      fillTextOffsetX: fillTextOffsetX,
      fillTextOffsetY: fillTextOffsetY,
      fillTextWidth: fw,
      fillTextHeight: fh,
      fontSize: fontSize
    };
  };

  /* Determine if there is room available in the given dimension */
  var canFitText = function canFitText(gx, gy, gw, gh, occupied) {
    // Go through the occupied points,
    // return false if the space is not available.
    var i = occupied.length;
    while (i--) {
      var px = gx + occupied[i][0];
      var py = gy + occupied[i][1];

      if (px >= ngx || py >= ngy || px < 0 || py < 0) {
        if (!settings.drawOutOfBound) {
          return false;
        }
        continue;
      }

      if (!grid[px][py]) {
        return false;
      }
    }
    return true;
  };

  /* Actually draw the text on the grid */
  var drawText = function drawText(
    gx,
    gy,
    info,
    word,
    weight,
    distance,
    theta,
    rotateDeg,
    attributes,
    extraDataArray
  ) {
    var fontSize = info.fontSize;
    var color;
    if (getTextColor) {
      color = getTextColor(
        word,
        weight,
        fontSize,
        distance,
        theta,
        extraDataArray
      );
    } else {
      color = settings.color;
    }

    // get fontWeight that will be used to set ctx.font and font style rule
    var fontWeight;
    if (getTextFontWeight) {
      fontWeight = getTextFontWeight(word, weight, fontSize, extraDataArray);
    } else {
      fontWeight = settings.fontWeight;
    }

    var classes;
    if (getTextClasses) {
      classes = getTextClasses(word, weight, fontSize, extraDataArray);
    } else {
      classes = settings.classes;
    }

    elements.forEach(function (el) {
      if (el.getContext) {
        var ctx = el.getContext('2d');
        var mu = info.mu;

        // Save the current state before messing it
        ctx.save();
        ctx.scale(1 / mu, 1 / mu);

        ctx.font =
          fontWeight +
          ' ' +
          (fontSize * mu).toString(10) +
          'px ' +
          settings.fontFamily;
        ctx.fillStyle = color;

        // Translate the canvas position to the origin coordinate of where
        // the text should be put.
        ctx.translate((gx + info.gw / 2) * g * mu, (gy + info.gh / 2) * g * mu);

        if (rotateDeg !== 0) {
          ctx.rotate(-rotateDeg);
        }

        // Finally, fill the text.

        // XXX: We cannot because textBaseline = 'top' here because
        // Firefox and Chrome uses different default line-height for canvas.
        // Please read https://bugzil.la/737852#c6.
        // Here, we use textBaseline = 'middle' and draw the text at exactly
        // 0.5 * fontSize lower.
        ctx.textBaseline = 'middle';
        ctx.fillText(
          word,
          info.fillTextOffsetX * mu,
          (info.fillTextOffsetY + fontSize * 0.5) * mu
        );

        // The below box is always matches how <span>s are positioned
        /* ctx.strokeRect(info.fillTextOffsetX, info.fillTextOffsetY,
            info.fillTextWidth, info.fillTextHeight); */

        // Restore the state.
        ctx.restore();
      } else {
        // drawText on DIV element
        var span = document.createElement('span');
        var transformRule = '';
        transformRule = 'rotate(' + (-rotateDeg / Math.PI) * 180 + 'deg) ';
        if (info.mu !== 1) {
          transformRule +=
            'translateX(-' +
            info.fillTextWidth / 4 +
            'px) ' +
            'scale(' +
            1 / info.mu +
            ')';
        }
        var styleRules = {
          position: 'absolute',
          display: 'block',
          font:
            fontWeight + ' ' + fontSize * info.mu + 'px ' + settings.fontFamily,
          left: (gx + info.gw / 2) * g + info.fillTextOffsetX + 'px',
          top: (gy + info.gh / 2) * g + info.fillTextOffsetY + 'px',
          width: info.fillTextWidth + 'px',
          height: info.fillTextHeight + 'px',
          lineHeight: fontSize + 'px',
          whiteSpace: 'nowrap',
          transform: transformRule,
          webkitTransform: transformRule,
          msTransform: transformRule,
          transformOrigin: '50% 40%',
          webkitTransformOrigin: '50% 40%',
          msTransformOrigin: '50% 40%'
        };
        if (color) {
          styleRules.color = color;
        }
        span.textContent = word;
        for (var cssProp in styleRules) {
          span.style[cssProp] = styleRules[cssProp];
        }
        if (attributes) {
          for (var attribute in attributes) {
            span.setAttribute(attribute, attributes[attribute]);
          }
        }
        if (classes) {
          span.className += classes;
        }
        el.appendChild(span);
      }
    });
  };

  /* Help function to updateGrid */
  var fillGridAt = function fillGridAt(x, y, drawMask, dimension, item) {
    if (x >= ngx || y >= ngy || x < 0 || y < 0) {
      return;
    }

    grid[x][y] = false;

    if (drawMask) {
      var ctx = elements[0].getContext('2d');
      ctx.fillRect(x * g, y * g, maskRectWidth, maskRectWidth);
    }

    if (interactive) {
      infoGrid[x][y] = { item: item, dimension: dimension };
    }
  };

  /* Update the filling information of the given space with occupied points.
       Draw the mask on the canvas if necessary. */
  var updateGrid = function updateGrid(gx, gy, gw, gh, info, item) {
    var occupied = info.occupied;
    var drawMask = settings.drawMask;
    var ctx;
    if (drawMask) {
      ctx = elements[0].getContext('2d');
      ctx.save();
      ctx.fillStyle = settings.maskColor;
    }

    var dimension;
    if (interactive) {
      var bounds = info.bounds;
      dimension = {
        x: (gx + bounds[3]) * g,
        y: (gy + bounds[0]) * g,
        w: (bounds[1] - bounds[3] + 1) * g,
        h: (bounds[2] - bounds[0] + 1) * g
      };
    }

    var i = occupied.length;
    while (i--) {
      var px = gx + occupied[i][0];
      var py = gy + occupied[i][1];

      if (px >= ngx || py >= ngy || px < 0 || py < 0) {
        continue;
      }

      fillGridAt(px, py, drawMask, dimension, item);
    }

    if (drawMask) {
      ctx.restore();
    }
  };

  /* putWord() processes each item on the list,
       calculate it's size and determine it's position, and actually
       put it on the canvas. */
  var putWord = function putWord(item, loopIndex) {
    if (loopIndex > 20) {
      return null;
    }

    var word, weight, attributes;
    if (Array.isArray(item)) {
      word = item[0];
      weight = item[1];
    } else {
      word = item.word;
      weight = item.weight;
      attributes = item.attributes;
    }
    var rotateDeg = getRotateDeg();

    var extraDataArray = getItemExtraData(item);

    // get info needed to put the text onto the canvas
    var info = getTextInfo(word, weight, rotateDeg, extraDataArray);

    // not getting the info means we shouldn't be drawing this one.
    if (!info) {
      return false;
    }

    if (exceedTime()) {
      return false;
    }

    // If drawOutOfBound is set to false,
    // skip the loop if we have already know the bounding box of
    // word is larger than the canvas.
    if (!settings.drawOutOfBound && !settings.shrinkToFit) {
      var bounds = info.bounds;
      if (bounds[1] - bounds[3] + 1 > ngx || bounds[2] - bounds[0] + 1 > ngy) {
        return false;
      }
    }

    // Determine the position to put the text by
    // start looking for the nearest points
    var r = maxRadius + 1;

    var tryToPutWordAtPoint = function (gxy) {
      var gx = Math.floor(gxy[0] - info.gw / 2);
      var gy = Math.floor(gxy[1] - info.gh / 2);
      var gw = info.gw;
      var gh = info.gh;

      // If we cannot fit the text at this position, return false
      // and go to the next position.
      if (!canFitText(gx, gy, gw, gh, info.occupied)) {
        return false;
      }

      // Actually put the text on the canvas
      drawText(
        gx,
        gy,
        info,
        word,
        weight,
        maxRadius - r,
        gxy[2],
        rotateDeg,
        attributes,
        extraDataArray
      );

      // Mark the spaces on the grid as filled
      updateGrid(gx, gy, gw, gh, info, item);

      return {
        gx: gx,
        gy: gy,
        rot: rotateDeg,
        info: info
      };
    };

    while (r--) {
      var points = getPointsAtRadius(maxRadius - r);

      if (settings.shuffle) {
        points = [].concat(points);
        shuffleArray(points);
      }

      // Try to fit the words by looking at each point.
      // array.some() will stop and return true
      // when putWordAtPoint() returns true.
      for (var i = 0; i < points.length; i++) {
        var res = tryToPutWordAtPoint(points[i]);
        if (res) {
          return res;
        }
      }

      // var drawn = points.some(tryToPutWordAtPoint);
      // if (drawn) {
      //   // leave putWord() and return true
      //   return true;
      // }
    }

    if (settings.shrinkToFit) {
      if (Array.isArray(item)) {
        item[1] = (item[1] * 3) / 4;
      } else {
        item.weight = (item.weight * 3) / 4;
      }
      return putWord(item, loopIndex + 1);
    }

    // we tried all distances but text won't fit, return null
    return null;
  };

  /* Send DOM event to all elements. Will stop sending event and return
       if the previous one is canceled (for cancelable events). */
  var sendEvent = function sendEvent(type, cancelable, details) {
    if (cancelable) {
      return !elements.some(function (el) {
        var event = new CustomEvent(type, {
          detail: details || {}
        });
        return !el.dispatchEvent(event);
      }, this);
    } else {
      elements.forEach(function (el) {
        var event = new CustomEvent(type, {
          detail: details || {}
        });
        el.dispatchEvent(event);
      }, this);
    }
  };

  /* Start drawing on a canvas */
  var start = function start() {
    // For dimensions, clearCanvas etc.,
    // we only care about the first element.
    var canvas = elements[0];

    if (canvas.getContext) {
      ngx = Math.ceil(canvas.width / g);
      ngy = Math.ceil(canvas.height / g);
    } else {
      var rect = canvas.getBoundingClientRect();
      ngx = Math.ceil(rect.width / g);
      ngy = Math.ceil(rect.height / g);
    }

    // Sending a wordcloudstart event which cause the previous loop to stop.
    // Do nothing if the event is canceled.
    if (!sendEvent('wordcloudstart', true)) {
      return;
    }

    // Determine the center of the word cloud
    center = settings.origin
      ? [settings.origin[0] / g, settings.origin[1] / g]
      : [ngx / 2, ngy / 2];

    // Maxium radius to look for space
    maxRadius = Math.floor(Math.sqrt(ngx * ngx + ngy * ngy));

    /* Clear the canvas only if the clearCanvas is set,
         if not, update the grid to the current canvas state */
    grid = [];

    var gx, gy, i;
    if (!canvas.getContext || settings.clearCanvas) {
      elements.forEach(function (el) {
        if (el.getContext) {
          var ctx = el.getContext('2d');
          ctx.fillStyle = settings.backgroundColor;
          ctx.clearRect(0, 0, ngx * (g + 1), ngy * (g + 1));
          ctx.fillRect(0, 0, ngx * (g + 1), ngy * (g + 1));
        } else {
          el.textContent = '';
          el.style.backgroundColor = settings.backgroundColor;
          el.style.position = 'relative';
        }
      });

      /* fill the grid with empty state */
      gx = ngx;
      while (gx--) {
        grid[gx] = [];
        gy = ngy;
        while (gy--) {
          grid[gx][gy] = true;
        }
      }
    } else {
      /* Determine bgPixel by creating
           another canvas and fill the specified background color. */
      var bctx = document.createElement('canvas').getContext('2d');

      bctx.fillStyle = settings.backgroundColor;
      bctx.fillRect(0, 0, 1, 1);
      var bgPixel = bctx.getImageData(0, 0, 1, 1).data;

      /* Read back the pixels of the canvas we got to tell which part of the
           canvas is empty.
           (no clearCanvas only works with a canvas, not divs) */
      var imageData = canvas
        .getContext('2d')
        .getImageData(0, 0, ngx * g, ngy * g).data;

      gx = ngx;
      var x, y;
      while (gx--) {
        grid[gx] = [];
        gy = ngy;
        while (gy--) {
          y = g;
          /* eslint no-labels: ['error', { 'allowLoop': true }] */
          singleGridLoop: while (y--) {
            x = g;
            while (x--) {
              i = 4;
              while (i--) {
                if (
                  imageData[((gy * g + y) * ngx * g + (gx * g + x)) * 4 + i] !==
                  bgPixel[i]
                ) {
                  grid[gx][gy] = false;
                  break singleGridLoop;
                }
              }
            }
          }
          if (grid[gx][gy] !== false) {
            grid[gx][gy] = true;
          }
        }
      }

      imageData = bctx = bgPixel = undefined;
    }

    // fill the infoGrid with empty state if we need it
    if (settings.hover || settings.click) {
      interactive = true;

      /* fill the grid with empty state */
      gx = ngx + 1;
      while (gx--) {
        infoGrid[gx] = [];
      }

      if (settings.hover) {
        canvas.addEventListener('mousemove', wordcloudhover);
      }

      if (settings.click) {
        canvas.addEventListener('click', wordcloudclick);
        canvas.addEventListener('touchstart', wordcloudclick);
        canvas.addEventListener('touchend', function (e) {
          e.preventDefault();
        });
        canvas.style.webkitTapHighlightColor = 'rgba(0, 0, 0, 0)';
      }

      canvas.addEventListener('wordcloudstart', function stopInteraction() {
        canvas.removeEventListener('wordcloudstart', stopInteraction);

        canvas.removeEventListener('mousemove', wordcloudhover);
        canvas.removeEventListener('click', wordcloudclick);
        hovered = undefined;
      });
    }

    i = 0;
    var loopingFunction, stoppingFunction;
    var layouting = true;
    if (!settings.layoutAnimation) {
      loopingFunction = function (cb) {
        cb();
      };
      stoppingFunction = function () {
        layouting = false;
      };
    } else if (settings.wait !== 0) {
      loopingFunction = window.setTimeout;
      stoppingFunction = window.clearTimeout;
    } else {
      loopingFunction = window.setImmediate;
      stoppingFunction = window.clearImmediate;
    }

    var addEventListener = function addEventListener(type, listener) {
      elements.forEach(function (el) {
        el.addEventListener(type, listener);
      }, this);
    };

    var removeEventListener = function removeEventListener(type, listener) {
      elements.forEach(function (el) {
        el.removeEventListener(type, listener);
      }, this);
    };

    var anotherWordCloudStart = function anotherWordCloudStart() {
      removeEventListener('wordcloudstart', anotherWordCloudStart);
      stoppingFunction(timer[timerId]);
    };

    addEventListener('wordcloudstart', anotherWordCloudStart);

    // At least wait the following code before call the first iteration.
    timer[timerId] = (settings.layoutAnimation ? loopingFunction : setTimeout)(
      function loop() {
        if (!layouting) {
          return;
        }
        if (i >= settings.list.length) {
          stoppingFunction(timer[timerId]);
          sendEvent('wordcloudstop', false);
          removeEventListener('wordcloudstart', anotherWordCloudStart);
          delete timer[timerId];
          return;
        }
        escapeTime = new Date().getTime();
        var drawn = putWord(settings.list[i], 0);
        var canceled = !sendEvent('wordclouddrawn', true, {
          item: settings.list[i],
          drawn: drawn
        });
        if (exceedTime() || canceled) {
          stoppingFunction(timer[timerId]);
          settings.abort();
          sendEvent('wordcloudabort', false);
          sendEvent('wordcloudstop', false);
          removeEventListener('wordcloudstart', anotherWordCloudStart);
          return;
        }
        i++;
        timer[timerId] = loopingFunction(loop, settings.wait);
      },
      settings.wait
    );
  };

  // All set, start the drawing
  start();
};

WordCloud.isSupported = isSupported;
WordCloud.minFontSize = minFontSize;

if (!WordCloud.isSupported) {
  throw new Error('Sorry your browser not support wordCloud');
}

// https://github.com/timdream/wordcloud2.js/blob/c236bee60436e048949f9becc4f0f67bd832dc5c/index.js#L233
function updateCanvasMask(maskCanvas) {
  var ctx = maskCanvas.getContext('2d');
  var imageData = ctx.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
  var newImageData = ctx.createImageData(imageData);

  var toneSum = 0;
  var toneCnt = 0;
  for (var i = 0; i < imageData.data.length; i += 4) {
    var alpha = imageData.data[i + 3];
    if (alpha > 128) {
      var tone =
        imageData.data[i] + imageData.data[i + 1] + imageData.data[i + 2];
      toneSum += tone;
      ++toneCnt;
    }
  }
  var threshold = toneSum / toneCnt;

  for (var i = 0; i < imageData.data.length; i += 4) {
    var tone =
      imageData.data[i] + imageData.data[i + 1] + imageData.data[i + 2];
    var alpha = imageData.data[i + 3];

    if (alpha < 128 || tone > threshold) {
      // Area not to draw
      newImageData.data[i] = 0;
      newImageData.data[i + 1] = 0;
      newImageData.data[i + 2] = 0;
      newImageData.data[i + 3] = 0;
    } else {
      // Area to draw
      // The color must be same with backgroundColor
      newImageData.data[i] = 255;
      newImageData.data[i + 1] = 255;
      newImageData.data[i + 2] = 255;
      newImageData.data[i + 3] = 255;
    }
  }

  ctx.putImageData(newImageData, 0, 0);
}

registerLayout(function (ecModel, api) {
  ecModel.eachSeriesByType('wordCloud', function (seriesModel) {
    var gridRect = getLayoutRect(
      seriesModel.getBoxLayoutParams(),
      {
        width: api.getWidth(),
        height: api.getHeight()
      }
    );

    var keepAspect = seriesModel.get('keepAspect');
    var maskImage = seriesModel.get('maskImage');
    var ratio = maskImage ? maskImage.width / maskImage.height : 1;
    keepAspect && adjustRectAspect(gridRect, ratio);

    var data = seriesModel.getData();

    var canvas = document.createElement('canvas');
    canvas.width = gridRect.width;
    canvas.height = gridRect.height;

    var ctx = canvas.getContext('2d');
    if (maskImage) {
      try {
        ctx.drawImage(maskImage, 0, 0, canvas.width, canvas.height);
        updateCanvasMask(canvas);
      } catch (e) {
        console.error('Invalid mask image');
        console.error(e.toString());
      }
    }

    var sizeRange = seriesModel.get('sizeRange');
    var rotationRange = seriesModel.get('rotationRange');
    var valueExtent = data.getDataExtent('value');

    var DEGREE_TO_RAD = Math.PI / 180;
    var gridSize = seriesModel.get('gridSize');
    WordCloud(canvas, {
      list: data
        .mapArray('value', function (value, idx) {
          var itemModel = data.getItemModel(idx);
          return [
            data.getName(idx),
            itemModel.get('textStyle.fontSize', true) ||
              linearMap(value, valueExtent, sizeRange),
            idx
          ];
        })
        .sort(function (a, b) {
          // Sort from large to small in case there is no more room for more words
          return b[1] - a[1];
        }),
      fontFamily:
        seriesModel.get('textStyle.fontFamily') ||
        seriesModel.get('emphasis.textStyle.fontFamily') ||
        ecModel.get('textStyle.fontFamily'),
      fontWeight:
        seriesModel.get('textStyle.fontWeight') ||
        seriesModel.get('emphasis.textStyle.fontWeight') ||
        ecModel.get('textStyle.fontWeight'),

      gridSize: gridSize,

      ellipticity: gridRect.height / gridRect.width,

      minRotation: rotationRange[0] * DEGREE_TO_RAD,
      maxRotation: rotationRange[1] * DEGREE_TO_RAD,

      clearCanvas: !maskImage,

      rotateRatio: 1,

      rotationStep: seriesModel.get('rotationStep') * DEGREE_TO_RAD,

      drawOutOfBound: seriesModel.get('drawOutOfBound'),
      shrinkToFit: seriesModel.get('shrinkToFit'),

      layoutAnimation: seriesModel.get('layoutAnimation'),

      shuffle: false,

      shape: seriesModel.get('shape')
    });

    function onWordCloudDrawn(e) {
      var item = e.detail.item;
      if (e.detail.drawn && seriesModel.layoutInstance.ondraw) {
        e.detail.drawn.gx += gridRect.x / gridSize;
        e.detail.drawn.gy += gridRect.y / gridSize;
        seriesModel.layoutInstance.ondraw(
          item[0],
          item[1],
          item[2],
          e.detail.drawn
        );
      }
    }

    canvas.addEventListener('wordclouddrawn', onWordCloudDrawn);

    if (seriesModel.layoutInstance) {
      // Dispose previous
      seriesModel.layoutInstance.dispose();
    }

    seriesModel.layoutInstance = {
      ondraw: null,

      dispose: function () {
        canvas.removeEventListener('wordclouddrawn', onWordCloudDrawn);
        // Abort
        canvas.addEventListener('wordclouddrawn', function (e) {
          // Prevent default to cancle the event and stop the loop
          e.preventDefault();
        });
      }
    };
  });
});

registerPreprocessor(function (option) {
  var series = (option || {}).series;
  !isArray(series) && (series = series ? [series] : []);

  var compats = ['shadowColor', 'shadowBlur', 'shadowOffsetX', 'shadowOffsetY'];

  each(series, function (seriesItem) {
    if (seriesItem && seriesItem.type === 'wordCloud') {
      var textStyle = seriesItem.textStyle || {};

      compatTextStyle(textStyle.normal);
      compatTextStyle(textStyle.emphasis);
    }
  });

  function compatTextStyle(textStyle) {
    textStyle &&
      each(compats, function (key) {
        if (textStyle.hasOwnProperty(key)) {
          textStyle['text' + capitalFirst(key)] = textStyle[key];
        }
      });
  }
});

function adjustRectAspect(gridRect, aspect) {
  // var outerWidth = gridRect.width + gridRect.x * 2;
  // var outerHeight = gridRect.height + gridRect.y * 2;
  var width = gridRect.width;
  var height = gridRect.height;
  if (width > height * aspect) {
    gridRect.x += (width - height * aspect) / 2;
    gridRect.width = height * aspect;
  } else {
    gridRect.y += (height - width / aspect) / 2;
    gridRect.height = width / aspect;
  }
}

const _hoisted_1$2 = { class: "seg-group" };
const _hoisted_2$2 = ["onClick"];
const _sfc_main$2 = /* @__PURE__ */ defineComponent({
  __name: "SegmentedControl",
  props: {
    modelValue: {},
    options: {}
  },
  emits: ["update:modelValue"],
  setup(__props) {
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$2, [
        (openBlock(true), createElementBlock(Fragment, null, renderList(__props.options, (opt) => {
          return openBlock(), createElementBlock("button", {
            key: opt.value,
            class: normalizeClass(["seg-btn", { active: __props.modelValue === opt.value }]),
            onClick: ($event) => _ctx.$emit("update:modelValue", opt.value)
          }, toDisplayString(opt.label), 11, _hoisted_2$2);
        }), 128))
      ]);
    };
  }
});

const SegmentedControl = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-ae024c45"]]);

const _hoisted_1$1 = { class: "donut-wrap" };
const _hoisted_2$1 = {
  class: "donut-svg",
  viewBox: "0 0 140 140"
};
const _hoisted_3$1 = ["stroke", "stroke-dasharray", "stroke-dashoffset"];
const _hoisted_4$1 = {
  x: "70",
  y: "66",
  "text-anchor": "middle",
  "font-size": "28",
  "font-weight": "600",
  fill: "#1d1d1f"
};
const _hoisted_5$1 = { class: "donut-legends" };
const _sfc_main$1 = /* @__PURE__ */ defineComponent({
  __name: "SentimentDonut",
  props: {
    data: {}
  },
  setup(__props) {
    const props = __props;
    const total = computed(() => props.data.reduce((s, d) => s + d.count, 0));
    const circumference = 2 * Math.PI * 58;
    const segments = computed(() => {
      let offset = 0;
      return props.data.map((d) => {
        const pct = total.value > 0 ? d.count / total.value : 0;
        const dash = pct * circumference;
        const seg = {
          ...d,
          pct: Math.round(pct * 100),
          dashArray: dash || 0,
          dashOffset: -offset
        };
        offset += dash;
        return seg;
      });
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$1, [
        (openBlock(), createElementBlock("svg", _hoisted_2$1, [
          _cache[0] || (_cache[0] = createBaseVNode("circle", {
            cx: "70",
            cy: "70",
            r: "58",
            fill: "none",
            stroke: "#e8e8ed",
            "stroke-width": "16"
          }, null, -1)),
          (openBlock(true), createElementBlock(Fragment, null, renderList(segments.value, (seg, i) => {
            return openBlock(), createElementBlock("circle", {
              key: i,
              cx: "70",
              cy: "70",
              r: "58",
              fill: "none",
              stroke: seg.color,
              "stroke-width": "16",
              "stroke-dasharray": seg.dashArray + " " + (364.4 - seg.dashArray),
              "stroke-dashoffset": seg.dashOffset,
              "stroke-linecap": "round",
              transform: "rotate(-90 70 70)"
            }, null, 8, _hoisted_3$1);
          }), 128)),
          createBaseVNode("text", _hoisted_4$1, toDisplayString(total.value), 1),
          _cache[1] || (_cache[1] = createBaseVNode("text", {
            x: "70",
            y: "85",
            "text-anchor": "middle",
            "font-size": "10",
            fill: "#86868b"
          }, " 总计 ", -1))
        ])),
        createBaseVNode("div", _hoisted_5$1, [
          (openBlock(true), createElementBlock(Fragment, null, renderList(segments.value, (seg) => {
            return openBlock(), createElementBlock("div", {
              key: seg.label,
              class: "donut-legend"
            }, [
              createBaseVNode("span", {
                class: "dl-dot",
                style: normalizeStyle({ background: seg.color })
              }, null, 4),
              createBaseVNode("span", null, toDisplayString(seg.label), 1),
              createBaseVNode("i", null, toDisplayString(seg.pct) + "%", 1),
              createBaseVNode("b", null, toDisplayString(seg.count), 1)
            ]);
          }), 128))
        ])
      ]);
    };
  }
});

const SentimentDonut = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-1e1d467a"]]);

const _hoisted_1 = { class: "dashboard" };
const _hoisted_2 = { class: "stat-grid" };
const _hoisted_3 = { class: "card stat-card" };
const _hoisted_4 = { class: "s-value" };
const _hoisted_5 = { class: "card stat-card is-green" };
const _hoisted_6 = { class: "s-value" };
const _hoisted_7 = { class: "card stat-card is-red" };
const _hoisted_8 = { class: "s-value danger" };
const _hoisted_9 = { class: "card stat-card is-amber" };
const _hoisted_10 = { class: "s-value" };
const _hoisted_11 = { class: "card stat-card is-blue" };
const _hoisted_12 = {
  class: "s-value",
  style: { "font-size": "24px", "display": "flex", "align-items": "center", "gap": "8px" }
};
const _hoisted_13 = { style: { "font-size": "14px", "font-weight": "400" } };
const _hoisted_14 = { class: "s-foot-row" };
const _hoisted_15 = { class: "s-foot" };
const _hoisted_16 = { class: "sit-left" };
const _hoisted_17 = { class: "sit-level" };
const _hoisted_18 = { class: "sit-text" };
const _hoisted_19 = { class: "sit-kpis" };
const _hoisted_20 = { class: "sit-kpi" };
const _hoisted_21 = { class: "k" };
const _hoisted_22 = { class: "sit-kpi" };
const _hoisted_23 = { class: "k danger" };
const _hoisted_24 = { class: "sit-kpi" };
const _hoisted_25 = { class: "k" };
const _hoisted_26 = { class: "sit-kpi" };
const _hoisted_27 = { class: "k" };
const _hoisted_28 = { class: "sit-kpi" };
const _hoisted_29 = { class: "k" };
const _hoisted_30 = { class: "sit-action" };
const _hoisted_31 = { class: "content-grid" };
const _hoisted_32 = { class: "card card-pad-lg area-trend" };
const _hoisted_33 = { class: "chart-head" };
const _hoisted_34 = { class: "card card-pad-lg area-donut" };
const _hoisted_35 = { class: "card card-pad-lg area-source" };
const _hoisted_36 = { class: "card card-pad-lg area-cloud" };
const _hoisted_37 = { class: "card card-pad-lg feed-card area-feed" };
const _hoisted_38 = { class: "scroll-wrap" };
const _hoisted_39 = ["onClick"];
const _hoisted_40 = { class: "fi-body" };
const _hoisted_41 = { class: "fi-title" };
const _hoisted_42 = { class: "fi-meta" };
const _hoisted_43 = {
  key: 0,
  class: "feed-empty"
};
const _hoisted_44 = { class: "card card-pad-lg feed-card area-alert" };
const _hoisted_45 = { class: "scroll-wrap" };
const _hoisted_46 = ["title", "onClick"];
const _hoisted_47 = { class: "ai-body" };
const _hoisted_48 = { class: "ai-title" };
const _hoisted_49 = { class: "ai-meta" };
const _hoisted_50 = {
  key: 0,
  class: "feed-empty"
};
const _hoisted_51 = { class: "card card-pad-lg area-geo" };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Dashboard",
  setup(__props) {
    const { can } = usePermission();
    const detailVisible = ref(false);
    const detailId = ref(null);
    function goOpinion(id) {
      if (!id) return;
      detailId.value = id;
      detailVisible.value = true;
    }
    const loading = ref(false);
    const trendDays = ref(7);
    const segOptions = [
      { label: "7天", value: 7 },
      { label: "14天", value: 14 },
      { label: "30天", value: 30 }
    ];
    const stats = reactive({
      total: 0,
      today: 0,
      high_risk: 0,
      event_count: 0,
      trend: [],
      keywords: [],
      sources: [],
      sentiments: [],
      regions: []
    });
    const recentNews = ref([]);
    const alerts = ref([]);
    const doubledNews = computed(() => recentNews.value.length ? [...recentNews.value, ...recentNews.value] : []);
    const doubledAlerts = computed(() => alerts.value.length ? [...alerts.value, ...alerts.value] : []);
    const feedDuration = computed(() => Math.max(12, recentNews.value.length * 3));
    const alertDuration = computed(() => Math.max(12, alerts.value.length * 3));
    const collectorOnline = ref(false);
    const collectorLastRun = ref("");
    const collectorText = computed(() => collectorOnline.value ? "运行中" : "等待触发");
    const riskRate = computed(() => stats.total ? Math.round((stats.high_risk || 0) / stats.total * 100) : 0);
    const negativeRate = computed(() => {
      const neg = stats.sentiments?.find((s) => s.label === "negative")?.count || 0;
      return stats.total ? Math.round(neg / stats.total * 100) : 0;
    });
    const situationLevel = computed(() => {
      if (!stats.total) return "green";
      if (riskRate.value < 10) return "green";
      if (riskRate.value < 20) return "yellow";
      return "red";
    });
    const levelText = computed(() => ({ green: "态势平稳", yellow: "态势需警惕", red: "态势紧张" })[situationLevel.value]);
    const situationText = computed(() => {
      if (situationLevel.value === "green") return "整体态势平稳，暂无需要紧急处置的高风险舆情。";
      if (situationLevel.value === "yellow") return "态势总体可控，存在少量高风险舆情，建议持续关注。";
      return "态势紧张，高风险舆情占比偏高，建议立即研判处置。";
    });
    const reporting = ref(false);
    async function downloadReport() {
      reporting.value = true;
      try {
        const res = await api.get("/reports/overview/pdf", {
          params: { days: trendDays.value },
          responseType: "blob"
        });
        const blob = new Blob([res.data], { type: "application/pdf" });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `舆情监测报告_${(/* @__PURE__ */ new Date()).toISOString().slice(0, 10)}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        ElMessage.success("报告已生成，开始下载");
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "生成报告失败");
      } finally {
        reporting.value = false;
      }
    }
    const trendRef = ref();
    let trendChart = null;
    const sourceRef = ref();
    let sourceChart = null;
    const wordcloudRef = ref();
    let wordcloudChart = null;
    const regionRef = ref();
    let regionChart = null;
    const realSentimentData = computed(() => {
      if (stats.sentiments && stats.sentiments.length) {
        const map = {
          negative: { label: "负面", count: 0, color: "#ff3b30" },
          neutral: { label: "中性", count: 0, color: "#86868b" },
          positive: { label: "正面", count: 0, color: "#34c759" }
        };
        for (const s of stats.sentiments) {
          const key = s.label.toLowerCase();
          if (map[key]) map[key].count = s.count;
        }
        return Object.values(map);
      }
      return [
        { label: "负面", count: stats.high_risk || 0, color: "#ff3b30" },
        { label: "中性", count: Math.max(0, (stats.total || 0) - (stats.high_risk || 0) - (stats.today || 0)), color: "#86868b" },
        { label: "正面", count: Math.max(0, (stats.today || 0) - (stats.high_risk || 0)), color: "#34c759" }
      ];
    });
    function renderTrend(trend) {
      if (!trendChart) return;
      trendChart.setOption({
        tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        grid: { left: 40, right: 20, top: 10, bottom: 30 },
        xAxis: { type: "category", data: trend.map((t) => t.date), axisLine: { lineStyle: { color: "#e8e8ed" } }, axisTick: { show: false }, axisLabel: { color: "#86868b", fontSize: 11 } },
        yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        series: [{ name: "舆情数", type: "line", smooth: true, symbol: "circle", symbolSize: 5, data: trend.map((t) => t.count), areaStyle: { color: new LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(0,113,227,0.12)" }, { offset: 1, color: "rgba(0,113,227,0)" }]) }, lineStyle: { width: 2.5, color: "#0071e3" }, itemStyle: { color: "#0071e3" } }]
      });
    }
    function renderSourceDistribution() {
      if (!sourceChart || !stats.sources?.length) return;
      const data = [...stats.sources].sort((a, b) => b.count - a.count).slice(0, 10);
      sourceChart.setOption({
        tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        grid: { left: 100, right: 30, top: 10, bottom: 20 },
        xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        yAxis: { type: "category", data: data.map((d) => d.source).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12 }, inverse: true },
        series: [{ name: "舆情数", type: "bar", data: data.map((d) => d.count).reverse(), barWidth: 16, itemStyle: { borderRadius: [0, 6, 6, 0], color: new LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#0071e3" }, { offset: 1, color: "#5ac8fa" }]) } }]
      });
    }
    function renderRegionDistribution() {
      if (!regionChart || !stats.regions?.length) return;
      const data = [...stats.regions].sort((a, b) => b.count - a.count).slice(0, 10);
      regionChart.setOption({
        tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        grid: { left: 110, right: 30, top: 10, bottom: 20 },
        xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        yAxis: { type: "category", data: data.map((d) => d.region_name).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12 }, inverse: true },
        series: [{ name: "舆情数", type: "bar", data: data.map((d) => d.count).reverse(), barWidth: 16, itemStyle: { borderRadius: [0, 6, 6, 0], color: new LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#ff9f0a" }, { offset: 1, color: "#ffd60a" }]) } }]
      });
    }
    function renderWordCloud() {
      if (!wordcloudChart || !stats.keywords?.length) return;
      const max = stats.keywords[0]?.count || 1;
      const data = stats.keywords.slice(0, 30).map((kw) => ({
        name: kw.word,
        value: kw.count,
        textStyle: { color: `hsl(${kw.count / max * 210 + 200}, 70%, ${60 - kw.count / max * 30}%)` }
      }));
      wordcloudChart.setOption({
        tooltip: { show: true, backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        series: [{ type: "wordCloud", shape: "circle", left: "center", top: "center", width: "90%", height: "90%", sizeRange: [14, 42], rotationRange: [-30, 30], gridSize: 8, layoutAnimation: true, textStyle: { fontFamily: "sans-serif", fontWeight: "bold" }, emphasis: { textStyle: { color: "#0071e3" } }, data }]
      });
    }
    async function loadCollectorStatus() {
      try {
        const res = await api.get("/collector/status");
        const d = res.data;
        collectorOnline.value = d.collector_type === "government";
        collectorLastRun.value = d.last_run ? new Date(d.last_run).toLocaleString("zh-CN") : "暂无记录";
      } catch {
        collectorOnline.value = false;
      }
    }
    async function loadFeeds() {
      try {
        const [r1, r2] = await Promise.all([
          api.get("/dashboard/recent", { params: { limit: 8 } }),
          api.get("/dashboard/alerts", { params: { limit: 8 } })
        ]);
        recentNews.value = r1.data;
        alerts.value = r2.data;
      } catch {
      }
    }
    function handleResize() {
      trendChart?.resize();
      sourceChart?.resize();
      wordcloudChart?.resize();
      regionChart?.resize();
    }
    async function loadData() {
      loading.value = true;
      try {
        const [statsRes] = await Promise.all([
          api.get("/dashboard/stats", { params: { days: trendDays.value } }),
          loadCollectorStatus(),
          loadFeeds()
        ]);
        Object.assign(stats, statsRes.data);
        await nextTick();
        renderTrend(stats.trend);
        renderSourceDistribution();
        renderRegionDistribution();
        renderWordCloud();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载统计数据失败");
      } finally {
        loading.value = false;
      }
    }
    watch(trendDays, () => {
      loadData();
    });
    function fmtTime(s) {
      if (!s) return "-";
      return s.replace("T", " ").slice(0, 16);
    }
    function sentClass(s) {
      return { negative: "neg", neutral: "neu", positive: "pos" }[s] || "neu";
    }
    function sentLabel(s) {
      return { negative: "负面", neutral: "中性", positive: "正面" }[s] || "中性";
    }
    function riskClass(l) {
      return { critical: "crit", high: "crit", medium: "med", low: "low" }[l] || "low";
    }
    function riskText(l) {
      return { critical: "严重", high: "高", medium: "中", low: "低" }[l] || l;
    }
    let feedTimer;
    onMounted(async () => {
      await nextTick();
      if (trendRef.value) trendChart = init(trendRef.value);
      if (sourceRef.value) sourceChart = init(sourceRef.value);
      if (wordcloudRef.value) wordcloudChart = init(wordcloudRef.value);
      if (regionRef.value) regionChart = init(regionRef.value);
      window.addEventListener("resize", handleResize);
      window.addEventListener("data-refresh", loadData);
      await loadData();
      feedTimer = window.setInterval(loadFeeds, 3e4);
    });
    onBeforeUnmount(() => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("data-refresh", loadData);
      if (feedTimer) clearInterval(feedTimer);
      trendChart?.dispose();
      trendChart = null;
      sourceChart?.dispose();
      sourceChart = null;
      wordcloudChart?.dispose();
      wordcloudChart = null;
      regionChart?.dispose();
      regionChart = null;
    });
    return (_ctx, _cache) => {
      const _component_el_button = resolveComponent("el-button");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            _cache[2] || (_cache[2] = createBaseVNode("div", { class: "s-ico" }, "≡", -1)),
            _cache[3] || (_cache[3] = createBaseVNode("div", { class: "s-label" }, "总舆情数", -1)),
            createBaseVNode("div", _hoisted_4, toDisplayString(stats.total.toLocaleString()), 1),
            _cache[4] || (_cache[4] = createBaseVNode("div", { class: "s-foot-row" }, [
              createBaseVNode("span", { class: "s-foot" }, "累计监测数据")
            ], -1))
          ]),
          createBaseVNode("div", _hoisted_5, [
            _cache[5] || (_cache[5] = createBaseVNode("div", { class: "s-ico" }, "↗", -1)),
            _cache[6] || (_cache[6] = createBaseVNode("div", { class: "s-label" }, "今日新增", -1)),
            createBaseVNode("div", _hoisted_6, toDisplayString(stats.today.toLocaleString()), 1),
            _cache[7] || (_cache[7] = createBaseVNode("div", { class: "s-foot-row" }, [
              createBaseVNode("span", { class: "s-foot" }, "当日采集")
            ], -1))
          ]),
          createBaseVNode("div", _hoisted_7, [
            _cache[8] || (_cache[8] = createBaseVNode("div", { class: "s-ico" }, "!", -1)),
            _cache[9] || (_cache[9] = createBaseVNode("div", { class: "s-label" }, "高风险", -1)),
            createBaseVNode("div", _hoisted_8, toDisplayString(stats.high_risk.toLocaleString()), 1),
            _cache[10] || (_cache[10] = createBaseVNode("div", { class: "s-foot-row" }, [
              createBaseVNode("span", { class: "s-foot" }, "需关注处理")
            ], -1))
          ]),
          createBaseVNode("div", _hoisted_9, [
            _cache[11] || (_cache[11] = createBaseVNode("div", { class: "s-ico" }, "◎", -1)),
            _cache[12] || (_cache[12] = createBaseVNode("div", { class: "s-label" }, "事件数", -1)),
            createBaseVNode("div", _hoisted_10, toDisplayString((stats.event_count || 0).toLocaleString()), 1),
            _cache[13] || (_cache[13] = createBaseVNode("div", { class: "s-foot-row" }, [
              createBaseVNode("span", { class: "s-foot" }, "聚合事件")
            ], -1))
          ]),
          createBaseVNode("div", _hoisted_11, [
            _cache[14] || (_cache[14] = createBaseVNode("div", { class: "s-ico" }, "↻", -1)),
            _cache[15] || (_cache[15] = createBaseVNode("div", { class: "s-label" }, "采集状态", -1)),
            createBaseVNode("div", _hoisted_12, [
              createBaseVNode("span", {
                style: normalizeStyle({ color: collectorOnline.value ? "#34c759" : "#86868b" })
              }, toDisplayString(collectorOnline.value ? "●" : "○"), 5),
              createBaseVNode("span", _hoisted_13, toDisplayString(collectorText.value), 1)
            ]),
            createBaseVNode("div", _hoisted_14, [
              createBaseVNode("span", _hoisted_15, toDisplayString(collectorLastRun.value), 1)
            ])
          ])
        ]),
        createBaseVNode("div", {
          class: normalizeClass(["card situation", "lvl-" + situationLevel.value])
        }, [
          createBaseVNode("div", _hoisted_16, [
            createBaseVNode("div", _hoisted_17, [
              _cache[16] || (_cache[16] = createBaseVNode("span", { class: "lvl-dot" }, null, -1)),
              createTextVNode(toDisplayString(levelText.value), 1)
            ]),
            createBaseVNode("div", _hoisted_18, toDisplayString(situationText.value), 1)
          ]),
          createBaseVNode("div", _hoisted_19, [
            createBaseVNode("div", _hoisted_20, [
              createBaseVNode("span", _hoisted_21, toDisplayString(stats.total.toLocaleString()), 1),
              _cache[17] || (_cache[17] = createBaseVNode("span", { class: "l" }, "总舆情", -1))
            ]),
            createBaseVNode("div", _hoisted_22, [
              createBaseVNode("span", _hoisted_23, toDisplayString(stats.high_risk.toLocaleString()), 1),
              _cache[18] || (_cache[18] = createBaseVNode("span", { class: "l" }, "高风险", -1))
            ]),
            createBaseVNode("div", _hoisted_24, [
              createBaseVNode("span", _hoisted_25, toDisplayString(riskRate.value) + "%", 1),
              _cache[19] || (_cache[19] = createBaseVNode("span", { class: "l" }, "风险率", -1))
            ]),
            createBaseVNode("div", _hoisted_26, [
              createBaseVNode("span", _hoisted_27, toDisplayString(negativeRate.value) + "%", 1),
              _cache[20] || (_cache[20] = createBaseVNode("span", { class: "l" }, "负面率", -1))
            ]),
            createBaseVNode("div", _hoisted_28, [
              createBaseVNode("span", _hoisted_29, toDisplayString((stats.event_count || 0).toLocaleString()), 1),
              _cache[21] || (_cache[21] = createBaseVNode("span", { class: "l" }, "事件", -1))
            ])
          ]),
          createBaseVNode("div", _hoisted_30, [
            unref(can)("reports:read") ? (openBlock(), createBlock(_component_el_button, {
              key: 0,
              type: "primary",
              loading: reporting.value,
              onClick: downloadReport
            }, {
              default: withCtx(() => [..._cache[22] || (_cache[22] = [
                createBaseVNode("span", { style: { "margin-right": "4px" } }, "⎙", -1),
                createTextVNode("导出舆情报告(PDF) ", -1)
              ])]),
              _: 1
            }, 8, ["loading"])) : createCommentVNode("", true)
          ])
        ], 2),
        createBaseVNode("div", _hoisted_31, [
          createBaseVNode("div", _hoisted_32, [
            createBaseVNode("div", _hoisted_33, [
              _cache[23] || (_cache[23] = createBaseVNode("h3", { class: "section-title" }, "舆情趋势", -1)),
              createVNode(SegmentedControl, {
                modelValue: trendDays.value,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => trendDays.value = $event),
                options: segOptions
              }, null, 8, ["modelValue"])
            ]),
            createBaseVNode("div", {
              ref_key: "trendRef",
              ref: trendRef,
              class: "chart-box"
            }, null, 512)
          ]),
          createBaseVNode("div", _hoisted_34, [
            _cache[24] || (_cache[24] = createBaseVNode("div", { class: "chart-head" }, [
              createBaseVNode("h3", { class: "section-title" }, "情感分布")
            ], -1)),
            createVNode(SentimentDonut, { data: realSentimentData.value }, null, 8, ["data"])
          ]),
          createBaseVNode("div", _hoisted_35, [
            _cache[25] || (_cache[25] = createBaseVNode("div", { class: "chart-head" }, [
              createBaseVNode("h3", { class: "section-title" }, "来源分布")
            ], -1)),
            createBaseVNode("div", {
              ref_key: "sourceRef",
              ref: sourceRef,
              class: "chart-box",
              style: { "height": "280px" }
            }, null, 512)
          ]),
          createBaseVNode("div", _hoisted_36, [
            _cache[26] || (_cache[26] = createBaseVNode("div", { class: "chart-head" }, [
              createBaseVNode("h3", { class: "section-title" }, "热点词云")
            ], -1)),
            createBaseVNode("div", {
              ref_key: "wordcloudRef",
              ref: wordcloudRef,
              class: "chart-box",
              style: { "height": "280px" }
            }, null, 512)
          ]),
          createBaseVNode("div", _hoisted_37, [
            _cache[27] || (_cache[27] = createBaseVNode("div", { class: "chart-head" }, [
              createBaseVNode("h3", { class: "section-title" }, "实时快讯"),
              createBaseVNode("span", { class: "live-dot" }, "● LIVE")
            ], -1)),
            createBaseVNode("div", _hoisted_38, [
              createBaseVNode("div", {
                class: "scroll-inner",
                style: normalizeStyle({ animationDuration: feedDuration.value + "s" })
              }, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(doubledNews.value, (n, i) => {
                  return openBlock(), createElementBlock("div", {
                    key: "n" + i,
                    class: "feed-item clickable",
                    title: "查看舆情详情",
                    onClick: ($event) => goOpinion(n.id)
                  }, [
                    createBaseVNode("span", {
                      class: normalizeClass(["fi-tag", sentClass(n.sentiment)])
                    }, toDisplayString(sentLabel(n.sentiment)), 3),
                    createBaseVNode("div", _hoisted_40, [
                      createBaseVNode("div", _hoisted_41, toDisplayString(n.title), 1),
                      createBaseVNode("div", _hoisted_42, toDisplayString(n.source) + " · " + toDisplayString(n.region_name) + " · " + toDisplayString(fmtTime(n.created_at)) + " · 风险 " + toDisplayString(n.risk_score), 1)
                    ])
                  ], 8, _hoisted_39);
                }), 128))
              ], 4),
              !recentNews.value.length ? (openBlock(), createElementBlock("div", _hoisted_43, "暂无实时快讯")) : createCommentVNode("", true)
            ])
          ]),
          createBaseVNode("div", _hoisted_44, [
            _cache[28] || (_cache[28] = createBaseVNode("div", { class: "chart-head" }, [
              createBaseVNode("h3", { class: "section-title" }, "预警滚动"),
              createBaseVNode("span", { class: "live-dot warn" }, "● ALERT")
            ], -1)),
            createBaseVNode("div", _hoisted_45, [
              createBaseVNode("div", {
                class: "scroll-inner",
                style: normalizeStyle({ animationDuration: alertDuration.value + "s" })
              }, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(doubledAlerts.value, (a, i) => {
                  return openBlock(), createElementBlock("div", {
                    key: "a" + i,
                    class: normalizeClass(["alert-item", { handled: a.handled, clickable: !!a.opinion_id }]),
                    title: a.opinion_id ? "查看舆情详情" : "",
                    onClick: ($event) => a.opinion_id && goOpinion(a.opinion_id)
                  }, [
                    createBaseVNode("span", {
                      class: normalizeClass(["ai-tag", riskClass(a.risk_level)])
                    }, toDisplayString(riskText(a.risk_level)), 3),
                    createBaseVNode("div", _hoisted_47, [
                      createBaseVNode("div", _hoisted_48, toDisplayString(a.opinion_title || a.rule_name), 1),
                      createBaseVNode("div", _hoisted_49, toDisplayString(a.rule_name) + " · " + toDisplayString(fmtTime(a.created_at)) + toDisplayString(a.handled ? " · 已处置" : ""), 1)
                    ])
                  ], 10, _hoisted_46);
                }), 128))
              ], 4),
              !alerts.value.length ? (openBlock(), createElementBlock("div", _hoisted_50, "暂无预警")) : createCommentVNode("", true)
            ])
          ]),
          createBaseVNode("div", _hoisted_51, [
            _cache[29] || (_cache[29] = createBaseVNode("div", { class: "chart-head" }, [
              createBaseVNode("h3", { class: "section-title" }, "地理分布（地区舆情 TOP）")
            ], -1)),
            createBaseVNode("div", {
              ref_key: "regionRef",
              ref: regionRef,
              class: "chart-box",
              style: { "height": "300px" }
            }, null, 512)
          ]),
          createVNode(OpinionDetailModal, {
            modelValue: detailVisible.value,
            "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => detailVisible.value = $event),
            "opinion-id": detailId.value
          }, null, 8, ["modelValue", "opinion-id"])
        ])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Dashboard = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-a48db90a"]]);

export { Dashboard as default };
