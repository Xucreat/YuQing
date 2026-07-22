import { d as defineComponent, p as onMounted, s as onBeforeUnmount, c as createElementBlock, O as createStaticVNode, a as createBaseVNode, n as normalizeClass, t as toDisplayString, j as computed, r as ref, o as openBlock, _ as _export_sfc, g as api, P as shallowRef, m as watch, F as Fragment, i as renderList, A as createCommentVNode, f as reactive, e as createTextVNode, Q as renderSlot, M as onUnmounted, k as normalizeStyle, q as nextTick, B as createVNode, x as unref, z as withCtx, h as useRouter } from './index-Gqv74_wN.js';
import { o as registerMap, n as init } from './index-DVLpPvFk.js';

const _hoisted_1$8 = { class: "cs-header" };
const _hoisted_2$8 = { class: "cs-header-right" };
const _hoisted_3$7 = ["title"];
const _hoisted_4$7 = { class: "cs-status-code cs-mono" };
const _hoisted_5$6 = { class: "cs-status-text" };
const _hoisted_6$5 = { class: "cs-clock cs-mono" };
const _sfc_main$9 = /* @__PURE__ */ defineComponent({
  __name: "ScreenHeader",
  props: {
    status: {}
  },
  emits: ["exit"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const statusDotClass = computed(() => ({
      "is-live": props.status === "live",
      "is-stale": props.status === "stale" || props.status === "connecting",
      "is-down": props.status === "down"
    }));
    const STATUS_MAP = {
      connecting: { code: "CONNECTING", text: "连接中", desc: "正在连接数据服务" },
      live: { code: "LIVE", text: "实时", desc: "数据正常" },
      stale: { code: "STALE", text: "延迟", desc: "暂未更新，显示最近成功结果" },
      down: { code: "DOWN", text: "异常", desc: "无法连接数据服务" }
    };
    const statusInfo = computed(() => STATUS_MAP[props.status]);
    const clock = ref("");
    let timer = null;
    function tick() {
      const d = /* @__PURE__ */ new Date();
      const p = (n) => String(n).padStart(2, "0");
      clock.value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    }
    onMounted(() => {
      tick();
      timer = setInterval(tick, 1e3);
    });
    onBeforeUnmount(() => {
      if (timer) clearInterval(timer);
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("header", _hoisted_1$8, [
        _cache[1] || (_cache[1] = createStaticVNode('<div class="cs-header-left" data-v-933db758><div class="cs-logo" data-v-933db758>YQ</div><div class="cs-titles" data-v-933db758><h1 class="cs-title" data-v-933db758>公安互联网舆情监测研判 · 指挥大屏</h1><p class="cs-subtitle" data-v-933db758>全域舆情态势 · 实时监测</p></div></div>', 1)),
        createBaseVNode("div", _hoisted_2$8, [
          createBaseVNode("div", {
            class: normalizeClass(["cs-status", statusDotClass.value]),
            title: statusInfo.value.desc
          }, [
            createBaseVNode("span", {
              class: normalizeClass(["cs-dot", statusDotClass.value])
            }, null, 2),
            createBaseVNode("span", _hoisted_4$7, toDisplayString(statusInfo.value.code), 1),
            createBaseVNode("span", _hoisted_5$6, toDisplayString(statusInfo.value.text) + " · " + toDisplayString(statusInfo.value.desc), 1)
          ], 10, _hoisted_3$7),
          createBaseVNode("div", _hoisted_6$5, toDisplayString(clock.value), 1),
          createBaseVNode("button", {
            class: "cs-exit",
            type: "button",
            title: "返回系统",
            onClick: _cache[0] || (_cache[0] = ($event) => _ctx.$emit("exit"))
          }, "↩ 返回系统")
        ])
      ]);
    };
  }
});

const ScreenHeader = /* @__PURE__ */ _export_sfc(_sfc_main$9, [["__scopeId", "data-v-933db758"]]);

const REFRESH_INTERVALS = {
  stats: 3e4,
  recent: 15e3,
  alerts: 15e3
};
function usePolledResource(fetcher, intervalMs) {
  const data = shallowRef(null);
  const loading = ref(false);
  const error = ref(null);
  const status = ref("connecting");
  let timer = null;
  let seq = 0;
  let hasData = false;
  let stopped = false;
  async function refresh() {
    const mySeq = ++seq;
    if (!hasData) loading.value = true;
    try {
      const result = await fetcher();
      if (mySeq !== seq || stopped) return;
      data.value = result;
      hasData = true;
      error.value = null;
      status.value = "live";
    } catch (err) {
      if (mySeq !== seq || stopped) return;
      error.value = err;
      status.value = hasData ? "stale" : "down";
    } finally {
      if (mySeq === seq) loading.value = false;
    }
  }
  function start() {
    stopped = false;
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    void refresh();
    timer = setInterval(() => void refresh(), intervalMs);
  }
  function stop() {
    stopped = true;
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }
  onMounted(start);
  onBeforeUnmount(stop);
  return { data, loading, error, status, refresh, start, stop };
}
function useCommandScreenStats(days = 7) {
  const getDays = () => typeof days === "number" ? days : days.value;
  return usePolledResource(async () => {
    const { data } = await api.get("/dashboard/stats", {
      params: { days: getDays() }
    });
    return data;
  }, REFRESH_INTERVALS.stats);
}
function useCommandScreenRecent(limit = 8) {
  return usePolledResource(async () => {
    const { data } = await api.get("/dashboard/recent", {
      params: { limit }
    });
    return data;
  }, REFRESH_INTERVALS.recent);
}
function useCommandScreenAlerts(limit = 8) {
  return usePolledResource(async () => {
    const { data } = await api.get("/dashboard/alerts", {
      params: { limit }
    });
    return data;
  }, REFRESH_INTERVALS.alerts);
}
function useCommandScreenSourceCount() {
  return usePolledResource(async () => {
    const { data } = await api.get("/admin/data-sources", {
      params: { enabled: true, size: 1 }
    });
    return { total: data.total };
  }, REFRESH_INTERVALS.stats);
}
async function fetchRegionChildren(province, days = 7) {
  const { data } = await api.get("/dashboard/region-children", {
    params: { province, days }
  });
  return data;
}
async function fetchKpiTrends(days = 14) {
  const { data } = await api.get("/dashboard/kpi-trends", {
    params: { days }
  });
  return data;
}

const _hoisted_1$7 = { class: "cs-kpi-bar" };
const _hoisted_2$7 = { class: "cs-kpi-label" };
const _hoisted_3$6 = { class: "cs-kpi-value cs-mono" };
const _hoisted_4$6 = { key: 0 };
const _hoisted_5$5 = {
  key: 1,
  class: "cs-kpi-skeleton"
};
const _hoisted_6$4 = { class: "cs-kpi-foot" };
const _hoisted_7$3 = { class: "cs-kpi-note" };
const _hoisted_8$3 = ["viewBox"];
const _hoisted_9$2 = ["id"];
const _hoisted_10$2 = ["stop-color"];
const _hoisted_11$2 = ["stop-color"];
const _hoisted_12$2 = ["d", "fill"];
const _hoisted_13$1 = ["d", "stroke"];
const SPARK_W = 80;
const SPARK_H = 28;
const SPARK_DAYS = 14;
const _sfc_main$8 = /* @__PURE__ */ defineComponent({
  __name: "KpiBar",
  props: {
    stats: {},
    sourceCount: {}
  },
  setup(__props) {
    const props = __props;
    const hasData = computed(() => props.stats != null);
    const trends = ref(null);
    let trendTimer = null;
    async function loadTrends() {
      try {
        const d = await fetchKpiTrends(SPARK_DAYS);
        trends.value = {
          opinions: d.opinions.map((i) => i.value),
          high_risk: d.high_risk.map((i) => i.value),
          events: d.events.map((i) => i.value)
        };
      } catch {
      }
    }
    onMounted(() => {
      void loadTrends();
      trendTimer = setInterval(() => void loadTrends(), 3e4);
    });
    onBeforeUnmount(() => {
      if (trendTimer) {
        clearInterval(trendTimer);
        trendTimer = null;
      }
    });
    const items = computed(() => {
      const srcCount = props.sourceCount != null ? props.sourceCount : props.stats?.sources?.length ?? 0;
      return [
        { key: "total", label: "舆情总量", tone: "cyan", value: props.stats?.total ?? 0, caliber: "累计", foot: "系统累计" },
        { key: "today", label: "今日新增", tone: "teal", value: props.stats?.today ?? 0, caliber: "今日入库", foot: "当日入库" },
        { key: "high_risk", label: "高危舆情", tone: "rose", value: props.stats?.high_risk ?? 0, caliber: "累计", foot: "风险≥70" },
        { key: "event_count", label: "事件总数", tone: "amber", value: props.stats?.event_count ?? 0, caliber: "累计", foot: "系统累计" },
        { key: "sources", label: "监测信源", tone: "violet", value: srcCount, caliber: "在监", foot: "启用信源" }
      ];
    });
    const displayed = reactive({});
    const targets = computed(
      () => Object.fromEntries(items.value.map((i) => [i.key, Number(i.value) || 0]))
    );
    const rafMap = {};
    let initialized = false;
    function tween(key, to) {
      if (!initialized) {
        displayed[key] = to;
        return;
      }
      const from = displayed[key] ?? 0;
      const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      if (reduce || from === to) {
        displayed[key] = to;
        return;
      }
      const start = performance.now();
      const dur = 750;
      cancelAnimationFrame(rafMap[key]);
      const step = (now) => {
        const t = Math.min(1, (now - start) / dur);
        const e = 1 - Math.pow(1 - t, 3);
        displayed[key] = Math.round(from + (to - from) * e);
        if (t < 1) rafMap[key] = requestAnimationFrame(step);
        else displayed[key] = to;
      };
      rafMap[key] = requestAnimationFrame(step);
    }
    watch(
      targets,
      (nv) => {
        for (const k of Object.keys(nv)) {
          if (displayed[k] === void 0) displayed[k] = 0;
          tween(k, nv[k]);
        }
        initialized = true;
      },
      { immediate: true, deep: true }
    );
    onBeforeUnmount(() => {
      for (const k of Object.keys(rafMap)) cancelAnimationFrame(rafMap[k]);
    });
    function sparkData(key) {
      if (!trends.value) return null;
      switch (key) {
        case "total":
        case "today":
          return trends.value.opinions;
        case "high_risk":
          return trends.value.high_risk;
        case "event_count":
          return trends.value.events;
        case "sources":
          return null;
        default:
          return null;
      }
    }
    function sparkColor(tone) {
      const map = {
        cyan: "#22d3ee",
        teal: "#2dd4bf",
        rose: "#fb7185",
        amber: "#fbbf24",
        violet: "#a78bfa"
      };
      return map[tone] || "#22d3ee";
    }
    function normalize(data) {
      if (!data.length) return [];
      const max = Math.max(...data, 1);
      return data.map((v) => v / max * (SPARK_H - 4));
    }
    function sparkLine(key) {
      const data = sparkData(key);
      if (!data || !data.length) return "";
      const pts = normalize(data);
      if (pts.every((v) => v === 0)) {
        return `M 0 ${SPARK_H - 2} L ${SPARK_W} ${SPARK_H - 2}`;
      }
      const stepX = SPARK_W / Math.max(pts.length - 1, 1);
      return catmullRomPath(pts, stepX);
    }
    function catmullRomPath(pts, stepX) {
      const n = pts.length;
      if (n === 0) return "";
      if (n === 1) return `M 0 ${SPARK_H - 2 - pts[0]} L ${SPARK_W} ${SPARK_H - 2 - pts[0]}`;
      if (n === 2) {
        return `M 0 ${SPARK_H - 2 - pts[0]} L ${SPARK_W} ${SPARK_H - 2 - pts[1]}`;
      }
      const tension = 0.3;
      let d = "";
      for (let i = 0; i < n; i++) {
        const x = i * stepX;
        const y = SPARK_H - 2 - pts[i];
        if (i === 0) {
          d += `M ${x} ${y}`;
        } else {
          const p0 = pts[Math.max(i - 2, 0)];
          const p1 = pts[i - 1];
          const p2 = pts[i];
          const p3 = pts[Math.min(i + 1, n - 1)];
          const x0 = (i - 1) * stepX;
          const x1 = x;
          const x2 = Math.min(i + 1, n - 1) * stepX;
          const cp1x = x0 + (x1 - x0) * tension;
          const cp1y = SPARK_H - 2 - (p1 + (p2 - p0) * tension);
          const cp2x = x1 - (x2 - x0) * tension * 0.5;
          const cp2y = SPARK_H - 2 - (p2 - (p3 - p1) * tension * 0.5);
          d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)} ${cp2x.toFixed(1)} ${cp2y.toFixed(1)} ${x} ${y.toFixed(1)}`;
        }
      }
      return d;
    }
    function sparkArea(key) {
      const lineD = sparkLine(key);
      if (!lineD) return "";
      return `${lineD} L ${SPARK_W} ${SPARK_H} L 0 ${SPARK_H} Z`;
    }
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$7, [
        (openBlock(true), createElementBlock(Fragment, null, renderList(items.value, (item) => {
          return openBlock(), createElementBlock("div", {
            key: item.key,
            class: normalizeClass(["cs-kpi", item.tone])
          }, [
            createBaseVNode("div", _hoisted_2$7, toDisplayString(item.label), 1),
            createBaseVNode("div", _hoisted_3$6, [
              hasData.value ? (openBlock(), createElementBlock("span", _hoisted_4$6, toDisplayString(displayed[item.key]), 1)) : (openBlock(), createElementBlock("span", _hoisted_5$5, "—"))
            ]),
            createBaseVNode("div", _hoisted_6$4, [
              createBaseVNode("span", {
                class: normalizeClass(["cs-kpi-caliber", "cal-" + item.tone])
              }, toDisplayString(item.caliber), 3),
              createBaseVNode("span", _hoisted_7$3, toDisplayString(item.foot), 1)
            ]),
            sparkData(item.key) ? (openBlock(), createElementBlock("svg", {
              key: 0,
              class: "cs-sparkline",
              viewBox: "0 0 " + SPARK_W + " " + SPARK_H,
              preserveAspectRatio: "none",
              "aria-hidden": "true"
            }, [
              createBaseVNode("defs", null, [
                createBaseVNode("linearGradient", {
                  id: "sg-" + item.key,
                  x1: "0",
                  y1: "0",
                  x2: "0",
                  y2: "1"
                }, [
                  createBaseVNode("stop", {
                    offset: "0%",
                    "stop-color": sparkColor(item.tone),
                    "stop-opacity": "0.25"
                  }, null, 8, _hoisted_10$2),
                  createBaseVNode("stop", {
                    offset: "100%",
                    "stop-color": sparkColor(item.tone),
                    "stop-opacity": "0.02"
                  }, null, 8, _hoisted_11$2)
                ], 8, _hoisted_9$2)
              ]),
              createBaseVNode("path", {
                d: sparkArea(item.key),
                fill: "url(#sg-" + item.key + ")"
              }, null, 8, _hoisted_12$2),
              createBaseVNode("path", {
                d: sparkLine(item.key),
                fill: "none",
                stroke: sparkColor(item.tone),
                "stroke-width": "1.5",
                "stroke-linecap": "round",
                "stroke-linejoin": "round"
              }, null, 8, _hoisted_13$1)
            ], 8, _hoisted_8$3)) : createCommentVNode("", true)
          ], 2);
        }), 128))
      ]);
    };
  }
});

const KpiBar = /* @__PURE__ */ _export_sfc(_sfc_main$8, [["__scopeId", "data-v-1b74f94e"]]);

const _hoisted_1$6 = { class: "cs-panel" };
const _hoisted_2$6 = {
  key: 0,
  class: "cs-panel-title"
};
const _hoisted_3$5 = {
  key: 0,
  class: "cs-badge is-cyan cs-mono",
  style: { "margin-left": "auto" }
};
const _hoisted_4$5 = { class: "cs-panel-body" };
const _sfc_main$7 = /* @__PURE__ */ defineComponent({
  __name: "ScreenPanel",
  props: {
    title: {},
    badge: {}
  },
  setup(__props) {
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("section", _hoisted_1$6, [
        __props.title ? (openBlock(), createElementBlock("h3", _hoisted_2$6, [
          createTextVNode(toDisplayString(__props.title) + " ", 1),
          __props.badge ? (openBlock(), createElementBlock("span", _hoisted_3$5, toDisplayString(__props.badge), 1)) : createCommentVNode("", true)
        ])) : createCommentVNode("", true),
        createBaseVNode("div", _hoisted_4$5, [
          renderSlot(_ctx.$slots, "default")
        ])
      ]);
    };
  }
});

function useEcharts(target, options = {}) {
  const el = target ?? ref(null);
  const chart = shallowRef(null);
  let ro = null;
  let rafId = 0;
  function resize() {
    if (!chart.value) return;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => {
      rafId = 0;
      chart.value?.resize();
    });
  }
  function init$1() {
    if (chart.value) return chart.value;
    if (!el.value) return null;
    chart.value = init(el.value, options.theme, options.initOptions);
    if (options.autoResize !== false) {
      window.addEventListener("resize", resize);
      if (typeof ResizeObserver !== "undefined") {
        ro = new ResizeObserver(resize);
        ro.observe(el.value);
      }
    }
    return chart.value;
  }
  function setOption(option, opts) {
    if (!chart.value) init$1();
    chart.value?.setOption(option, opts);
  }
  function showLoading(text = "") {
    chart.value?.showLoading("default", {
      text,
      color: "#22d3ee",
      textColor: "#a9c2da",
      maskColor: "rgba(6, 11, 22, 0.35)"
    });
  }
  function hideLoading() {
    chart.value?.hideLoading();
  }
  function dispose() {
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = 0;
    }
    window.removeEventListener("resize", resize);
    if (ro) {
      ro.disconnect();
      ro = null;
    }
    if (chart.value) {
      chart.value.dispose();
      chart.value = null;
    }
  }
  onMounted(() => {
    init$1();
  });
  onBeforeUnmount(() => {
    dispose();
  });
  return { el, chart, init: init$1, setOption, resize, showLoading, hideLoading, dispose };
}
const _registeredMaps = /* @__PURE__ */ new Set();
function registerMapOnce(name, geoJson) {
  if (_registeredMaps.has(name)) return;
  registerMap(name, geoJson);
  _registeredMaps.add(name);
}

const _sfc_main$6 = /* @__PURE__ */ defineComponent({
  __name: "BaseChart",
  props: {
    option: {},
    loading: { type: Boolean }
  },
  setup(__props) {
    const props = __props;
    const chartEl = ref(null);
    const { setOption, showLoading, hideLoading } = useEcharts(chartEl, {
      initOptions: { renderer: "canvas" }
    });
    watch(
      () => props.option,
      (opt) => {
        if (opt) {
          hideLoading();
          setOption(opt, { notMerge: true });
        }
      },
      { immediate: true, deep: true }
    );
    watch(
      () => props.loading,
      (v) => {
        if (v && !props.option) showLoading("加载中");
        else hideLoading();
      },
      { immediate: true }
    );
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", {
        ref_key: "chartEl",
        ref: chartEl,
        class: "cs-chart"
      }, null, 512);
    };
  }
});

const BaseChart = /* @__PURE__ */ _export_sfc(_sfc_main$6, [["__scopeId", "data-v-f3ec95da"]]);

const _hoisted_1$5 = {
  key: 0,
  class: "cs-map-msg"
};
const _hoisted_2$5 = {
  key: 1,
  class: "cs-map-msg"
};
const _hoisted_3$4 = {
  key: 2,
  class: "cs-map-overlay"
};
const _hoisted_4$4 = {
  key: 0,
  class: "cs-map-badge cs-mono"
};
const _hoisted_5$4 = {
  key: 1,
  class: "cs-map-badge"
};
const CHINA_NAME = "china";
const _sfc_main$5 = /* @__PURE__ */ defineComponent({
  __name: "ChinaMap",
  props: {
    regions: {},
    days: {}
  },
  setup(__props) {
    const props = __props;
    const mapEl = ref(null);
    const mapReady = ref(false);
    const mapError = ref(false);
    const { setOption, chart } = useEcharts(mapEl);
    const level = ref("country");
    const provinceName = ref(null);
    const provinceAdcode = ref(null);
    const children = ref(null);
    const loadingChildren = ref(false);
    const chinaAdcodeMap = /* @__PURE__ */ new Map();
    const geoCache = /* @__PURE__ */ new Map();
    function renderCountry() {
      if (!mapReady.value) return;
      const data = (props.regions ?? []).map((r) => ({ name: r.region_name, value: r.count }));
      const max = data.reduce((m, d) => Math.max(m, d.value), 0) || 1;
      const option = baseOption(max, data);
      setOption(option, { notMerge: true });
    }
    function renderProvince() {
      if (provinceAdcode.value == null || !geoCache.has(provinceAdcode.value)) return;
      const data = (children.value?.cities ?? []).map((c) => ({ name: c.name, value: c.count }));
      const max = data.reduce((m, d) => Math.max(m, d.value), 0) || 1;
      const option = baseOption(
        max,
        data,
        /*roam*/
        true
      );
      setOption(option, { notMerge: true });
    }
    function baseOption(max, data, roam = false) {
      const mapName = level.value === "province" && provinceAdcode.value != null ? `prov-${provinceAdcode.value}` : CHINA_NAME;
      return {
        tooltip: {
          trigger: "item",
          backgroundColor: "rgba(10,17,32,0.92)",
          borderColor: "rgba(34,211,238,0.35)",
          textStyle: { color: "#eaf6ff" },
          formatter: (p) => {
            const v = p.value ?? 0;
            const suffix = level.value === "province" ? "（含所辖县）" : "";
            return `${p.name}${suffix}<br/>舆情数量：${v}`;
          }
        },
        visualMap: {
          min: 0,
          max,
          left: 12,
          bottom: 12,
          calculable: true,
          inRange: { color: ["#0e2233", "#0f6d80", "#22d3ee"] },
          textStyle: { color: "#a9c2da" }
        },
        series: [
          {
            type: "map",
            map: mapName,
            roam,
            aspectScale: 0.78,
            data,
            label: { show: false },
            itemStyle: {
              areaColor: "#0c1a2b",
              borderColor: "rgba(90,138,178,0.35)",
              borderWidth: 0.6
            },
            emphasis: {
              label: { show: true, color: "#eaf6ff" },
              itemStyle: { areaColor: "#164863", borderColor: "#22d3ee" }
            }
          }
        ]
      };
    }
    async function loadProvinceGeo(adcode) {
      if (geoCache.has(adcode)) return geoCache.get(adcode);
      try {
        const local = await fetch(`/geo/${adcode}_full.json`);
        if (local.ok) {
          const geo2 = await local.json();
          geoCache.set(adcode, geo2);
          return geo2;
        }
      } catch {
      }
      const res = await fetch(`https://geo.datav.aliyun.com/areas_v3/bound/${adcode}_full.json`);
      if (!res.ok) throw new Error(`province geo ${adcode} ${res.status}`);
      const geo = await res.json();
      geoCache.set(adcode, geo);
      return geo;
    }
    async function drillTo(name) {
      const adcode = chinaAdcodeMap.get(name);
      if (adcode == null) return;
      provinceName.value = name;
      provinceAdcode.value = adcode;
      loadingChildren.value = true;
      children.value = null;
      try {
        const geo = await loadProvinceGeo(adcode);
        registerMapOnce(`prov-${adcode}`, geo);
        level.value = "province";
        try {
          const data = await fetchRegionChildren(name, props.days ?? 7);
          children.value = data;
        } catch (e) {
          if (e?.response?.status === 404) {
            children.value = { province: name, province_code: String(adcode), total: 0, cities: [], raw: [] };
          } else {
            throw e;
          }
        }
        loadingChildren.value = false;
        renderProvince();
      } catch (e) {
        loadingChildren.value = false;
        console.error("[ChinaMap] 省级下钻失败：", e);
        backToCountry();
      }
    }
    function backToCountry() {
      level.value = "country";
      provinceName.value = null;
      provinceAdcode.value = null;
      children.value = null;
      renderCountry();
    }
    function onMapClick(params) {
      if (level.value !== "country") return;
      if (params?.componentType === "series" && params.name) {
        void drillTo(params.name);
      }
    }
    onMounted(async () => {
      chart.value?.on("click", onMapClick);
      try {
        const res = await fetch("/geo/china-provinces.json");
        if (!res.ok) throw new Error(`geojson ${res.status}`);
        const geo = await res.json();
        for (const f of geo.features ?? []) {
          const p = f?.properties;
          if (p?.name != null && p?.adcode != null) chinaAdcodeMap.set(p.name, p.adcode);
        }
        registerMapOnce(CHINA_NAME, geo);
        mapReady.value = true;
        renderCountry();
      } catch (e) {
        mapError.value = true;
        console.error("[ChinaMap] 加载省级 GeoJSON 失败：", e);
      }
    });
    watch(() => props.regions, renderCountry, { deep: true });
    watch(() => props.days, () => {
      if (level.value === "province" && provinceName.value) {
        loadingChildren.value = true;
        fetchRegionChildren(provinceName.value, props.days ?? 7).then((d) => {
          children.value = d;
          loadingChildren.value = false;
          renderProvince();
        }).catch(() => {
          loadingChildren.value = false;
        });
      }
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", {
        class: normalizeClass(["cs-map-wrap", { "is-province": level.value === "province" }])
      }, [
        createBaseVNode("div", {
          ref_key: "mapEl",
          ref: mapEl,
          class: "cs-map"
        }, null, 512),
        mapError.value ? (openBlock(), createElementBlock("div", _hoisted_1$5, "地图资源加载失败，仅影响地图展示")) : !mapReady.value ? (openBlock(), createElementBlock("div", _hoisted_2$5, "地图加载中…")) : createCommentVNode("", true),
        level.value === "province" ? (openBlock(), createElementBlock("div", _hoisted_3$4, [
          createBaseVNode("button", {
            class: "cs-map-back",
            type: "button",
            onClick: backToCountry
          }, " ← 返回全国 "),
          children.value ? (openBlock(), createElementBlock("div", _hoisted_4$4, [
            children.value.total > 0 ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
              createTextVNode("已下钻 · " + toDisplayString(children.value.province) + " · 共 " + toDisplayString(children.value.total) + " 条", 1)
            ], 64)) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
              createTextVNode("已下钻 · " + toDisplayString(children.value.province) + " · 该省暂无细分数据", 1)
            ], 64))
          ])) : loadingChildren.value ? (openBlock(), createElementBlock("div", _hoisted_5$4, "加载细分数据…")) : createCommentVNode("", true)
        ])) : createCommentVNode("", true)
      ], 2);
    };
  }
});

