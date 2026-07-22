import { d as defineComponent, m as watch, p as onMounted, L as onUnmounted, y as createBlock, c as createElementBlock, I as withModifiers, a as createBaseVNode, t as toDisplayString, A as createCommentVNode, w as withDirectives, x as unref, F as Fragment, i as renderList, n as normalizeClass, e as createTextVNode, k as normalizeStyle, T as Teleport, r as ref, j as computed, g as api, E as ElMessage, C as resolveComponent, D as resolveDirective, o as openBlock, _ as _export_sfc } from './index-BPeYYIlC.js';

function riskColor(score) {
  if (score >= 70) return "#ff3b30";
  if (score >= 40) return "#ff9f0a";
  return "#34c759";
}
function levelPill(score) {
  if (score >= 70) return "pill-red";
  if (score >= 40) return "pill-orange";
  return "pill-green";
}
function levelText(score) {
  if (score >= 70) return "高危";
  if (score >= 40) return "中危";
  return "低危";
}
function sentimentPill(s) {
  return { negative: "pill-red", positive: "pill-green", neutral: "pill-gray" }[s] || "pill-gray";
}
function sentimentText(s) {
  return { negative: "负面", positive: "正面", neutral: "中性" }[s] || s;
}
function statusPill(s) {
  return { completed: "pill-green", failed: "pill-red", processing: "pill-orange", pending: "pill-gray" }[s] || "pill-gray";
}
function statusText(s) {
  return { completed: "已完成", failed: "失败", processing: "分析中", pending: "待分析" }[s] || s;
}
function formatTime(t) {
  if (!t) return "-";
  return t.replace("T", " ").slice(0, 19);
}

