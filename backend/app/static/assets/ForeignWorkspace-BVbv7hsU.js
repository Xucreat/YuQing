import { d as defineComponent, z as usePermission, r as ref, C as onMounted, G as onBeforeUnmount, g as api, E as ElMessage, A as watch, w as withDirectives, c as createElementBlock, a as createBaseVNode, F as Fragment, i as renderList, H as unref, t as toDisplayString, s as createCommentVNode, n as normalizeClass, e as createTextVNode, N as vModelSelect, I as vShow, k as normalizeStyle, q as createBlock, m as createVNode, L as useRoute, j as computed, f as reactive, B as resolveDirective, D as nextTick, o as openBlock, h as useRouter, _ as _export_sfc } from './index-CNz59AKK.js';
import { c as createTextStyle$1, S as SeriesModel, C as ChartView, u as use, a as install, b as install$1, d as installLabelLayout, e as createDimensions, f as SeriesData, Z as ZRText, g as enableHoverEmphasis, r as registerLayout, h as getLayoutRect, l as linearMap, j as registerPreprocessor, k as isArray, m as each, n as capitalFirst, i as init, L as LinearGradient } from './index-F2TANFn2.js';
import { F as ForeignOpinionDetailModal } from './ForeignOpinionDetailModal-IbLRcgq2.js';
import { F as ForeignOpinionListView, a as ForeignAIReviewView } from './ForeignOpinionListView-B2ZQCLdN.js';
import { F as ForeignEventsView } from './ForeignEventsView-BlL4cd5u.js';
import './opinion-Cag9WtuS.js';
import './EventDispositionDialog-CBvIUHGY.js';

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