const ChinaMap = /* @__PURE__ */ _export_sfc(_sfc_main$5, [["__scopeId", "data-v-fda86135"]]);

const _hoisted_1$4 = { class: "cs-rd" };
const _hoisted_2$4 = { class: "cs-rd-head" };
const _hoisted_3$3 = { class: "cs-rd-sub cs-mono" };
const _hoisted_4$3 = {
  key: 0,
  class: "cs-rd-skeleton",
  "aria-hidden": "true"
};
const _hoisted_5$3 = {
  key: 1,
  class: "cs-rd-empty"
};
const _hoisted_6$3 = {
  key: 2,
  class: "cs-rd-list"
};
const _hoisted_7$2 = { class: "cs-rd-rank" };
const _hoisted_8$2 = { class: "cs-rd-main" };
const _hoisted_9$1 = { class: "cs-rd-row" };
const _hoisted_10$1 = ["title"];
const _hoisted_11$1 = { class: "cs-rd-count cs-mono" };
const _hoisted_12$1 = { class: "cs-rd-bar" };
const _sfc_main$4 = /* @__PURE__ */ defineComponent({
  __name: "RegionDetailList",
  props: {
    items: {},
    days: {},
    loading: { type: Boolean }
  },
  setup(__props) {
    const props = __props;
    const max = computed(() => {
      const arr = props.items ?? [];
      return arr.reduce((m, it) => Math.max(m, it.count), 0) || 1;
    });
    function pct(c) {
      return `${Math.max(2, c / max.value * 100)}%`;
    }
    const display = ref([]);
    let raf = 0;
    function animateTo(targets) {
      cancelAnimationFrame(raf);
      const from = targets.map((_, i) => display.value[i] ?? 0);
      const t0 = performance.now();
      const dur = 700;
      const step = (now) => {
        const p = Math.min(1, (now - t0) / dur);
        const e = 1 - Math.pow(1 - p, 3);
        display.value = targets.map((tg, i) => Math.round(from[i] + (tg - from[i]) * e));
        if (p < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    }
    watch(
      () => props.items,
      (v) => {
        const targets = (v ?? []).map((x) => x.count);
        if (display.value.length !== targets.length) display.value = targets.map(() => 0);
        animateTo(targets);
      },
      { immediate: true }
    );
    onUnmounted(() => cancelAnimationFrame(raf));
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$4, [
        createBaseVNode("div", _hoisted_2$4, [
          _cache[0] || (_cache[0] = createBaseVNode("span", { class: "cs-rd-title" }, "地区舆情 TOP", -1)),
          createBaseVNode("span", _hoisted_3$3, "市 / 县 · 窗口 " + toDisplayString(__props.days) + " 天", 1)
        ]),
        __props.loading ? (openBlock(), createElementBlock("div", _hoisted_4$3, [
          (openBlock(), createElementBlock(Fragment, null, renderList(6, (i) => {
            return createBaseVNode("div", {
              key: i,
              class: "cs-rd-skel-row"
            });
          }), 64))
        ])) : !__props.items || __props.items.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_5$3, " 窗口内暂无市 / 县细分数据 ")) : (openBlock(), createElementBlock("ul", _hoisted_6$3, [
          (openBlock(true), createElementBlock(Fragment, null, renderList(__props.items, (it, idx) => {
            return openBlock(), createElementBlock("li", {
              key: it.region_id,
              class: normalizeClass(["cs-rd-item", { "is-top": idx < 3 }])
            }, [
              createBaseVNode("span", _hoisted_7$2, toDisplayString(idx + 1), 1),
              createBaseVNode("div", _hoisted_8$2, [
                createBaseVNode("div", _hoisted_9$1, [
                  createBaseVNode("span", {
                    class: "cs-rd-name",
                    title: it.region_name
                  }, toDisplayString(it.region_name), 9, _hoisted_10$1),
                  createBaseVNode("span", _hoisted_11$1, toDisplayString(display.value[idx] ?? 0), 1)
                ]),
                createBaseVNode("div", _hoisted_12$1, [
                  createBaseVNode("span", {
                    class: "cs-rd-bar-fill",
                    style: normalizeStyle({ width: pct(it.count) })
                  }, null, 4)
                ])
              ])
            ], 2);
          }), 128))
        ]))
      ]);
    };
  }
});

