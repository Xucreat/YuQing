import { d as defineComponent, c as createElementBlock, a as createBaseVNode, t as toDisplayString, s as createCommentVNode, e as createTextVNode, F as Fragment, i as renderList, o as openBlock, _ as _export_sfc, z as usePermission, C as onMounted, w as withDirectives, n as normalizeClass, H as unref, k as normalizeStyle, q as createBlock, m as createVNode, p as withCtx, r as ref, j as computed, g as api, E as ElMessage, y as resolveComponent, B as resolveDirective, L as useRoute, h as useRouter } from './index-yZr-pUsf.js';
import { e as eventStatusPill, a as eventStatusLabel, b as EventDispositionDialog } from './EventDispositionDialog-DAhNI74V.js';
import { F as ForeignOpinionDetailModal } from './ForeignOpinionDetailModal-d7Rsjrt8.js';
import { f as formatTime, r as riskColor } from './opinion-Cag9WtuS.js';

const _hoisted_1$1 = {
  key: 0,
  class: "stat-panel"
};
const _hoisted_2$1 = { class: "stat-grid" };
const _hoisted_3$1 = {
  key: 0,
  class: "stat-item"
};
const _hoisted_4$1 = {
  key: 1,
  class: "stat-item"
};
const _hoisted_5$1 = {
  key: 2,
  class: "stat-item"
};
const _hoisted_6$1 = { class: "dist-pills" };
const _hoisted_7$1 = { class: "pill pill-red" };
const _hoisted_8$1 = { class: "pill pill-orange" };
const _hoisted_9$1 = { class: "pill pill-green" };
const _hoisted_10$1 = {
  key: 3,
  class: "stat-item"
};
const _hoisted_11$1 = {
  key: 4,
  class: "stat-item"
};
const _hoisted_12$1 = {
  key: 0,
  class: "risk-factor-list"
};
const _sfc_main$1 = /* @__PURE__ */ defineComponent({
  __name: "EventAnalysisStats",
  props: {
    statistics: {},
    situation: {}
  },
  setup(__props) {
    function formatTime(t) {
      if (!t) return "-";
      return String(t).replace("T", " ").slice(0, 19);
    }
    function sufficiencyText(value) {
      return { sufficient: "充分", limited: "有限", insufficient: "不足" }[value || ""] || "未知";
    }
    return (_ctx, _cache) => {
      return __props.statistics || __props.situation ? (openBlock(), createElementBlock("section", _hoisted_1$1, [
        _cache[8] || (_cache[8] = createBaseVNode("h3", { class: "section-title" }, "研判与统计", -1)),
        createBaseVNode("div", _hoisted_2$1, [
          __props.statistics?.source_count != null || __props.situation?.source_distribution?.length ? (openBlock(), createElementBlock("div", _hoisted_3$1, [
            _cache[0] || (_cache[0] = createBaseVNode("span", { class: "stat-label" }, "来源数量", -1)),
            createBaseVNode("strong", null, toDisplayString(__props.statistics?.source_count ?? (__props.situation?.source_distribution?.length || 0)) + " 个", 1)
          ])) : createCommentVNode("", true),
          __props.situation?.data_window?.first_time || __props.situation?.data_window?.last_time ? (openBlock(), createElementBlock("div", _hoisted_4$1, [
            _cache[1] || (_cache[1] = createBaseVNode("span", { class: "stat-label" }, "时间范围", -1)),
            createBaseVNode("strong", null, toDisplayString(formatTime(__props.situation?.data_window?.first_time)) + " - " + toDisplayString(formatTime(__props.situation?.data_window?.last_time)), 1)
          ])) : createCommentVNode("", true),
          __props.statistics ? (openBlock(), createElementBlock("div", _hoisted_5$1, [
            _cache[5] || (_cache[5] = createBaseVNode("span", { class: "stat-label" }, "风险分布", -1)),
            createBaseVNode("span", _hoisted_6$1, [
              createBaseVNode("span", _hoisted_7$1, [
                _cache[2] || (_cache[2] = createBaseVNode("span", { class: "dot" }, null, -1)),
                createTextVNode("高 " + toDisplayString(__props.statistics.risk_distribution?.high ?? 0), 1)
              ]),
              createBaseVNode("span", _hoisted_8$1, [
                _cache[3] || (_cache[3] = createBaseVNode("span", { class: "dot" }, null, -1)),
                createTextVNode("中 " + toDisplayString(__props.statistics.risk_distribution?.medium ?? 0), 1)
              ]),
              createBaseVNode("span", _hoisted_9$1, [
                _cache[4] || (_cache[4] = createBaseVNode("span", { class: "dot" }, null, -1)),
                createTextVNode("低 " + toDisplayString(__props.statistics.risk_distribution?.low ?? 0), 1)
              ])
            ])
          ])) : createCommentVNode("", true),
          __props.situation?.risk_shadow ? (openBlock(), createElementBlock("div", _hoisted_10$1, [
            _cache[6] || (_cache[6] = createBaseVNode("span", { class: "stat-label" }, "影子风险", -1)),
            createBaseVNode("strong", null, toDisplayString(__props.situation.risk_shadow?.score ?? "-") + " 分", 1)
          ])) : createCommentVNode("", true),
          __props.situation?.data_sufficiency ? (openBlock(), createElementBlock("div", _hoisted_11$1, [
            _cache[7] || (_cache[7] = createBaseVNode("span", { class: "stat-label" }, "数据充分性", -1)),
            createBaseVNode("strong", null, toDisplayString(sufficiencyText(__props.situation.data_sufficiency?.level)), 1)
          ])) : createCommentVNode("", true)
        ]),
        (__props.situation?.risk_factors || []).length ? (openBlock(), createElementBlock("div", _hoisted_12$1, [
          (openBlock(true), createElementBlock(Fragment, null, renderList(__props.situation.risk_factors || [], (factor) => {
            return openBlock(), createElementBlock("span", {
              key: factor.factor,
              class: "risk-factor"
            }, toDisplayString(factor.description), 1);
          }), 128))
        ])) : createCommentVNode("", true)
      ])) : createCommentVNode("", true);
    };
  }
});

