import { d as defineComponent, z as usePermission, r as ref, A as watch, q as createBlock, c as createElementBlock, L as withModifiers, a as createBaseVNode, t as toDisplayString, s as createCommentVNode, w as withDirectives, F as Fragment, n as normalizeClass, e as createTextVNode, H as unref, i as renderList, O as vShow, k as normalizeStyle, a1 as Teleport, j as computed, g as api, E as ElMessage, y as resolveComponent, B as resolveDirective, o as openBlock, _ as _export_sfc } from './index-Dcs1vdKg.js';
import { f as formatTime, r as riskColor, c as statusPill, d as statusText, a as sentimentText } from './opinion-Cag9WtuS.js';

const _hoisted_1 = { class: "modal-card" };
const _hoisted_2 = { class: "modal-header" };
const _hoisted_3 = { class: "modal-title-wrap" };
const _hoisted_4 = { class: "modal-title" };
const _hoisted_5 = { class: "modal-header-right" };
const _hoisted_6 = ["href"];
const _hoisted_7 = { class: "modal-body" };
const _hoisted_8 = {
  class: "risk-view-switch",
  role: "group",
  "aria-label": "risk view source"
};
const _hoisted_9 = { class: "detail-grid" };
const _hoisted_10 = { class: "card card-pad" };
const _hoisted_11 = {
  class: "detail-card-top",
  style: { "display": "flex", "justify-content": "space-between", "align-items": "center", "margin-bottom": "8px" }
};
const _hoisted_12 = ["disabled"];
const _hoisted_13 = { class: "detail-meta" };
const _hoisted_14 = { class: "detail-content" };
const _hoisted_15 = {
  key: 0,
  class: "kw-line"
};
const _hoisted_16 = {
  key: 1,
  class: "orig-p"
};
const _hoisted_17 = {
  key: 2,
  class: "orig-p"
};
const _hoisted_18 = {
  key: 3,
  class: "orig-empty"
};
const _hoisted_19 = {
  key: 0,
  class: "detail-content"
};
const _hoisted_20 = { class: "detail-right" };
const _hoisted_21 = { class: "card card-pad eff-card" };
const _hoisted_22 = { class: "ai-header" };
const _hoisted_23 = { class: "report-meta" };
const _hoisted_24 = { class: "meta-item" };
const _hoisted_25 = { class: "meta-item" };
const _hoisted_26 = {
  key: 0,
  class: "meta-sep"
};
const _hoisted_27 = {
  key: 1,
  class: "meta-item"
};
const _hoisted_28 = { class: "report-body" };
const _hoisted_29 = { class: "report-p report-muted" };
const _hoisted_30 = {
  key: 0,
  class: "dual-row"
};
const _hoisted_31 = { class: "dual-val" };
const _hoisted_32 = {
  key: 0,
  class: "dual-sub"
};
const _hoisted_33 = {
  key: 1,
  class: "dual-row"
};
const _hoisted_34 = { class: "dual-val" };
const _hoisted_35 = {
  key: 2,
  class: "dual-row"
};
const _hoisted_36 = { class: "dual-val" };
const _hoisted_37 = {
  key: 0,
  class: "dual-sub"
};
const _hoisted_38 = { class: "card card-pad sys-card" };
const _hoisted_39 = { class: "ai-header" };
const _hoisted_40 = { class: "report-meta" };
const _hoisted_41 = { class: "meta-item" };
const _hoisted_42 = { class: "meta-item" };
const _hoisted_43 = { class: "meta-item" };
const _hoisted_44 = { class: "report-body" };
const _hoisted_45 = {
  key: 0,
  class: "report-p"
};
const _hoisted_46 = {
  key: 1,
  class: "report-p report-muted"
};
const _hoisted_47 = {
  key: 0,
  class: "report-keywords"
};
const _hoisted_48 = { class: "card card-pad ai-card" };
const _hoisted_49 = { class: "ai-header" };
const _hoisted_50 = { class: "ai-header-tools" };
const _hoisted_51 = { class: "report-meta" };
const _hoisted_52 = { class: "meta-item" };
const _hoisted_53 = { class: "meta-item" };
const _hoisted_54 = { class: "meta-item" };
const _hoisted_55 = { class: "report-body" };
const _hoisted_56 = {
  key: 0,
  class: "report-p"
};
const _hoisted_57 = {
  key: 1,
  class: "report-p"
};
const _hoisted_58 = {
  key: 1,
  class: "report-p report-muted"
};
const _hoisted_59 = {
  key: 2,
  class: "report-p report-muted"
};
const _hoisted_60 = {
  key: 0,
  class: "ai-actions"
};
const _hoisted_61 = ["disabled"];
const _hoisted_62 = { class: "modal-card history-modal" };
const _hoisted_63 = { class: "modal-header" };
const _hoisted_64 = { class: "modal-body" };
const _hoisted_65 = {
  key: 0,
  class: "history-list"
};
const _hoisted_66 = {
  key: 0,
  class: "history-row history-row--batch"
};
const _hoisted_67 = { class: "error-cell" };
const _hoisted_68 = { class: "error-cell" };
const _sfc_main = /* @__PURE__ */ defineComponent({
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
    const batchRun = ref(null);
    const translating = ref(false);
    const translatedText = ref("");
    const translatedTitle = ref("");
    const showTranslation = ref(false);
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
      batchRun.value = null;
      showTranslation.value = false;
      translatedText.value = "";
      translatedTitle.value = "";
      try {
        const { data } = await api.get("/foreign/opinions/" + id + "/detail", { params: { risk_source: viewSource.value } });
        detail.value = sanitizeDetail(data);
        if (data.current_batch_run_id) {
          try {
            const { data: br } = await api.get("/foreign/ai-analysis/batch/" + data.current_batch_run_id);
            batchRun.value = br;
          } catch {
            batchRun.value = null;
          }
        }
      } catch (err) {
        if (err?.response?.status !== 404) ElMessage.error(err?.response?.data?.detail || "外网舆情详情加载失败");
      } finally {
        detailLoading.value = false;
      }
    }
    function close() {
      emit("update:modelValue", false);
    }
    function batchStatusZh(status) {
      switch (status) {
        case "pending":
          return "排队中";
        case "running":
          return "运行中";
        case "success":
          return "成功";
        case "partial":
          return "部分失败";
        case "failed":
          return "失败";
        case "cancelled":
          return "已取消";
        default:
          return status || "未知";
      }
    }
    async function translateContent() {
      if (!detail.value) return;
      if (showTranslation.value) {
        showTranslation.value = false;
        return;
      }
      const title = (detail.value.title || "").trim();
      const text = (detail.value.content || detail.value.summary || "").trim();
      if (!title && !text) {
        ElMessage.info("暂无可翻译内容");
        return;
      }
      translating.value = true;
      try {
        const tasks = [];
        tasks.push(title ? api.post("/translate", { text: title }).then((r) => r.data.translated_text) : Promise.resolve(""));
        tasks.push(text ? api.post("/translate", { text }).then((r) => r.data.translated_text) : Promise.resolve(""));
        const [tTitle, tBody] = await Promise.all(tasks);
        translatedTitle.value = tTitle;
        translatedText.value = tBody;
        showTranslation.value = true;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || err?.response?.data?.message || "翻译失败，请稍后重试");
      } finally {
        translating.value = false;
      }
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
          createBaseVNode("div", _hoisted_1, [
            createBaseVNode("div", _hoisted_2, [
              createBaseVNode("div", _hoisted_3, [
                _cache[5] || (_cache[5] = createBaseVNode("span", { class: "modal-kicker" }, "外网舆情详情与 AI 分析", -1)),
                createBaseVNode("h3", _hoisted_4, toDisplayString(showTranslation.value && translatedTitle.value ? translatedTitle.value : detail.value?.title || "加载中…"), 1)
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
              detail.value ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                createBaseVNode("div", _hoisted_8, [
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
                createBaseVNode("div", _hoisted_9, [
                  createBaseVNode("div", _hoisted_10, [
                    createBaseVNode("div", _hoisted_11, [
                      _cache[7] || (_cache[7] = createBaseVNode("span", { class: "section-title" }, "原文 / 摘要", -1)),
                      createBaseVNode("button", {
                        class: "btn btn-ghost btn-sm",
                        disabled: translating.value,
                        onClick: translateContent
                      }, toDisplayString(translating.value ? "翻译中…" : showTranslation.value ? "显示原文" : "翻译"), 9, _hoisted_12)
                    ]),
                    _cache[9] || (_cache[9] = createTextVNode()),
                    createBaseVNode("div", _hoisted_13, [
                      createBaseVNode("span", null, "来源：" + toDisplayString(detail.value.source_name_snapshot || "-"), 1),
                      createBaseVNode("span", null, "发布时间：" + toDisplayString(unref(formatTime)(detail.value.published_at)), 1),
                      createBaseVNode("span", null, "采集时间：" + toDisplayString(unref(formatTime)(detail.value.collected_at)), 1)
                    ]),
                    _cache[10] || (_cache[10] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                    withDirectives(createBaseVNode("div", _hoisted_14, [
                      detail.value.matched_keywords && detail.value.matched_keywords.length ? (openBlock(), createElementBlock("p", _hoisted_15, [
                        _cache[8] || (_cache[8] = createBaseVNode("span", { class: "kw-label" }, "命中关键词", -1)),
                        (openBlock(true), createElementBlock(Fragment, null, renderList(detail.value.matched_keywords, (k) => {
                          return openBlock(), createElementBlock("span", {
                            key: k,
                            class: "kw-tag"
                          }, toDisplayString(k), 1);
                        }), 128))
                      ])) : createCommentVNode("", true),
                      detail.value.summary && detail.value.summary !== detail.value.content ? (openBlock(), createElementBlock("p", _hoisted_16, toDisplayString(detail.value.summary), 1)) : createCommentVNode("", true),
                      detail.value.content ? (openBlock(), createElementBlock("p", _hoisted_17, toDisplayString(detail.value.content), 1)) : !detail.value.content && !detail.value.summary ? (openBlock(), createElementBlock("p", _hoisted_18, "暂无摘要与正文（正文抓取已关闭）。")) : createCommentVNode("", true)
                    ], 512), [
                      [vShow, !showTranslation.value]
                    ]),
                    showTranslation.value ? (openBlock(), createElementBlock("div", _hoisted_19, [
                      createBaseVNode("p", null, toDisplayString(translatedText.value || translatedTitle.value), 1)
                    ])) : createCommentVNode("", true)
                  ]),
                  createBaseVNode("div", _hoisted_20, [
                    createBaseVNode("div", _hoisted_21, [
                      createBaseVNode("div", _hoisted_22, [
                        _cache[11] || (_cache[11] = createBaseVNode("span", { class: "section-title" }, "当前查看风险", -1)),
                        createBaseVNode("span", {
                          class: normalizeClass(["src-tag", displayRiskSource.value === "ai" ? "src-tag-ai" : "src-tag-rule"])
                        }, toDisplayString(displayRiskSourceLabel.value), 3)
                      ]),
                      _cache[20] || (_cache[20] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                      createBaseVNode("div", _hoisted_23, [
                        createBaseVNode("span", _hoisted_24, [
                          _cache[12] || (_cache[12] = createTextVNode("风险评分 ", -1)),
                          createBaseVNode("b", {
                            style: normalizeStyle({ color: unref(riskColor)(displayRiskScore.value ?? 0) })
                          }, toDisplayString(displayRiskScore.value ?? "-"), 5)
                        ]),
                        _cache[15] || (_cache[15] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_25, [
                          _cache[13] || (_cache[13] = createTextVNode("等级 ", -1)),
                          createBaseVNode("b", null, toDisplayString(riskLevelZh(displayRiskLevel.value)), 1)
                        ]),
                        effectiveRiskReason.value ? (openBlock(), createElementBlock("span", _hoisted_26, "·")) : createCommentVNode("", true),
                        effectiveRiskReason.value ? (openBlock(), createElementBlock("span", _hoisted_27, [
                          _cache[14] || (_cache[14] = createTextVNode("依据 ", -1)),
                          createBaseVNode("b", null, toDisplayString(effectiveRiskReasonText.value), 1)
                        ])) : createCommentVNode("", true)
                      ]),
                      createBaseVNode("div", _hoisted_28, [
                        createBaseVNode("p", _hoisted_29, toDisplayString(displayRiskDesc.value), 1)
                      ]),
                      detail.value.rule_risk ? (openBlock(), createElementBlock("div", _hoisted_30, [
                        _cache[16] || (_cache[16] = createBaseVNode("span", { class: "dual-label" }, "规则基线", -1)),
                        createBaseVNode("span", _hoisted_31, [
                          createTextVNode(toDisplayString(detail.value.rule_risk.risk_score ?? "-") + " / " + toDisplayString(riskLevelZh(detail.value.rule_risk.risk_level)) + " ", 1),
                          detail.value.rule_risk.risk_category ? (openBlock(), createElementBlock("span", _hoisted_32, "· " + toDisplayString(detail.value.rule_risk.risk_category), 1)) : createCommentVNode("", true)
                        ])
                      ])) : createCommentVNode("", true),
                      detail.value.latest_ai_risk ? (openBlock(), createElementBlock("div", _hoisted_33, [
                        _cache[18] || (_cache[18] = createBaseVNode("span", { class: "dual-label" }, "AI 研判", -1)),
                        createBaseVNode("span", _hoisted_34, [
                          createTextVNode(toDisplayString(detail.value.latest_ai_risk.risk_score ?? "-") + " / " + toDisplayString(riskLevelZh(detail.value.latest_ai_risk.risk_level)) + " ", 1),
                          _cache[17] || (_cache[17] = createBaseVNode("span", { class: "dual-flag flag-off" }, "仅历史", -1))
                        ])
                      ])) : createCommentVNode("", true),
                      detail.value.alert ? (openBlock(), createElementBlock("div", _hoisted_35, [
                        _cache[19] || (_cache[19] = createBaseVNode("span", { class: "dual-label" }, "关联告警", -1)),
                        createBaseVNode("span", _hoisted_36, [
                          createTextVNode(" #" + toDisplayString(detail.value.alert.id) + " · " + toDisplayString(alertStatusText(detail.value.alert.status)) + " ", 1),
                          createBaseVNode("span", {
                            class: normalizeClass(["dual-flag", detail.value.alert.is_active ? "flag-on" : "flag-off"])
                          }, toDisplayString(detail.value.alert.is_active ? "生效中" : "已结束"), 3),
                          detail.value.alert.expires_at ? (openBlock(), createElementBlock("span", _hoisted_37, " · 有效期至 " + toDisplayString(unref(formatTime)(detail.value.alert.expires_at)), 1)) : createCommentVNode("", true)
                        ])
                      ])) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("div", _hoisted_38, [
                      createBaseVNode("div", _hoisted_39, [
                        _cache[21] || (_cache[21] = createBaseVNode("span", { class: "section-title" }, "系统规则研判", -1)),
                        createBaseVNode("span", {
                          class: normalizeClass(["pill", unref(statusPill)(detail.value.rule_result?.analysis_status || "pending")])
                        }, toDisplayString(unref(statusText)(detail.value.rule_result?.analysis_status || "pending")), 3)
                      ]),
                      _cache[28] || (_cache[28] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                      createBaseVNode("div", _hoisted_40, [
                        createBaseVNode("span", _hoisted_41, [
                          _cache[22] || (_cache[22] = createTextVNode("风险评分 ", -1)),
                          createBaseVNode("b", {
                            style: normalizeStyle({ color: unref(riskColor)(detail.value.rule_result?.risk_score ?? 0) })
                          }, toDisplayString(detail.value.rule_result?.risk_score ?? "-"), 5)
                        ]),
                        _cache[25] || (_cache[25] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_42, [
                          _cache[23] || (_cache[23] = createTextVNode("等级 ", -1)),
                          createBaseVNode("b", null, toDisplayString(riskLevelZh(detail.value.rule_result?.risk_level)), 1)
                        ]),
                        _cache[26] || (_cache[26] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_43, [
                          _cache[24] || (_cache[24] = createTextVNode("风险类别 ", -1)),
                          createBaseVNode("b", null, toDisplayString(detail.value.rule_result?.risk_category || "-"), 1)
                        ])
                      ]),
                      createBaseVNode("div", _hoisted_44, [
                        detail.value.rule_result?.explanation ? (openBlock(), createElementBlock("p", _hoisted_45, toDisplayString(detail.value.rule_result.explanation), 1)) : (openBlock(), createElementBlock("p", _hoisted_46, "暂无规则研判解释。"))
                      ]),
                      ruleTermHits.value.length ? (openBlock(), createElementBlock("div", _hoisted_47, [
                        _cache[27] || (_cache[27] = createBaseVNode("span", { class: "kw-label" }, "命中风险词", -1)),
                        (openBlock(true), createElementBlock(Fragment, null, renderList(ruleTermHits.value, (h) => {
                          return openBlock(), createElementBlock("span", {
                            key: h,
                            class: "re-hit-tag"
                          }, toDisplayString(h), 1);
                        }), 128))
                      ])) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("div", _hoisted_48, [
                      createBaseVNode("div", _hoisted_49, [
                        _cache[29] || (_cache[29] = createBaseVNode("span", { class: "section-title" }, "AI 研判记录（历史）", -1)),
                        createBaseVNode("div", _hoisted_50, [
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
                      _cache[35] || (_cache[35] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                      createBaseVNode("div", _hoisted_51, [
                        createBaseVNode("span", _hoisted_52, [
                          _cache[30] || (_cache[30] = createTextVNode("风险评分 ", -1)),
                          createBaseVNode("b", {
                            style: normalizeStyle({ color: unref(riskColor)(detail.value.ai_result?.risk_score ?? 0) })
                          }, toDisplayString(detail.value.ai_result?.risk_score ?? "-"), 5)
                        ]),
                        _cache[33] || (_cache[33] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_53, [
                          _cache[31] || (_cache[31] = createTextVNode("情感 ", -1)),
                          createBaseVNode("b", null, toDisplayString(unref(sentimentText)(detail.value.ai_result?.sentiment || "unknown")), 1)
                        ]),
                        _cache[34] || (_cache[34] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                        createBaseVNode("span", _hoisted_54, [
                          _cache[32] || (_cache[32] = createTextVNode("模型 ", -1)),
                          createBaseVNode("b", null, toDisplayString(detail.value.ai_result?.model_version || "-"), 1)
                        ])
                      ]),
                      createBaseVNode("div", _hoisted_55, [
                        detail.value.ai_result?.status === "completed" ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                          detail.value.ai_result.summary ? (openBlock(), createElementBlock("p", _hoisted_56, toDisplayString(detail.value.ai_result.summary), 1)) : createCommentVNode("", true),
                          detail.value.ai_result.suggestion ? (openBlock(), createElementBlock("p", _hoisted_57, toDisplayString(detail.value.ai_result.suggestion), 1)) : createCommentVNode("", true)
                        ], 64)) : detail.value.ai_result?.status === "failed" ? (openBlock(), createElementBlock("p", _hoisted_58, " AI 分析失败：" + toDisplayString(detail.value.ai_result.error_message || "请稍后重试"), 1)) : (openBlock(), createElementBlock("p", _hoisted_59, "尚未生成 AI 研判报告，点击下方按钮触发分析。"))
                      ]),
                      canAnalyzeAI.value || detail.value.ai_result?.status === "processing" ? (openBlock(), createElementBlock("div", _hoisted_60, [
                        canAnalyzeAI.value && detail.value.ai_result?.status !== "processing" ? (openBlock(), createElementBlock("button", {
                          key: 0,
                          class: "btn btn-primary btn-block",
                          disabled: analyzing.value,
                          onClick: triggerAnalyze
                        }, toDisplayString(analyzing.value ? "分析中..." : detail.value.ai_result?.status === "completed" ? "重新触发 AI 分析" : "触发 AI 分析"), 9, _hoisted_61)) : createCommentVNode("", true)
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
          createBaseVNode("div", _hoisted_62, [
            createBaseVNode("div", _hoisted_63, [
              _cache[36] || (_cache[36] = createBaseVNode("div", { class: "modal-title-wrap" }, [
                createBaseVNode("span", { class: "modal-kicker" }, "分析运行历史"),
                createBaseVNode("h3", { class: "modal-title" }, "AI 研判运行记录")
              ], -1)),
              createBaseVNode("button", {
                class: "modal-close",
                title: "关闭",
                onClick: _cache[3] || (_cache[3] = ($event) => showHistoryModal.value = false)
              }, "✕")
            ]),
            createBaseVNode("div", _hoisted_64, [
              detail.value && detail.value.analysis_runs && detail.value.analysis_runs.length || batchRun.value ? (openBlock(), createElementBlock("div", _hoisted_65, [
                batchRun.value ? (openBlock(), createElementBlock("div", _hoisted_66, [
                  createBaseVNode("span", null, "批量 " + toDisplayString(batchRun.value.run_id.slice(0, 8)), 1),
                  _cache[37] || (_cache[37] = createBaseVNode("span", null, "batch", -1)),
                  createBaseVNode("span", null, toDisplayString(batchStatusZh(batchRun.value.status)), 1),
                  createBaseVNode("span", null, toDisplayString(batchRun.value.processed_count || 0) + "/" + toDisplayString(batchRun.value.total_count || 0), 1),
                  createBaseVNode("span", _hoisted_67, " 成功 " + toDisplayString(batchRun.value.success_count || 0) + " · 失败 " + toDisplayString(batchRun.value.failed_count || 0) + " · 跳过 " + toDisplayString(batchRun.value.skipped_count || 0), 1)
                ])) : createCommentVNode("", true),
                (openBlock(true), createElementBlock(Fragment, null, renderList(detail.value?.analysis_runs || [], (run) => {
                  return openBlock(), createElementBlock("div", {
                    key: run.id,
                    class: "history-row"
                  }, [
                    createBaseVNode("span", null, "#" + toDisplayString(run.id), 1),
                    createBaseVNode("span", null, toDisplayString(run.analyzer_type), 1),
                    createBaseVNode("span", null, toDisplayString(run.status), 1),
                    createBaseVNode("span", null, toDisplayString(unref(formatTime)(run.finished_at || run.started_at)), 1),
                    createBaseVNode("span", _hoisted_68, toDisplayString(run.error_message || ""), 1)
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

const ForeignOpinionDetailModal = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-c640815f"]]);

export { ForeignOpinionDetailModal as F };