const RegionDetailList = /* @__PURE__ */ _export_sfc(_sfc_main$4, [["__scopeId", "data-v-c275e6d6"]]);

const _hoisted_1$3 = { class: "cs-hot" };
const _hoisted_2$3 = {
  key: 0,
  class: "cs-hot-empty"
};
const _hoisted_3$2 = {
  key: 1,
  class: "cs-hot-list"
};
const _hoisted_4$2 = { class: "cs-hot-word" };
const _hoisted_5$2 = { class: "cs-hot-bar" };
const _hoisted_6$2 = { class: "cs-hot-count cs-mono" };
const _sfc_main$3 = /* @__PURE__ */ defineComponent({
  __name: "HotKeywordList",
  props: {
    items: {}
  },
  setup(__props) {
    const props = __props;
    const maxCount = computed(() => (props.items ?? []).reduce((m, k) => Math.max(m, k.count), 0) || 1);
    function barWidth(count) {
      return `${Math.max(6, Math.round(count / maxCount.value * 100))}%`;
    }
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$3, [
        !__props.items || __props.items.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_2$3, "暂无热门关键词")) : (openBlock(), createElementBlock("ul", _hoisted_3$2, [
          (openBlock(true), createElementBlock(Fragment, null, renderList(__props.items, (k, i) => {
            return openBlock(), createElementBlock("li", {
              key: k.keyword,
              class: "cs-hot-row"
            }, [
              createBaseVNode("span", {
                class: normalizeClass(["cs-hot-rank cs-mono", { top: i < 3 }])
              }, toDisplayString(i + 1), 3),
              createBaseVNode("span", _hoisted_4$2, toDisplayString(k.keyword), 1),
              createBaseVNode("div", _hoisted_5$2, [
                createBaseVNode("div", {
                  class: "cs-hot-bar-fill",
                  style: normalizeStyle({ width: barWidth(k.count) })
                }, null, 4)
              ]),
              createBaseVNode("span", _hoisted_6$2, toDisplayString(k.count), 1),
              createBaseVNode("span", {
                class: normalizeClass(["cs-hot-trend", "t-" + k.trend]),
                "aria-hidden": "true"
              }, toDisplayString(k.trend === "up" ? "▲" : k.trend === "down" ? "▼" : "–"), 3)
            ]);
          }), 128))
        ]))
      ]);
    };
  }
});