const _hoisted_1 = { class: "modal-card" };
const _hoisted_2 = { class: "modal-header" };
const _hoisted_3 = { class: "modal-title-wrap" };
const _hoisted_4 = { class: "modal-title" };
const _hoisted_5 = { class: "modal-header-right" };
const _hoisted_6 = ["href"];
const _hoisted_7 = { class: "modal-body" };
const _hoisted_8 = {
  key: 0,
  class: "detail-grid"
};
const _hoisted_9 = { class: "card card-pad" };
const _hoisted_10 = { class: "detail-meta" };
const _hoisted_11 = {
  class: "detail-content",
  "element-loading-text": "正在抓取来源页原文…"
};
const _hoisted_12 = { key: 1 };
const _hoisted_13 = {
  key: 2,
  class: "orig-empty"
};
const _hoisted_14 = {
  key: 0,
  class: "detail-foot-note"
};
const _hoisted_15 = { class: "detail-right" };
const _hoisted_16 = { class: "card card-pad sys-card" };
const _hoisted_17 = { class: "ai-header" };
const _hoisted_18 = { class: "report-meta" };
const _hoisted_19 = { class: "meta-item" };
const _hoisted_20 = { class: "meta-item" };
const _hoisted_21 = { class: "meta-item" };
const _hoisted_22 = { class: "report-body" };
const _hoisted_23 = {
  key: 0,
  class: "report-p"
};
const _hoisted_24 = {
  key: 1,
  class: "report-p report-muted"
};
const _hoisted_25 = {
  key: 2,
  class: "report-p"
};
const _hoisted_26 = {
  key: 0,
  class: "report-keywords"
};
const _hoisted_27 = {
  key: 1,
  class: "report-time"
};
const _hoisted_28 = { class: "card card-pad ai-card" };
const _hoisted_29 = { class: "ai-header" };
const _hoisted_30 = { class: "report-meta" };
const _hoisted_31 = { class: "meta-item" };
const _hoisted_32 = { class: "meta-item" };
const _hoisted_33 = { class: "meta-item" };
const _hoisted_34 = { class: "report-body" };
const _hoisted_35 = {
  key: 0,
  class: "report-p"
};
const _hoisted_36 = {
  key: 1,
  class: "report-p"
};
const _hoisted_37 = {
  key: 1,
  class: "report-p report-muted"
};
const _hoisted_38 = {
  key: 2,
  class: "report-p report-muted"
};
const _hoisted_39 = {
  key: 0,
  class: "report-keywords"
};
const _hoisted_40 = {
  key: 1,
  class: "report-time"
};
const _hoisted_41 = { class: "ai-actions" };
const _hoisted_42 = ["disabled"];
const _hoisted_43 = {
  key: 1,
  class: "ai-status-line"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "OpinionDetailModal",
  props: {
    modelValue: { type: Boolean },
    opinionId: { default: null }
  },
  emits: ["update:modelValue"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const detailLoading = ref(false);
    const originalLoading = ref(false);
    const analyzing = ref(false);
    const detail = ref(null);
    const originalParas = ref([]);
    const originalFetched = ref(false);
    const keywordList = computed(
      () => (detail.value?.keywords || "").split(",").map((k) => k.trim()).filter(Boolean)
    );
    const aiKeywordList = computed(
      () => (detail.value?.ai_keywords || "").split(",").map((k) => k.trim()).filter(Boolean)
    );
    async function openDetail(id) {
      detailLoading.value = true;
      originalLoading.value = true;
      detail.value = null;
      originalParas.value = [];
      originalFetched.value = false;
      try {
        const { data } = await api.get("/opinions/" + id);
        detail.value = data;
      } catch (err) {
        if (err?.response?.status === 404) {
          detail.value = null;
        } else {
          ElMessage.error(err?.response?.data?.detail || "加载详情失败");
        }
      } finally {
        detailLoading.value = false;
      }
      try {
        const { data } = await api.get("/opinions/" + id + "/original");
        originalParas.value = Array.isArray(data.original) ? data.original : [];
        originalFetched.value = true;
      } catch {
        originalFetched.value = true;
      } finally {
        originalLoading.value = false;
      }
    }
    function close() {
      emit("update:modelValue", false);
    }
    async function triggerAnalyze() {
      if (analyzing.value || !detail.value) return;
      const id = detail.value.id;
      analyzing.value = true;
      try {
        const { data } = await api.post("/analyze/" + id);
        detail.value = data;
        ElMessage.success("AI 分析完成");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "AI 分析失败，请稍后重试");
        openDetail(id);
      } finally {
        analyzing.value = false;
      }
    }
    function onKeydown(e) {
      if (e.key === "Escape" && props.modelValue) close();
    }
    watch(
      () => [props.modelValue, props.opinionId],
      ([visible, id]) => {
        if (visible && id != null) openDetail(id);
      }
    );
    onMounted(() => window.addEventListener("keydown", onKeydown));
    onUnmounted(() => window.removeEventListener("keydown", onKeydown));
    return (_ctx, _cache) => {
      const _component_el_empty = resolveComponent("el-empty");
      const _directive_loading = resolveDirective("loading");
      return openBlock(), createBlock(Teleport, { to: "body" }, [
        __props.modelValue ? (openBlock(), createElementBlock("div", {
          key: 0,
          class: "modal-mask",
          onClick: withModifiers(close, ["self"])
        }, [
          createBaseVNode("div", _hoisted_1, [
            createBaseVNode("div", _hoisted_2, [
              createBaseVNode("div", _hoisted_3, [
                _cache[0] || (_cache[0] = createBaseVNode("span", { class: "modal-kicker" }, "舆情详情与 AI 分析", -1)),
                createBaseVNode("h3", _hoisted_4, toDisplayString(detail.value?.title || "加载中…"), 1)
              ]),
              createBaseVNode("div", _hoisted_5, [
                detail.value?.url ? (openBlock(), createElementBlock("a", {
                  key: 0,
                  class: "jump-link",
                  href: detail.value.url,
                  target: "_blank",
                  rel: "noopener"
                }, "🔗 跳转原文", 8, _hoisted_6)) : createCommentVNode("", true),
                createBaseVNode("button", {
                  class: "modal-close",
                  title: "关闭",
                  onClick: close
                }, "✕")
              ])
            ]),
            withDirectives((openBlock(), createElementBlock("div", _hoisted_7, [
              detail.value ? (openBlock(), createElementBlock("div", _hoisted_8, [
                createBaseVNode("div", _hoisted_9, [
                  createBaseVNode("div", _hoisted_10, [
                    createBaseVNode("span", null, "来源：" + toDisplayString(detail.value.source), 1),
                    createBaseVNode("span", null, "发布时间：" + toDisplayString(unref(formatTime)(detail.value.publish_time)), 1)
                  ]),
                  _cache[1] || (_cache[1] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                  withDirectives((openBlock(), createElementBlock("div", _hoisted_11, [
                    originalParas.value.length ? (openBlock(true), createElementBlock(Fragment, { key: 0 }, renderList(originalParas.value, (p, i) => {
                      return openBlock(), createElementBlock("p", {
                        key: i,
                        class: "orig-p"
                      }, toDisplayString(p), 1);
                    }), 128)) : detail.value.content && !originalLoading.value ? (openBlock(), createElementBlock("p", _hoisted_12, toDisplayString(detail.value.content), 1)) : !originalLoading.value ? (openBlock(), createElementBlock("p", _hoisted_13, "暂无原文内容。")) : createCommentVNode("", true)
                  ])), [
                    [_directive_loading, originalLoading.value]
                  ]),
                  originalFetched.value && !originalParas.value.length && detail.value.content ? (openBlock(), createElementBlock("div", _hoisted_14, " 来源页暂无可抓取正文，已显示摘要。 ")) : createCommentVNode("", true)
                ]),
                createBaseVNode("div", _hoisted_15, [
                  createBaseVNode("div", _hoisted_16, [
                    createBaseVNode("div", _hoisted_17, [
                      _cache[2] || (_cache[2] = createBaseVNode("span", { class: "section-title" }, "系统研判报告", -1)),
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(statusPill)(detail.value.analysis_status)])
                      }, toDisplayString(unref(statusText)(detail.value.analysis_status)), 3)
                    ]),
                    _cache[9] || (_cache[9] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                    createBaseVNode("div", _hoisted_18, [
                      createBaseVNode("span", _hoisted_19, [
                        _cache[3] || (_cache[3] = createTextVNode("风险评分 ", -1)),
                        createBaseVNode("b", {
                          style: normalizeStyle({ color: unref(riskColor)(detail.value.risk_score) })
                        }, toDisplayString(detail.value.risk_score), 5)
                      ]),
                      _cache[6] || (_cache[6] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                      createBaseVNode("span", _hoisted_20, [
                        _cache[4] || (_cache[4] = createTextVNode("级别 ", -1)),
                        createBaseVNode("b", null, toDisplayString(unref(levelText)(detail.value.risk_score)), 1)
                      ]),
                      _cache[7] || (_cache[7] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                      createBaseVNode("span", _hoisted_21, [
                        _cache[5] || (_cache[5] = createTextVNode("情感 ", -1)),
                        createBaseVNode("b", null, toDisplayString(unref(sentimentText)(detail.value.sentiment)), 1)
                      ])
                    ]),
                    createBaseVNode("div", _hoisted_22, [
                      detail.value.summary ? (openBlock(), createElementBlock("p", _hoisted_23, toDisplayString(detail.value.summary), 1)) : (openBlock(), createElementBlock("p", _hoisted_24, "暂无系统研判摘要。")),
                      detail.value.analysis_suggestion ? (openBlock(), createElementBlock("p", _hoisted_25, toDisplayString(detail.value.analysis_suggestion), 1)) : createCommentVNode("", true)
                    ]),
                    keywordList.value.length ? (openBlock(), createElementBlock("div", _hoisted_26, [
                      _cache[8] || (_cache[8] = createBaseVNode("span", { class: "kw-label" }, "关键词", -1)),
                      (openBlock(true), createElementBlock(Fragment, null, renderList(keywordList.value, (k) => {
                        return openBlock(), createElementBlock("span", {
                          key: k,
                          class: "kw-tag"
                        }, toDisplayString(k), 1);
                      }), 128))
                    ])) : createCommentVNode("", true),
                    detail.value.analysis_time ? (openBlock(), createElementBlock("div", _hoisted_27, " 分析时间：" + toDisplayString(unref(formatTime)(detail.value.analysis_time)), 1)) : createCommentVNode("", true)
                  ]),
                  createBaseVNode("div", _hoisted_28, [
                    createBaseVNode("div", _hoisted_29, [
                      _cache[10] || (_cache[10] = createBaseVNode("span", { class: "section-title" }, "AI 研判报告", -1)),
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(statusPill)(detail.value.ai_analysis_status)])
                      }, toDisplayString(unref(statusText)(detail.value.ai_analysis_status)), 3)
                    ]),
                    _cache[18] || (_cache[18] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                    createBaseVNode("div", _hoisted_30, [
                      createBaseVNode("span", _hoisted_31, [
                        _cache[11] || (_cache[11] = createTextVNode("风险评分 ", -1)),
                        createBaseVNode("b", {
                          style: normalizeStyle({ color: unref(riskColor)(detail.value.ai_risk_score ?? 0) })
                        }, toDisplayString(detail.value.ai_risk_score ?? 0), 5)
                      ]),
                      _cache[14] || (_cache[14] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                      createBaseVNode("span", _hoisted_32, [
                        _cache[12] || (_cache[12] = createTextVNode("级别 ", -1)),
                        createBaseVNode("b", null, toDisplayString(unref(levelText)(detail.value.ai_risk_score ?? 0)), 1)
                      ]),
                      _cache[15] || (_cache[15] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                      createBaseVNode("span", _hoisted_33, [
                        _cache[13] || (_cache[13] = createTextVNode("情感 ", -1)),
                        createBaseVNode("b", null, toDisplayString(unref(sentimentText)(detail.value.ai_sentiment)), 1)
                      ])
                    ]),
                    createBaseVNode("div", _hoisted_34, [
                      detail.value.ai_analysis_status === "completed" ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                        detail.value.ai_summary ? (openBlock(), createElementBlock("p", _hoisted_35, toDisplayString(detail.value.ai_summary), 1)) : createCommentVNode("", true),
                        detail.value.ai_analysis_suggestion ? (openBlock(), createElementBlock("p", _hoisted_36, toDisplayString(detail.value.ai_analysis_suggestion), 1)) : createCommentVNode("", true)
                      ], 64)) : detail.value.ai_analysis_status === "failed" ? (openBlock(), createElementBlock("p", _hoisted_37, " AI 分析失败（DeepSeek 未配置或余额不足），请稍后重试。 ")) : (openBlock(), createElementBlock("p", _hoisted_38, " 尚未生成 AI 研判报告，点击下方按钮由 DeepSeek 生成。 "))
                    ]),
                    aiKeywordList.value.length ? (openBlock(), createElementBlock("div", _hoisted_39, [
                      _cache[16] || (_cache[16] = createBaseVNode("span", { class: "kw-label" }, "关键词", -1)),
                      (openBlock(true), createElementBlock(Fragment, null, renderList(aiKeywordList.value, (k) => {
                        return openBlock(), createElementBlock("span", {
                          key: k,
                          class: "kw-tag"
                        }, toDisplayString(k), 1);
                      }), 128))
                    ])) : createCommentVNode("", true),
                    detail.value.ai_analysis_time ? (openBlock(), createElementBlock("div", _hoisted_40, " 分析时间：" + toDisplayString(unref(formatTime)(detail.value.ai_analysis_time)), 1)) : createCommentVNode("", true),
                    _cache[19] || (_cache[19] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                    createBaseVNode("div", _hoisted_41, [
                      detail.value.ai_analysis_status !== "processing" ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "btn btn-primary btn-block",
                        disabled: analyzing.value,
                        onClick: triggerAnalyze
                      }, toDisplayString(analyzing.value ? "分析中..." : detail.value.ai_analysis_status === "completed" ? "重新触发 AI 分析" : "触发 AI 分析"), 9, _hoisted_42)) : (openBlock(), createElementBlock("div", _hoisted_43, [..._cache[17] || (_cache[17] = [
                        createBaseVNode("span", { class: "spinner" }, null, -1),
                        createBaseVNode("span", { class: "ai-text" }, "AI 分析进行中...", -1)
                      ])]))
                    ])
                  ])
                ])
              ])) : (openBlock(), createBlock(_component_el_empty, {
                key: 1,
                description: "未找到该舆情"
              }))
            ])), [
              [_directive_loading, detailLoading.value]
            ])
          ])
        ])) : createCommentVNode("", true)
      ]);
    };
  }
});

const OpinionDetailModal = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-1258033a"]]);

export { OpinionDetailModal as O, sentimentText as a, levelText as b, statusPill as c, statusText as d, formatTime as f, levelPill as l, riskColor as r, sentimentPill as s };