const _hoisted_1 = { class: "foreign-page" };
const _hoisted_2 = {
  class: "tabs",
  role: "tablist"
};
const _hoisted_3 = ["onClick"];
const _hoisted_4 = { class: "tab-actions" };
const _hoisted_5 = { class: "source-scope-label" };
const _hoisted_6 = {
  key: 0,
  class: "panel visualization-panel"
};
const _hoisted_7 = { key: 0 };
const _hoisted_8 = {
  key: 1,
  class: "error-text"
};
const _hoisted_9 = { class: "fw-dash-head" };
const _hoisted_10 = {
  class: "toolbar",
  style: { "margin-bottom": "0" }
};
const _hoisted_11 = { class: "muted" };
const _hoisted_12 = {
  key: 0,
  class: "stale-badge"
};
const _hoisted_13 = {
  key: 0,
  class: "error-state"
};
const _hoisted_14 = {
  key: 1,
  class: "fw-dash"
};
const _hoisted_15 = { class: "fw-kpi-grid" };
const _hoisted_16 = { class: "fw-kpi" };
const _hoisted_17 = { class: "fw-kpi-value" };
const _hoisted_18 = { class: "fw-kpi" };
const _hoisted_19 = { class: "fw-kpi-value" };
const _hoisted_20 = { class: "fw-kpi" };
const _hoisted_21 = { class: "fw-kpi-value" };
const _hoisted_22 = { class: "fw-kpi" };
const _hoisted_23 = { class: "fw-kpi-value" };
const _hoisted_24 = { class: "fw-kpi" };
const _hoisted_25 = { class: "fw-kpi-value" };
const _hoisted_26 = { class: "fw-kpi" };
const _hoisted_27 = { class: "fw-kpi-value" };
const _hoisted_28 = { class: "fw-dash-grid" };
const _hoisted_29 = { class: "fw-card fw-card-trend fw-col-1" };
const _hoisted_30 = { class: "fw-card-head" };
const _hoisted_31 = { class: "fw-legend" };
const _hoisted_32 = ["onClick"];
const _hoisted_33 = {
  key: 0,
  class: "empty"
};
const _hoisted_34 = { class: "fw-card fw-card-alert fw-col-2" };
const _hoisted_35 = { class: "fw-card-head" };
const _hoisted_36 = { class: "muted" };
const _hoisted_37 = {
  key: 0,
  class: "empty"
};
const _hoisted_38 = {
  key: 1,
  class: "fw-alert-feed"
};
const _hoisted_39 = { class: "fw-alert-summary" };
const _hoisted_40 = { class: "fw-alert-sum" };
const _hoisted_41 = { class: "fw-alert-sum" };
const _hoisted_42 = { class: "fw-alert-list" };
const _hoisted_43 = ["onClick"];
const _hoisted_44 = { class: "fw-alert-main" };
const _hoisted_45 = { class: "fw-alert-title" };
const _hoisted_46 = { class: "fw-alert-meta" };
const _hoisted_47 = {
  key: 0,
  class: "fw-alert-copy"
};
const _hoisted_48 = { class: "fw-alert-list" };
const _hoisted_49 = ["onClick"];
const _hoisted_50 = { class: "fw-alert-main" };
const _hoisted_51 = { class: "fw-alert-title" };
const _hoisted_52 = { class: "fw-alert-meta" };
const _hoisted_53 = { class: "fw-card fw-card-source fw-col-1" };
const _hoisted_54 = { class: "fw-card-head" };
const _hoisted_55 = { class: "muted" };
const _hoisted_56 = {
  key: 0,
  class: "empty"
};
const _hoisted_57 = { class: "fw-card fw-col-2" };
const _hoisted_58 = {
  key: 0,
  class: "empty"
};
const _hoisted_59 = { class: "fw-card fw-card-hotword fw-col-1" };
const _hoisted_60 = { class: "fw-card-head" };
const _hoisted_61 = { class: "muted" };
const _hoisted_62 = {
  key: 0,
  class: "empty"
};
const _hoisted_63 = { class: "fw-card fw-card-eventstatus fw-col-2" };
const _hoisted_64 = { class: "fw-eventstatus-scroll" };
const _hoisted_65 = {
  key: 0,
  class: "empty"
};
const _hoisted_66 = { class: "visualization-meta" };
const _hoisted_67 = {
  key: 2,
  class: "state"
};
const _hoisted_68 = { key: 1 };
const _hoisted_69 = { class: "subtabs" };
const opinionSize = 20;
const riskSize = 100;
const riskMaxPages = 20;
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "ForeignWorkspace",
  setup(__props) {
    const tabs = [
      { value: "dashboard", label: "外网 Dashboard" },
      { value: "opinions", label: "国外舆情" },
      { value: "events", label: "外网事件" }
    ];
    const visibleTabs = tabs.filter((item) => item.value !== "alerts" && item.value !== "alertRules");
    const route = useRoute();
    const router = useRouter();
    const { hasPermission } = usePermission();
    function normalizeTab(value) {
      const valid = ["dashboard", "opinions", "events"];
      return valid.includes(value) ? value : "dashboard";
    }
    const activeTab = ref(normalizeTab(route.query.tab));
    const loading = ref(false);
    const approvedSources = ref([]);
    const selectedSourceIds = ref([]);
    const approvedSourceLabel = computed(() => approvedSources.value.length ? approvedSources.value.map((source) => source.name || String(source.id)).join("、") : "暂无");
    const scheduleStatus = ref(null);
    const opinions = ref([]);
    const runs = ref([]);
    const risks = ref([]);
    const eventCandidates = ref([]);
    const foreignEvents = ref([]);
    const eventRunFailures = ref([]);
    const eventAutoStatus = ref(null);
    const eventLoadError = ref(null);
    const selectedForeignEvent = ref(null);
    const opinionSection = ref("list");
    const manualReviews = ref([]);
    const reviewStatusFilter = ref("pending_review");
    const eventDetailLoadingId = ref(null);
    const visualizationDays = ref(7);
    const visualizationError = ref(null);
    const visualizationStale = ref(false);
    const dashboardSummary = ref(null);
    const dashboardRisk = ref(null);
    const dashboardEvents = ref(null);
    const dashboardTrends = ref(null);
    const dashboardAlerts = ref(null);
    const dashboardSources = ref(null);
    const hotwordItems = ref([]);
    const hotwordTrendItems = ref([]);
    const hotwordMeta = ref({});
    const hotwordLanguage = ref("");
    const opinionSources = ref([]);
    const opinionTotal = ref(0);
    const opinionPage = ref(1);
    const riskTotal = ref(0);
    const riskPage = ref(1);
    const detailVisible = ref(false);
    const detailId = ref(null);
    const riskSource = ref(
      window.localStorage.getItem("foreign-risk-source") === "ai" ? "ai" : window.localStorage.getItem("foreign-risk-source") === "rule" ? "rule" : "current"
    );
    function setRiskSource(value) {
      riskSource.value = value === "ai" || value === "rule" ? value : "current";
      window.localStorage.setItem("foreign-risk-source", riskSource.value);
      loadOpinions();
    }
    const ZH_DICT = {
      high: "高",
      medium: "中",
      low: "低",
      critical: "紧急",
      unknown: "未知",
      none: "无",
      other: "其他",
      positive: "正面",
      negative: "负面",
      neutral: "中性",
      completed: "已完成",
      pending: "待处理",
      processing: "进行中",
      running: "运行中",
      queued: "排队中",
      failed: "失败",
      success: "成功",
      partial: "部分成功",
      skipped: "已跳过",
      error: "异常",
      candidate: "候选",
      converted: "已转正",
      confirmed: "已确认",
      rejected: "已拒绝",
      merged: "已合并",
      pending_review: "待人工复核",
      use_ai_display: "采用 AI 作为当前风险",
      keep_rule: "保留规则",
      confirm_event_change: "确认事件影响",
      confirm_alert_change: "确认预警影响",
      reject_change: "驳回",
      monitoring: "监测中",
      closed: "已关闭",
      archived: "已归档",
      split: "已拆分",
      dismissed: "已忽略",
      triggered: "待处理",
      acknowledged: "已确认",
      resolved: "已解决",
      suppressed: "已抑制",
      manual: "人工",
      auto: "自动",
      automatic: "自动",
      rule: "规则",
      system: "系统",
      enabled: "已启用",
      disabled: "已停用",
      included: "已纳入",
      excluded: "未纳入",
      zh: "中文",
      en: "英文",
      mixed: "中英混合",
      risk_score: "风险分",
      risk_level: "风险等级",
      risk_category: "风险类别",
      keyword_combo: "关键词组合",
      confirmed_event: "确认事件"
    };
    function zh(value) {
      if (value === null || value === void 0 || value === "") return "-";
      const key = String(value);
      return ZH_DICT[key] || key;
    }
    const aiBatchRun = ref(null);
    const selectedReviewIds = ref([]);
    let aiBatchTimer = null;
    const opinionFilters = reactive({ q: "", source: "", keyword: "", date_from: "", date_to: "" });
    const riskFilters = reactive({ q: "", source: "", language: "", sentiment: "", risk_level: "", analysis_status: "", date_from: "", date_to: "" });
    hasPermission("foreign:risk:analyze");
    hasPermission("foreign:ai:analyze");
    hasPermission("foreign:ai:batch:read");
    hasPermission("foreign:ai:batch:cancel");
    hasPermission("foreign:ai:review:read");
    hasPermission("foreign:events:review:read");
    hasPermission("foreign:alerts:review:read");
    hasPermission("foreign:events:review:confirm");
    hasPermission("foreign:alerts:review:confirm");
    hasPermission("foreign:ai:review:reject");
    hasPermission("foreign:ai:full-confirm");
    hasPermission("foreign:events:confirm");
    hasPermission("foreign:events:status");
    hasPermission("foreign:events:merge");
    hasPermission("foreign:events:split");
    async function loadApprovedSources() {
      try {
        const { data } = await api.get("/foreign/sources/approved");
        approvedSources.value = (data.items || []).map((item) => ({ id: item.id, name: item.name }));
        const available = new Set(approvedSources.value.map((item) => item.id));
        selectedSourceIds.value = selectedSourceIds.value.filter((id) => available.has(id));
        if (!selectedSourceIds.value.length) selectedSourceIds.value = approvedSources.value.map((item) => item.id);
      } catch {
        approvedSources.value = [];
        selectedSourceIds.value = [];
      }
    }
    async function loadScheduleStatus() {
      try {
        scheduleStatus.value = (await api.get("/foreign/collection-schedule/status")).data;
      } catch {
        scheduleStatus.value = { enabled: false, registered: false, running: false, eligible_source_count: 0 };
      }
    }
    function switchTab(tab) {
      router.push({ path: "/foreign", query: { ...route.query, tab } });
    }
    function loadTab(tab) {
      if (tab === "dashboard") {
        loadDashboard();
        loadScheduleStatus();
      }
      if (tab === "opinions") {
        loadOpinions();
        loadRisk();
      }
      if (tab === "events") loadEvents();
    }
    function visualizationFailure(err) {
      const status = err?.response?.status;
      const code = err?.response?.data?.error_code;
      if (code === "FOREIGN_VISUALIZATION_QUERY_FAILED" || status === 503) return "外网可视化数据暂时不可用";
      if (status === 403) return "当前账号没有外网可视化权限";
      if (status === 422) return "外网可视化请求参数无效";
      return "外网可视化数据加载失败，请稍后重试";
    }
    const trendChartRef = ref();
    const hotwordChartRef = ref();
    let trendChart = null;
    let hotwordChart = null;
    const sourceChartRef = ref();
    let sourceChart = null;
    const riskChartRef = ref();
    let riskChart = null;
    const RISK_MAP = {
      critical: { name: "紧急", color: "#ff3b30" },
      high: { name: "高", color: "#ff6b35" },
      medium: { name: "中", color: "#ff9f0a" },
      low: { name: "低", color: "#34c759" },
      unknown: { name: "未知", color: "#8e8e93" },
      none: { name: "无", color: "#c7c7cc" },
      other: { name: "其他", color: "#af52de" }
    };
    const alertFeed = ref([]);
    const alertViewportEl = ref();
    const alertTrackEl = ref();
    const alertFeedOverflow = ref(false);
    const alertNeedScroll = ref(false);
    const alertScrollDuration = ref("18s");
    const alertPendingCount = computed(() => (alertFeed.value || []).filter((a) => a.status === "triggered").length);
    const alertDoneCount = computed(() => (alertFeed.value || []).length - alertPendingCount.value);
    let alertResizeObserver = null;
    const trendSeriesOptions = [
      { key: "articles", label: "文章", color: "#0071e3" },
      { key: "risk_completed", label: "风险完成", color: "#34c759" },
      { key: "risk_failed", label: "风险失败", color: "#ff3b30" },
      { key: "events", label: "事件", color: "#ff9f0a" },
      { key: "alerts", label: "告警", color: "#af52de" }
    ];
    const trendSeriesOn = reactive({
      articles: true,
      risk_completed: true,
      risk_failed: true,
      events: true,
      alerts: true
    });
    function toggleTrendSeries(key) {
      trendSeriesOn[key] = !trendSeriesOn[key];
      renderTrendChart();
    }
    function renderTrendChart() {
      if (!trendChart) return;
      const items = dashboardTrends.value?.items || [];
      const series = trendSeriesOptions.filter((item) => trendSeriesOn[item.key]).map((item) => ({
        name: item.label,
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 5,
        data: items.map((row) => row[item.key] ?? 0),
        lineStyle: { width: item.key === "articles" ? 2.5 : 1.8, color: item.color },
        itemStyle: { color: item.color },
        areaStyle: item.key === "articles" ? { color: new LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(0,113,227,0.12)" }, { offset: 1, color: "rgba(0,113,227,0)" }]) } : void 0
      }));
      trendChart.setOption({
        tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        grid: { left: 44, right: 20, top: 12, bottom: 30 },
        xAxis: { type: "category", data: items.map((row) => row.date), axisLine: { lineStyle: { color: "#e8e8ed" } }, axisTick: { show: false }, axisLabel: { color: "#86868b", fontSize: 11 } },
        yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        series
      }, { notMerge: true });
    }
    function renderHotwordChart() {
      if (!hotwordChart) return;
      const items = hotwordItems.value || [];
      if (!items.length) {
        hotwordChart.clear();
        return;
      }
      const max = Math.max(...items.map((item) => item.count || 0), 1);
      const data = items.map((item) => ({
        name: item.word,
        value: item.count,
        textStyle: { color: `hsl(${item.count / max * 210 + 200}, 70%, ${60 - item.count / max * 30}%)` }
      }));
      hotwordChart.setOption({
        tooltip: {
          show: true,
          backgroundColor: "rgba(29,29,31,0.94)",
          borderColor: "transparent",
          textStyle: { color: "#fff", fontSize: 12 },
          formatter: (params) => {
            const raw = items.find((item) => item.word === params.name);
            if (!raw) return `${params.name}: ${params.value}`;
            const trend = raw.trend === "up" ? "↑ 上升" : raw.trend === "down" ? "↓ 下降" : "→ 持平";
            return `${raw.word}<br/>近 ${visualizationDays.value} 天：${raw.count}<br/>语言：${zh(raw.language)}<br/>趋势：${trend}<br/>来源：${(raw.sources || []).join("、") || "-"}`;
          }
        },
        series: [{
          type: "wordCloud",
          shape: "circle",
          left: "center",
          top: "center",
          width: "92%",
          height: "92%",
          sizeRange: [14, 40],
          rotationRange: [-30, 30],
          gridSize: 8,
          layoutAnimation: true,
          textStyle: { fontFamily: "sans-serif", fontWeight: "bold" },
          emphasis: { textStyle: { color: "#0071e3" } },
          data
        }]
      }, { notMerge: true });
    }
    function severityText(s) {
      return zh(s);
    }
    function severityBadge(s) {
      if (s === "critical" || s === "high") return "is-rose";
      if (s === "medium") return "is-amber";
      if (s === "low") return "is-teal";
      return "is-cyan";
    }
    function shortTime(s) {
      if (!s) return "";
      const d = new Date(s);
      const pad = (n) => String(n).padStart(2, "0");
      return pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
    }
    function isHandled(status) {
      return status !== "triggered";
    }
    function renderSourceChart() {
      if (!sourceChart) return;
      const items = dashboardSources.value?.items || [];
      const top = [...items].sort((a, b) => (b.opinion_count || 0) - (a.opinion_count || 0)).slice(0, 10);
      const names = top.map((it) => it.source_name_snapshot || it.source || it.source_key || "未知");
      const values = top.map((it) => it.opinion_count || 0);
      sourceChart.setOption({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        grid: { left: 8, right: 24, top: 10, bottom: 6, containLabel: true },
        xAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        yAxis: { type: "category", inverse: true, data: names, axisLine: { lineStyle: { color: "#e8e8ed" } }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12 } },
        series: [{
          type: "bar",
          data: values,
          barWidth: 14,
          itemStyle: { borderRadius: [0, 6, 6, 0], color: new LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#0a84ff" }, { offset: 1, color: "#0071e3" }]) },
          label: { show: true, position: "right", color: "#86868b", fontSize: 11 }
        }]
      }, { notMerge: true });
    }
    function renderRiskChart() {
      if (!riskChart) return;
      const levels = dashboardRisk.value?.risk_levels;
      if (!levels || !Object.keys(levels).length) {
        riskChart.clear();
        return;
      }
      const entries = Object.entries(levels);
      const total = entries.reduce((acc, [, v]) => acc + (Number(v) || 0), 0) || 1;
      const data = entries.map(([label, count]) => {
        const m = RISK_MAP[label] ?? { name: zh(label), color: "#8e8e93" };
        return { name: m.name, value: Number(count) || 0, itemStyle: { color: m.color } };
      });
      const pctOf = (v) => (v / total * 100).toFixed(1);
      riskChart.setOption({
        tooltip: { trigger: "item", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 }, formatter: (p) => `${p.name}<br/>${p.value} 条 · 占比 ${pctOf(p.value)}%` },
        legend: { bottom: 0, left: "center", itemWidth: 10, itemHeight: 10, textStyle: { color: "#515154", fontSize: 11 }, formatter: (name) => {
          const it = data.find((d) => d.name === name);
          return it ? `${name} ${pctOf(it.value)}%` : name;
        } },
        graphic: { type: "text", left: "center", top: "38%", style: { text: `${total}
风险结果`, textAlign: "center", fill: "#1d1d1f", fontSize: 20, fontWeight: 700, lineHeight: 22 } },
        series: [{ type: "pie", radius: ["46%", "68%"], center: ["50%", "44%"], avoidLabelOverlap: true, label: { show: false }, data }]
      }, { notMerge: true });
    }
    function measureAlertFeed() {
      const vp = alertViewportEl.value;
      const tr = alertTrackEl.value;
      if (!vp || !tr) {
        alertFeedOverflow.value = false;
        alertNeedScroll.value = false;
        return;
      }
      const oneHeight = tr.scrollHeight;
      const portHeight = vp.clientHeight;
      const overflow = oneHeight > portHeight + 4;
      alertFeedOverflow.value = overflow;
      alertNeedScroll.value = overflow;
      if (overflow) {
        alertScrollDuration.value = Math.max((alertFeed.value || []).length * 2.4, 10) + "s";
      }
    }
    async function ensureDashboardCharts() {
      await nextTick();
      if (trendChart && !trendChart.getDom()?.isConnected) {
        trendChart.dispose();
        trendChart = null;
      }
      if (hotwordChart && !hotwordChart.getDom()?.isConnected) {
        hotwordChart.dispose();
        hotwordChart = null;
      }
      if (sourceChart && !sourceChart.getDom()?.isConnected) {
        sourceChart.dispose();
        sourceChart = null;
      }
      if (riskChart && !riskChart.getDom()?.isConnected) {
        riskChart.dispose();
        riskChart = null;
      }
      if (trendChartRef.value && !trendChart) trendChart = init(trendChartRef.value);
      if (hotwordChartRef.value && !hotwordChart) hotwordChart = init(hotwordChartRef.value);
      if (sourceChartRef.value && !sourceChart) sourceChart = init(sourceChartRef.value);
      if (riskChartRef.value && !riskChart) riskChart = init(riskChartRef.value);
      renderTrendChart();
      renderHotwordChart();
      renderSourceChart();
      renderRiskChart();
      await nextTick();
      measureAlertFeed();
      if (alertViewportEl.value && !alertResizeObserver) {
        alertResizeObserver = new ResizeObserver(() => measureAlertFeed());
        alertResizeObserver.observe(alertViewportEl.value);
      }
    }
    function handleDashboardResize() {
      trendChart?.resize();
      hotwordChart?.resize();
      sourceChart?.resize();
      riskChart?.resize();
    }
    onMounted(() => {
      window.addEventListener("resize", handleDashboardResize);
      const runId = localStorage.getItem("foreign-ai-batch-run-id");
      if (runId) resumeAIBatchIfRunning(runId);
    });
    onBeforeUnmount(() => {
      if (aiBatchTimer) clearTimeout(aiBatchTimer);
      window.removeEventListener("foreign-data-refresh", onForeignRefresh);
      window.removeEventListener("resize", handleDashboardResize);
      trendChart?.dispose();
      trendChart = null;
      hotwordChart?.dispose();
      hotwordChart = null;
      sourceChart?.dispose();
      sourceChart = null;
      riskChart?.dispose();
      riskChart = null;
      alertResizeObserver?.disconnect();
      alertResizeObserver = null;
    });
    function markVisualizationFresh(data) {
      const asOf = data?.data_as_of ? new Date(data.data_as_of).getTime() : Date.now();
      visualizationStale.value = Date.now() - asOf > 15 * 60 * 1e3;
    }
    async function loadDashboard() {
      loading.value = true;
      visualizationError.value = null;
      try {
        const params = { days: visualizationDays.value };
        const hotwordParams = { days: visualizationDays.value, limit: 30 };
        if (hotwordLanguage.value) hotwordParams.language = hotwordLanguage.value;
        const emptyItems = { data: { items: [] } };
        const [summary, trends, risk, events, alerts, sourceStats, hotwords, hotwordTrends, alertFeedData] = await Promise.all([
          api.get("/foreign/dashboard/summary", { params }),
          api.get("/foreign/dashboard/trends", { params }),
          api.get("/foreign/dashboard/risk", { params }),
          api.get("/foreign/dashboard/events", { params }),
          api.get("/foreign/dashboard/alerts", { params }),
          api.get("/foreign/dashboard/sources", { params }),
          // 热词接口单独降级：即使无权限或失败也不影响整个看板渲染
          api.get("/foreign/hotwords", { params: hotwordParams }).catch(() => emptyItems),
          api.get("/foreign/hotwords/trends", { params: hotwordParams }).catch(() => emptyItems),
          api.get("/foreign/alerts", { params: { size: 30 } }).catch(() => ({ data: { items: [] } }))
        ]);
        dashboardSummary.value = summary.data;
        dashboardTrends.value = trends.data;
        dashboardRisk.value = risk.data;
        dashboardEvents.value = events.data;
        dashboardAlerts.value = alerts.data;
        dashboardSources.value = sourceStats.data;
        alertFeed.value = alertFeedData?.data?.items || [];
        hotwordItems.value = hotwords.data.items || [];
        hotwordTrendItems.value = hotwordTrends.data.items || [];
        hotwordMeta.value = hotwords.data;
        markVisualizationFresh(summary.data);
        await ensureDashboardCharts();
      } catch (err) {
        visualizationError.value = visualizationFailure(err);
        dashboardSummary.value = null;
      } finally {
        loading.value = false;
      }
    }
    function formatTime(value) {
      return value ? new Date(value).toLocaleString() : "-";
    }
    async function loadOpinions() {
      loading.value = true;
      try {
        const params = { page: opinionPage.value, size: opinionSize, risk_source: riskSource.value };
        if (opinionFilters.q) params.q = opinionFilters.q;
        if (opinionFilters.source) params.source = opinionFilters.source;
        if (opinionFilters.keyword) params.keyword = opinionFilters.keyword;
        if (opinionFilters.date_from) params.date_from = opinionFilters.date_from;
        if (opinionFilters.date_to) params.date_to = opinionFilters.date_to;
        if (riskFilters.language) params.language = riskFilters.language;
        if (riskFilters.risk_level) params.risk_level = riskFilters.risk_level;
        if (riskFilters.analysis_status) params.analysis_status = riskFilters.analysis_status;
        const [list, sourceList] = await Promise.all([
          api.get("/foreign/opinions", { params }),
          api.get("/foreign/opinions/sources")
        ]);
        opinions.value = list.data.items;
        opinionTotal.value = list.data.total;
        opinionSources.value = sourceList.data;
      } catch (err) {
        opinions.value = [];
        opinionTotal.value = 0;
        if (err?.response?.status !== 401 && err?.response?.status !== 403) ElMessage.error(err?.response?.data?.detail || "外网舆情加载失败，请稍后重试");
      } finally {
        loading.value = false;
      }
    }
    async function resumeAIBatchIfRunning(runId) {
      try {
        const { data } = await api.get(`/foreign/ai-analysis/batch/${runId}`);
        const terminal = ["success", "partial", "failed", "cancelled"].includes(data.status);
        if (terminal) {
          localStorage.removeItem("foreign-ai-batch-run-id");
          return;
        }
        aiBatchRun.value = { ...aiBatchRun.value || {}, ...data, run_id: runId };
        pollAIBatch(runId, true);
      } catch {
        localStorage.removeItem("foreign-ai-batch-run-id");
      }
    }
    function pollAIBatch(runId, immediate = false) {
      if (aiBatchTimer) clearTimeout(aiBatchTimer);
      aiBatchTimer = setTimeout(async () => {
        try {
          const { data } = await api.get(`/foreign/ai-analysis/batch/${runId}`);
          aiBatchRun.value = { ...aiBatchRun.value || {}, ...data, run_id: runId };
          if (["success", "partial", "failed", "cancelled"].includes(data.status)) {
            localStorage.setItem("foreign-ai-batch-run-id", runId);
            ElMessage({ type: data.status === "success" ? "success" : data.status === "partial" ? "warning" : "error", message: `批量 AI 研判${zh(data.status)}：成功 ${data.success_count || 0}，失败 ${data.failed_count || 0}，跳过 ${data.skipped_count || 0}` });
            await loadOpinions();
            await loadRisk();
            return;
          }
          pollAIBatch(runId);
        } catch (err) {
          ElMessage.error(err?.response?.data?.detail || "批量 AI 进度查询失败");
        }
      }, immediate ? 0 : 1200);
    }
    async function loadRisk() {
      loading.value = true;
      try {
        const base = { size: riskSize };
        if (riskFilters.q) base.q = riskFilters.q;
        if (riskFilters.source) base.source = riskFilters.source;
        if (riskFilters.language) base.language = riskFilters.language;
        if (riskFilters.sentiment) base.sentiment = riskFilters.sentiment;
        if (riskFilters.risk_level) base.risk_level = riskFilters.risk_level;
        if (riskFilters.analysis_status) base.analysis_status = riskFilters.analysis_status;
        if (riskFilters.date_from) base.date_from = riskFilters.date_from;
        if (riskFilters.date_to) base.date_to = riskFilters.date_to;
        const [first, sourceList] = await Promise.all([
          api.get("/foreign/risk", { params: { ...base, page: 1 } }),
          api.get("/foreign/opinions/sources").catch(() => ({ data: [] }))
        ]);
        const total = first.data.total || 0;
        let items = first.data.items || [];
        const pages = Math.min(Math.ceil(total / riskSize), riskMaxPages);
        if (pages > 1) {
          const rest = await Promise.all(
            Array.from(
              { length: pages - 1 },
              (_, index) => api.get("/foreign/risk", { params: { ...base, page: index + 2 } }).catch(() => ({ data: { items: [] } }))
            )
          );
          for (const response of rest) items = items.concat(response.data.items || []);
        }
        risks.value = items;
        riskTotal.value = total;
        riskPage.value = 1;
        if (Array.isArray(sourceList.data) && sourceList.data.length) {
          opinionSources.value = sourceList.data;
        }
      } catch (err) {
        risks.value = [];
        if (err?.response?.status !== 401 && err?.response?.status !== 403) ElMessage.error(err?.response?.data?.detail || "外网风险加载失败，请稍后重试");
      } finally {
        loading.value = false;
      }
    }
    async function loadRuns() {
      loading.value = true;
      try {
        runs.value = (await api.get("/foreign/collection-runs", { params: { size: 100 } })).data.items;
      } finally {
        loading.value = false;
      }
    }
    async function loadEvents() {
      loading.value = true;
      eventLoadError.value = null;
      try {
        const [candidateResponse, eventResponse, runResponse, autoStatus] = await Promise.all([
          api.get("/foreign/events/candidates", { params: { size: 100, status: "candidate" } }),
          api.get("/foreign/events", { params: { size: 100 } }),
          api.get("/foreign/event-runs", { params: { size: 20, status: "failed" } }),
          api.get("/foreign/events/auto-aggregate/status")
        ]);
        eventCandidates.value = candidateResponse.data.items;
        foreignEvents.value = eventResponse.data.items;
        eventRunFailures.value = runResponse.data.items;
        eventAutoStatus.value = autoStatus.data;
      } catch (err) {
        eventLoadError.value = err?.response?.data?.detail || "请求失败，请稍后重试";
        eventCandidates.value = [];
        foreignEvents.value = [];
        eventRunFailures.value = [];
      } finally {
        loading.value = false;
      }
    }
    async function loadManualReviews() {
      try {
        const params = { size: 100 };
        if (reviewStatusFilter.value && reviewStatusFilter.value !== "all") params.status = reviewStatusFilter.value;
        manualReviews.value = (await api.get("/foreign/ai-analysis/reviews", { params })).data.items || [];
        selectedReviewIds.value = selectedReviewIds.value.filter((id) => manualReviews.value.some((row) => row.id === id));
      } catch {
        manualReviews.value = [];
      }
    }
    async function loadEventDetail(id) {
      if (selectedForeignEvent.value?.id === id && selectedForeignEvent.value.opinions) return;
      if (eventDetailLoadingId.value) return;
      eventDetailLoadingId.value = id;
      try {
        selectedForeignEvent.value = (await api.get(`/foreign/events/${id}`)).data;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网事件详情加载失败");
      } finally {
        eventDetailLoadingId.value = null;
      }
    }
    async function openOpinion(id) {
      detailId.value = id;
      detailVisible.value = true;
    }
    function openAlertTarget(row) {
      if (row.foreign_opinion_id) {
        openOpinion(row.foreign_opinion_id);
      } else if (row.foreign_event_id) {
        activeTab.value = "events";
        loadEventDetail(row.foreign_event_id);
      }
    }
    watch(
      () => route.query.tab,
      (value) => {
        const tab = value;
        if (tab === "alerts" || tab === "alertRules") {
          router.replace({ path: "/alerts", query: { tab: tab === "alerts" ? "records" : "rules", scope: "foreign" } });
          return;
        }
        const normalizedTab = normalizeTab(tab);
        activeTab.value = normalizedTab;
        loadTab(normalizedTab);
      },
      { immediate: true }
    );
    watch(
      () => route.query.section,
      (value) => {
        if (value === "ai-review") {
          activeTab.value = "opinions";
          opinionSection.value = "ai-review";
          loadManualReviews();
        }
      },
      { immediate: true }
    );
    function onForeignRefresh() {
      loadOpinions();
      loadRuns();
      loadRisk();
    }
    onMounted(() => {
      loadApprovedSources();
      window.addEventListener("foreign-data-refresh", onForeignRefresh);
    });
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          (openBlock(true), createElementBlock(Fragment, null, renderList(unref(visibleTabs), (tab) => {
            return openBlock(), createElementBlock("button", {
              key: tab.value,
              class: normalizeClass(["tab", { active: activeTab.value === tab.value }]),
              onClick: ($event) => switchTab(tab.value)
            }, toDisplayString(tab.label), 11, _hoisted_3);
          }), 128)),
          createBaseVNode("div", _hoisted_4, [
            createBaseVNode("span", _hoisted_5, "已批准数据源：" + toDisplayString(approvedSourceLabel.value), 1)
          ])
        ]),
        activeTab.value === "dashboard" ? (openBlock(), createElementBlock("section", _hoisted_6, [
          createBaseVNode("div", {
            class: normalizeClass(["schedule-status", { disabled: !scheduleStatus.value?.enabled }])
          }, [
            _cache[4] || (_cache[4] = createBaseVNode("strong", null, "外网自动采集", -1)),
            createBaseVNode("span", null, toDisplayString(scheduleStatus.value?.enabled ? "已启用" : "部署级开关已关闭"), 1),
            createBaseVNode("span", null, "已注册：" + toDisplayString(scheduleStatus.value?.registered ? "是" : "否"), 1),
            createBaseVNode("span", null, "运行中：" + toDisplayString(scheduleStatus.value?.running ? "是" : "否"), 1),
            createBaseVNode("span", null, "符合来源：" + toDisplayString(scheduleStatus.value?.eligible_source_count ?? 0), 1),
            scheduleStatus.value?.last_run ? (openBlock(), createElementBlock("span", _hoisted_7, "最近运行：" + toDisplayString(zh(scheduleStatus.value.last_run.status)) + " " + toDisplayString(formatTime(scheduleStatus.value.last_run.ended_at || scheduleStatus.value.last_run.started_at)), 1)) : createCommentVNode("", true),
            scheduleStatus.value?.last_run?.error_summary ? (openBlock(), createElementBlock("span", _hoisted_8, toDisplayString(scheduleStatus.value.last_run.error_summary), 1)) : createCommentVNode("", true)
          ], 2),
          createBaseVNode("div", _hoisted_9, [
            _cache[7] || (_cache[7] = createBaseVNode("div", null, [
              createBaseVNode("h2", { class: "fw-dash-title" }, "外网舆情看板"),
              createBaseVNode("p", { class: "muted" }, "面向外网公开来源采集的舆情概览（仅外网数据）")
            ], -1)),
            createBaseVNode("div", _hoisted_10, [
              createBaseVNode("label", _hoisted_11, [
                _cache[6] || (_cache[6] = createTextVNode("统计窗口 ", -1)),
                withDirectives(createBaseVNode("select", {
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => visualizationDays.value = $event),
                  class: "input",
                  onChange: loadDashboard
                }, [..._cache[5] || (_cache[5] = [
                  createBaseVNode("option", { value: 1 }, "近 1 天", -1),
                  createBaseVNode("option", { value: 7 }, "近 7 天", -1),
                  createBaseVNode("option", { value: 30 }, "近 30 天", -1),
                  createBaseVNode("option", { value: 90 }, "近 90 天", -1)
                ])], 544), [
                  [
                    vModelSelect,
                    visualizationDays.value,
                    void 0,
                    { number: true }
                  ]
                ])
              ]),
              createBaseVNode("button", {
                class: "btn btn-primary",
                onClick: loadDashboard
              }, "刷新看板"),
              visualizationStale.value ? (openBlock(), createElementBlock("span", _hoisted_12, "数据较旧")) : createCommentVNode("", true)
            ])
          ]),
          visualizationError.value ? (openBlock(), createElementBlock("div", _hoisted_13, [
            createBaseVNode("span", null, toDisplayString(visualizationError.value), 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadDashboard
            }, "重试")
          ])) : dashboardSummary.value ? (openBlock(), createElementBlock("div", _hoisted_14, [
            createBaseVNode("div", _hoisted_15, [
              createBaseVNode("div", _hoisted_16, [
                _cache[8] || (_cache[8] = createBaseVNode("span", { class: "fw-kpi-label" }, "文章总数", -1)),
                createBaseVNode("strong", _hoisted_17, toDisplayString(dashboardSummary.value.articles.total), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.articles.window_new) + " 条在窗口内", 1)
              ]),
              createBaseVNode("div", _hoisted_18, [
                _cache[9] || (_cache[9] = createBaseVNode("span", { class: "fw-kpi-label" }, "数据源", -1)),
                createBaseVNode("strong", _hoisted_19, toDisplayString(dashboardSummary.value.articles.sources), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.articles.languages?.en || 0) + " 英文 / " + toDisplayString(dashboardSummary.value.articles.languages?.zh || 0) + " 中文", 1)
              ]),
              createBaseVNode("div", _hoisted_20, [
                _cache[10] || (_cache[10] = createBaseVNode("span", { class: "fw-kpi-label" }, "风险已完成", -1)),
                createBaseVNode("strong", _hoisted_21, toDisplayString(dashboardSummary.value.risk.completed), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.risk.failed) + " 失败 · " + toDisplayString(dashboardSummary.value.risk.pending) + " 待处理", 1)
              ]),
              createBaseVNode("div", _hoisted_22, [
                _cache[11] || (_cache[11] = createBaseVNode("span", { class: "fw-kpi-label" }, "已确认事件", -1)),
                createBaseVNode("strong", _hoisted_23, toDisplayString(dashboardSummary.value.events.confirmed), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.events.candidate) + " 候选", 1)
              ]),
              createBaseVNode("div", _hoisted_24, [
                _cache[12] || (_cache[12] = createBaseVNode("span", { class: "fw-kpi-label" }, "外网告警", -1)),
                createBaseVNode("strong", _hoisted_25, toDisplayString(dashboardSummary.value.alerts.total), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.alerts.by_status?.triggered || 0) + " 已触发", 1)
              ]),
              createBaseVNode("div", _hoisted_26, [
                _cache[13] || (_cache[13] = createBaseVNode("span", { class: "fw-kpi-label" }, "外网采集", -1)),
                createBaseVNode("strong", _hoisted_27, toDisplayString(dashboardSummary.value.collection?.success ?? 0), 1),
                createBaseVNode("small", null, "成功 / 失败 " + toDisplayString(dashboardSummary.value.collection?.failed ?? 0) + " · " + toDisplayString(zh(dashboardSummary.value.collection?.latest?.status || "unknown")), 1)
              ])
            ]),
            createBaseVNode("div", _hoisted_28, [
              createBaseVNode("article", _hoisted_29, [
                createBaseVNode("header", _hoisted_30, [
                  _cache[14] || (_cache[14] = createBaseVNode("h3", null, "每日趋势", -1)),
                  createBaseVNode("div", _hoisted_31, [
                    (openBlock(), createElementBlock(Fragment, null, renderList(trendSeriesOptions, (item) => {
                      return createBaseVNode("button", {
                        key: item.key,
                        type: "button",
                        class: normalizeClass(["fw-legend-item", { off: !trendSeriesOn[item.key] }]),
                        onClick: ($event) => toggleTrendSeries(item.key)
                      }, [
                        createBaseVNode("i", {
                          style: normalizeStyle({ background: item.color })
                        }, null, 4),
                        createTextVNode(toDisplayString(item.label), 1)
                      ], 10, _hoisted_32);
                    }), 64))
                  ])
                ]),
                withDirectives(createBaseVNode("div", {
                  ref_key: "trendChartRef",
                  ref: trendChartRef,
                  class: "fw-chart"
                }, null, 512), [
                  [vShow, (dashboardTrends.value?.items || []).length]
                ]),
                !(dashboardTrends.value?.items || []).length ? (openBlock(), createElementBlock("p", _hoisted_33, "该窗口内暂无趋势数据")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_34, [
                createBaseVNode("header", _hoisted_35, [
                  _cache[15] || (_cache[15] = createBaseVNode("h3", null, "外网告警", -1)),
                  createBaseVNode("span", _hoisted_36, "滚动播报 · 共 " + toDisplayString(alertFeed.value.length) + " 条", 1)
                ]),
                !alertFeed.value.length ? (openBlock(), createElementBlock("div", _hoisted_37, "该窗口内暂无外网告警")) : (openBlock(), createElementBlock("div", _hoisted_38, [
                  createBaseVNode("div", _hoisted_39, [
                    createBaseVNode("span", _hoisted_40, [
                      _cache[16] || (_cache[16] = createBaseVNode("i", { class: "fw-sum-dot is-amber" }, null, -1)),
                      createTextVNode("待处置 " + toDisplayString(alertPendingCount.value), 1)
                    ]),
                    createBaseVNode("span", _hoisted_41, [
                      _cache[17] || (_cache[17] = createBaseVNode("i", { class: "fw-sum-dot is-teal" }, null, -1)),
                      createTextVNode("已处置 " + toDisplayString(alertDoneCount.value), 1)
                    ])
                  ]),
                  createBaseVNode("div", {
                    ref_key: "alertViewportEl",
                    ref: alertViewportEl,
                    class: "fw-alert-viewport"
                  }, [
                    createBaseVNode("div", {
                      ref_key: "alertTrackEl",
                      ref: alertTrackEl,
                      class: normalizeClass(["fw-alert-track", { scrolling: alertFeedOverflow.value }]),
                      style: normalizeStyle({ animationDuration: alertScrollDuration.value })
                    }, [
                      createBaseVNode("ul", _hoisted_42, [
                        (openBlock(true), createElementBlock(Fragment, null, renderList(alertFeed.value, (a) => {
                          return openBlock(), createElementBlock("li", {
                            key: "a-" + a.id,
                            class: "fw-alert-row",
                            onClick: ($event) => openAlertTarget(a)
                          }, [
                            createBaseVNode("span", {
                              class: normalizeClass(["fw-badge fw-mono", severityBadge(a.severity)])
                            }, toDisplayString(severityText(a.severity)), 3),
                            createBaseVNode("div", _hoisted_44, [
                              createBaseVNode("div", _hoisted_45, toDisplayString(a.title || "未命名告警"), 1),
                              createBaseVNode("div", _hoisted_46, toDisplayString(a.rule_snapshot?.name || a.source_name_snapshot || "外网告警") + " · " + toDisplayString(shortTime(a.triggered_at)), 1)
                            ]),
                            createBaseVNode("span", {
                              class: normalizeClass(["fw-badge", isHandled(a.status) ? "is-teal" : "is-amber"])
                            }, toDisplayString(zh(a.status)), 3)
                          ], 8, _hoisted_43);
                        }), 128))
                      ]),
                      alertNeedScroll.value ? (openBlock(), createElementBlock("div", _hoisted_47, [
                        createBaseVNode("ul", _hoisted_48, [
                          (openBlock(true), createElementBlock(Fragment, null, renderList(alertFeed.value, (a) => {
                            return openBlock(), createElementBlock("li", {
                              key: "b-" + a.id,
                              class: "fw-alert-row",
                              onClick: ($event) => openAlertTarget(a)
                            }, [
                              createBaseVNode("span", {
                                class: normalizeClass(["fw-badge fw-mono", severityBadge(a.severity)])
                              }, toDisplayString(severityText(a.severity)), 3),
                              createBaseVNode("div", _hoisted_50, [
                                createBaseVNode("div", _hoisted_51, toDisplayString(a.title || "未命名告警"), 1),
                                createBaseVNode("div", _hoisted_52, toDisplayString(a.rule_snapshot?.name || a.source_name_snapshot || "外网告警") + " · " + toDisplayString(shortTime(a.triggered_at)), 1)
                              ]),
                              createBaseVNode("span", {
                                class: normalizeClass(["fw-badge", isHandled(a.status) ? "is-teal" : "is-amber"])
                              }, toDisplayString(zh(a.status)), 3)
                            ], 8, _hoisted_49);
                          }), 128))
                        ])
                      ])) : createCommentVNode("", true)
                    ], 6)
                  ], 512)
                ]))
              ]),
              createBaseVNode("article", _hoisted_53, [
                createBaseVNode("header", _hoisted_54, [
                  _cache[18] || (_cache[18] = createBaseVNode("h3", null, "数据源分布", -1)),
                  createBaseVNode("span", _hoisted_55, "近 " + toDisplayString(visualizationDays.value) + " 天 · 各来源文章量", 1)
                ]),
                withDirectives(createBaseVNode("div", {
                  ref_key: "sourceChartRef",
                  ref: sourceChartRef,
                  class: "fw-chart fw-chart-tall"
                }, null, 512), [
                  [vShow, (dashboardSources.value?.items || []).length]
                ]),
                !(dashboardSources.value?.items || []).length ? (openBlock(), createElementBlock("p", _hoisted_56, "该窗口内暂无数据源分布")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_57, [
                _cache[19] || (_cache[19] = createBaseVNode("h3", null, "风险分布", -1)),
                withDirectives(createBaseVNode("div", {
                  ref_key: "riskChartRef",
                  ref: riskChartRef,
                  class: "fw-chart fw-chart-tall"
                }, null, 512), [
                  [vShow, dashboardRisk.value?.risk_levels && Object.keys(dashboardRisk.value.risk_levels || {}).length]
                ]),
                !dashboardRisk.value || !Object.keys(dashboardRisk.value.risk_levels || {}).length ? (openBlock(), createElementBlock("p", _hoisted_58, "暂无已完成风险结果")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_59, [
                createBaseVNode("header", _hoisted_60, [
                  _cache[20] || (_cache[20] = createBaseVNode("h3", null, "外网热词", -1)),
                  createBaseVNode("span", _hoisted_61, "近 " + toDisplayString(visualizationDays.value) + " 天 · 共 " + toDisplayString(hotwordItems.value.length) + " 个热词", 1)
                ]),
                withDirectives(createBaseVNode("div", {
                  ref_key: "hotwordChartRef",
                  ref: hotwordChartRef,
                  class: "fw-chart"
                }, null, 512), [
                  [vShow, hotwordItems.value.length]
                ]),
                !hotwordItems.value.length ? (openBlock(), createElementBlock("p", _hoisted_62, "该窗口内暂无外网热词")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_63, [
                _cache[21] || (_cache[21] = createBaseVNode("h3", null, "事件状态", -1)),
                createBaseVNode("div", _hoisted_64, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(dashboardEvents.value?.formal_events, (count, label) => {
                    return openBlock(), createElementBlock("div", {
                      key: label,
                      class: "distribution-row"
                    }, [
                      createBaseVNode("span", null, toDisplayString(zh(label)), 1),
                      createBaseVNode("strong", null, toDisplayString(count), 1)
                    ]);
                  }), 128)),
                  !dashboardEvents.value || !Object.keys(dashboardEvents.value.formal_events || {}).length ? (openBlock(), createElementBlock("p", _hoisted_65, "暂无外网事件")) : createCommentVNode("", true)
                ])
              ])
            ]),
            createBaseVNode("div", _hoisted_66, "数据范围：" + toDisplayString(formatTime(dashboardSummary.value.window_start)) + " - " + toDisplayString(formatTime(dashboardSummary.value.window_end)) + " · 更新于：" + toDisplayString(formatTime(dashboardSummary.value.data_as_of)), 1)
          ])) : (openBlock(), createElementBlock("div", _hoisted_67, "加载外网看板中..."))
        ])) : createCommentVNode("", true),
        activeTab.value === "opinions" ? (openBlock(), createElementBlock("section", _hoisted_68, [
          createBaseVNode("div", _hoisted_69, [
            createBaseVNode("button", {
              class: normalizeClass(["tab", { active: opinionSection.value === "list" }]),
              onClick: _cache[1] || (_cache[1] = ($event) => opinionSection.value = "list")
            }, "国外舆情", 2),
            createBaseVNode("button", {
              class: normalizeClass(["tab", { active: opinionSection.value === "ai-review" }]),
              onClick: _cache[2] || (_cache[2] = ($event) => {
                opinionSection.value = "ai-review";
                loadManualReviews();
              })
            }, "AI 人工复核", 2)
          ]),
          opinionSection.value === "list" ? (openBlock(), createBlock(ForeignOpinionListView, { key: 0 })) : opinionSection.value === "ai-review" ? (openBlock(), createBlock(ForeignAIReviewView, { key: 1 })) : createCommentVNode("", true)
        ])) : createCommentVNode("", true),
        activeTab.value === "events" ? (openBlock(), createBlock(ForeignEventsView, { key: 2 })) : createCommentVNode("", true),
        createVNode(ForeignOpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value,
          "risk-source": riskSource.value,
          "onUpdate:riskSource": setRiskSource
        }, null, 8, ["modelValue", "opinion-id", "risk-source"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const ForeignWorkspace = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-80277a8c"]]);

export { ForeignWorkspace as default };