const HotKeywordList = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-73917fc1"]]);

const _hoisted_1$2 = { class: "cs-feed" };
const _hoisted_2$2 = {
  key: 0,
  class: "cs-alert-summary"
};
const _hoisted_3$1 = { class: "cs-alert-sum cs-mono" };
const _hoisted_4$1 = { class: "cs-alert-sum cs-mono" };
const _hoisted_5$1 = {
  key: 1,
  class: "cs-feed-empty"
};
const _hoisted_6$1 = {
  key: 0,
  class: "cs-feed-list"
};
const _hoisted_7$1 = { class: "cs-feed-main" };
const _hoisted_8$1 = { class: "cs-feed-title" };
const _hoisted_9 = { class: "cs-feed-meta cs-muted" };
const _hoisted_10 = { class: "cs-mono" };
const _hoisted_11 = {
  key: 1,
  class: "cs-feed-list"
};
const _hoisted_12 = { class: "cs-feed-main" };
const _hoisted_13 = { class: "cs-feed-title" };
const _hoisted_14 = { class: "cs-feed-meta cs-muted" };
const _hoisted_15 = { class: "cs-mono" };
const _sfc_main$2 = /* @__PURE__ */ defineComponent({
  __name: "FeedList",
  props: {
    kind: {},
    recent: {},
    alerts: {}
  },
  setup(__props) {
    const props = __props;
    const viewportEl = ref(null);
    const trackEl = ref(null);
    const overflowing = ref(false);
    const rows = computed(
      () => props.kind === "recent" ? props.recent ?? [] : props.alerts ?? []
    );
    const hasRows = computed(() => rows.value.length > 0);
    const pendingCount = computed(() => (props.alerts ?? []).filter((a) => !a.handled).length);
    const doneCount = computed(() => (props.alerts ?? []).filter((a) => a.handled).length);
    const duration = computed(() => `${Math.max(rows.value.length * 2.4, 8)}s`);
    function measure() {
      if (!viewportEl.value || !trackEl.value) return;
      const oneCopy = trackEl.value.scrollHeight / 2;
      overflowing.value = oneCopy > viewportEl.value.clientHeight + 1;
    }
    function shortTime(s) {
      if (!s) return "-";
      return s.replace("T", " ").slice(5, 16);
    }
    function sentLabel(s) {
      return { negative: "负面", neutral: "中性", positive: "正面" }[s] || "中性";
    }
    function sentBadge(s) {
      return { negative: "is-rose", neutral: "is-cyan", positive: "is-teal" }[s] || "is-cyan";
    }
    function riskBadge(score) {
      if (score >= 70) return "is-rose";
      if (score >= 40) return "is-amber";
      return "is-teal";
    }
    function riskLevelBadge(l) {
      return { critical: "is-rose", high: "is-rose", medium: "is-amber", low: "is-teal" }[l] || "is-cyan";
    }
    function riskLevelText(l) {
      return { critical: "严重", high: "高", medium: "中", low: "低" }[l] || l;
    }
    let ro = null;
    onMounted(() => {
      nextTick(measure);
      if (viewportEl.value && typeof ResizeObserver !== "undefined") {
        ro = new ResizeObserver(() => measure());
        ro.observe(viewportEl.value);
      }
    });
    onBeforeUnmount(() => {
      if (ro) {
        ro.disconnect();
        ro = null;
      }
    });
    watch(rows, () => nextTick(measure), { deep: true });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$2, [
        __props.kind === "alert" && __props.alerts && __props.alerts.length ? (openBlock(), createElementBlock("div", _hoisted_2$2, [
          createBaseVNode("span", _hoisted_3$1, [
            _cache[0] || (_cache[0] = createBaseVNode("i", { class: "cs-sum-dot is-amber" }, null, -1)),
            createTextVNode("待处置 " + toDisplayString(pendingCount.value), 1)
          ]),
          createBaseVNode("span", _hoisted_4$1, [
            _cache[1] || (_cache[1] = createBaseVNode("i", { class: "cs-sum-dot is-teal" }, null, -1)),
            createTextVNode("已处置 " + toDisplayString(doneCount.value), 1)
          ])
        ])) : createCommentVNode("", true),
        !hasRows.value ? (openBlock(), createElementBlock("div", _hoisted_5$1, toDisplayString(__props.kind === "alert" ? "暂无预警" : "暂无快讯"), 1)) : (openBlock(), createElementBlock("div", {
          key: 2,
          ref_key: "viewportEl",
          ref: viewportEl,
          class: "cs-feed-viewport"
        }, [
          createBaseVNode("div", {
            ref_key: "trackEl",
            ref: trackEl,
            class: normalizeClass(["cs-feed-track", { scrolling: overflowing.value }]),
            style: normalizeStyle({ animationDuration: duration.value })
          }, [
            (openBlock(), createElementBlock(Fragment, null, renderList(2, (copy) => {
              return createBaseVNode("div", {
                key: copy,
                class: "cs-feed-copy"
              }, [
                __props.kind === "recent" ? (openBlock(), createElementBlock("ul", _hoisted_6$1, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(__props.recent, (o) => {
                    return openBlock(), createElementBlock("li", {
                      key: "r" + copy + "-" + o.id,
                      class: "cs-feed-row"
                    }, [
                      createBaseVNode("span", {
                        class: normalizeClass(["cs-badge cs-mono", riskBadge(o.risk_score)])
                      }, toDisplayString(o.risk_score), 3),
                      createBaseVNode("div", _hoisted_7$1, [
                        createBaseVNode("div", _hoisted_8$1, toDisplayString(o.title), 1),
                        createBaseVNode("div", _hoisted_9, [
                          createBaseVNode("span", null, toDisplayString(o.source), 1),
                          _cache[2] || (_cache[2] = createBaseVNode("span", null, "·", -1)),
                          createBaseVNode("span", null, toDisplayString(o.region_name || "未知地区"), 1),
                          _cache[3] || (_cache[3] = createBaseVNode("span", null, "·", -1)),
                          createBaseVNode("span", _hoisted_10, toDisplayString(shortTime(o.created_at)), 1)
                        ])
                      ]),
                      createBaseVNode("span", {
                        class: normalizeClass(["cs-badge", sentBadge(o.sentiment)])
                      }, toDisplayString(sentLabel(o.sentiment)), 3)
                    ]);
                  }), 128))
                ])) : (openBlock(), createElementBlock("ul", _hoisted_11, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(__props.alerts, (a) => {
                    return openBlock(), createElementBlock("li", {
                      key: "a" + copy + "-" + a.id,
                      class: "cs-feed-row"
                    }, [
                      createBaseVNode("span", {
                        class: normalizeClass(["cs-badge cs-mono", riskLevelBadge(a.risk_level)])
                      }, toDisplayString(riskLevelText(a.risk_level)), 3),
                      createBaseVNode("div", _hoisted_12, [
                        createBaseVNode("div", _hoisted_13, toDisplayString(a.opinion_title || a.rule_name), 1),
                        createBaseVNode("div", _hoisted_14, [
                          createBaseVNode("span", null, toDisplayString(a.rule_name), 1),
                          _cache[4] || (_cache[4] = createBaseVNode("span", null, "·", -1)),
                          createBaseVNode("span", _hoisted_15, toDisplayString(shortTime(a.created_at)), 1)
                        ])
                      ]),
                      createBaseVNode("span", {
                        class: normalizeClass(["cs-badge", a.handled ? "is-teal" : "is-amber"])
                      }, toDisplayString(a.handled ? "已处置" : "待处置"), 3)
                    ]);
                  }), 128))
                ]))
              ]);
            }), 64))
          ], 6)
        ], 512))
      ]);
    };
  }
});

