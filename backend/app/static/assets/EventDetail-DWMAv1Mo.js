import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, t as toDisplayString, n as normalizeClass, e as createTextVNode, A as createCommentVNode, k as normalizeStyle, F as Fragment, i as renderList, B as createVNode, r as ref, g as api, E as ElMessage, D as resolveDirective, M as useRoute, o as openBlock, h as useRouter, _ as _export_sfc } from './index-DYwSRqnI.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-Gp2lq1AC.js';

const _hoisted_1 = { class: "event-detail" };
const _hoisted_2 = { class: "detail-back" };
const _hoisted_3 = { class: "event-header" };
const _hoisted_4 = { class: "event-title-row" };
const _hoisted_5 = { class: "detail-title" };
const _hoisted_6 = { class: "event-meta" };
const _hoisted_7 = {
  key: 0,
  class: "event-desc"
};
const _hoisted_8 = { class: "situation-strip" };
const _hoisted_9 = { class: "situation-item" };
const _hoisted_10 = { class: "situation-item" };
const _hoisted_11 = { class: "situation-item" };
const _hoisted_12 = { class: "card table-card" };
const _hoisted_13 = { class: "card-header" };
const _hoisted_14 = { class: "section-title" };
const _hoisted_15 = { class: "tbl" };
const _hoisted_16 = ["onClick"];
const _hoisted_17 = { class: "t-title" };
const _hoisted_18 = { class: "col-center" };
const _hoisted_19 = { class: "col-center" };
const _hoisted_20 = { key: 0 };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "EventDetail",
  setup(__props) {
    const route = useRoute();
    useRouter();
    const loading = ref(false);
    const detailVisible = ref(false);
    const detailId = ref(null);
    function openOpinion(id) {
      detailId.value = id;
      detailVisible.value = true;
    }
    const event = ref({
      id: 0,
      title: "",
      region_id: null,
      risk_level: "",
      risk_score: 0,
      topic_category: null,
      heat_score: 0,
      trend: "unknown",
      opinion_count: 0,
      status: "",
      first_time: null,
      last_time: null,
      description: "",
      keyword: "",
      opinions: [],
      total_opinions: 0
    });
    function riskPill(level) {
      return { high: "pill-red", medium: "pill-orange", low: "pill-green" }[level] || "pill-gray";
    }
    function riskText(level) {
      return { high: "高风险", medium: "中风险", low: "低风险" }[level] || level;
    }
    function sentimentPill(s) {
      return { positive: "pill-green", negative: "pill-red", neutral: "pill-gray" }[s] || "pill-gray";
    }
    function sentimentText(s) {
      return { positive: "正面", negative: "负面", neutral: "中性" }[s] || s;
    }
    function riskColor(score) {
      if (score >= 70) return "#ff3b30";
      if (score >= 40) return "#ff9f0a";
      return "#34c759";
    }
    function trendText(value) {
      return { rising: "↑ 升温", stable: "→ 稳定", falling: "↓ 降温", unknown: "数据不足" }[value] || value;
    }
    function formatTime(t) {
      if (!t) return "-";
      return t.replace("T", " ").slice(0, 19);
    }
    async function loadData() {
      loading.value = true;
      try {
        const id = route.params.id;
        const { data } = await api.get("/events/" + id);
        event.value = { ...event.value, ...data };
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载事件详情失败");
      } finally {
        loading.value = false;
      }
    }
    onMounted(loadData);
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: _cache[0] || (_cache[0] = ($event) => _ctx.$router.back())
          }, "← 返回")
        ]),
        createBaseVNode("div", _hoisted_3, [
          createBaseVNode("div", _hoisted_4, [
            createBaseVNode("h2", _hoisted_5, toDisplayString(event.value.title), 1),
            createBaseVNode("span", {
              class: normalizeClass(["pill", riskPill(event.value.risk_level)])
            }, [
              _cache[2] || (_cache[2] = createBaseVNode("span", { class: "dot" }, null, -1)),
              createTextVNode(toDisplayString(riskText(event.value.risk_level)), 1)
            ], 2)
          ]),
          createBaseVNode("div", _hoisted_6, [
            createBaseVNode("span", null, [
              _cache[3] || (_cache[3] = createTextVNode("关联舆情：", -1)),
              createBaseVNode("b", null, toDisplayString(event.value.total_opinions), 1),
              _cache[4] || (_cache[4] = createTextVNode(" 条", -1))
            ]),
            createBaseVNode("span", null, "首次发现：" + toDisplayString(formatTime(event.value.first_time)), 1),
            createBaseVNode("span", null, "最后更新：" + toDisplayString(formatTime(event.value.last_time)), 1)
          ]),
          event.value.description ? (openBlock(), createElementBlock("div", _hoisted_7, toDisplayString(event.value.description), 1)) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_8, [
          createBaseVNode("div", _hoisted_9, [
            _cache[5] || (_cache[5] = createBaseVNode("span", { class: "situation-label" }, "当前风险", -1)),
            createBaseVNode("strong", {
              style: normalizeStyle({ color: riskColor(event.value.risk_score) })
            }, toDisplayString(event.value.risk_score) + " 分 · " + toDisplayString(riskText(event.value.risk_level)), 5)
          ]),
          createBaseVNode("div", _hoisted_10, [
            _cache[6] || (_cache[6] = createBaseVNode("span", { class: "situation-label" }, "当前热度", -1)),
            createBaseVNode("strong", null, toDisplayString(event.value.heat_score) + " 分", 1)
          ]),
          createBaseVNode("div", _hoisted_11, [
            _cache[7] || (_cache[7] = createBaseVNode("span", { class: "situation-label" }, "发展趋势", -1)),
            createBaseVNode("strong", null, toDisplayString(trendText(event.value.trend)), 1)
          ])
        ]),
        createBaseVNode("div", _hoisted_12, [
          createBaseVNode("div", _hoisted_13, [
            createBaseVNode("h3", _hoisted_14, "关联舆情列表 (" + toDisplayString(event.value.total_opinions) + ")", 1)
          ]),
          createBaseVNode("table", _hoisted_15, [
            _cache[10] || (_cache[10] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", { style: { "width": "70px" } }, "ID"),
                createBaseVNode("th", { style: { "min-width": "280px" } }, "标题"),
                createBaseVNode("th", { style: { "width": "160px" } }, "来源"),
                createBaseVNode("th", {
                  style: { "width": "90px" },
                  class: "col-center"
                }, "情感"),
                createBaseVNode("th", {
                  style: { "width": "90px" },
                  class: "col-center"
                }, "风险分"),
                createBaseVNode("th", {
                  style: { "width": "100px" },
                  class: "col-center"
                }, "分析状态"),
                createBaseVNode("th", { style: { "width": "170px" } }, "发布时间")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(event.value.opinions, (row) => {
                return openBlock(), createElementBlock("tr", {
                  key: row.id,
                  onClick: ($event) => openOpinion(row.id),
                  style: { "cursor": "pointer" }
                }, [
                  createBaseVNode("td", null, toDisplayString(row.id), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", _hoisted_17, toDisplayString(row.title), 1)
                  ]),
                  createBaseVNode("td", null, toDisplayString(row.source), 1),
                  createBaseVNode("td", _hoisted_18, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", sentimentPill(row.sentiment)])
                    }, [
                      _cache[8] || (_cache[8] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(sentimentText(row.sentiment)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", {
                    class: "col-center risk-num",
                    style: normalizeStyle({ color: riskColor(row.risk_score) })
                  }, toDisplayString(row.risk_score), 5),
                  createBaseVNode("td", _hoisted_19, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", row.analysis_status === "completed" ? "pill-green" : "pill-gray"])
                    }, toDisplayString(row.analysis_status === "completed" ? "已完成" : row.analysis_status), 3)
                  ]),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.publish_time)), 1)
                ], 8, _hoisted_16);
              }), 128)),
              event.value.opinions.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_20, [..._cache[9] || (_cache[9] = [
                createBaseVNode("td", {
                  colspan: "7",
                  class: "empty-row"
                }, "暂无关联舆情", -1)
              ])])) : createCommentVNode("", true)
            ])
          ])
        ]),
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const EventDetail = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-c7e54931"]]);

export { EventDetail as default };
