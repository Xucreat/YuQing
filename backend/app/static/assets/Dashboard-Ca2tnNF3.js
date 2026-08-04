import { c as createTextStyle$1, S as SeriesModel, C as ChartView, u as use, i as install, a as install$1, b as installLabelLayout, d as createDimensions, e as SeriesData, Z as ZRText, f as enableHoverEmphasis, r as registerLayout, g as getLayoutRect, l as linearMap, h as registerPreprocessor, j as isArray, k as each, m as capitalFirst, n as init, L as LinearGradient } from './index-DVLpPvFk.js';
import { g as api, d as defineComponent, c as createElementBlock, F as Fragment, i as renderList, o as openBlock, n as normalizeClass, t as toDisplayString, _ as _export_sfc, a as createBaseVNode, j as computed, k as normalizeStyle, l as useModel, m as createVNode, p as withCtx, e as createTextVNode, q as createBlock, s as createCommentVNode, x as mergeModels, r as ref, y as resolveComponent, z as usePermission, A as watch, w as withDirectives, E as ElMessage, B as resolveDirective, C as onMounted, D as nextTick, G as onBeforeUnmount, H as unref, f as reactive, h as useRouter } from './index-CHoAHtX2.js';
import { t as topicValueFromLabel, e as eventStatusPill, a as eventStatusLabel } from './event-DY3DZBkH.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-W6X-BJzl.js';
import './admission-DpEuIHXC.js';

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

async function getEventsByHotTopic(keyword) {
  const { data } = await api.get(`/events/hot-topic/${encodeURI(keyword)}`);
  return data;
}

const _hoisted_1$4 = { class: "seg-group" };
const _hoisted_2$4 = ["onClick"];
const _sfc_main$4 = /* @__PURE__ */ defineComponent({
  __name: "SegmentedControl",
  props: {
    modelValue: {},
    options: {}
  },
  emits: ["update:modelValue"],
  setup(__props) {
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$4, [
        (openBlock(true), createElementBlock(Fragment, null, renderList(__props.options, (opt) => {
          return openBlock(), createElementBlock("button", {
            key: opt.value,
            class: normalizeClass(["seg-btn", { active: __props.modelValue === opt.value }]),
            onClick: ($event) => _ctx.$emit("update:modelValue", opt.value)
          }, toDisplayString(opt.label), 11, _hoisted_2$4);
        }), 128))
      ]);
    };
  }
});

const SegmentedControl = /* @__PURE__ */ _export_sfc(_sfc_main$4, [["__scopeId", "data-v-ae024c45"]]);