const FeedList = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-ce262d09"]]);

const _hoisted_1$1 = { class: "cs-ticker" };
const _hoisted_2$1 = { class: "cs-ticker-viewport" };
const _sfc_main$1 = /* @__PURE__ */ defineComponent({
  __name: "ScreenTicker",
  props: {
    items: {}
  },
  setup(__props) {
    const props = __props;
    const loopItems = computed(() => {
      const base = props.items.length ? props.items : ["等待实时数据接入…"];
      return [...base, ...base];
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$1, [
        _cache[1] || (_cache[1] = createBaseVNode("span", { class: "cs-ticker-tag" }, "实时解码", -1)),
        createBaseVNode("div", _hoisted_2$1, [
          createBaseVNode("div", {
            class: normalizeClass(["cs-ticker-track", { paused: __props.items.length === 0 }])
          }, [
            (openBlock(true), createElementBlock(Fragment, null, renderList(loopItems.value, (t, i) => {
              return openBlock(), createElementBlock("span", {
                key: i,
                class: "cs-ticker-item cs-mono"
              }, [
                _cache[0] || (_cache[0] = createBaseVNode("span", { class: "cs-ticker-dot" }, "◈", -1)),
                createTextVNode(toDisplayString(t), 1)
              ]);
            }), 128))
          ], 2)
        ])
      ]);
    };
  }
});