const EventAnalysisStats = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-5119133f"]]);

const _hoisted_1 = { class: "event-detail" };
const _hoisted_2 = { class: "overview-card" };
const _hoisted_3 = { class: "event-title-row" };
const _hoisted_4 = { class: "detail-title" };
const _hoisted_5 = {
  key: 0,
  class: "focus-mark"
};
const _hoisted_6 = {
  key: 0,
  class: "event-desc"
};
const _hoisted_7 = { class: "event-meta" };
const _hoisted_8 = { class: "situation-strip" };
const _hoisted_9 = { class: "situation-item" };
const _hoisted_10 = { class: "situation-item" };
const _hoisted_11 = {
  key: 0,
  class: "situation-item"
};
const _hoisted_12 = { class: "situation-item" };
const _hoisted_13 = { class: "situation-item" };
const _hoisted_14 = { class: "situation-item" };
const _hoisted_15 = { class: "card table-card" };
const _hoisted_16 = { class: "tbl" };
const _hoisted_17 = ["onClick"];
const _hoisted_18 = { class: "t-title" };
const _hoisted_19 = { class: "col-center" };
const _hoisted_20 = { key: 0 };
const _hoisted_21 = { class: "tbl" };
const _hoisted_22 = { class: "t-title" };
const _hoisted_23 = { class: "col-center" };
const _hoisted_24 = { class: "col-center" };
const _hoisted_25 = { class: "col-center" };
const _hoisted_26 = { key: 0 };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "ForeignEventDetail",
  setup(__props) {
    const route = useRoute();
    const router = useRouter();
    const loading = ref(false);
    const situation = ref(null);
    const handleDialogVisible = ref(false);
    const { hasPermission } = usePermission();
    const canUpdateEvent = computed(() => hasPermission("foreign:events:write"));
    const activeRelatedTab = ref("opinions");
    const detailVisible = ref(false);
    const detailId = ref(null);
    function openOpinion(id) {
      detailId.value = id;
      detailVisible.value = true;
    }
    const event = ref({
      id: 0,
      title: "",
      summary: null,
      language: "unknown",
      event_type: "other",
      status: "",
      event_status: "",
      risk_level: "",
      heat_score: 0,
      formal_risk_score: 0,
      formal_risk_level: "low",
      linked_opinion_current_risk: null,
      confidence: 0,
      first_seen_at: null,
      last_seen_at: null,
      opinion_count: 0,
      source_count: 0,
      confirmation_source: "",
      opinions: [],
      alerts: []
    });
    const isKeyEvent = computed(() => event.value.risk_level === "high");
    function riskPill(level) {
      return { high: "pill-red", medium: "pill-orange", low: "pill-green" }[level] || "pill-gray";
    }
    function riskText(level) {
      return { high: "高风险", medium: "中风险", low: "低风险", unknown: "未知" }[level] || level || "未知";
    }
    function languageText(value) {
      return { en: "英文", zh: "中文", unknown: "未标注" }[value || ""] || (value || "未标注");
    }
    function eventTypeText(value) {
      return { other: "其他", conflict: "冲突", disaster: "灾害", epidemic: "疫情", election: "选举", economy: "经济", terrorism: "恐怖袭击", human_rights: "人权", diplomacy: "外交" }[value || ""] || value || "其他";
    }
    function confidenceText(value) {
      if (value == null) return "-";
      return value <= 1 ? `${Math.round(value * 100)}%` : `${value}`;
    }
    function similarityText(value) {
      if (value == null) return "-";
      return value <= 1 ? `${Math.round(value * 100)}%` : `${value}`;
    }
    function alertStatusText(value) {
      return {
        pending: "待处理",
        processing: "处理中",
        resolved: "已解决",
        ignored: "已忽略",
        false_positive: "误报"
      }[value] || value;
    }
    function goBack() {
      router.back();
    }
    function errorMessage(err, fallback) {
      const detail = err?.response?.data?.detail;
      return typeof detail === "string" ? detail : fallback;
    }
    async function loadData() {
      loading.value = true;
      const id = route.params.id;
      try {
        const { data } = await api.get("/foreign/events/" + id);
        event.value = { ...event.value, ...data };
        try {
          const situationResponse = await api.get(`/foreign/events/${id}/situation`);
          situation.value = situationResponse.data;
        } catch (_) {
          situation.value = null;
        }
      } catch (err) {
        ElMessage.error(errorMessage(err, "加载外网事件详情失败"));
      } finally {
        loading.value = false;
      }
    }
    onMounted(loadData);
    return (_ctx, _cache) => {
      const _component_el_tab_pane = resolveComponent("el-tab-pane");
      const _component_el_tabs = resolveComponent("el-tabs");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", { class: "detail-back" }, [
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: goBack
          }, "← 返回事件中心")
        ]),
        createBaseVNode("section", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            createBaseVNode("h2", _hoisted_4, toDisplayString(event.value.title), 1),
            createBaseVNode("span", {
              class: normalizeClass(["pill", riskPill(event.value.risk_level)])
            }, [
              _cache[4] || (_cache[4] = createBaseVNode("span", { class: "dot" }, null, -1)),
              createTextVNode(toDisplayString(riskText(event.value.risk_level)), 1)
            ], 2),
            isKeyEvent.value ? (openBlock(), createElementBlock("span", _hoisted_5, "重点关注")) : createCommentVNode("", true),
            canUpdateEvent.value ? (openBlock(), createElementBlock("button", {
              key: 1,
              class: "btn btn-primary handle-open-btn",
              onClick: _cache[0] || (_cache[0] = ($event) => handleDialogVisible.value = true)
            }, "处置")) : createCommentVNode("", true)
          ]),
          event.value.summary ? (openBlock(), createElementBlock("div", _hoisted_6, toDisplayString(event.value.summary), 1)) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_7, [
            createBaseVNode("span", null, [
              _cache[5] || (_cache[5] = createTextVNode("关联舆情：", -1)),
              createBaseVNode("b", null, toDisplayString(event.value.opinion_count), 1),
              _cache[6] || (_cache[6] = createTextVNode(" 条", -1))
            ]),
            createBaseVNode("span", null, "首次发现：" + toDisplayString(unref(formatTime)(event.value.first_seen_at)), 1),
            createBaseVNode("span", null, "最后更新：" + toDisplayString(unref(formatTime)(event.value.last_seen_at)), 1)
          ]),
          createBaseVNode("div", _hoisted_8, [
            createBaseVNode("div", _hoisted_9, [
              _cache[7] || (_cache[7] = createBaseVNode("span", { class: "situation-label" }, "处置状态", -1)),
              createBaseVNode("strong", {
                class: normalizeClass(unref(eventStatusPill)(event.value.status))
              }, toDisplayString(unref(eventStatusLabel)(event.value.status)), 3)
            ]),
            createBaseVNode("div", _hoisted_10, [
              _cache[8] || (_cache[8] = createBaseVNode("span", { class: "situation-label" }, "正式记录风险", -1)),
              createBaseVNode("strong", {
                style: normalizeStyle({ color: unref(riskColor)(event.value.formal_risk_score ?? 0) })
              }, toDisplayString(event.value.formal_risk_score ?? "-") + " 分 · " + toDisplayString(riskText(event.value.formal_risk_level || event.value.risk_level)), 5)
            ]),
            event.value.linked_opinion_current_risk ? (openBlock(), createElementBlock("div", _hoisted_11, [
              _cache[9] || (_cache[9] = createBaseVNode("span", { class: "situation-label" }, "关联舆情当前风险", -1)),
              createBaseVNode("strong", {
                style: normalizeStyle({ color: unref(riskColor)(event.value.linked_opinion_current_risk.risk_score ?? 0) })
              }, toDisplayString(event.value.linked_opinion_current_risk.risk_score ?? "-") + " 分 · " + toDisplayString(riskText(event.value.linked_opinion_current_risk.risk_level)), 5)
            ])) : createCommentVNode("", true),
            createBaseVNode("div", _hoisted_12, [
              _cache[10] || (_cache[10] = createBaseVNode("span", { class: "situation-label" }, "语种", -1)),
              createBaseVNode("strong", null, toDisplayString(languageText(event.value.language)), 1)
            ]),
            createBaseVNode("div", _hoisted_13, [
              _cache[11] || (_cache[11] = createBaseVNode("span", { class: "situation-label" }, "事件类型", -1)),
              createBaseVNode("strong", null, toDisplayString(eventTypeText(event.value.event_type)), 1)
            ]),
            createBaseVNode("div", _hoisted_14, [
              _cache[12] || (_cache[12] = createBaseVNode("span", { class: "situation-label" }, "置信度", -1)),
              createBaseVNode("strong", null, toDisplayString(confidenceText(event.value.confidence)), 1)
            ])
          ])
        ]),
        event.value.id && situation.value ? (openBlock(), createBlock(EventAnalysisStats, {
          key: 0,
          statistics: situation.value?.statistics,
          situation: situation.value?.situation
        }, null, 8, ["statistics", "situation"])) : createCommentVNode("", true),
        createVNode(EventDispositionDialog, {
          modelValue: handleDialogVisible.value,
          "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => handleDialogVisible.value = $event),
          "event-id": event.value.id,
          scope: "foreign",
          onUpdated: loadData
        }, null, 8, ["modelValue", "event-id"]),
        createBaseVNode("div", _hoisted_15, [
          createVNode(_component_el_tabs, {
            modelValue: activeRelatedTab.value,
            "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => activeRelatedTab.value = $event),
            class: "related-tabs"
          }, {
            default: withCtx(() => [
              createVNode(_component_el_tab_pane, {
                label: `关联舆情 (${event.value.opinion_count})`,
                name: "opinions"
              }, {
                default: withCtx(() => [
                  createBaseVNode("table", _hoisted_16, [
                    _cache[14] || (_cache[14] = createBaseVNode("thead", null, [
                      createBaseVNode("tr", null, [
                        createBaseVNode("th", { style: { "width": "70px" } }, "ID"),
                        createBaseVNode("th", { style: { "min-width": "280px" } }, "标题"),
                        createBaseVNode("th", { style: { "width": "160px" } }, "来源"),
                        createBaseVNode("th", {
                          style: { "width": "110px" },
                          class: "col-center"
                        }, "当前风险"),
                        createBaseVNode("th", { style: { "width": "170px" } }, "发布时间"),
                        createBaseVNode("th", {
                          style: { "width": "100px" },
                          class: "col-center"
                        }, "相似度")
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
                            createBaseVNode("span", _hoisted_18, toDisplayString(row.title), 1)
                          ]),
                          createBaseVNode("td", null, toDisplayString(row.source_name_snapshot || "-"), 1),
                          createBaseVNode("td", {
                            class: "col-center risk-num",
                            style: normalizeStyle({ color: unref(riskColor)(row.current_risk?.risk_score ?? 0) })
                          }, toDisplayString(row.current_risk?.risk_score != null ? `${row.current_risk.risk_score} · ${riskText(row.current_risk.risk_level)}` : "-"), 5),
                          createBaseVNode("td", null, toDisplayString(unref(formatTime)(row.published_at)), 1),
                          createBaseVNode("td", _hoisted_19, toDisplayString(similarityText(row.similarity_score)), 1)
                        ], 8, _hoisted_17);
                      }), 128)),
                      event.value.opinions.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_20, [..._cache[13] || (_cache[13] = [
                        createBaseVNode("td", {
                          colspan: "6",
                          class: "empty-row"
                        }, "暂无关联舆情", -1)
                      ])])) : createCommentVNode("", true)
                    ])
                  ])
                ]),
                _: 1
              }, 8, ["label"]),
              createVNode(_component_el_tab_pane, {
                label: `关联预警 (${event.value.alerts?.length || 0})`,
                name: "alerts"
              }, {
                default: withCtx(() => [
                  createBaseVNode("table", _hoisted_21, [
                    _cache[17] || (_cache[17] = createBaseVNode("thead", null, [
                      createBaseVNode("tr", null, [
                        createBaseVNode("th", { style: { "min-width": "240px" } }, "标题"),
                        createBaseVNode("th", {
                          style: { "width": "150px" },
                          class: "col-center"
                        }, "正式记录风险"),
                        createBaseVNode("th", {
                          style: { "width": "160px" },
                          class: "col-center"
                        }, "关联舆情当前风险"),
                        createBaseVNode("th", {
                          style: { "width": "110px" },
                          class: "col-center"
                        }, "状态"),
                        createBaseVNode("th", { style: { "width": "170px" } }, "时间")
                      ])
                    ], -1)),
                    createBaseVNode("tbody", null, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(event.value.alerts || [], (a) => {
                        return openBlock(), createElementBlock("tr", {
                          key: a.id
                        }, [
                          createBaseVNode("td", null, [
                            createBaseVNode("span", _hoisted_22, toDisplayString(a.title), 1)
                          ]),
                          createBaseVNode("td", _hoisted_23, [
                            createBaseVNode("span", {
                              class: normalizeClass(["pill", riskPill(a.formal_risk_level || a.risk_level)])
                            }, [
                              _cache[15] || (_cache[15] = createBaseVNode("span", { class: "dot" }, null, -1)),
                              createTextVNode(toDisplayString(a.formal_risk_score ?? "-") + " · " + toDisplayString(riskText(a.formal_risk_level || a.risk_level)), 1)
                            ], 2)
                          ]),
                          createBaseVNode("td", _hoisted_24, toDisplayString(a.linked_opinion_current_risk ? `${a.linked_opinion_current_risk.risk_score ?? "-"} · ${riskText(a.linked_opinion_current_risk.risk_level)}` : "-"), 1),
                          createBaseVNode("td", _hoisted_25, toDisplayString(alertStatusText(a.status)), 1),
                          createBaseVNode("td", null, toDisplayString(unref(formatTime)(a.created_at)), 1)
                        ]);
                      }), 128)),
                      (event.value.alerts?.length || 0) === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_26, [..._cache[16] || (_cache[16] = [
                        createBaseVNode("td", {
                          colspan: "5",
                          class: "empty-row"
                        }, "暂无关联预警", -1)
                      ])])) : createCommentVNode("", true)
                    ])
                  ])
                ]),
                _: 1
              }, 8, ["label"])
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        createVNode(ForeignOpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const ForeignEventDetail = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-316c0ef9"]]);

export { ForeignEventDetail as default };
