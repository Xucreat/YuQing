import { d as defineComponent, z as usePermission, r as ref, A as watch, q as createBlock, c as createElementBlock, L as withModifiers, a as createBaseVNode, t as toDisplayString, s as createCommentVNode, w as withDirectives, F as Fragment, n as normalizeClass, H as unref, i as renderList, e as createTextVNode, k as normalizeStyle, T as Teleport, j as computed, g as api, E as ElMessage, y as resolveComponent, B as resolveDirective, o as openBlock, _ as _export_sfc, C as onMounted, G as onBeforeUnmount, J as vModelSelect, O as vShow, b as withKeys, v as vModelText, P as createStaticVNode, m as createVNode, Q as _sfc_main$2, p as withCtx, N as useRoute, f as reactive, M as ElMessageBox, R as pollTask, D as nextTick, K as vModelCheckbox, h as useRouter } from './index-BTuLLqEP.js';
import { i as init, L as LinearGradient } from './index-F2TANFn2.js';
import './wordCloud-DTX2zCb6.js';
import { f as formatTime, r as riskColor, c as statusPill, d as statusText, a as sentimentText } from './opinion-Cag9WtuS.js';

const _hoisted_1$1 = { class: "modal-card" };
const _hoisted_2$1 = { class: "modal-header" };
const _hoisted_3$1 = { class: "modal-title-wrap" };
const _hoisted_4$1 = { class: "modal-title" };
const _hoisted_5$1 = { class: "modal-header-right" };
const _hoisted_6$1 = ["href"];
const _hoisted_7$1 = { class: "modal-body" };
const _hoisted_8$1 = {
  class: "risk-view-switch",
  role: "group",
  "aria-label": "risk view source"
};
const _hoisted_9$1 = { class: "detail-grid" };
const _hoisted_10$1 = { class: "card card-pad" };
const _hoisted_11$1 = { class: "detail-meta" };
const _hoisted_12$1 = { class: "detail-content" };
const _hoisted_13$1 = {
  key: 0,
  class: "kw-line"
};
const _hoisted_14$1 = {
  key: 1,
  class: "orig-p"
};
const _hoisted_15$1 = {
  key: 2,
  class: "orig-p"
};
const _hoisted_16$1 = {
  key: 3,
  class: "orig-empty"
};
const _hoisted_17$1 = { class: "detail-right" };
const _hoisted_18$1 = { class: "card card-pad eff-card" };
const _hoisted_19$1 = { class: "ai-header" };
const _hoisted_20$1 = { class: "report-meta" };
const _hoisted_21$1 = { class: "meta-item" };
const _hoisted_22$1 = { class: "meta-item" };
const _hoisted_23$1 = {
  key: 0,
  class: "meta-sep"
};
const _hoisted_24$1 = {
  key: 1,
  class: "meta-item"
};
const _hoisted_25$1 = { class: "report-body" };
const _hoisted_26$1 = { class: "report-p report-muted" };
const _hoisted_27$1 = {
  key: 0,
  class: "dual-row"
};
const _hoisted_28$1 = { class: "dual-val" };
const _hoisted_29$1 = {
  key: 0,
  class: "dual-sub"
};
const _hoisted_30$1 = {
  key: 1,
  class: "dual-row"
};
const _hoisted_31$1 = { class: "dual-val" };
const _hoisted_32$1 = {
  key: 2,
  class: "dual-row"
};
const _hoisted_33$1 = { class: "dual-val" };
const _hoisted_34$1 = {
  key: 0,
  class: "dual-sub"
};
const _hoisted_35$1 = { class: "card card-pad sys-card" };
const _hoisted_36$1 = { class: "ai-header" };
const _hoisted_37$1 = { class: "report-meta" };
const _hoisted_38$1 = { class: "meta-item" };
const _hoisted_39$1 = { class: "meta-item" };
const _hoisted_40$1 = { class: "meta-item" };
const _hoisted_41$1 = { class: "report-body" };
const _hoisted_42$1 = {
  key: 0,
  class: "report-p"
};
const _hoisted_43$1 = {
  key: 1,
  class: "report-p report-muted"
};
const _hoisted_44$1 = {
  key: 0,
  class: "report-keywords"
};
const _hoisted_45$1 = { class: "card card-pad ai-card" };
const _hoisted_46$1 = { class: "ai-header" };
const _hoisted_47$1 = { class: "ai-header-tools" };
const _hoisted_48$1 = { class: "report-meta" };
const _hoisted_49$1 = { class: "meta-item" };
const _hoisted_50$1 = { class: "meta-item" };
const _hoisted_51$1 = { class: "meta-item" };
const _hoisted_52$1 = { class: "report-body" };
const _hoisted_53$1 = {
  key: 0,
  class: "report-p"
};
const _hoisted_54$1 = {
  key: 1,
  class: "report-p"
};
const _hoisted_55$1 = {
  key: 1,
  class: "report-p report-muted"
};
const _hoisted_56$1 = {
  key: 2,
  class: "report-p report-muted"
};
const _hoisted_57$1 = {
  key: 0,
  class: "ai-actions"
};
const _hoisted_58$1 = ["disabled"];
const _hoisted_59$1 = { class: "modal-card history-modal" };
const _hoisted_60$1 = { class: "modal-header" };
const _hoisted_61$1 = { class: "modal-body" };
const _hoisted_62$1 = {
  key: 0,
  class: "history-list"
};
const _hoisted_63$1 = { class: "error-cell" };
const _sfc_main$1 = /* @__PURE__ */ defineComponent({
  __name: "ForeignOpinionDetailModal",
  props: {
    modelValue: { type: Boolean },
    opinionId: { default: null },
    riskSource: { default: "rule" }
  },
  emits: ["update:modelValue", "update:riskSource"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const { hasPermission } = usePermission();
    const canAnalyzeAI = computed(() => hasPermission("foreign:ai:analyze"));
    const detailLoading = ref(false);
    const analyzing = ref(false);
    const showHistoryModal = ref(false);
    const detail = ref(null);
    const viewSource = ref(props.riskSource);
    function setViewSource(value) {
      viewSource.value = value;
      window.localStorage.setItem("foreign-risk-source", value);
      emit("update:riskSource", value);
      if (detail.value?.id != null) openDetail(detail.value.id);
    }
    const ruleTermHits = computed(
      () => (detail.value?.rule_result?.matched_terms || []).map((t) => t.word)
    );
    const effectiveRisk = computed(() => detail.value?.effective_risk || null);
    const effectiveRiskReason = computed(() => effectiveRisk.value?.reason || "rule_baseline");
    const effectiveRiskReasonText = computed(() => {
      switch (effectiveRiskReason.value) {
        case "not_analyzed":
          return "未评估";
        default:
          return "规则基线";
      }
    });
    const displayRisk = computed(() => detail.value?.display_risk || effectiveRisk.value || null);
    const displayRiskScore = computed(() => displayRisk.value?.risk_score ?? null);
    const displayRiskLevel = computed(() => displayRisk.value?.risk_level || "unknown");
    const displayRiskSource = computed(() => displayRisk.value?.source || "rule");
    const displayRiskSourceLabel = computed(() => displayRiskSource.value === "ai" ? "AI 研判" : "系统规则");
    const displayRiskDesc = computed(() => {
      if (displayRisk.value?.fallback) return "暂无已完成的 AI 研判，当前回退显示系统规则风险。";
      return displayRiskSource.value === "ai" ? "AI 研判结果仅用于辅助分析，不改变系统正式风险和告警。" : "系统规则研判是正式风险和告警的依据。";
    });
    function alertStatusText(status) {
      switch (status) {
        case "triggered":
          return "已触发";
        case "acknowledged":
          return "已确认";
        case "resolved":
          return "已解除";
        case "suppressed":
          return "已抑制";
        case "failed":
          return "已失败";
        default:
          return status || "未知";
      }
    }
    function riskLevelZh(level) {
      switch (level) {
        case "high":
          return "高危";
        case "medium":
          return "中危";
        case "low":
          return "低危";
        case "unknown":
          return "未知";
        default:
          return level || "未知";
      }
    }
    function decodeHtml(input) {
      if (!input) return input;
      try {
        const doc = new DOMParser().parseFromString(input, "text/html");
        return doc.body.textContent || "";
      } catch {
        return input;
      }
    }
    function sanitizeDetail(d) {
      if (d.title) d.title = decodeHtml(d.title);
      if (d.summary) d.summary = decodeHtml(d.summary);
      if (d.content) d.content = decodeHtml(d.content);
      if (d.rule_result?.explanation) d.rule_result.explanation = decodeHtml(d.rule_result.explanation);
      if (d.ai_result?.summary) d.ai_result.summary = decodeHtml(d.ai_result.summary);
      if (d.ai_result?.suggestion) d.ai_result.suggestion = decodeHtml(d.ai_result.suggestion);
      if (d.ai_result?.error_message) d.ai_result.error_message = decodeHtml(d.ai_result.error_message);
      return d;
    }
    async function openDetail(id) {
      detailLoading.value = true;
      detail.value = null;
      try {
        const { data } = await api.get("/foreign/opinions/" + id + "/detail", { params: { risk_source: viewSource.value } });
        detail.value = sanitizeDetail(data);
      } catch (err) {
        if (err?.response?.status !== 404) ElMessage.error(err?.response?.data?.detail || "外网舆情详情加载失败");
      } finally {
        detailLoading.value = false;
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
        await api.post("/foreign/opinions/" + id + "/ai-analyze", {});
        const { data } = await api.get("/foreign/opinions/" + id + "/detail", { params: { risk_source: viewSource.value } });
        detail.value = sanitizeDetail(data);
        ElMessage.success("AI 分析完成");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "AI 分析失败");
      } finally {
        analyzing.value = false;
      }
    }
    watch(
      () => [props.modelValue, props.opinionId],
      ([visible, id]) => {
        viewSource.value = props.riskSource;
        if (visible && id != null) openDetail(id);
      }
    );
    return (_ctx, _cache) => {
      const _component_el_empty = resolveComponent("el-empty");
      const _directive_loading = resolveDirective("loading");
      return openBlock(), createBlock(Teleport, { to: "body" }, [
        __props.modelValue ? (openBlock(), createElementBlock("div", {
          key: 0,
          class: "modal-mask",
          onClick: withModifiers(close, ["self"])
        }, [
          createBaseVNode("div", _hoisted_1$1, [
            createBaseVNode("div", _hoisted_2$1, [
              createBaseVNode("div", _hoisted_3$1, [
                _cache[5] || (_cache[5] = createBaseVNode("span", { class: "modal-kicker" }, "外网舆情详情与 AI 分析", -1)),
                createBaseVNode("h3", _hoisted_4$1, toDisplayString(detail.value?.title || "加载中…"), 1)
              ]),
              createBaseVNode("div", _hoisted_5$1, [
                detail.value?.url ? (openBlock(), createElementBlock("a", {
                  key: 0,
                  class: "jump-link",
                  href: detail.value.url,
                  target: "_blank",
                  rel: "noopener"
                }, "🔗 跳转原文", 8, _hoisted_6$1)) : createCommentVNode("", true),
                createBaseVNode("button", {
                  class: "modal-close",
                  title: "关闭",
                  onClick: close
                }, "✕")
              ])
            ]),
            withDirectives((openBlock(), createElementBlock("div", _hoisted_7$1, [
              detail.value ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                createBaseVNode("div", _hoisted_8$1, [
                  _cache[6] || (_cache[6] = createBaseVNode("span", { class: "muted" }, "当前查看口径", -1)),
                  createBaseVNode("button", {
                    type: "button",
                    class: normalizeClass(["btn btn-secondary btn-sm", { active: viewSource.value === "rule" }]),
                    onClick: _cache[0] || (_cache[0] = ($event) => setViewSource("rule"))
                  }, "系统规则", 2),
                  createBaseVNode("button", {
                    type: "button",
                    class: normalizeClass(["btn btn-secondary btn-sm", { active: viewSource.value === "ai" }]),
                    onClick: _cache[1] || (_cache[1] = ($event) => setViewSource("ai"))
                  }, "AI 研判", 2)
                ]),
                createBaseVNode("div", _hoisted_9$1, [
                  createBaseVNode("div", _hoisted_10$1, [
                    createBaseVNode("div", _hoisted_11$1, [
                      createBaseVNode("span", null, "来源：" + toDisplayString(detail.value.source_name_snapshot || "-"), 1),
                      createBaseVNode("span", null, "发布时间：" + toDisplayString(unref(formatTime)(detail.value.published_at)), 1),
                      createBaseVNode("span", null, "采集时间：" + toDisplayString(unref(formatTime)(detail.value.collected_at)), 1)
                    ]),
                    _cache[8] || (_cache[8] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                    createBaseVNode("div", _hoisted_12$1, [
                      detail.value.matched_keywords && detail.value.matched_keywords.length ? (openBlock(), createElementBlock("p", _hoisted_13$1, [
                        _cache[7] || (_cache[7] = createBaseVNode("span", { class: "kw-label" }, "命中关键词", -1)),
                        (openBlock(true), createElementBlock(Fragment, null, renderList(detail.value.matched_keywords, (k) => {
                          return openBlock(), createElementBlock("span", {
                            key: k,
                            class: "kw-tag"
                          }, toDisplayString(k), 1);
                        }), 128))
                      ])) : createCommentVNode("", true),
                      detail.value.summary && detail.value.summary !== detail.value.content ? (openBlock(), createElementBlock("p", _hoisted_14$1, toDisplayString(detail.value.summary), 1)) : createCommentVNode("", true),
                      detail.value.content ? (openBlock(), createElementBlock("p", _hoisted_15$1, toDisplayString(detail.value.content), 1)) : !detail.value.content && !detail.value.summary ? (openBlock(), createElementBlock("p", _hoisted_16$1, "暂无摘要与正文（正文抓取已关闭）。")) : createCommentVNode("", true)
                    ])
                  ]),
                  createBaseVNode("div", _hoisted_17$1, [
                    createBaseVNode("div", _hoisted_18$1, [
                      createBaseVNode("div", _hoisted_19$1, [
                        _cache[9] || (_cache[9] = createBaseVNode("span", { class: "section-title" }, "当前查看风险", -1)),
                        createBaseVNode("span", {
                          class: normalizeClass(["src-tag", displayRiskSource.value === "ai" ? "src-tag-ai" : "src-tag-rule"])
                        }, toDisplayString(displayRiskSourceLabel.value), 3)
                      ]),
                      _cache[18] || (_cache[18] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                      createBaseVNode("div", _hoisted_20$1, [
                        createBaseVNode("span", _hoisted_21$1, [
                          _cache[10] || (_cache[10] = createTextVNode("风险评分 ", -1)),
                          createBaseVNode("b", {
                            style: normalizeStyle({ color: unref(riskColor)(displayRiskScore.value ?? 0) })
                          }, toDisplayString(displayRiskScore.value ?? "-"), 5)
                        ]),
                        _cache[13] || (_cache[13] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_22$1, [
                          _cache[11] || (_cache[11] = createTextVNode("等级 ", -1)),
                          createBaseVNode("b", null, toDisplayString(riskLevelZh(displayRiskLevel.value)), 1)
                        ]),
                        effectiveRiskReason.value ? (openBlock(), createElementBlock("span", _hoisted_23$1, "·")) : createCommentVNode("", true),
                        effectiveRiskReason.value ? (openBlock(), createElementBlock("span", _hoisted_24$1, [
                          _cache[12] || (_cache[12] = createTextVNode("依据 ", -1)),
                          createBaseVNode("b", null, toDisplayString(effectiveRiskReasonText.value), 1)
                        ])) : createCommentVNode("", true)
                      ]),
                      createBaseVNode("div", _hoisted_25$1, [
                        createBaseVNode("p", _hoisted_26$1, toDisplayString(displayRiskDesc.value), 1)
                      ]),
                      detail.value.rule_risk ? (openBlock(), createElementBlock("div", _hoisted_27$1, [
                        _cache[14] || (_cache[14] = createBaseVNode("span", { class: "dual-label" }, "规则基线", -1)),
                        createBaseVNode("span", _hoisted_28$1, [
                          createTextVNode(toDisplayString(detail.value.rule_risk.risk_score ?? "-") + " / " + toDisplayString(riskLevelZh(detail.value.rule_risk.risk_level)) + " ", 1),
                          detail.value.rule_risk.risk_category ? (openBlock(), createElementBlock("span", _hoisted_29$1, "· " + toDisplayString(detail.value.rule_risk.risk_category), 1)) : createCommentVNode("", true)
                        ])
                      ])) : createCommentVNode("", true),
                      detail.value.latest_ai_risk ? (openBlock(), createElementBlock("div", _hoisted_30$1, [
                        _cache[16] || (_cache[16] = createBaseVNode("span", { class: "dual-label" }, "AI 研判", -1)),
                        createBaseVNode("span", _hoisted_31$1, [
                          createTextVNode(toDisplayString(detail.value.latest_ai_risk.risk_score ?? "-") + " / " + toDisplayString(riskLevelZh(detail.value.latest_ai_risk.risk_level)) + " ", 1),
                          _cache[15] || (_cache[15] = createBaseVNode("span", { class: "dual-flag flag-off" }, "仅历史", -1))
                        ])
                      ])) : createCommentVNode("", true),
                      detail.value.alert ? (openBlock(), createElementBlock("div", _hoisted_32$1, [
                        _cache[17] || (_cache[17] = createBaseVNode("span", { class: "dual-label" }, "关联告警", -1)),
                        createBaseVNode("span", _hoisted_33$1, [
                          createTextVNode(" #" + toDisplayString(detail.value.alert.id) + " · " + toDisplayString(alertStatusText(detail.value.alert.status)) + " ", 1),
                          createBaseVNode("span", {
                            class: normalizeClass(["dual-flag", detail.value.alert.is_active ? "flag-on" : "flag-off"])
                          }, toDisplayString(detail.value.alert.is_active ? "生效中" : "已结束"), 3),
                          detail.value.alert.expires_at ? (openBlock(), createElementBlock("span", _hoisted_34$1, " · 有效期至 " + toDisplayString(unref(formatTime)(detail.value.alert.expires_at)), 1)) : createCommentVNode("", true)
                        ])
                      ])) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("div", _hoisted_35$1, [
                      createBaseVNode("div", _hoisted_36$1, [
                        _cache[19] || (_cache[19] = createBaseVNode("span", { class: "section-title" }, "系统规则研判", -1)),
                        createBaseVNode("span", {
                          class: normalizeClass(["pill", unref(statusPill)(detail.value.rule_result?.analysis_status || "pending")])
                        }, toDisplayString(unref(statusText)(detail.value.rule_result?.analysis_status || "pending")), 3)
                      ]),
                      _cache[26] || (_cache[26] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                      createBaseVNode("div", _hoisted_37$1, [
                        createBaseVNode("span", _hoisted_38$1, [
                          _cache[20] || (_cache[20] = createTextVNode("风险评分 ", -1)),
                          createBaseVNode("b", {
                            style: normalizeStyle({ color: unref(riskColor)(detail.value.rule_result?.risk_score ?? 0) })
                          }, toDisplayString(detail.value.rule_result?.risk_score ?? "-"), 5)
                        ]),
                        _cache[23] || (_cache[23] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_39$1, [
                          _cache[21] || (_cache[21] = createTextVNode("等级 ", -1)),
                          createBaseVNode("b", null, toDisplayString(riskLevelZh(detail.value.rule_result?.risk_level)), 1)
                        ]),
                        _cache[24] || (_cache[24] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_40$1, [
                          _cache[22] || (_cache[22] = createTextVNode("风险类别 ", -1)),
                          createBaseVNode("b", null, toDisplayString(detail.value.rule_result?.risk_category || "-"), 1)
                        ])
                      ]),
                      createBaseVNode("div", _hoisted_41$1, [
                        detail.value.rule_result?.explanation ? (openBlock(), createElementBlock("p", _hoisted_42$1, toDisplayString(detail.value.rule_result.explanation), 1)) : (openBlock(), createElementBlock("p", _hoisted_43$1, "暂无规则研判解释。"))
                      ]),
                      ruleTermHits.value.length ? (openBlock(), createElementBlock("div", _hoisted_44$1, [
                        _cache[25] || (_cache[25] = createBaseVNode("span", { class: "kw-label" }, "命中风险词", -1)),
                        (openBlock(true), createElementBlock(Fragment, null, renderList(ruleTermHits.value, (h) => {
                          return openBlock(), createElementBlock("span", {
                            key: h,
                            class: "re-hit-tag"
                          }, toDisplayString(h), 1);
                        }), 128))
                      ])) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("div", _hoisted_45$1, [
                      createBaseVNode("div", _hoisted_46$1, [
                        _cache[27] || (_cache[27] = createBaseVNode("span", { class: "section-title" }, "AI 研判记录（历史）", -1)),
                        createBaseVNode("div", _hoisted_47$1, [
                          createBaseVNode("span", {
                            class: normalizeClass(["pill", unref(statusPill)(detail.value.ai_result?.status || "pending")])
                          }, toDisplayString(unref(statusText)(detail.value.ai_result?.status || "pending")), 3),
                          detail.value.analysis_runs && detail.value.analysis_runs.length ? (openBlock(), createElementBlock("button", {
                            key: 0,
                            class: "btn btn-secondary btn-sm",
                            onClick: _cache[2] || (_cache[2] = ($event) => showHistoryModal.value = true)
                          }, "查看分析历史")) : createCommentVNode("", true)
                        ])
                      ]),
                      _cache[33] || (_cache[33] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                      createBaseVNode("div", _hoisted_48$1, [
                        createBaseVNode("span", _hoisted_49$1, [
                          _cache[28] || (_cache[28] = createTextVNode("风险评分 ", -1)),
                          createBaseVNode("b", {
                            style: normalizeStyle({ color: unref(riskColor)(detail.value.ai_result?.risk_score ?? 0) })
                          }, toDisplayString(detail.value.ai_result?.risk_score ?? "-"), 5)
                        ]),
                        _cache[31] || (_cache[31] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_50$1, [
                          _cache[29] || (_cache[29] = createTextVNode("情感 ", -1)),
                          createBaseVNode("b", null, toDisplayString(unref(sentimentText)(detail.value.ai_result?.sentiment || "unknown")), 1)
                        ]),
                        _cache[32] || (_cache[32] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_51$1, [
                          _cache[30] || (_cache[30] = createTextVNode("模型 ", -1)),
                          createBaseVNode("b", null, toDisplayString(detail.value.ai_result?.model_version || "-"), 1)
                        ])
                      ]),
                      createBaseVNode("div", _hoisted_52$1, [
                        detail.value.ai_result?.status === "completed" ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                          detail.value.ai_result.summary ? (openBlock(), createElementBlock("p", _hoisted_53$1, toDisplayString(detail.value.ai_result.summary), 1)) : createCommentVNode("", true),
                          detail.value.ai_result.suggestion ? (openBlock(), createElementBlock("p", _hoisted_54$1, toDisplayString(detail.value.ai_result.suggestion), 1)) : createCommentVNode("", true)
                        ], 64)) : detail.value.ai_result?.status === "failed" ? (openBlock(), createElementBlock("p", _hoisted_55$1, " AI 分析失败：" + toDisplayString(detail.value.ai_result.error_message || "请稍后重试"), 1)) : (openBlock(), createElementBlock("p", _hoisted_56$1, "尚未生成 AI 研判报告，点击下方按钮触发分析。"))
                      ]),
                      canAnalyzeAI.value || detail.value.ai_result?.status === "processing" ? (openBlock(), createElementBlock("div", _hoisted_57$1, [
                        canAnalyzeAI.value && detail.value.ai_result?.status !== "processing" ? (openBlock(), createElementBlock("button", {
                          key: 0,
                          class: "btn btn-primary btn-block",
                          disabled: analyzing.value,
                          onClick: triggerAnalyze
                        }, toDisplayString(analyzing.value ? "分析中..." : detail.value.ai_result?.status === "completed" ? "重新触发 AI 分析" : "触发 AI 分析"), 9, _hoisted_58$1)) : createCommentVNode("", true)
                      ])) : createCommentVNode("", true)
                    ])
                  ])
                ])
              ], 64)) : (openBlock(), createBlock(_component_el_empty, {
                key: 1,
                description: "未找到该外网舆情"
              }))
            ])), [
              [_directive_loading, detailLoading.value]
            ])
          ])
        ])) : createCommentVNode("", true),
        showHistoryModal.value ? (openBlock(), createElementBlock("div", {
          key: 1,
          class: "modal-mask",
          onClick: _cache[4] || (_cache[4] = withModifiers(($event) => showHistoryModal.value = false, ["self"]))
        }, [
          createBaseVNode("div", _hoisted_59$1, [
            createBaseVNode("div", _hoisted_60$1, [
              _cache[34] || (_cache[34] = createBaseVNode("div", { class: "modal-title-wrap" }, [
                createBaseVNode("span", { class: "modal-kicker" }, "分析运行历史"),
                createBaseVNode("h3", { class: "modal-title" }, "AI 研判运行记录")
              ], -1)),
              createBaseVNode("button", {
                class: "modal-close",
                title: "关闭",
                onClick: _cache[3] || (_cache[3] = ($event) => showHistoryModal.value = false)
              }, "✕")
            ]),
            createBaseVNode("div", _hoisted_61$1, [
              detail.value && detail.value.analysis_runs && detail.value.analysis_runs.length ? (openBlock(), createElementBlock("div", _hoisted_62$1, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(detail.value.analysis_runs, (run) => {
                  return openBlock(), createElementBlock("div", {
                    key: run.id,
                    class: "history-row"
                  }, [
                    createBaseVNode("span", null, "#" + toDisplayString(run.id), 1),
                    createBaseVNode("span", null, toDisplayString(run.analyzer_type), 1),
                    createBaseVNode("span", null, toDisplayString(run.status), 1),
                    createBaseVNode("span", null, toDisplayString(unref(formatTime)(run.finished_at || run.started_at)), 1),
                    createBaseVNode("span", _hoisted_63$1, toDisplayString(run.error_message || ""), 1)
                  ]);
                }), 128))
              ])) : (openBlock(), createBlock(_component_el_empty, {
                key: 1,
                description: "暂无分析运行历史"
              }))
            ])
          ])
        ])) : createCommentVNode("", true)
      ]);
    };
  }
});