const ScreenTicker = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-0021daf4"]]);

const _hoisted_1 = { class: "command-screen cs-root" };
const _hoisted_2 = { class: "cs-main" };
const _hoisted_3 = { class: "cs-col cs-col-left" };
const _hoisted_4 = { class: "cs-col cs-col-center" };
const _hoisted_5 = { class: "cs-geo-split" };
const _hoisted_6 = { class: "cs-geo-map" };
const _hoisted_7 = { class: "cs-geo-detail" };
const _hoisted_8 = { class: "cs-col cs-col-right" };
const days = 7;
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "CommandScreen",
  setup(__props) {
    const router = useRouter();
    function exitScreen() {
      router.push("/dashboard");
    }
    const stats = useCommandScreenStats(days);
    const recent = useCommandScreenRecent(8);
    const alerts = useCommandScreenAlerts(50);
    const sourceCount = useCommandScreenSourceCount();
    const overallStatus = computed(() => {
      const rank = { live: 0, connecting: 1, stale: 2, down: 3 };
      const worst = [stats.status.value, recent.status.value, alerts.status.value].reduce(
        (acc, s) => rank[s] > rank[acc] ? s : acc,
        "live"
      );
      return worst;
    });
    const axisLabel = { color: "#a9c2da", fontSize: 11 };
    const splitLine = { lineStyle: { color: "rgba(90,138,178,0.12)" } };
    const SENT_MAP = {
      negative: { name: "负面", color: "#fb7185" },
      neutral: { name: "中性", color: "#22d3ee" },
      positive: { name: "正面", color: "#2dd4bf" }
    };
    const sentimentOption = computed(() => {
      const s = stats.data.value?.sentiments;
      if (!s) return null;
      const total = s.reduce((acc, x) => acc + x.count, 0) || 1;
      const data = s.map((x) => {
        const m = SENT_MAP[x.label] ?? { name: x.label, color: "#a78bfa" };
        return {
          name: m.name,
          value: x.count,
          itemStyle: { color: m.color }
        };
      });
      const pctOf = (v) => (v / total * 100).toFixed(1);
      return {
        tooltip: {
          trigger: "item",
          backgroundColor: "rgba(10,17,32,0.92)",
          borderColor: "rgba(34,211,238,0.35)",
          textStyle: { color: "#eaf6ff" },
          formatter: (p) => `${p.name}（系统研判）<br/>${p.value} 条 · 占比 ${pctOf(p.value)}%`
        },
        legend: {
          bottom: 0,
          left: "center",
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { color: "#a9c2da", fontSize: 11 },
          formatter: (name) => {
            const it = data.find((d) => d.name === name);
            return it ? `${name} ${pctOf(it.value)}%` : name;
          }
        },
        graphic: {
          type: "text",
          left: "center",
          top: "38%",
          style: {
            text: `${total}
系统研判`,
            textAlign: "center",
            fill: "#eaf6ff",
            fontSize: 20,
            fontWeight: 700,
            lineHeight: 22
          }
        },
        series: [
          {
            type: "pie",
            radius: ["46%", "68%"],
            center: ["50%", "44%"],
            avoidLabelOverlap: true,
            label: { show: false },
            data
          }
        ]
      };
    });
    const sourceOption = computed(() => {
      const src = stats.data.value?.sources;
      if (!src) return null;
      const top = [...src].slice(0, 8).reverse();
      return {
        grid: { left: 8, right: 16, top: 10, bottom: 6, containLabel: true },
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, backgroundColor: "rgba(10,17,32,0.92)", borderColor: "rgba(34,211,238,0.35)", textStyle: { color: "#eaf6ff" } },
        xAxis: { type: "value", axisLabel, splitLine },
        yAxis: { type: "category", data: top.map((s) => s.source), axisLabel, axisLine: { lineStyle: { color: "rgba(90,138,178,0.3)" } } },
        series: [
          {
            type: "bar",
            data: top.map((s) => s.count),
            barWidth: 12,
            itemStyle: {
              borderRadius: [0, 6, 6, 0],
              color: { type: "linear", x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: "#0f6d80" }, { offset: 1, color: "#22d3ee" }] }
            }
          }
        ]
      };
    });
    const trendOption = computed(() => {
      const t = stats.data.value?.trend;
      if (!t) return null;
      return {
        grid: { left: 8, right: 16, top: 16, bottom: 6, containLabel: true },
        tooltip: {
          trigger: "axis",
          backgroundColor: "rgba(10,17,32,0.92)",
          borderColor: "rgba(34,211,238,0.35)",
          textStyle: { color: "#eaf6ff" },
          // 趋势按 created_at 统计的「入库数量」，明确口径避免误读为「舆情总量」
          formatter: (params) => {
            const p = Array.isArray(params) ? params[0] : params;
            return `${p.axisValue}<br/>新增入库：<b>${p.data}</b> 条`;
          }
        },
        xAxis: { type: "category", boundaryGap: false, data: t.map((p) => p.date.slice(5)), axisLabel, axisLine: { lineStyle: { color: "rgba(90,138,178,0.3)" } } },
        yAxis: { type: "value", axisLabel, splitLine },
        series: [
          {
            type: "line",
            smooth: true,
            symbol: "circle",
            symbolSize: 5,
            data: t.map((p) => p.count),
            lineStyle: { width: 2.5, color: "#22d3ee" },
            itemStyle: { color: "#22d3ee" },
            areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "rgba(34,211,238,0.28)" }, { offset: 1, color: "rgba(34,211,238,0)" }] } }
          }
        ]
      };
    });
    const tickerItems = computed(() => {
      const d = stats.data.value;
      if (!d) return [];
      const regions = (d.regions ?? []).map((r) => `${r.region_name} · ${r.count}`);
      const hot = (d.hot_keywords ?? []).map((k) => `${k.keyword} · ${k.count}`);
      const latest = recent.data.value?.[0]?.created_at;
      const items = [...regions, ...hot];
      if (latest) {
        const hhmm = latest.replace("T", " ").slice(11, 16);
        items.push(`最新入库 ${hhmm}`);
      }
      return items;
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1, [
        createVNode(ScreenHeader, {
          class: "cs-row-header",
          status: overallStatus.value,
          onExit: exitScreen
        }, null, 8, ["status"]),
        createVNode(KpiBar, {
          class: "cs-row-kpi",
          stats: unref(stats).data.value,
          "source-count": unref(sourceCount).data.value?.total ?? null
        }, null, 8, ["stats", "source-count"]),
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            createVNode(_sfc_main$7, {
              title: "情感分布 · 系统研判",
              class: "cs-flex-1"
            }, {
              default: withCtx(() => [
                createVNode(BaseChart, {
                  option: sentimentOption.value,
                  loading: unref(stats).loading.value
                }, null, 8, ["option", "loading"])
              ]),
              _: 1
            }),
            createVNode(_sfc_main$7, {
              title: "来源分布 TOP",
              class: "cs-flex-1"
            }, {
              default: withCtx(() => [
                createVNode(BaseChart, {
                  option: sourceOption.value,
                  loading: unref(stats).loading.value
                }, null, 8, ["option", "loading"])
              ]),
              _: 1
            })
          ]),
          createBaseVNode("div", _hoisted_4, [
            createVNode(_sfc_main$7, {
              title: "全域舆情热力 · 地区 TOP",
              class: "cs-flex-2",
              badge: `窗口 ${days}天`
            }, {
              default: withCtx(() => [
                createBaseVNode("div", _hoisted_5, [
                  createBaseVNode("div", _hoisted_6, [
                    createVNode(ChinaMap, {
                      regions: unref(stats).data.value?.regions ?? null,
                      days
                    }, null, 8, ["regions"])
                  ]),
                  createBaseVNode("div", _hoisted_7, [
                    createVNode(RegionDetailList, {
                      items: unref(stats).data.value?.region_detail ?? null,
                      days,
                      loading: unref(stats).loading.value
                    }, null, 8, ["items", "loading"])
                  ])
                ])
              ]),
              _: 1
            }, 8, ["badge"]),
            createVNode(_sfc_main$7, {
              title: "传播趋势",
              class: "cs-flex-1"
            }, {
              default: withCtx(() => [
                createVNode(BaseChart, {
                  option: trendOption.value,
                  loading: unref(stats).loading.value
                }, null, 8, ["option", "loading"])
              ]),
              _: 1
            })
          ]),
          createBaseVNode("div", _hoisted_8, [
            createVNode(_sfc_main$7, {
              title: "热门关键词",
              class: "cs-flex-1",
              badge: `${days}天`
            }, {
              default: withCtx(() => [
                createVNode(HotKeywordList, {
                  items: unref(stats).data.value?.hot_keywords ?? null
                }, null, 8, ["items"])
              ]),
              _: 1
            }, 8, ["badge"]),
            createVNode(_sfc_main$7, {
              title: "实时快讯",
              class: "cs-flex-1"
            }, {
              default: withCtx(() => [
                createVNode(FeedList, {
                  kind: "recent",
                  recent: unref(recent).data.value
                }, null, 8, ["recent"])
              ]),
              _: 1
            }),
            createVNode(_sfc_main$7, {
              title: "预警滚动",
              class: "cs-flex-1"
            }, {
              default: withCtx(() => [
                createVNode(FeedList, {
                  kind: "alert",
                  alerts: unref(alerts).data.value
                }, null, 8, ["alerts"])
              ]),
              _: 1
            })
          ])
        ]),
        createVNode(ScreenTicker, {
          class: "cs-row-ticker",
          items: tickerItems.value
        }, null, 8, ["items"])
      ]);
    };
  }
});

const CommandScreen = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-f1160aa2"]]);

export { CommandScreen as default };