const _hoisted_1$3 = { class: "donut-wrap" };
const _hoisted_2$3 = {
  class: "donut-svg",
  viewBox: "0 0 140 140"
};
const _hoisted_3$3 = ["stroke", "stroke-dasharray", "stroke-dashoffset"];
const _hoisted_4$3 = {
  x: "70",
  y: "66",
  "text-anchor": "middle",
  "font-size": "28",
  "font-weight": "600",
  fill: "#1d1d1f"
};
const _hoisted_5$3 = { class: "donut-legends" };
const _sfc_main$3 = /* @__PURE__ */ defineComponent({
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
      return openBlock(), createElementBlock("div", _hoisted_1$3, [
        (openBlock(), createElementBlock("svg", _hoisted_2$3, [
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
            }, null, 8, _hoisted_3$3);
          }), 128)),
          createBaseVNode("text", _hoisted_4$3, toDisplayString(total.value), 1),
          _cache[1] || (_cache[1] = createBaseVNode("text", {
            x: "70",
            y: "85",
            "text-anchor": "middle",
            "font-size": "10",
            fill: "#86868b"
          }, " 总计 ", -1))
        ])),
        createBaseVNode("div", _hoisted_5$3, [
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

const SentimentDonut = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-1e1d467a"]]);

function getReportModules() {
  return api.get("/reports/modules");
}
function generateReport(payload) {
  return api.post("/reports/export", payload, { responseType: "blob" });
}
function getTemplates() {
  return api.get("/reports/templates");
}
function createTemplate(payload) {
  return api.post("/reports/templates", payload);
}
function deleteTemplate(id) {
  return api.delete(`/reports/templates/${id}`);
}

const _hoisted_1$2 = { class: "module-list" };
const _hoisted_2$2 = { class: "module-idx" };
const _hoisted_3$2 = { class: "module-title" };
const _hoisted_4$2 = { class: "module-ops" };
const _hoisted_5$2 = {
  key: 0,
  class: "module-add"
};
const _hoisted_6$2 = {
  key: 1,
  class: "form-hint warn"
};
const _sfc_main$2 = /* @__PURE__ */ defineComponent({
  __name: "ModuleSelector",
  props: /* @__PURE__ */ mergeModels({
    modules: {}
  }, {
    "modelValue": { required: true },
    "modelModifiers": {}
  }),
  emits: ["update:modelValue"],
  setup(__props) {
    const model = useModel(__props, "modelValue");
    const props = __props;
    const toAdd = ref("");
    const available = computed(
      () => props.modules.filter((m) => !model.value.includes(m.key))
    );
    function titleOf(key) {
      return props.modules.find((m) => m.key === key)?.title || key;
    }
    function move(idx, dir) {
      const j = idx + dir;
      if (j < 0 || j >= model.value.length) return;
      const arr = [...model.value];
      [arr[idx], arr[j]] = [arr[j], arr[idx]];
      model.value = arr;
    }
    function remove(idx) {
      const arr = [...model.value];
      arr.splice(idx, 1);
      model.value = arr;
    }
    function add(key) {
      if (key && !model.value.includes(key)) {
        model.value = [...model.value, key];
      }
      toAdd.value = "";
    }
    return (_ctx, _cache) => {
      const _component_el_button = resolveComponent("el-button");
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      return openBlock(), createElementBlock("div", _hoisted_1$2, [
        (openBlock(true), createElementBlock(Fragment, null, renderList(model.value, (key, idx) => {
          return openBlock(), createElementBlock("div", {
            key,
            class: "module-item"
          }, [
            createBaseVNode("span", _hoisted_2$2, toDisplayString(idx + 1), 1),
            createBaseVNode("span", _hoisted_3$2, toDisplayString(titleOf(key)), 1),
            createBaseVNode("span", _hoisted_4$2, [
              createVNode(_component_el_button, {
                link: "",
                disabled: idx === 0,
                onClick: ($event) => move(idx, -1),
                title: "上移"
              }, {
                default: withCtx(() => [..._cache[1] || (_cache[1] = [
                  createTextVNode("↑", -1)
                ])]),
                _: 1
              }, 8, ["disabled", "onClick"]),
              createVNode(_component_el_button, {
                link: "",
                disabled: idx === model.value.length - 1,
                onClick: ($event) => move(idx, 1),
                title: "下移"
              }, {
                default: withCtx(() => [..._cache[2] || (_cache[2] = [
                  createTextVNode("↓", -1)
                ])]),
                _: 1
              }, 8, ["disabled", "onClick"]),
              createVNode(_component_el_button, {
                link: "",
                type: "danger",
                onClick: ($event) => remove(idx),
                title: "移除"
              }, {
                default: withCtx(() => [..._cache[3] || (_cache[3] = [
                  createTextVNode("✕", -1)
                ])]),
                _: 1
              }, 8, ["onClick"])
            ])
          ]);
        }), 128)),
        available.value.length ? (openBlock(), createElementBlock("div", _hoisted_5$2, [
          _cache[4] || (_cache[4] = createBaseVNode("span", { class: "add-label" }, "添加模块：", -1)),
          createVNode(_component_el_select, {
            modelValue: toAdd.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => toAdd.value = $event),
            placeholder: "选择未选模块",
            onChange: add,
            clearable: ""
          }, {
            default: withCtx(() => [
              (openBlock(true), createElementBlock(Fragment, null, renderList(available.value, (m) => {
                return openBlock(), createBlock(_component_el_option, {
                  key: m.key,
                  value: m.key,
                  label: m.title
                }, null, 8, ["value", "label"]);
              }), 128))
            ]),
            _: 1
          }, 8, ["modelValue"])
        ])) : createCommentVNode("", true),
        !model.value.length ? (openBlock(), createElementBlock("div", _hoisted_6$2, "未选择任何模块，生成将失败。")) : createCommentVNode("", true)
      ]);
    };
  }
});

const ModuleSelector = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-8665a50e"]]);

const _hoisted_1$1 = { class: "tpl-row" };
const _hoisted_2$1 = {
  key: 0,
  class: "param-zone"
};
const _hoisted_3$1 = { class: "param-block-title" };
const _hoisted_4$1 = {
  key: 0,
  class: "param-rows"
};
const _hoisted_5$1 = { class: "param-label" };
const _hoisted_6$1 = {
  key: 1,
  class: "form-hint"
};
const _sfc_main$1 = /* @__PURE__ */ defineComponent({
  __name: "ReportExportDrawer",
  props: {
    "modelValue": { type: Boolean, ...{ required: true } },
    "modelModifiers": {}
  },
  emits: ["update:modelValue"],
  setup(__props) {
    const open = useModel(__props, "modelValue");
    const reporting = ref(false);
    const loadingModules = ref(false);
    const reportName = ref("舆情监测报告");
    const reportTimeField = ref("created_at");
    const reportRangeMode = ref("preset");
    const reportPresetDays = ref(7);
    const reportCustomRange = ref(null);
    const allModules = ref([]);
    const selectedModules = ref([]);
    const moduleParams = ref({});
    const templates = ref([]);
    const selectedTemplateId = ref(null);
    const loadingTemplates = ref(false);
    const saveDialogVisible = ref(false);
    const savingTemplate = ref(false);
    const deleting = ref(false);
    const templateForm = ref({
      name: "",
      description: "",
      is_public: false
    });
    function buildDefaults(def) {
      const o = {};
      for (const p of def.params) o[p.key] = p.default;
      return o;
    }
    const selectedWithParams = computed(
      () => selectedModules.value.map((key) => allModules.value.find((m) => m.key === key)).filter((m) => !!m && !!m.params && m.params.length > 0)
    );
    const { hasPermission } = usePermission();
    const canManageTemplate = computed(() => hasPermission("reports:manage"));
    const currentTemplateCanEdit = computed(() => {
      const t = templates.value.find((t2) => t2.id === selectedTemplateId.value);
      return !!t && t.can_edit && canManageTemplate.value;
    });
    watch(
      selectedModules,
      (keys) => {
        const set = new Set(keys);
        for (const k of Object.keys(moduleParams.value)) {
          if (!set.has(k)) delete moduleParams.value[k];
        }
        for (const k of keys) {
          const def = allModules.value.find((m) => m.key === k);
          if (def && def.params && def.params.length && !moduleParams.value[k]) {
            moduleParams.value[k] = buildDefaults(def);
          }
        }
      },
      { deep: false }
    );
    async function onOpen() {
      if (loadingModules.value) return;
      loadingModules.value = true;
      try {
        const { data } = await getReportModules();
        allModules.value = data.modules || [];
        if (!selectedModules.value.length) {
          selectedModules.value = [...data.default_modules || allModules.value.map((m) => m.key)];
        }
        for (const key of selectedModules.value) {
          const def = allModules.value.find((m) => m.key === key);
          if (def && def.params && def.params.length && !moduleParams.value[key]) {
            moduleParams.value[key] = buildDefaults(def);
          }
        }
      } catch {
        allModules.value = [];
        selectedModules.value = [];
        ElMessage.error("获取报告模块清单失败");
      } finally {
        loadingModules.value = false;
      }
      await loadTemplates();
    }
    async function loadTemplates() {
      if (loadingTemplates.value) return;
      loadingTemplates.value = true;
      try {
        const { data } = await getTemplates();
        templates.value = data || [];
      } catch {
        templates.value = [];
      } finally {
        loadingTemplates.value = false;
      }
    }
    function applyConfigToForm(cfg) {
      reportName.value = cfg.name || "舆情监测报告";
      reportTimeField.value = cfg.time_field || "created_at";
      if (cfg.range_type === "custom") {
        reportRangeMode.value = "custom";
        reportCustomRange.value = cfg.start_date && cfg.end_date ? [cfg.start_date, cfg.end_date] : null;
      } else {
        reportRangeMode.value = "preset";
        reportPresetDays.value = cfg.range_days || 7;
      }
      selectedModules.value = (cfg.modules || []).map(
        (m) => typeof m === "string" ? m : m.key
      );
      const params = {};
      for (const m of cfg.modules || []) {
        if (typeof m === "string") continue;
        const def = allModules.value.find((d) => d.key === m.key);
        if (def && def.params && def.params.length) {
          const stored = m.params || {};
          const out = {};
          for (const p of def.params) {
            out[p.key] = stored[p.key] !== void 0 ? stored[p.key] : p.default;
          }
          params[m.key] = out;
        }
      }
      moduleParams.value = params;
    }
    function onTemplateSelected() {
      const tpl = templates.value.find((t) => t.id === selectedTemplateId.value);
      if (!tpl) return;
      applyConfigToForm(tpl.config_json);
    }
    function buildConfigFromForm() {
      const isCustom = reportRangeMode.value === "custom";
      const modulesPayload = selectedModules.value.map((key) => {
        const def = allModules.value.find((m) => m.key === key);
        if (def && def.params && def.params.length) {
          return { key, params: collectParams(key, def) };
        }
        return key;
      });
      return {
        name: reportName.value.trim() || "舆情监测报告",
        time_field: reportTimeField.value,
        range_type: isCustom ? "custom" : "last_n_days",
        range_days: isCustom ? 7 : reportPresetDays.value,
        start_date: isCustom && reportCustomRange.value ? reportCustomRange.value[0] : null,
        end_date: isCustom && reportCustomRange.value ? reportCustomRange.value[1] : null,
        modules: modulesPayload
      };
    }
    function openSaveDialog() {
      templateForm.value = {
        name: reportName.value || "舆情监测报告",
        description: "",
        is_public: false
      };
      saveDialogVisible.value = true;
    }
    async function saveAsTemplate() {
      if (!templateForm.value.name.trim()) {
        ElMessage.warning("请输入模板名称");
        return;
      }
      savingTemplate.value = true;
      try {
        const config = buildConfigFromForm();
        const { data } = await createTemplate({
          name: templateForm.value.name.trim(),
          description: templateForm.value.description || null,
          is_public: templateForm.value.is_public,
          config_json: config
        });
        ElMessage.success("已保存为模板");
        saveDialogVisible.value = false;
        await loadTemplates();
        selectedTemplateId.value = data.id;
      } catch (e) {
        let msg = "保存模板失败";
        try {
          const text = e?.response?.data ? await e.response.data.text() : "";
          const j = text ? JSON.parse(text) : null;
          if (j?.detail) msg = `保存模板失败：${j.detail}`;
        } catch {
        }
        ElMessage.error(msg);
      } finally {
        savingTemplate.value = false;
      }
    }
    async function onDeleteTemplate() {
      if (!selectedTemplateId.value) return;
      deleting.value = true;
      try {
        await deleteTemplate(selectedTemplateId.value);
        ElMessage.success("模板已删除");
        await loadTemplates();
        selectedTemplateId.value = null;
      } catch (e) {
        let msg = "删除模板失败";
        try {
          const text = e?.response?.data ? await e.response.data.text() : "";
          const j = text ? JSON.parse(text) : null;
          if (j?.detail) msg = `删除模板失败：${j.detail}`;
        } catch {
        }
        ElMessage.error(msg);
      } finally {
        deleting.value = false;
      }
    }
    function collectParams(key, def) {
      const stored = moduleParams.value[key] || {};
      const out = {};
      for (const p of def.params) {
        let v = stored[p.key];
        if (v === void 0 || v === null || v === "") v = p.default;
        if (p.type === "int" && v != null) v = Number(v);
        out[p.key] = v;
      }
      return out;
    }
    async function generateAndDownload() {
      if (!selectedModules.value.length) {
        ElMessage.warning("请至少选择一个报告模块");
        return;
      }
      const modulesPayload = selectedModules.value.map((key) => {
        const def = allModules.value.find((m) => m.key === key);
        if (def && def.params && def.params.length) {
          return { key, params: collectParams(key, def) };
        }
        return key;
      });
      const isCustom = reportRangeMode.value === "custom";
      const payload = {
        name: reportName.value.trim() || "舆情监测报告",
        time_field: reportTimeField.value,
        range_type: isCustom ? "custom" : "last_n_days",
        range_days: isCustom ? 7 : reportPresetDays.value,
        start_date: isCustom && reportCustomRange.value ? reportCustomRange.value[0] : null,
        end_date: isCustom && reportCustomRange.value ? reportCustomRange.value[1] : null,
        modules: modulesPayload,
        delivery: "download"
      };
      reporting.value = true;
      try {
        const res = await generateReport(payload);
        const blob = new Blob([res.data], { type: res.data.type || "application/pdf" });
        if (blob.size === 0) {
          ElMessage.error("生成的报告为空，请调整筛选条件后重试");
          return;
        }
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const now = /* @__PURE__ */ new Date();
        const ds = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`;
        a.download = `${payload.name}_${ds}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        ElMessage.success("报告已生成，开始下载");
        open.value = false;
      } catch (e) {
        let msg = "生成报告失败，请稍后重试";
        try {
          const text = e?.response?.data ? await e.response.data.text() : "";
          const j = text ? JSON.parse(text) : null;
          if (j?.detail) msg = `报告生成失败：${j.detail}`;
        } catch {
        }
        ElMessage.error(msg);
      } finally {
        reporting.value = false;
      }
    }
    return (_ctx, _cache) => {
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_button = resolveComponent("el-button");
      const _component_el_form_item = resolveComponent("el-form-item");
      const _component_el_input = resolveComponent("el-input");
      const _component_el_radio = resolveComponent("el-radio");
      const _component_el_radio_group = resolveComponent("el-radio-group");
      const _component_el_date_picker = resolveComponent("el-date-picker");
      const _component_el_input_number = resolveComponent("el-input-number");
      const _component_el_form = resolveComponent("el-form");
      const _component_el_switch = resolveComponent("el-switch");
      const _component_el_dialog = resolveComponent("el-dialog");
      const _component_el_drawer = resolveComponent("el-drawer");
      const _directive_loading = resolveDirective("loading");
      return openBlock(), createBlock(_component_el_drawer, {
        modelValue: open.value,
        "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => open.value = $event),
        title: "导出舆情报告",
        direction: "rtl",
        size: "460px",
        "close-on-click-modal": false,
        onOpen
      }, {
        footer: withCtx(() => [
          createVNode(_component_el_button, {
            onClick: _cache[7] || (_cache[7] = ($event) => open.value = false)
          }, {
            default: withCtx(() => [..._cache[21] || (_cache[21] = [
              createTextVNode("取消", -1)
            ])]),
            _: 1
          }),
          canManageTemplate.value ? (openBlock(), createBlock(_component_el_button, {
            key: 0,
            onClick: openSaveDialog,
            loading: savingTemplate.value
          }, {
            default: withCtx(() => [..._cache[22] || (_cache[22] = [
              createTextVNode("保存为模板", -1)
            ])]),
            _: 1
          }, 8, ["loading"])) : createCommentVNode("", true),
          createVNode(_component_el_button, {
            type: "primary",
            loading: reporting.value,
            onClick: generateAndDownload
          }, {
            default: withCtx(() => [..._cache[23] || (_cache[23] = [
              createTextVNode(" 生成并下载 PDF ", -1)
            ])]),
            _: 1
          }, 8, ["loading"])
        ]),
        default: withCtx(() => [
          withDirectives((openBlock(), createBlock(_component_el_form, {
            "label-position": "top",
            class: "report-form",
            "element-loading-text": "加载模块清单…"
          }, {
            default: withCtx(() => [
              createVNode(_component_el_form_item, { label: "报告模板" }, {
                default: withCtx(() => [
                  createBaseVNode("div", _hoisted_1$1, [
                    createVNode(_component_el_select, {
                      modelValue: selectedTemplateId.value,
                      "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => selectedTemplateId.value = $event),
                      placeholder: "选择模板以载入配置",
                      loading: loadingTemplates.value,
                      onChange: onTemplateSelected,
                      class: "tpl-select"
                    }, {
                      default: withCtx(() => [
                        (openBlock(true), createElementBlock(Fragment, null, renderList(templates.value, (t) => {
                          return openBlock(), createBlock(_component_el_option, {
                            key: t.id,
                            value: t.id,
                            label: (t.is_public ? "🌐 " : "") + t.name
                          }, null, 8, ["value", "label"]);
                        }), 128))
                      ]),
                      _: 1
                    }, 8, ["modelValue", "loading"]),
                    selectedTemplateId.value && currentTemplateCanEdit.value ? (openBlock(), createBlock(_component_el_button, {
                      key: 0,
                      type: "danger",
                      link: "",
                      loading: deleting.value,
                      onClick: onDeleteTemplate
                    }, {
                      default: withCtx(() => [..._cache[14] || (_cache[14] = [
                        createTextVNode("删除", -1)
                      ])]),
                      _: 1
                    }, 8, ["loading"])) : createCommentVNode("", true)
                  ]),
                  _cache[15] || (_cache[15] = createBaseVNode("div", { class: "form-hint" }, "模板 = 当前导出配置快照（不含投递方式）。🌐 为公共模板。", -1))
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "报告名称" }, {
                default: withCtx(() => [
                  createVNode(_component_el_input, {
                    modelValue: reportName.value,
                    "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => reportName.value = $event),
                    maxlength: "40",
                    "show-word-limit": "",
                    placeholder: "舆情监测报告"
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "统计时间字段" }, {
                default: withCtx(() => [
                  createVNode(_component_el_radio_group, {
                    modelValue: reportTimeField.value,
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => reportTimeField.value = $event)
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_radio, { value: "created_at" }, {
                        default: withCtx(() => [..._cache[16] || (_cache[16] = [
                          createTextVNode("采集时间", -1)
                        ])]),
                        _: 1
                      }),
                      createVNode(_component_el_radio, { value: "publish_time" }, {
                        default: withCtx(() => [..._cache[17] || (_cache[17] = [
                          createTextVNode("发布时间（缺失回退采集时间）", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  _cache[18] || (_cache[18] = createBaseVNode("div", { class: "form-hint" }, "发布时间为空的数据将回退使用采集时间（COALESCE），不丢弃。", -1))
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "统计时间范围" }, {
                default: withCtx(() => [
                  createVNode(_component_el_radio_group, {
                    modelValue: reportRangeMode.value,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => reportRangeMode.value = $event),
                    class: "range-mode"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_radio, { value: "preset" }, {
                        default: withCtx(() => [..._cache[19] || (_cache[19] = [
                          createTextVNode("预设周期", -1)
                        ])]),
                        _: 1
                      }),
                      createVNode(_component_el_radio, { value: "custom" }, {
                        default: withCtx(() => [..._cache[20] || (_cache[20] = [
                          createTextVNode("自定义区间", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  reportRangeMode.value === "preset" ? (openBlock(), createBlock(_component_el_select, {
                    key: 0,
                    modelValue: reportPresetDays.value,
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => reportPresetDays.value = $event),
                    class: "range-control"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_option, {
                        value: 7,
                        label: "近 7 天"
                      }),
                      createVNode(_component_el_option, {
                        value: 15,
                        label: "近 15 天"
                      }),
                      createVNode(_component_el_option, {
                        value: 30,
                        label: "近 30 天"
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"])) : (openBlock(), createBlock(_component_el_date_picker, {
                    key: 1,
                    modelValue: reportCustomRange.value,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => reportCustomRange.value = $event),
                    type: "daterange",
                    "value-format": "YYYY-MM-DD",
                    "range-separator": "至",
                    "start-placeholder": "开始日期",
                    "end-placeholder": "结束日期",
                    class: "range-control"
                  }, null, 8, ["modelValue"]))
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "报告模块（可增删与排序）" }, {
                default: withCtx(() => [
                  createVNode(ModuleSelector, {
                    modelValue: selectedModules.value,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => selectedModules.value = $event),
                    modules: allModules.value
                  }, null, 8, ["modelValue", "modules"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "模块参数" }, {
                default: withCtx(() => [
                  selectedWithParams.value.length ? (openBlock(), createElementBlock("div", _hoisted_2$1, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(selectedWithParams.value, (m) => {
                      return openBlock(), createElementBlock("div", {
                        key: "p-" + m.key,
                        class: "param-block"
                      }, [
                        createBaseVNode("div", _hoisted_3$1, toDisplayString(m.title), 1),
                        moduleParams.value[m.key] ? (openBlock(), createElementBlock("div", _hoisted_4$1, [
                          (openBlock(true), createElementBlock(Fragment, null, renderList(m.params, (p) => {
                            return openBlock(), createElementBlock("div", {
                              class: "param-row",
                              key: p.key
                            }, [
                              createBaseVNode("span", _hoisted_5$1, toDisplayString(p.label), 1),
                              p.type === "int" ? (openBlock(), createBlock(_component_el_input_number, {
                                key: 0,
                                modelValue: moduleParams.value[m.key][p.key],
                                "onUpdate:modelValue": ($event) => moduleParams.value[m.key][p.key] = $event,
                                min: p.min ?? void 0,
                                max: p.max ?? void 0,
                                size: "small",
                                "controls-position": "right"
                              }, null, 8, ["modelValue", "onUpdate:modelValue", "min", "max"])) : (openBlock(), createBlock(_component_el_input, {
                                key: 1,
                                modelValue: moduleParams.value[m.key][p.key],
                                "onUpdate:modelValue": ($event) => moduleParams.value[m.key][p.key] = $event,
                                size: "small"
                              }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                            ]);
                          }), 128))
                        ])) : createCommentVNode("", true)
                      ]);
                    }), 128))
                  ])) : (openBlock(), createElementBlock("div", _hoisted_6$1, "所选模块暂无可配置参数。"))
                ]),
                _: 1
              })
            ]),
            _: 1
          })), [
            [_directive_loading, loadingModules.value]
          ]),
          createVNode(_component_el_dialog, {
            modelValue: saveDialogVisible.value,
            "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => saveDialogVisible.value = $event),
            title: "保存为模板",
            width: "420px",
            "append-to-body": ""
          }, {
            footer: withCtx(() => [
              createVNode(_component_el_button, {
                onClick: _cache[11] || (_cache[11] = ($event) => saveDialogVisible.value = false)
              }, {
                default: withCtx(() => [..._cache[24] || (_cache[24] = [
                  createTextVNode("取消", -1)
                ])]),
                _: 1
              }),
              createVNode(_component_el_button, {
                type: "primary",
                loading: savingTemplate.value,
                onClick: saveAsTemplate
              }, {
                default: withCtx(() => [..._cache[25] || (_cache[25] = [
                  createTextVNode("保存", -1)
                ])]),
                _: 1
              }, 8, ["loading"])
            ]),
            default: withCtx(() => [
              createVNode(_component_el_form, { "label-position": "top" }, {
                default: withCtx(() => [
                  createVNode(_component_el_form_item, { label: "模板名称" }, {
                    default: withCtx(() => [
                      createVNode(_component_el_input, {
                        modelValue: templateForm.value.name,
                        "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => templateForm.value.name = $event),
                        maxlength: "128",
                        "show-word-limit": "",
                        placeholder: "周报模板"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, { label: "描述" }, {
                    default: withCtx(() => [
                      createVNode(_component_el_input, {
                        modelValue: templateForm.value.description,
                        "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => templateForm.value.description = $event),
                        type: "textarea",
                        rows: 2,
                        maxlength: "255",
                        placeholder: "可选"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, { label: "公开模板（所有用户可见）" }, {
                    default: withCtx(() => [
                      createVNode(_component_el_switch, {
                        modelValue: templateForm.value.is_public,
                        "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => templateForm.value.is_public = $event)
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        _: 1
      }, 8, ["modelValue"]);
    };
  }
});

const ReportExportDrawer = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-06af7116"]]);

const _hoisted_1 = { class: "cockpit" };
const _hoisted_2 = {
  class: "kpi-row",
  "aria-label": "核心指标"
};
const _hoisted_3 = { class: "kpi-card kpi-blue" };
const _hoisted_4 = { class: "kpi-body" };
const _hoisted_5 = { class: "kpi-value" };
const _hoisted_6 = { class: "kpi-card kpi-green" };
const _hoisted_7 = { class: "kpi-body" };
const _hoisted_8 = { class: "kpi-value" };
const _hoisted_9 = { class: "kpi-card kpi-red" };
const _hoisted_10 = { class: "kpi-body" };
const _hoisted_11 = { class: "kpi-value danger" };
const _hoisted_12 = { class: "kpi-card kpi-amber" };
const _hoisted_13 = { class: "kpi-body" };
const _hoisted_14 = { class: "kpi-value" };
const _hoisted_15 = { class: "kpi-body" };
const _hoisted_16 = { class: "kpi-value kpi-status-val" };
const _hoisted_17 = { class: "kpi-foot" };
const _hoisted_18 = { class: "sit-left" };
const _hoisted_19 = { class: "sit-level" };
const _hoisted_20 = { class: "sit-text" };
const _hoisted_21 = { class: "sit-kpis" };
const _hoisted_22 = { class: "sit-kpi" };
const _hoisted_23 = { class: "k" };
const _hoisted_24 = { class: "sit-kpi" };
const _hoisted_25 = { class: "k danger" };
const _hoisted_26 = { class: "sit-kpi" };
const _hoisted_27 = { class: "k" };
const _hoisted_28 = { class: "sit-kpi" };
const _hoisted_29 = { class: "k" };
const _hoisted_30 = { class: "sit-kpi" };
const _hoisted_31 = { class: "k" };
const _hoisted_32 = {
  key: 0,
  class: "sit-action"
};
const _hoisted_33 = { class: "widget-grid" };
const _hoisted_34 = { class: "card widget widget-trend" };
const _hoisted_35 = { class: "w-head" };
const _hoisted_36 = { class: "card widget widget-alert" };
const _hoisted_37 = { class: "scroll-wrap" };
const _hoisted_38 = ["title", "onClick"];
const _hoisted_39 = { class: "ai-body" };
const _hoisted_40 = { class: "ai-title" };
const _hoisted_41 = { class: "ai-meta" };
const _hoisted_42 = {
  key: 0,
  class: "feed-empty"
};
const _hoisted_43 = { class: "card widget widget-source" };
const _hoisted_44 = { class: "card widget widget-sentiment" };
const _hoisted_45 = { class: "card widget widget-feed" };
const _hoisted_46 = { class: "scroll-wrap" };
const _hoisted_47 = ["onClick"];
const _hoisted_48 = { class: "fi-body" };
const _hoisted_49 = { class: "fi-title" };
const _hoisted_50 = { class: "fi-meta" };
const _hoisted_51 = {
  key: 0,
  class: "feed-empty"
};
const _hoisted_52 = { class: "card widget widget-word" };
const _hoisted_53 = { class: "w-head" };
const _hoisted_54 = { class: "card widget widget-geo" };
const _hoisted_55 = { class: "ht-body" };
const _hoisted_56 = {
  key: 0,
  class: "ht-error"
};
const _hoisted_57 = ["onClick"];
const _hoisted_58 = { class: "ht-event-head" };
const _hoisted_59 = { class: "ht-event-title" };
const _hoisted_60 = { class: "ht-event-meta" };
const _hoisted_61 = {
  key: 0,
  class: "ht-empty"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Dashboard",
  setup(__props) {
    const { can } = usePermission();
    const router = useRouter();
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
    const wordMode = ref("risk");
    const wordModeOptions = [
      { label: "风险关键词", value: "risk" },
      { label: "热点主题", value: "hot" }
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
      regions: [],
      region_detail: []
    });
    const recentNews = ref([]);
    const alerts = ref([]);
    const doubledNews = computed(() => recentNews.value.length ? [...recentNews.value, ...recentNews.value] : []);
    const doubledAlerts = computed(() => alerts.value.length ? [...alerts.value, ...alerts.value] : []);
    const feedDuration = computed(() => Math.max(12, recentNews.value.length * 3));
    const alertDuration = computed(() => Math.max(12, alerts.value.length * 3));
    const topicKeywords = ref([]);
    const topicLoaded = ref(false);
    const topicLoading = ref(false);
    function loadTopicKeywords(force = false) {
      if (topicLoading.value) return Promise.resolve();
      if (topicLoaded.value && !force) return Promise.resolve();
      topicLoading.value = true;
      return api.get("/dashboard/hot-keywords", {
        params: { days: trendDays.value, limit: 10, category: "主题" }
      }).then((res) => {
        topicKeywords.value = res.data.items || [];
        topicLoaded.value = true;
      }).catch(() => {
        topicKeywords.value = [];
      }).finally(() => {
        topicLoading.value = false;
      });
    }
    const hotTopicDrawer = ref(false);
    const hotTopicLabel = ref("");
    const hotTopicEvents = ref([]);
    const hotTopicLoading = ref(false);
    const hotTopicError = ref("");
    async function openHotTopic(keyword) {
      if (!keyword) return;
      hotTopicLabel.value = keyword;
      hotTopicDrawer.value = true;
      hotTopicLoading.value = true;
      hotTopicError.value = "";
      hotTopicEvents.value = [];
      const kw = topicValueFromLabel(keyword);
      try {
        const data = await getEventsByHotTopic(kw);
        hotTopicEvents.value = data.items || [];
      } catch {
        hotTopicError.value = "加载失败，请稍后重试";
      } finally {
        hotTopicLoading.value = false;
      }
    }
    function goEventDetail(id) {
      if (!id) return;
      hotTopicDrawer.value = false;
      router.push(`/event/${id}`);
    }
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
    const reportDrawer = ref(false);
    function openReportDrawer() {
      reportDrawer.value = true;
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
      const src = stats.region_detail?.length ? stats.region_detail : stats.regions;
      if (!regionChart || !src?.length) return;
      const data = [...src].sort((a, b) => b.count - a.count).slice(0, 10);
      regionChart.setOption({
        tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        grid: { left: 110, right: 30, top: 10, bottom: 20 },
        xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        yAxis: { type: "category", data: data.map((d) => d.region_name).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12 }, inverse: true },
        series: [{ name: "舆情数", type: "bar", data: data.map((d) => d.count).reverse(), barWidth: 16, itemStyle: { borderRadius: [0, 6, 6, 0], color: new LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#ff9f0a" }, { offset: 1, color: "#ffd60a" }]) } }]
      });
    }
    function renderWordCloud() {
      if (!wordcloudChart) return;
      let data = [];
      let tooltipFormatter = (p) => `${p.name}: ${p.value}`;
      if (wordMode.value === "hot") {
        if (!topicKeywords.value.length) {
          wordcloudChart.clear();
          return;
        }
        const max = Math.max(...topicKeywords.value.map((k) => k.count), 1);
        data = topicKeywords.value.slice(0, 30).map((k) => ({
          name: k.keyword,
          value: k.count,
          textStyle: { color: `hsl(${k.count / max * 210 + 200}, 70%, ${60 - k.count / max * 30}%)` }
        }));
        tooltipFormatter = (p) => {
          const k = topicKeywords.value.find((x) => x.keyword === p.name);
          if (!k) return `${p.name}: ${p.value}`;
          const arrow = k.trend === "up" ? "↑" : k.trend === "down" ? "↓" : "→";
          const label = k.trend === "up" ? "上升" : k.trend === "down" ? "下降" : "持平";
          return `${k.keyword}<br/>近${trendDays.value}天: ${k.count}<br/>趋势: ${arrow} ${label}`;
        };
      } else {
        if (!stats.keywords?.length) {
          wordcloudChart.clear();
          return;
        }
        const max = stats.keywords[0]?.count || 1;
        data = stats.keywords.slice(0, 30).map((kw) => ({
          name: kw.word,
          value: kw.count,
          textStyle: { color: `hsl(${kw.count / max * 210 + 200}, 70%, ${60 - kw.count / max * 30}%)` }
        }));
      }
      wordcloudChart.setOption({
        tooltip: {
          show: true,
          backgroundColor: "rgba(29,29,31,0.94)",
          borderColor: "transparent",
          textStyle: { color: "#fff", fontSize: 12 },
          formatter: tooltipFormatter
        },
        series: [{ type: "wordCloud", shape: "circle", left: "center", top: "center", width: "90%", height: "90%", sizeRange: [14, 42], rotationRange: [-30, 30], gridSize: 8, layoutAnimation: true, textStyle: { fontFamily: "sans-serif", fontWeight: "bold" }, emphasis: { textStyle: { color: "#0071e3" } }, data }]
      }, { notMerge: true });
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
      if (wordMode.value === "hot") {
        loadTopicKeywords(true).then(() => renderWordCloud());
      }
    });
    watch(wordMode, async (m) => {
      if (m === "hot") {
        await loadTopicKeywords();
      }
      renderWordCloud();
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
    function riskPill(l) {
      return { critical: "pill-red", high: "pill-red", medium: "pill-orange", low: "pill-green" }[l] || "pill-gray";
    }
    let feedTimer;
    onMounted(async () => {
      await nextTick();
      if (trendRef.value) trendChart = init(trendRef.value);
      if (sourceRef.value) sourceChart = init(sourceRef.value);
      if (wordcloudRef.value) wordcloudChart = init(wordcloudRef.value);
      if (regionRef.value) regionChart = init(regionRef.value);
      wordcloudChart?.on("click", (params) => {
        if (wordMode.value !== "hot") return;
        const name = params?.name;
        if (name) openHotTopic(name);
      });
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
      const _component_el_drawer = resolveComponent("el-drawer");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("section", _hoisted_2, [
          createBaseVNode("article", _hoisted_3, [
            _cache[7] || (_cache[7] = createBaseVNode("span", { class: "kpi-ico" }, "▦", -1)),
            createBaseVNode("div", _hoisted_4, [
              _cache[5] || (_cache[5] = createBaseVNode("div", { class: "kpi-label" }, "总舆情数", -1)),
              createBaseVNode("div", _hoisted_5, toDisplayString(stats.total.toLocaleString()), 1),
              _cache[6] || (_cache[6] = createBaseVNode("div", { class: "kpi-foot" }, "累计监测数据", -1))
            ])
          ]),
          createBaseVNode("article", _hoisted_6, [
            _cache[10] || (_cache[10] = createBaseVNode("span", { class: "kpi-ico" }, "↗", -1)),
            createBaseVNode("div", _hoisted_7, [
              _cache[8] || (_cache[8] = createBaseVNode("div", { class: "kpi-label" }, "今日新增", -1)),
              createBaseVNode("div", _hoisted_8, toDisplayString(stats.today.toLocaleString()), 1),
              _cache[9] || (_cache[9] = createBaseVNode("div", { class: "kpi-foot" }, "当日采集", -1))
            ])
          ]),
          createBaseVNode("article", _hoisted_9, [
            _cache[13] || (_cache[13] = createBaseVNode("span", { class: "kpi-ico" }, "!", -1)),
            createBaseVNode("div", _hoisted_10, [
              _cache[11] || (_cache[11] = createBaseVNode("div", { class: "kpi-label" }, "高风险", -1)),
              createBaseVNode("div", _hoisted_11, toDisplayString(stats.high_risk.toLocaleString()), 1),
              _cache[12] || (_cache[12] = createBaseVNode("div", { class: "kpi-foot" }, "需关注处理", -1))
            ])
          ]),
          createBaseVNode("article", _hoisted_12, [
            _cache[16] || (_cache[16] = createBaseVNode("span", { class: "kpi-ico" }, "◎", -1)),
            createBaseVNode("div", _hoisted_13, [
              _cache[14] || (_cache[14] = createBaseVNode("div", { class: "kpi-label" }, "事件数", -1)),
              createBaseVNode("div", _hoisted_14, toDisplayString((stats.event_count || 0).toLocaleString()), 1),
              _cache[15] || (_cache[15] = createBaseVNode("div", { class: "kpi-foot" }, "聚合事件", -1))
            ])
          ]),
          createBaseVNode("article", {
            class: normalizeClass(["kpi-card kpi-status", collectorOnline.value ? "is-on" : "is-off"])
          }, [
            _cache[19] || (_cache[19] = createBaseVNode("span", { class: "kpi-ico" }, "↻", -1)),
            createBaseVNode("div", _hoisted_15, [
              _cache[18] || (_cache[18] = createBaseVNode("div", { class: "kpi-label" }, "采集状态", -1)),
              createBaseVNode("div", _hoisted_16, [
                _cache[17] || (_cache[17] = createBaseVNode("span", { class: "status-dot" }, null, -1)),
                createTextVNode(toDisplayString(collectorText.value), 1)
              ]),
              createBaseVNode("div", _hoisted_17, toDisplayString(collectorLastRun.value), 1)
            ])
          ], 2)
        ]),
        createBaseVNode("section", {
          class: normalizeClass(["situation", "lvl-" + situationLevel.value])
        }, [
          createBaseVNode("div", _hoisted_18, [
            createBaseVNode("div", _hoisted_19, [
              _cache[20] || (_cache[20] = createBaseVNode("span", { class: "lvl-dot" }, null, -1)),
              createTextVNode(toDisplayString(levelText.value), 1)
            ]),
            createBaseVNode("div", _hoisted_20, toDisplayString(situationText.value), 1)
          ]),
          createBaseVNode("div", _hoisted_21, [
            createBaseVNode("div", _hoisted_22, [
              createBaseVNode("span", _hoisted_23, toDisplayString(stats.total.toLocaleString()), 1),
              _cache[21] || (_cache[21] = createBaseVNode("span", { class: "l" }, "总舆情", -1))
            ]),
            createBaseVNode("div", _hoisted_24, [
              createBaseVNode("span", _hoisted_25, toDisplayString(stats.high_risk.toLocaleString()), 1),
              _cache[22] || (_cache[22] = createBaseVNode("span", { class: "l" }, "高风险", -1))
            ]),
            createBaseVNode("div", _hoisted_26, [
              createBaseVNode("span", _hoisted_27, toDisplayString(riskRate.value) + "%", 1),
              _cache[23] || (_cache[23] = createBaseVNode("span", { class: "l" }, "风险率", -1))
            ]),
            createBaseVNode("div", _hoisted_28, [
              createBaseVNode("span", _hoisted_29, toDisplayString(negativeRate.value) + "%", 1),
              _cache[24] || (_cache[24] = createBaseVNode("span", { class: "l" }, "负面率", -1))
            ]),
            createBaseVNode("div", _hoisted_30, [
              createBaseVNode("span", _hoisted_31, toDisplayString((stats.event_count || 0).toLocaleString()), 1),
              _cache[25] || (_cache[25] = createBaseVNode("span", { class: "l" }, "事件", -1))
            ])
          ]),
          unref(can)("reports:read") || unref(can)("reports:export") ? (openBlock(), createElementBlock("div", _hoisted_32, [
            unref(can)("reports:export") ? (openBlock(), createBlock(_component_el_button, {
              key: 0,
              type: "primary",
              onClick: openReportDrawer
            }, {
              default: withCtx(() => [..._cache[26] || (_cache[26] = [
                createBaseVNode("span", { style: { "margin-right": "4px" } }, "⎙", -1),
                createTextVNode("导出舆情报告 ", -1)
              ])]),
              _: 1
            })) : createCommentVNode("", true)
          ])) : createCommentVNode("", true)
        ], 2),
        createBaseVNode("section", _hoisted_33, [
          createBaseVNode("article", _hoisted_34, [
            createBaseVNode("header", _hoisted_35, [
              _cache[27] || (_cache[27] = createBaseVNode("h3", { class: "w-title" }, "舆情趋势", -1)),
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
          createBaseVNode("article", _hoisted_36, [
            _cache[28] || (_cache[28] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "预警滚动"),
              createBaseVNode("span", { class: "live-dot warn" }, "● ALERT")
            ], -1)),
            createBaseVNode("div", _hoisted_37, [
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
                    createBaseVNode("div", _hoisted_39, [
                      createBaseVNode("div", _hoisted_40, toDisplayString(a.opinion_title || a.rule_name), 1),
                      createBaseVNode("div", _hoisted_41, toDisplayString(a.rule_name) + " · " + toDisplayString(fmtTime(a.created_at)) + toDisplayString(a.handled ? " · 已处置" : ""), 1)
                    ])
                  ], 10, _hoisted_38);
                }), 128))
              ], 4),
              !alerts.value.length ? (openBlock(), createElementBlock("div", _hoisted_42, "暂无预警")) : createCommentVNode("", true)
            ])
          ]),
          createBaseVNode("article", _hoisted_43, [
            _cache[29] || (_cache[29] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "来源分布")
            ], -1)),
            createBaseVNode("div", {
              ref_key: "sourceRef",
              ref: sourceRef,
              class: "chart-box"
            }, null, 512)
          ]),
          createBaseVNode("article", _hoisted_44, [
            _cache[30] || (_cache[30] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "情感分布")
            ], -1)),
            createVNode(SentimentDonut, { data: realSentimentData.value }, null, 8, ["data"])
          ]),
          createBaseVNode("article", _hoisted_45, [
            _cache[31] || (_cache[31] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "实时快讯"),
              createBaseVNode("span", { class: "live-dot" }, "● LIVE")
            ], -1)),
            createBaseVNode("div", _hoisted_46, [
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
                    createBaseVNode("div", _hoisted_48, [
                      createBaseVNode("div", _hoisted_49, toDisplayString(n.title), 1),
                      createBaseVNode("div", _hoisted_50, toDisplayString(n.source) + " · " + toDisplayString(n.region_name) + " · " + toDisplayString(fmtTime(n.created_at)) + " · 风险 " + toDisplayString(n.risk_score), 1)
                    ])
                  ], 8, _hoisted_47);
                }), 128))
              ], 4),
              !recentNews.value.length ? (openBlock(), createElementBlock("div", _hoisted_51, "暂无实时快讯")) : createCommentVNode("", true)
            ])
          ]),
          createBaseVNode("article", _hoisted_52, [
            createBaseVNode("header", _hoisted_53, [
              _cache[32] || (_cache[32] = createBaseVNode("h3", { class: "w-title" }, "热点词云", -1)),
              createVNode(SegmentedControl, {
                modelValue: wordMode.value,
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => wordMode.value = $event),
                options: wordModeOptions
              }, null, 8, ["modelValue"])
            ]),
            createBaseVNode("div", {
              ref_key: "wordcloudRef",
              ref: wordcloudRef,
              class: "chart-box"
            }, null, 512)
          ]),
          createBaseVNode("article", _hoisted_54, [
            _cache[33] || (_cache[33] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "地理分布（地区舆情细分 TOP）")
            ], -1)),
            createBaseVNode("div", {
              ref_key: "regionRef",
              ref: regionRef,
              class: "chart-box"
            }, null, 512)
          ])
        ]),
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"]),
        createVNode(ReportExportDrawer, {
          modelValue: reportDrawer.value,
          "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => reportDrawer.value = $event)
        }, null, 8, ["modelValue"]),
        createVNode(_component_el_drawer, {
          modelValue: hotTopicDrawer.value,
          "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => hotTopicDrawer.value = $event),
          title: `${hotTopicLabel.value} 相关事件`,
          direction: "rtl",
          size: "480px",
          class: "hot-topic-drawer"
        }, {
          default: withCtx(() => [
            withDirectives((openBlock(), createElementBlock("div", _hoisted_55, [
              hotTopicError.value ? (openBlock(), createElementBlock("div", _hoisted_56, toDisplayString(hotTopicError.value), 1)) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(hotTopicEvents.value, (ev) => {
                  return openBlock(), createElementBlock("div", {
                    key: ev.id,
                    class: "ht-event",
                    onClick: ($event) => goEventDetail(ev.id)
                  }, [
                    createBaseVNode("div", _hoisted_58, [
                      createBaseVNode("span", _hoisted_59, toDisplayString(ev.title), 1),
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", riskPill(ev.risk_level)])
                      }, [
                        _cache[34] || (_cache[34] = createBaseVNode("span", { class: "dot" }, null, -1)),
                        createTextVNode(toDisplayString(riskText(ev.risk_level)), 1)
                      ], 2)
                    ]),
                    createBaseVNode("div", _hoisted_60, [
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(eventStatusPill)(ev.status)])
                      }, toDisplayString(unref(eventStatusLabel)(ev.status)), 3),
                      createBaseVNode("span", null, "热度 " + toDisplayString(ev.heat_score), 1),
                      createBaseVNode("span", null, toDisplayString(ev.source_count ?? "-") + " 个来源", 1),
                      createBaseVNode("span", null, toDisplayString(fmtTime(ev.last_time || "")), 1)
                    ])
                  ], 8, _hoisted_57);
                }), 128)),
                !hotTopicLoading.value && hotTopicEvents.value.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_61, " 暂无相关事件 ")) : createCommentVNode("", true)
              ], 64))
            ])), [
              [_directive_loading, hotTopicLoading.value]
            ])
          ]),
          _: 1
        }, 8, ["modelValue", "title"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Dashboard = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-251a66a4"]]);

export { Dashboard as default };