const ForeignOpinionDetailModal = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-e3606a45"]]);

const _hoisted_1 = { class: "foreign-page" };
const _hoisted_2 = {
  class: "tabs",
  role: "tablist"
};
const _hoisted_3 = ["onClick"];
const _hoisted_4 = { class: "tab-actions" };
const _hoisted_5 = { class: "source-picker" };
const _hoisted_6 = { class: "source-picker-menu" };
const _hoisted_7 = ["value"];
const _hoisted_8 = {
  key: 0,
  class: "muted"
};
const _hoisted_9 = { class: "source-scope-label" };
const _hoisted_10 = ["disabled"];
const _hoisted_11 = ["disabled"];
const _hoisted_12 = {
  key: 0,
  class: "panel visualization-panel"
};
const _hoisted_13 = { key: 0 };
const _hoisted_14 = {
  key: 1,
  class: "error-text"
};
const _hoisted_15 = { class: "fw-dash-head" };
const _hoisted_16 = {
  class: "toolbar",
  style: { "margin-bottom": "0" }
};
const _hoisted_17 = { class: "muted" };
const _hoisted_18 = {
  key: 0,
  class: "stale-badge"
};
const _hoisted_19 = {
  key: 0,
  class: "error-state"
};
const _hoisted_20 = {
  key: 1,
  class: "fw-dash"
};
const _hoisted_21 = { class: "fw-kpi-grid" };
const _hoisted_22 = { class: "fw-kpi" };
const _hoisted_23 = { class: "fw-kpi-value" };
const _hoisted_24 = { class: "fw-kpi" };
const _hoisted_25 = { class: "fw-kpi-value" };
const _hoisted_26 = { class: "fw-kpi" };
const _hoisted_27 = { class: "fw-kpi-value" };
const _hoisted_28 = { class: "fw-kpi" };
const _hoisted_29 = { class: "fw-kpi-value" };
const _hoisted_30 = { class: "fw-kpi" };
const _hoisted_31 = { class: "fw-kpi-value" };
const _hoisted_32 = { class: "fw-kpi" };
const _hoisted_33 = { class: "fw-kpi-value" };
const _hoisted_34 = { class: "fw-dash-grid" };
const _hoisted_35 = { class: "fw-card fw-card-trend fw-col-1" };
const _hoisted_36 = { class: "fw-card-head" };
const _hoisted_37 = { class: "fw-legend" };
const _hoisted_38 = ["onClick"];
const _hoisted_39 = {
  key: 0,
  class: "empty"
};
const _hoisted_40 = { class: "fw-card fw-card-alert fw-col-2" };
const _hoisted_41 = { class: "fw-card-head" };
const _hoisted_42 = { class: "muted" };
const _hoisted_43 = {
  key: 0,
  class: "empty"
};
const _hoisted_44 = {
  key: 1,
  class: "fw-alert-feed"
};
const _hoisted_45 = { class: "fw-alert-summary" };
const _hoisted_46 = { class: "fw-alert-sum" };
const _hoisted_47 = { class: "fw-alert-sum" };
const _hoisted_48 = { class: "fw-alert-list" };
const _hoisted_49 = ["onClick"];
const _hoisted_50 = { class: "fw-alert-main" };
const _hoisted_51 = { class: "fw-alert-title" };
const _hoisted_52 = { class: "fw-alert-meta" };
const _hoisted_53 = {
  key: 0,
  class: "fw-alert-copy"
};
const _hoisted_54 = { class: "fw-alert-list" };
const _hoisted_55 = ["onClick"];
const _hoisted_56 = { class: "fw-alert-main" };
const _hoisted_57 = { class: "fw-alert-title" };
const _hoisted_58 = { class: "fw-alert-meta" };
const _hoisted_59 = { class: "fw-card fw-card-source fw-col-1" };
const _hoisted_60 = { class: "fw-card-head" };
const _hoisted_61 = { class: "muted" };
const _hoisted_62 = {
  key: 0,
  class: "empty"
};
const _hoisted_63 = { class: "fw-card fw-col-2" };
const _hoisted_64 = {
  key: 0,
  class: "empty"
};
const _hoisted_65 = { class: "fw-card fw-card-hotword fw-col-1" };
const _hoisted_66 = { class: "fw-card-head" };
const _hoisted_67 = { class: "muted" };
const _hoisted_68 = {
  key: 0,
  class: "empty"
};
const _hoisted_69 = { class: "fw-card fw-col-2" };
const _hoisted_70 = {
  key: 0,
  class: "empty"
};
const _hoisted_71 = { class: "visualization-meta" };
const _hoisted_72 = {
  key: 2,
  class: "state"
};
const _hoisted_73 = {
  key: 1,
  class: "panel"
};
const _hoisted_74 = { class: "toolbar" };
const _hoisted_75 = ["value"];
const _hoisted_76 = { class: "muted" };
const _hoisted_77 = ["disabled"];
const _hoisted_78 = {
  key: 0,
  class: "ai-batch-status"
};
const _hoisted_79 = { key: 0 };
const _hoisted_80 = { class: "table-wrap tbl-scroll" };
const _hoisted_81 = ["onClick"];
const _hoisted_82 = { class: "title-cell" };
const _hoisted_83 = { class: "dual-cell" };
const _hoisted_84 = { class: "muted" };
const _hoisted_85 = {
  key: 0,
  class: "muted"
};
const _hoisted_86 = { class: "actions" };
const _hoisted_87 = ["disabled", "onClick"];
const _hoisted_88 = { key: 0 };
const _hoisted_89 = {
  key: 1,
  class: "pager"
};
const _hoisted_90 = {
  key: 2,
  class: "panel"
};
const _hoisted_91 = { class: "alert-scope-note" };
const _hoisted_92 = { class: "toolbar" };
const _hoisted_93 = ["disabled"];
const _hoisted_94 = {
  key: 0,
  class: "state error-state"
};
const _hoisted_95 = {
  key: 1,
  class: "event-failures"
};
const _hoisted_96 = { class: "subtabs" };
const _hoisted_97 = {
  key: 2,
  class: "table-wrap"
};
const _hoisted_98 = { class: "title-cell" };
const _hoisted_99 = { class: "actions" };
const _hoisted_100 = ["disabled", "onClick"];
const _hoisted_101 = ["disabled", "onClick"];
const _hoisted_102 = { key: 0 };
const _hoisted_103 = {
  key: 3,
  class: "table-wrap"
};
const _hoisted_104 = ["onClick"];
const _hoisted_105 = { class: "title-cell" };
const _hoisted_106 = ["disabled", "onClick"];
const _hoisted_107 = ["disabled", "onClick"];
const _hoisted_108 = { key: 0 };
const _hoisted_109 = {
  key: 4,
  class: "event-detail"
};
const _hoisted_110 = { class: "event-provenance" };
const _hoisted_111 = { key: 0 };
const _hoisted_112 = { class: "event-detail-head" };
const _hoisted_113 = { class: "actions" };
const _hoisted_114 = ["disabled"];
const _hoisted_115 = ["disabled"];
const _hoisted_116 = ["disabled"];
const _hoisted_117 = { class: "muted" };
const _hoisted_118 = { class: "event-metrics" };
const _hoisted_119 = { class: "muted" };
const _hoisted_120 = ["href"];
const _hoisted_121 = {
  key: 0,
  class: "ai-batch-preview"
};
const _hoisted_122 = ["disabled"];
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
    const collecting = ref(false);
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
    const eventSection = ref("candidates");
    const rebuildingEvents = ref(false);
    const eventActionKey = ref(null);
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
      window.localStorage.getItem("foreign-risk-source") === "ai" ? "ai" : "rule"
    );
    function setRiskSource(value) {
      riskSource.value = value === "ai" ? "ai" : "rule";
      window.localStorage.setItem("foreign-risk-source", riskSource.value);
      loadOpinions();
    }
    const riskByOpinion = computed(() => {
      const m = /* @__PURE__ */ new Map();
      for (const r of risks.value) m.set(r.foreign_opinion_id, r);
      return m;
    });
    function riskOf(id) {
      return riskByOpinion.value.get(id) || null;
    }
    function effOf(row) {
      return row?.effective_risk || null;
    }
    function displayOf(row) {
      return row?.display_risk || effOf(row);
    }
    function ruleOf(row) {
      return row?.rule_risk || null;
    }
    function aiOf(row) {
      return row?.latest_ai_risk || null;
    }
    function aiHistoryLabel(row) {
      const ai = aiOf(row);
      if (!ai) return "未做 AI 研判";
      const score = ai.risk_score === null || ai.risk_score === void 0 ? "-" : ai.risk_score;
      return `AI ${score}（历史）`;
    }
    function displaySourceLabel() {
      return riskSource.value === "ai" ? "AI 研判" : "系统规则";
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
    const aiBatchDialog = ref(false);
    const aiBatchLoading = ref(false);
    const aiBatchPreview = ref(null);
    const aiBatchRun = ref(null);
    let aiBatchTimer = null;
    const opinionFilters = reactive({ q: "", source: "", keyword: "", date_from: "", date_to: "" });
    const riskFilters = reactive({ q: "", source: "", language: "", sentiment: "", risk_level: "", analysis_status: "", date_from: "", date_to: "" });
    const canAnalyzeRisk = hasPermission("foreign:risk:analyze");
    const canAnalyzeAI = hasPermission("foreign:ai:analyze");
    const canConfirmEvents = hasPermission("foreign:events:confirm");
    const canChangeEventStatus = hasPermission("foreign:events:status");
    const canMergeEvents = hasPermission("foreign:events:merge");
    const canSplitEvents = hasPermission("foreign:events:split");
    const canCollectSelected = computed(() => hasPermission("foreign:sources:collect"));
    const canCollectAll = computed(() => hasPermission("foreign:sources:collect_all"));
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
    onMounted(() => window.addEventListener("resize", handleDashboardResize));
    onBeforeUnmount(() => {
      if (aiBatchTimer) clearTimeout(aiBatchTimer);
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
    function operationRequestId(prefix) {
      const random = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      return `${prefix}-${random}`.slice(0, 128);
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
      } finally {
        loading.value = false;
      }
    }
    async function openAIBatch() {
      if (!canAnalyzeAI || aiBatchLoading.value) return;
      aiBatchLoading.value = true;
      try {
        const payload = {
          opinion_ids: opinions.value.map((row) => row.id),
          limit: Math.max(opinions.value.length, opinionSize),
          only_unanalyzed: true,
          force: false
        };
        aiBatchPreview.value = (await api.post("/foreign/ai-analysis/batch/preview", payload)).data;
        aiBatchDialog.value = true;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "批量 AI 预览失败");
      } finally {
        aiBatchLoading.value = false;
      }
    }
    async function startAIBatch() {
      if (!aiBatchPreview.value?.opinion_ids?.length || aiBatchLoading.value) return;
      aiBatchLoading.value = true;
      try {
        const { data } = await api.post("/foreign/ai-analysis/batch", {
          opinion_ids: aiBatchPreview.value.opinion_ids,
          limit: aiBatchPreview.value.opinion_ids.length,
          only_unanalyzed: true,
          force: false
        });
        aiBatchRun.value = { ...data, task_id: data.task_id, status: data.status };
        aiBatchDialog.value = false;
        pollAIBatch(data.run_id);
        ElMessage.success("批量 AI 研判任务已提交");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "批量 AI 研判提交失败");
      } finally {
        aiBatchLoading.value = false;
      }
    }
    function pollAIBatch(runId) {
      if (aiBatchTimer) clearTimeout(aiBatchTimer);
      aiBatchTimer = setTimeout(async () => {
        try {
          const { data } = await api.get(`/foreign/ai-analysis/batch/${runId}`);
          aiBatchRun.value = { ...aiBatchRun.value || {}, ...data, run_id: runId };
          if (["success", "failed", "cancelled"].includes(data.status)) {
            await loadOpinions();
            await loadRisk();
            return;
          }
          pollAIBatch(runId);
        } catch (err) {
          ElMessage.error(err?.response?.data?.detail || "批量 AI 进度查询失败");
        }
      }, 1200);
    }
    async function cancelAIBatch() {
      const runId = aiBatchRun.value?.run_id;
      if (!runId) return;
      try {
        const { data } = await api.post(`/foreign/ai-analysis/batch/${runId}/cancel`);
        aiBatchRun.value = { ...aiBatchRun.value || {}, ...data, run_id: runId };
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "取消批量 AI 任务失败");
      }
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
        riskTotal.value = 0;
        ElMessage.error(err?.response?.data?.detail || "外网风险研判数据加载失败");
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
    async function rebuildEvents() {
      if (rebuildingEvents.value) return;
      rebuildingEvents.value = true;
      try {
        await api.post("/foreign/events/rebuild", { dry_run: true });
        ElMessage.success("外网事件候选 Dry-Run 已完成");
        await loadEvents();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网事件候选重建失败");
      } finally {
        rebuildingEvents.value = false;
      }
    }
    async function confirmCandidate(row) {
      const key = `candidate-confirm-${row.id}`;
      if (eventActionKey.value) return;
      eventActionKey.value = key;
      try {
        await api.post(`/foreign/events/candidates/${row.id}/confirm`, { reason: "Foreign workspace manual confirmation", request_id: operationRequestId(`candidate-confirm-${row.id}`) });
        ElMessage.success("外网事件候选已确认");
        await loadEvents();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "确认外网事件候选失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function rejectCandidate(row) {
      const key = `candidate-reject-${row.id}`;
      if (eventActionKey.value) return;
      eventActionKey.value = key;
      try {
        await api.post(`/foreign/events/candidates/${row.id}/reject`, { reason: "Foreign workspace manual rejection", request_id: operationRequestId(`candidate-reject-${row.id}`) });
        ElMessage.success("外网事件候选已拒绝");
        await loadEvents();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "拒绝外网事件候选失败");
      } finally {
        eventActionKey.value = null;
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
    async function archiveEvent(row) {
      if (eventActionKey.value) return;
      eventActionKey.value = `event-archive-${row.id}`;
      try {
        await api.post(`/foreign/events/${row.id}/status`, { status: "archived", reason: "Foreign workspace archive", request_id: operationRequestId(`event-archive-${row.id}`) });
        ElMessage.success("外网事件已归档");
        await loadEvents();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网事件归档失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function closeEvent(row) {
      if (!canChangeEventStatus || eventActionKey.value) return;
      eventActionKey.value = `event-close-${row.id}`;
      try {
        const prompt = await ElMessageBox.prompt("请输入关闭原因", "关闭外网事件", { inputType: "textarea", inputValidator: (value) => value.trim() ? true : "原因不能为空" });
        await api.post(`/foreign/events/${row.id}/close`, { reason: prompt.value, request_id: operationRequestId(`event-close-${row.id}`) });
        ElMessage.success("外网事件已关闭");
        await loadEvents();
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "关闭外网事件失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function mergeEvent(row) {
      if (!canMergeEvents || eventActionKey.value) return;
      eventActionKey.value = `event-merge-${row.id}`;
      try {
        const prompt = await ElMessageBox.prompt("请输入目标外网事件 ID", "合并外网事件", { inputType: "number", inputValidator: (value) => /^\d+$/.test(value) && Number(value) !== row.id ? true : "请输入不同的有效事件 ID" });
        await api.post(`/foreign/events/${row.id}/merge`, { target_event_id: Number(prompt.value), reason: "Foreign workspace manual merge", request_id: operationRequestId(`event-merge-${row.id}`) });
        ElMessage.success("外网事件已合并");
        selectedForeignEvent.value = null;
        await loadEvents();
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "外网事件合并失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function splitEvent(row) {
      if (!canSplitEvents || !row.opinions?.length || eventActionKey.value) return;
      eventActionKey.value = `event-split-${row.id}`;
      try {
        const prompt = await ElMessageBox.prompt("请输入要拆出的文章 ID，多个 ID 用逗号分隔", "拆分外网事件", { inputValidator: (value) => value.split(",").every((item) => /^\s*\d+\s*$/.test(item)) ? true : "请输入逗号分隔的文章 ID" });
        const opinion_ids = prompt.value.split(",").map((item) => Number(item.trim())).filter(Boolean);
        await api.post(`/foreign/events/${row.id}/split`, { opinion_ids, reason: "Foreign workspace manual split", request_id: operationRequestId(`event-split-${row.id}`) });
        ElMessage.success("外网事件已拆分");
        selectedForeignEvent.value = null;
        await loadEvents();
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "外网事件拆分失败");
      } finally {
        eventActionKey.value = null;
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
    async function analyzeRisk(id) {
      if (!canAnalyzeRisk) {
        ElMessage.warning("当前账号没有外网规则分析权限");
        return;
      }
      try {
        await api.post(`/foreign/risk/${id}/analyze`, {});
        ElMessage.success("外网规则分析完成");
        await loadRisk();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网规则分析失败");
      }
    }
    async function collectNow() {
      if (collecting.value) return;
      collecting.value = true;
      try {
        const { data } = await api.post("/foreign/collect", { source_ids: selectedSourceIds.value });
        const result = await pollTask(data.task_id);
        if (result.status === "success") {
          ElMessage.success(`外网采集完成：新增 ${result.result?.created || 0} 条，已自动规则研判 ${result.result?.analyzed || 0} 条`);
          await loadOpinions();
          await loadRuns();
          await loadRisk();
        } else ElMessage.error(result.error || "外网采集失败");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || err?.message || "外网采集失败");
      } finally {
        collecting.value = false;
      }
    }
    async function collectAll() {
      try {
        await ElMessageBox.confirm(
          "This runs every enabled foreign source. Continue?",
          "Confirm full foreign collection",
          { type: "warning", confirmButtonText: "Collect all", cancelButtonText: "Cancel" }
        );
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        throw err;
      }
      if (collecting.value) return;
      collecting.value = true;
      try {
        const { data } = await api.post("/foreign/collect", { all_sources: true });
        const result = await pollTask(data.task_id);
        if (result.status === "success") {
          ElMessage.success(`Full collection complete: ${result.result?.created || 0} new articles, ${result.result?.analyzed || 0} auto-analyzed`);
          await loadOpinions();
          await loadRuns();
          await loadRisk();
        } else ElMessage.error(result.error || "Foreign collection failed");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || err?.message || "Foreign collection failed");
      } finally {
        collecting.value = false;
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
    onMounted(loadApprovedSources);
    return (_ctx, _cache) => {
      const _component_el_dialog = resolveComponent("el-dialog");
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
            createBaseVNode("details", _hoisted_5, [
              _cache[25] || (_cache[25] = createBaseVNode("summary", null, "选择来源", -1)),
              createBaseVNode("div", _hoisted_6, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(approvedSources.value, (source) => {
                  return openBlock(), createElementBlock("label", {
                    key: source.id
                  }, [
                    withDirectives(createBaseVNode("input", {
                      "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => selectedSourceIds.value = $event),
                      type: "checkbox",
                      value: source.id
                    }, null, 8, _hoisted_7), [
                      [vModelCheckbox, selectedSourceIds.value]
                    ]),
                    createTextVNode(" " + toDisplayString(source.name), 1)
                  ]);
                }), 128)),
                !approvedSources.value.length ? (openBlock(), createElementBlock("span", _hoisted_8, "暂无已批准外网来源")) : createCommentVNode("", true)
              ])
            ]),
            createBaseVNode("span", _hoisted_9, "已批准数据源：" + toDisplayString(approvedSourceLabel.value), 1),
            canCollectSelected.value ? (openBlock(), createElementBlock("button", {
              key: 0,
              class: "btn btn-primary btn-sm",
              disabled: collecting.value || !selectedSourceIds.value.length,
              onClick: collectNow
            }, toDisplayString(collecting.value ? "采集中..." : "采集外网 RSS"), 9, _hoisted_10)) : createCommentVNode("", true),
            canCollectAll.value ? (openBlock(), createElementBlock("button", {
              key: 1,
              class: "btn btn-secondary btn-sm",
              disabled: collecting.value,
              onClick: collectAll
            }, "采集全部已启用外网数据源", 8, _hoisted_11)) : createCommentVNode("", true)
          ])
        ]),
        activeTab.value === "dashboard" ? (openBlock(), createElementBlock("section", _hoisted_12, [
          createBaseVNode("div", {
            class: normalizeClass(["schedule-status", { disabled: !scheduleStatus.value?.enabled }])
          }, [
            _cache[26] || (_cache[26] = createBaseVNode("strong", null, "外网自动采集", -1)),
            createBaseVNode("span", null, toDisplayString(scheduleStatus.value?.enabled ? "已启用" : "部署级开关已关闭"), 1),
            createBaseVNode("span", null, "已注册：" + toDisplayString(scheduleStatus.value?.registered ? "是" : "否"), 1),
            createBaseVNode("span", null, "运行中：" + toDisplayString(scheduleStatus.value?.running ? "是" : "否"), 1),
            createBaseVNode("span", null, "符合来源：" + toDisplayString(scheduleStatus.value?.eligible_source_count ?? 0), 1),
            scheduleStatus.value?.last_run ? (openBlock(), createElementBlock("span", _hoisted_13, "最近运行：" + toDisplayString(zh(scheduleStatus.value.last_run.status)) + " " + toDisplayString(formatTime(scheduleStatus.value.last_run.ended_at || scheduleStatus.value.last_run.started_at)), 1)) : createCommentVNode("", true),
            scheduleStatus.value?.last_run?.error_summary ? (openBlock(), createElementBlock("span", _hoisted_14, toDisplayString(scheduleStatus.value.last_run.error_summary), 1)) : createCommentVNode("", true)
          ], 2),
          createBaseVNode("div", _hoisted_15, [
            _cache[29] || (_cache[29] = createBaseVNode("div", null, [
              createBaseVNode("h2", { class: "fw-dash-title" }, "外网舆情看板"),
              createBaseVNode("p", { class: "muted" }, "面向外网公开来源采集的舆情概览（仅外网数据）")
            ], -1)),
            createBaseVNode("div", _hoisted_16, [
              createBaseVNode("label", _hoisted_17, [
                _cache[28] || (_cache[28] = createTextVNode("统计窗口 ", -1)),
                withDirectives(createBaseVNode("select", {
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => visualizationDays.value = $event),
                  class: "input",
                  onChange: loadDashboard
                }, [..._cache[27] || (_cache[27] = [
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
              visualizationStale.value ? (openBlock(), createElementBlock("span", _hoisted_18, "数据较旧")) : createCommentVNode("", true)
            ])
          ]),
          visualizationError.value ? (openBlock(), createElementBlock("div", _hoisted_19, [
            createBaseVNode("span", null, toDisplayString(visualizationError.value), 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadDashboard
            }, "重试")
          ])) : dashboardSummary.value ? (openBlock(), createElementBlock("div", _hoisted_20, [
            createBaseVNode("div", _hoisted_21, [
              createBaseVNode("div", _hoisted_22, [
                _cache[30] || (_cache[30] = createBaseVNode("span", { class: "fw-kpi-label" }, "文章总数", -1)),
                createBaseVNode("strong", _hoisted_23, toDisplayString(dashboardSummary.value.articles.total), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.articles.window_new) + " 条在窗口内", 1)
              ]),
              createBaseVNode("div", _hoisted_24, [
                _cache[31] || (_cache[31] = createBaseVNode("span", { class: "fw-kpi-label" }, "数据源", -1)),
                createBaseVNode("strong", _hoisted_25, toDisplayString(dashboardSummary.value.articles.sources), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.articles.languages?.en || 0) + " 英文 / " + toDisplayString(dashboardSummary.value.articles.languages?.zh || 0) + " 中文", 1)
              ]),
              createBaseVNode("div", _hoisted_26, [
                _cache[32] || (_cache[32] = createBaseVNode("span", { class: "fw-kpi-label" }, "风险已完成", -1)),
                createBaseVNode("strong", _hoisted_27, toDisplayString(dashboardSummary.value.risk.completed), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.risk.failed) + " 失败 · " + toDisplayString(dashboardSummary.value.risk.pending) + " 待处理", 1)
              ]),
              createBaseVNode("div", _hoisted_28, [
                _cache[33] || (_cache[33] = createBaseVNode("span", { class: "fw-kpi-label" }, "已确认事件", -1)),
                createBaseVNode("strong", _hoisted_29, toDisplayString(dashboardSummary.value.events.confirmed), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.events.candidate) + " 候选", 1)
              ]),
              createBaseVNode("div", _hoisted_30, [
                _cache[34] || (_cache[34] = createBaseVNode("span", { class: "fw-kpi-label" }, "外网告警", -1)),
                createBaseVNode("strong", _hoisted_31, toDisplayString(dashboardSummary.value.alerts.total), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.alerts.by_status?.triggered || 0) + " 已触发", 1)
              ]),
              createBaseVNode("div", _hoisted_32, [
                _cache[35] || (_cache[35] = createBaseVNode("span", { class: "fw-kpi-label" }, "外网采集", -1)),
                createBaseVNode("strong", _hoisted_33, toDisplayString(dashboardSummary.value.collection?.success ?? 0), 1),
                createBaseVNode("small", null, "成功 / 失败 " + toDisplayString(dashboardSummary.value.collection?.failed ?? 0) + " · " + toDisplayString(zh(dashboardSummary.value.collection?.latest?.status || "unknown")), 1)
              ])
            ]),
            createBaseVNode("div", _hoisted_34, [
              createBaseVNode("article", _hoisted_35, [
                createBaseVNode("header", _hoisted_36, [
                  _cache[36] || (_cache[36] = createBaseVNode("h3", null, "每日趋势", -1)),
                  createBaseVNode("div", _hoisted_37, [
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
                      ], 10, _hoisted_38);
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
                !(dashboardTrends.value?.items || []).length ? (openBlock(), createElementBlock("p", _hoisted_39, "该窗口内暂无趋势数据")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_40, [
                createBaseVNode("header", _hoisted_41, [
                  _cache[37] || (_cache[37] = createBaseVNode("h3", null, "外网告警", -1)),
                  createBaseVNode("span", _hoisted_42, "滚动播报 · 共 " + toDisplayString(alertFeed.value.length) + " 条", 1)
                ]),
                !alertFeed.value.length ? (openBlock(), createElementBlock("div", _hoisted_43, "该窗口内暂无外网告警")) : (openBlock(), createElementBlock("div", _hoisted_44, [
                  createBaseVNode("div", _hoisted_45, [
                    createBaseVNode("span", _hoisted_46, [
                      _cache[38] || (_cache[38] = createBaseVNode("i", { class: "fw-sum-dot is-amber" }, null, -1)),
                      createTextVNode("待处置 " + toDisplayString(alertPendingCount.value), 1)
                    ]),
                    createBaseVNode("span", _hoisted_47, [
                      _cache[39] || (_cache[39] = createBaseVNode("i", { class: "fw-sum-dot is-teal" }, null, -1)),
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
                      createBaseVNode("ul", _hoisted_48, [
                        (openBlock(true), createElementBlock(Fragment, null, renderList(alertFeed.value, (a) => {
                          return openBlock(), createElementBlock("li", {
                            key: "a-" + a.id,
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
                      ]),
                      alertNeedScroll.value ? (openBlock(), createElementBlock("div", _hoisted_53, [
                        createBaseVNode("ul", _hoisted_54, [
                          (openBlock(true), createElementBlock(Fragment, null, renderList(alertFeed.value, (a) => {
                            return openBlock(), createElementBlock("li", {
                              key: "b-" + a.id,
                              class: "fw-alert-row",
                              onClick: ($event) => openAlertTarget(a)
                            }, [
                              createBaseVNode("span", {
                                class: normalizeClass(["fw-badge fw-mono", severityBadge(a.severity)])
                              }, toDisplayString(severityText(a.severity)), 3),
                              createBaseVNode("div", _hoisted_56, [
                                createBaseVNode("div", _hoisted_57, toDisplayString(a.title || "未命名告警"), 1),
                                createBaseVNode("div", _hoisted_58, toDisplayString(a.rule_snapshot?.name || a.source_name_snapshot || "外网告警") + " · " + toDisplayString(shortTime(a.triggered_at)), 1)
                              ]),
                              createBaseVNode("span", {
                                class: normalizeClass(["fw-badge", isHandled(a.status) ? "is-teal" : "is-amber"])
                              }, toDisplayString(zh(a.status)), 3)
                            ], 8, _hoisted_55);
                          }), 128))
                        ])
                      ])) : createCommentVNode("", true)
                    ], 6)
                  ], 512)
                ]))
              ]),
              createBaseVNode("article", _hoisted_59, [
                createBaseVNode("header", _hoisted_60, [
                  _cache[40] || (_cache[40] = createBaseVNode("h3", null, "数据源分布", -1)),
                  createBaseVNode("span", _hoisted_61, "近 " + toDisplayString(visualizationDays.value) + " 天 · 各来源文章量", 1)
                ]),
                withDirectives(createBaseVNode("div", {
                  ref_key: "sourceChartRef",
                  ref: sourceChartRef,
                  class: "fw-chart fw-chart-tall"
                }, null, 512), [
                  [vShow, (dashboardSources.value?.items || []).length]
                ]),
                !(dashboardSources.value?.items || []).length ? (openBlock(), createElementBlock("p", _hoisted_62, "该窗口内暂无数据源分布")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_63, [
                _cache[41] || (_cache[41] = createBaseVNode("h3", null, "风险分布", -1)),
                withDirectives(createBaseVNode("div", {
                  ref_key: "riskChartRef",
                  ref: riskChartRef,
                  class: "fw-chart fw-chart-tall"
                }, null, 512), [
                  [vShow, dashboardRisk.value?.risk_levels && Object.keys(dashboardRisk.value.risk_levels || {}).length]
                ]),
                !dashboardRisk.value || !Object.keys(dashboardRisk.value.risk_levels || {}).length ? (openBlock(), createElementBlock("p", _hoisted_64, "暂无已完成风险结果")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_65, [
                createBaseVNode("header", _hoisted_66, [
                  _cache[42] || (_cache[42] = createBaseVNode("h3", null, "外网热词", -1)),
                  createBaseVNode("span", _hoisted_67, "近 " + toDisplayString(visualizationDays.value) + " 天 · 共 " + toDisplayString(hotwordItems.value.length) + " 个热词", 1)
                ]),
                withDirectives(createBaseVNode("div", {
                  ref_key: "hotwordChartRef",
                  ref: hotwordChartRef,
                  class: "fw-chart"
                }, null, 512), [
                  [vShow, hotwordItems.value.length]
                ]),
                !hotwordItems.value.length ? (openBlock(), createElementBlock("p", _hoisted_68, "该窗口内暂无外网热词")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_69, [
                _cache[43] || (_cache[43] = createBaseVNode("h3", null, "事件状态", -1)),
                (openBlock(true), createElementBlock(Fragment, null, renderList(dashboardEvents.value?.formal_events, (count, label) => {
                  return openBlock(), createElementBlock("div", {
                    key: label,
                    class: "distribution-row"
                  }, [
                    createBaseVNode("span", null, toDisplayString(zh(label)), 1),
                    createBaseVNode("strong", null, toDisplayString(count), 1)
                  ]);
                }), 128)),
                !dashboardEvents.value || !Object.keys(dashboardEvents.value.formal_events || {}).length ? (openBlock(), createElementBlock("p", _hoisted_70, "暂无外网事件")) : createCommentVNode("", true)
              ])
            ]),
            createBaseVNode("div", _hoisted_71, "数据范围：" + toDisplayString(formatTime(dashboardSummary.value.window_start)) + " - " + toDisplayString(formatTime(dashboardSummary.value.window_end)) + " · 更新于：" + toDisplayString(formatTime(dashboardSummary.value.data_as_of)), 1)
          ])) : (openBlock(), createElementBlock("div", _hoisted_72, "加载外网看板中..."))
        ])) : createCommentVNode("", true),
        activeTab.value === "opinions" ? (openBlock(), createElementBlock("section", _hoisted_73, [
          createBaseVNode("div", _hoisted_74, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => opinionFilters.q = $event),
              class: "input",
              placeholder: "搜索标题、摘要、正文",
              onKeyup: withKeys(loadOpinions, ["enter"])
            }, null, 544), [
              [vModelText, opinionFilters.q]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => opinionFilters.source = $event),
              class: "input",
              onChange: loadOpinions
            }, [
              _cache[44] || (_cache[44] = createBaseVNode("option", { value: "" }, "全部来源", -1)),
              (openBlock(true), createElementBlock(Fragment, null, renderList(opinionSources.value, (source) => {
                return openBlock(), createElementBlock("option", {
                  key: source,
                  value: source
                }, toDisplayString(source), 9, _hoisted_75);
              }), 128))
            ], 544), [
              [vModelSelect, opinionFilters.source]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => opinionFilters.keyword = $event),
              class: "input",
              placeholder: "命中关键词",
              onKeyup: withKeys(loadOpinions, ["enter"])
            }, null, 544), [
              [vModelText, opinionFilters.keyword]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => riskFilters.language = $event),
              class: "input",
              onChange: _cache[6] || (_cache[6] = ($event) => {
                loadOpinions();
                loadRisk();
              })
            }, [..._cache[45] || (_cache[45] = [
              createStaticVNode('<option value="" data-v-a4a87add>全部语言</option><option value="zh" data-v-a4a87add>中文</option><option value="en" data-v-a4a87add>英文</option><option value="mixed" data-v-a4a87add>中英混合</option><option value="unknown" data-v-a4a87add>未知</option>', 5)
            ])], 544), [
              [vModelSelect, riskFilters.language]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => riskSource.value = $event),
              class: "input",
              "aria-label": "risk view source",
              onChange: _cache[8] || (_cache[8] = ($event) => setRiskSource(riskSource.value))
            }, [..._cache[46] || (_cache[46] = [
              createBaseVNode("option", { value: "rule" }, "系统规则", -1),
              createBaseVNode("option", { value: "ai" }, "AI 研判", -1)
            ])], 544), [
              [vModelSelect, riskSource.value]
            ]),
            createBaseVNode("span", _hoisted_76, "当前查看口径：" + toDisplayString(displaySourceLabel()), 1),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => riskFilters.risk_level = $event),
              class: "input",
              onChange: _cache[10] || (_cache[10] = ($event) => {
                loadOpinions();
                loadRisk();
              })
            }, [..._cache[47] || (_cache[47] = [
              createStaticVNode('<option value="" data-v-a4a87add>全部风险等级</option><option value="high" data-v-a4a87add>高</option><option value="medium" data-v-a4a87add>中</option><option value="low" data-v-a4a87add>低</option><option value="unknown" data-v-a4a87add>未知</option>', 5)
            ])], 544), [
              [vModelSelect, riskFilters.risk_level]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => riskFilters.analysis_status = $event),
              class: "input",
              onChange: _cache[12] || (_cache[12] = ($event) => {
                loadOpinions();
                loadRisk();
              })
            }, [..._cache[48] || (_cache[48] = [
              createBaseVNode("option", { value: "" }, "全部分析状态", -1),
              createBaseVNode("option", { value: "completed" }, "完成", -1),
              createBaseVNode("option", { value: "skipped" }, "跳过", -1),
              createBaseVNode("option", { value: "failed" }, "失败", -1)
            ])], 544), [
              [vModelSelect, riskFilters.analysis_status]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => opinionFilters.date_from = $event),
              class: "input date-input",
              type: "date",
              title: "发布时间起始",
              onChange: loadOpinions
            }, null, 544), [
              [vModelText, opinionFilters.date_from]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => opinionFilters.date_to = $event),
              class: "input date-input",
              type: "date",
              title: "发布时间截止",
              onChange: loadOpinions
            }, null, 544), [
              [vModelText, opinionFilters.date_to]
            ]),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadOpinions
            }, "搜索"),
            unref(canAnalyzeAI) ? (openBlock(), createElementBlock("button", {
              key: 0,
              class: "btn btn-primary",
              disabled: aiBatchLoading.value,
              onClick: openAIBatch
            }, "批量 AI 研判", 8, _hoisted_77)) : createCommentVNode("", true),
            _cache[49] || (_cache[49] = createBaseVNode("span", { class: "muted" }, "AI 研判结果仅用于辅助分析，不改变系统正式风险和告警", -1))
          ]),
          aiBatchRun.value ? (openBlock(), createElementBlock("div", _hoisted_78, [
            createBaseVNode("strong", null, "AI 批次 " + toDisplayString(aiBatchRun.value.status), 1),
            createBaseVNode("span", null, toDisplayString(aiBatchRun.value.processed_count || 0) + "/" + toDisplayString(aiBatchRun.value.total_count || 0), 1),
            aiBatchRun.value.status === "running" || aiBatchRun.value.status === "pending" ? (openBlock(), createElementBlock("span", _hoisted_79, toDisplayString(aiBatchRun.value.progress || 0) + "%", 1)) : createCommentVNode("", true),
            aiBatchRun.value.status === "running" || aiBatchRun.value.status === "pending" ? (openBlock(), createElementBlock("button", {
              key: 1,
              class: "link-btn danger",
              onClick: cancelAIBatch
            }, "取消")) : createCommentVNode("", true)
          ])) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_80, [
            createBaseVNode("table", null, [
              _cache[51] || (_cache[51] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "标题"),
                  createBaseVNode("th", null, "来源快照"),
                  createBaseVNode("th", null, "命中关键词"),
                  createBaseVNode("th", null, "发布时间"),
                  createBaseVNode("th", null, "采集时间"),
                  createBaseVNode("th", null, "当前风险分"),
                  createBaseVNode("th", null, "当前等级"),
                  createBaseVNode("th", null, "风险来源"),
                  createBaseVNode("th", null, "规则 / AI"),
                  createBaseVNode("th", null, "情感"),
                  createBaseVNode("th", null, "风险类别"),
                  createBaseVNode("th", null, "命中风险词"),
                  createBaseVNode("th", null, "分析状态"),
                  createBaseVNode("th", null, "分析时间"),
                  createBaseVNode("th", null, "版本"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(opinions.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id,
                    onClick: ($event) => openOpinion(row.id)
                  }, [
                    createBaseVNode("td", _hoisted_82, toDisplayString(row.title || "无标题"), 1),
                    createBaseVNode("td", null, toDisplayString(row.source_name_snapshot), 1),
                    createBaseVNode("td", null, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(row.matched_keywords, (word) => {
                        return openBlock(), createElementBlock("span", {
                          key: word,
                          class: "tag"
                        }, toDisplayString(word), 1);
                      }), 128))
                    ]),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.published_at)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.collected_at)), 1),
                    createBaseVNode("td", null, toDisplayString(displayOf(row)?.risk_score ?? "-"), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: displayOf(row)?.risk_level === "high" }])
                      }, toDisplayString(zh(displayOf(row)?.risk_level)), 3)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["src-tag", { ai: displayOf(row)?.source === "ai" }])
                      }, toDisplayString(displayOf(row)?.source === "ai" ? "AI 研判" : "系统规则"), 3)
                    ]),
                    createBaseVNode("td", _hoisted_83, [
                      createBaseVNode("span", null, "规则 " + toDisplayString(ruleOf(row)?.risk_score ?? "-"), 1),
                      createBaseVNode("span", _hoisted_84, toDisplayString(aiHistoryLabel(row)), 1)
                    ]),
                    createBaseVNode("td", null, toDisplayString(zh(displayOf(row)?.sentiment)), 1),
                    createBaseVNode("td", null, toDisplayString(zh(ruleOf(row)?.risk_category)), 1),
                    createBaseVNode("td", null, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(riskOf(row.id)?.matched_terms || [], (term) => {
                        return openBlock(), createElementBlock("span", {
                          key: term.word,
                          class: "tag"
                        }, toDisplayString(term.word), 1);
                      }), 128)),
                      !(riskOf(row.id)?.matched_terms || []).length ? (openBlock(), createElementBlock("span", _hoisted_85, "无")) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: ruleOf(row)?.analysis_status === "completed" }])
                      }, toDisplayString(zh(ruleOf(row)?.analysis_status)), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(formatTime(displayOf(row)?.evaluated_at)), 1),
                    createBaseVNode("td", null, toDisplayString(displayOf(row)?.model_version || "-"), 1),
                    createBaseVNode("td", _hoisted_86, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        disabled: !unref(canAnalyzeRisk),
                        onClick: withModifiers(($event) => analyzeRisk(row.id), ["stop"])
                      }, toDisplayString(ruleOf(row) ? "重新分析" : "分析"), 9, _hoisted_87)
                    ])
                  ], 8, _hoisted_81);
                }), 128)),
                !opinions.value.length ? (openBlock(), createElementBlock("tr", _hoisted_88, [..._cache[50] || (_cache[50] = [
                  createBaseVNode("td", {
                    colspan: "16",
                    class: "empty"
                  }, "暂无外网舆情", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ]),
          opinionTotal.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_89, [
            createVNode(_sfc_main$2, {
              total: opinionTotal.value,
              "current-page": opinionPage.value,
              "onUpdate:currentPage": _cache[15] || (_cache[15] = ($event) => opinionPage.value = $event),
              "page-size": opinionSize,
              onCurrentChange: loadOpinions
            }, null, 8, ["total", "current-page"])
          ])) : createCommentVNode("", true)
        ])) : activeTab.value === "events" ? (openBlock(), createElementBlock("section", _hoisted_90, [
          createBaseVNode("div", _hoisted_91, "外网自动聚合：" + toDisplayString(eventAutoStatus.value?.enabled ? "已启用" : "已停用") + " · 调度已注册：" + toDisplayString(eventAutoStatus.value?.scheduler_registered ? "是" : "否") + " · 置信度阈值 " + toDisplayString(eventAutoStatus.value?.confidence_threshold ?? "-") + " · 时间窗口 " + toDisplayString(eventAutoStatus.value?.time_window_hours ?? "-") + " 小时", 1),
          createBaseVNode("div", _hoisted_92, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadEvents
            }, "刷新外网事件"),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: rebuildingEvents.value,
              onClick: rebuildEvents
            }, toDisplayString(rebuildingEvents.value ? "重建中..." : "候选 Dry-Run"), 9, _hoisted_93),
            _cache[52] || (_cache[52] = createBaseVNode("span", { class: "muted" }, "候选只进入外网事件表，必须人工确认后才形成正式事件", -1))
          ]),
          eventLoadError.value ? (openBlock(), createElementBlock("div", _hoisted_94, [
            createBaseVNode("span", null, "外网事件加载失败：" + toDisplayString(eventLoadError.value), 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadEvents
            }, "重试")
          ])) : createCommentVNode("", true),
          eventRunFailures.value.length ? (openBlock(), createElementBlock("div", _hoisted_95, [
            _cache[54] || (_cache[54] = createBaseVNode("strong", null, "外网事件运行失败", -1)),
            (openBlock(true), createElementBlock(Fragment, null, renderList(eventRunFailures.value, (run) => {
              return openBlock(), createElementBlock("div", {
                key: run.id,
                class: "event-failure-row"
              }, [
                _cache[53] || (_cache[53] = createBaseVNode("span", { class: "status failed" }, "失败", -1)),
                createBaseVNode("span", null, toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
                createBaseVNode("span", null, toDisplayString(run.error_message || "运行失败，未提供错误摘要"), 1)
              ]);
            }), 128))
          ])) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_96, [
            createBaseVNode("button", {
              class: normalizeClass(["tab", { active: eventSection.value === "candidates" }]),
              onClick: _cache[16] || (_cache[16] = ($event) => eventSection.value = "candidates")
            }, "事件候选", 2),
            createBaseVNode("button", {
              class: normalizeClass(["tab", { active: eventSection.value === "confirmed" }]),
              onClick: _cache[17] || (_cache[17] = ($event) => eventSection.value = "confirmed")
            }, "外网事件", 2)
          ]),
          eventSection.value === "candidates" ? (openBlock(), createElementBlock("div", _hoisted_97, [
            createBaseVNode("table", null, [
              _cache[56] || (_cache[56] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "标题"),
                  createBaseVNode("th", null, "语言"),
                  createBaseVNode("th", null, "审核来源"),
                  createBaseVNode("th", null, "置信度"),
                  createBaseVNode("th", null, "文章数"),
                  createBaseVNode("th", null, "来源数"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(eventCandidates.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", _hoisted_98, toDisplayString(row.title || "无标题"), 1),
                    createBaseVNode("td", null, toDisplayString(zh(row.language)), 1),
                    createBaseVNode("td", null, toDisplayString(zh(row.review_source || "manual")), 1),
                    createBaseVNode("td", null, toDisplayString(Math.round(row.confidence * 100)) + "%", 1),
                    createBaseVNode("td", null, toDisplayString(row.opinion_count), 1),
                    createBaseVNode("td", null, toDisplayString(row.source_count), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.candidate_status === "converted" }])
                      }, toDisplayString(zh(row.candidate_status)), 3)
                    ]),
                    createBaseVNode("td", _hoisted_99, [
                      row.candidate_status === "candidate" ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "link-btn",
                        disabled: !unref(canConfirmEvents) || eventActionKey.value === `candidate-confirm-${row.id}`,
                        onClick: ($event) => confirmCandidate(row)
                      }, "确认", 8, _hoisted_100)) : createCommentVNode("", true),
                      row.candidate_status === "candidate" ? (openBlock(), createElementBlock("button", {
                        key: 1,
                        class: "link-btn danger",
                        disabled: !unref(canConfirmEvents) || eventActionKey.value === `candidate-reject-${row.id}`,
                        onClick: ($event) => rejectCandidate(row)
                      }, "拒绝", 8, _hoisted_101)) : createCommentVNode("", true)
                    ])
                  ]);
                }), 128)),
                !eventCandidates.value.length ? (openBlock(), createElementBlock("tr", _hoisted_102, [..._cache[55] || (_cache[55] = [
                  createBaseVNode("td", {
                    colspan: "8",
                    class: "empty"
                  }, "暂无外网事件候选", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])) : (openBlock(), createElementBlock("div", _hoisted_103, [
            createBaseVNode("table", null, [
              _cache[58] || (_cache[58] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "标题"),
                  createBaseVNode("th", null, "语言"),
                  createBaseVNode("th", null, "确认来源"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "风险快照"),
                  createBaseVNode("th", null, "热度"),
                  createBaseVNode("th", null, "文章数"),
                  createBaseVNode("th", null, "来源数"),
                  createBaseVNode("th", null, "置信度"),
                  createBaseVNode("th", null, "首次出现"),
                  createBaseVNode("th", null, "最近出现"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(foreignEvents.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id,
                    onClick: ($event) => loadEventDetail(row.id)
                  }, [
                    createBaseVNode("td", _hoisted_105, toDisplayString(row.title || "无标题"), 1),
                    createBaseVNode("td", null, toDisplayString(zh(row.language)), 1),
                    createBaseVNode("td", null, toDisplayString(zh(row.confirmation_source || "manual")), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.event_status === "monitoring", failed: row.event_status === "failed" }])
                      }, toDisplayString(zh(row.event_status)), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(zh(row.risk_level)), 1),
                    createBaseVNode("td", null, toDisplayString(row.heat_score ?? "-"), 1),
                    createBaseVNode("td", null, toDisplayString(row.opinion_count), 1),
                    createBaseVNode("td", null, toDisplayString(row.source_count), 1),
                    createBaseVNode("td", null, toDisplayString(Math.round(row.confidence * 100)) + "%", 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.first_seen_at)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.last_seen_at)), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        disabled: !unref(canChangeEventStatus) || eventActionKey.value === `event-close-${row.id}`,
                        onClick: withModifiers(($event) => closeEvent(row), ["stop"])
                      }, "关闭", 8, _hoisted_106),
                      createBaseVNode("button", {
                        class: "link-btn",
                        disabled: !unref(canChangeEventStatus) || eventActionKey.value === `event-archive-${row.id}`,
                        onClick: withModifiers(($event) => archiveEvent(row), ["stop"])
                      }, "归档", 8, _hoisted_107)
                    ])
                  ], 8, _hoisted_104);
                }), 128)),
                !foreignEvents.value.length ? (openBlock(), createElementBlock("tr", _hoisted_108, [..._cache[57] || (_cache[57] = [
                  createBaseVNode("td", {
                    colspan: "12",
                    class: "empty"
                  }, "暂无已确认外网事件", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])),
          selectedForeignEvent.value ? (openBlock(), createElementBlock("article", _hoisted_109, [
            createBaseVNode("div", _hoisted_110, [
              _cache[60] || (_cache[60] = createBaseVNode("strong", null, "事件溯源", -1)),
              createBaseVNode("span", null, "确认来源：" + toDisplayString(zh(selectedForeignEvent.value.confirmation_source || "manual")), 1),
              createBaseVNode("span", null, "审核来源：" + toDisplayString(zh(selectedForeignEvent.value.auto_aggregation?.review_source)), 1),
              createBaseVNode("span", null, "置信度：" + toDisplayString(Math.round((selectedForeignEvent.value.confidence || 0) * 100)) + "%", 1),
              createBaseVNode("span", null, "文章数：" + toDisplayString(selectedForeignEvent.value.opinion_count) + " · 来源数：" + toDisplayString(selectedForeignEvent.value.source_count), 1),
              selectedForeignEvent.value.auto_aggregation?.evidence ? (openBlock(), createElementBlock("details", _hoisted_111, [
                _cache[59] || (_cache[59] = createBaseVNode("summary", null, "聚合证据", -1)),
                createBaseVNode("pre", null, toDisplayString(JSON.stringify(selectedForeignEvent.value.auto_aggregation.evidence, null, 2)), 1)
              ])) : createCommentVNode("", true)
            ]),
            createBaseVNode("div", _hoisted_112, [
              createBaseVNode("h3", null, toDisplayString(selectedForeignEvent.value.title), 1),
              createBaseVNode("div", _hoisted_113, [
                createBaseVNode("button", {
                  class: "link-btn",
                  disabled: !unref(canChangeEventStatus) || Boolean(eventActionKey.value),
                  onClick: _cache[18] || (_cache[18] = ($event) => closeEvent(selectedForeignEvent.value))
                }, "关闭事件", 8, _hoisted_114),
                createBaseVNode("button", {
                  class: "link-btn",
                  disabled: !unref(canMergeEvents) || Boolean(eventActionKey.value),
                  onClick: _cache[19] || (_cache[19] = ($event) => mergeEvent(selectedForeignEvent.value))
                }, "合并", 8, _hoisted_115),
                createBaseVNode("button", {
                  class: "link-btn",
                  disabled: !unref(canSplitEvents) || Boolean(eventActionKey.value),
                  onClick: _cache[20] || (_cache[20] = ($event) => splitEvent(selectedForeignEvent.value))
                }, "拆分", 8, _hoisted_116),
                createBaseVNode("button", {
                  class: "link-btn",
                  onClick: _cache[21] || (_cache[21] = ($event) => selectedForeignEvent.value = null)
                }, "关闭详情")
              ])
            ]),
            createBaseVNode("p", _hoisted_117, toDisplayString(zh(selectedForeignEvent.value.language)) + " · " + toDisplayString(zh(selectedForeignEvent.value.event_status)) + " · " + toDisplayString(selectedForeignEvent.value.opinion_count) + " 篇文章", 1),
            createBaseVNode("div", _hoisted_118, [
              createBaseVNode("span", null, "热度：" + toDisplayString(selectedForeignEvent.value.heat_score ?? "-"), 1),
              createBaseVNode("span", null, "首次出现：" + toDisplayString(formatTime(selectedForeignEvent.value.first_seen_at)), 1),
              createBaseVNode("span", null, "最近出现：" + toDisplayString(formatTime(selectedForeignEvent.value.last_seen_at)), 1)
            ]),
            createBaseVNode("p", null, toDisplayString(selectedForeignEvent.value.summary || "暂无摘要"), 1),
            (openBlock(true), createElementBlock(Fragment, null, renderList(selectedForeignEvent.value.opinions, (opinion) => {
              return openBlock(), createElementBlock("div", {
                key: opinion.id,
                class: "event-opinion"
              }, [
                createBaseVNode("strong", null, toDisplayString(opinion.title), 1),
                createBaseVNode("span", _hoisted_119, toDisplayString(opinion.source_name_snapshot) + " · " + toDisplayString(formatTime(opinion.published_at)), 1),
                createBaseVNode("a", {
                  href: opinion.url,
                  target: "_blank",
                  rel: "noreferrer",
                  class: "original"
                }, "原文", 8, _hoisted_120)
              ]);
            }), 128))
          ])) : createCommentVNode("", true)
        ])) : createCommentVNode("", true),
        createVNode(ForeignOpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[22] || (_cache[22] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value,
          "risk-source": riskSource.value,
          "onUpdate:riskSource": setRiskSource
        }, null, 8, ["modelValue", "opinion-id", "risk-source"]),
        createVNode(_component_el_dialog, {
          modelValue: aiBatchDialog.value,
          "onUpdate:modelValue": _cache[24] || (_cache[24] = ($event) => aiBatchDialog.value = $event),
          title: "批量 AI 研判",
          width: "min(640px, calc(100vw - 24px))"
        }, {
          footer: withCtx(() => [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: _cache[23] || (_cache[23] = ($event) => aiBatchDialog.value = false)
            }, "取消"),
            createBaseVNode("button", {
              class: "btn btn-primary",
              disabled: aiBatchLoading.value || !aiBatchPreview.value?.opinion_ids?.length,
              onClick: startAIBatch
            }, "确认提交", 8, _hoisted_122)
          ]),
          default: withCtx(() => [
            aiBatchPreview.value ? (openBlock(), createElementBlock("div", _hoisted_121, [
              createBaseVNode("p", null, [
                _cache[61] || (_cache[61] = createTextVNode("符合条件舆情：", -1)),
                createBaseVNode("strong", null, toDisplayString(aiBatchPreview.value.matched_count), 1),
                _cache[62] || (_cache[62] = createTextVNode(" 条", -1))
              ]),
              createBaseVNode("p", null, [
                _cache[63] || (_cache[63] = createTextVNode("待分析：", -1)),
                createBaseVNode("strong", null, toDisplayString(aiBatchPreview.value.pending_analysis_count), 1),
                _cache[64] || (_cache[64] = createTextVNode(" 条 · 预计 Token：", -1)),
                createBaseVNode("strong", null, toDisplayString(aiBatchPreview.value.estimated_token_usage), 1)
              ]),
              createBaseVNode("p", null, "预计耗时：" + toDisplayString(aiBatchPreview.value.estimated_duration_seconds) + " 秒", 1),
              _cache[65] || (_cache[65] = createBaseVNode("p", { class: "muted" }, "AI 结果必须经过人工复核后，才可用于正式事件或预警变更。", -1))
            ])) : createCommentVNode("", true)
          ]),
          _: 1
        }, 8, ["modelValue"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const ForeignWorkspace = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-a4a87add"]]);

export { ForeignWorkspace as default };
