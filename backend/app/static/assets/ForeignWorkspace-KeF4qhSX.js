import { d as defineComponent, z as usePermission, A as watch, q as createBlock, c as createElementBlock, L as withModifiers, a as createBaseVNode, t as toDisplayString, s as createCommentVNode, w as withDirectives, H as unref, F as Fragment, i as renderList, n as normalizeClass, e as createTextVNode, k as normalizeStyle, T as Teleport, j as computed, r as ref, M as ElMessageBox, g as api, E as ElMessage, y as resolveComponent, B as resolveDirective, o as openBlock, _ as _export_sfc, C as onMounted, G as onBeforeUnmount, J as vModelSelect, O as vShow, b as withKeys, v as vModelText, P as createStaticVNode, m as createVNode, Q as _sfc_main$2, K as vModelCheckbox, N as useRoute, f as reactive, D as nextTick, R as pollTask, h as useRouter } from './index-Nx1eeH-M.js';
import { i as init, L as LinearGradient } from './index-F2TANFn2.js';
import './wordCloud-DTX2zCb6.js';
import { f as formatTime, c as statusPill, d as statusText, r as riskColor, b as levelText, a as sentimentText } from './opinion-Cag9WtuS.js';

const _hoisted_1$1 = { class: "modal-card" };
const _hoisted_2$1 = { class: "modal-header" };
const _hoisted_3$1 = { class: "modal-title-wrap" };
const _hoisted_4$1 = { class: "modal-title" };
const _hoisted_5$1 = { class: "modal-header-right" };
const _hoisted_6$1 = ["href"];
const _hoisted_7$1 = { class: "modal-body" };
const _hoisted_8$1 = {
  key: 0,
  class: "detail-grid"
};
const _hoisted_9$1 = { class: "card card-pad" };
const _hoisted_10$1 = { class: "detail-meta" };
const _hoisted_11$1 = { class: "detail-content" };
const _hoisted_12$1 = {
  key: 0,
  class: "kw-line"
};
const _hoisted_13$1 = {
  key: 1,
  class: "orig-p"
};
const _hoisted_14$1 = {
  key: 2,
  class: "orig-p"
};
const _hoisted_15$1 = {
  key: 3,
  class: "orig-empty"
};
const _hoisted_16$1 = { class: "detail-right" };
const _hoisted_17$1 = { class: "card card-pad sys-card" };
const _hoisted_18$1 = { class: "ai-header" };
const _hoisted_19$1 = { class: "report-meta" };
const _hoisted_20$1 = { class: "meta-item" };
const _hoisted_21$1 = { class: "meta-item" };
const _hoisted_22$1 = { class: "meta-item" };
const _hoisted_23$1 = { class: "report-body" };
const _hoisted_24$1 = {
  key: 0,
  class: "report-p"
};
const _hoisted_25$1 = {
  key: 1,
  class: "report-p report-muted"
};
const _hoisted_26$1 = {
  key: 0,
  class: "report-keywords"
};
const _hoisted_27$1 = { class: "card card-pad ai-card" };
const _hoisted_28$1 = { class: "ai-header" };
const _hoisted_29$1 = { class: "report-meta" };
const _hoisted_30$1 = { class: "meta-item" };
const _hoisted_31$1 = { class: "meta-item" };
const _hoisted_32$1 = { class: "meta-item" };
const _hoisted_33$1 = { class: "report-body" };
const _hoisted_34$1 = {
  key: 0,
  class: "report-p"
};
const _hoisted_35$1 = {
  key: 1,
  class: "report-p"
};
const _hoisted_36$1 = {
  key: 1,
  class: "report-p report-muted"
};
const _hoisted_37$1 = {
  key: 2,
  class: "report-p report-muted"
};
const _hoisted_38$1 = {
  key: 0,
  class: "ai-actions"
};
const _hoisted_39$1 = ["disabled"];
const _hoisted_40$1 = {
  key: 0,
  class: "card card-pad admission-card"
};
const _hoisted_41$1 = { class: "ai-header" };
const _hoisted_42$1 = {
  key: 0,
  class: "report-p"
};
const _hoisted_43$1 = {
  key: 1,
  class: "admission-actions"
};
const _hoisted_44$1 = ["disabled"];
const _hoisted_45$1 = ["disabled"];
const _hoisted_46$1 = {
  key: 2,
  class: "history-list"
};
const _hoisted_47$1 = {
  key: 1,
  class: "card card-pad"
};
const _hoisted_48$1 = { class: "history-list" };
const _hoisted_49$1 = { class: "error-cell" };
const _sfc_main$1 = /* @__PURE__ */ defineComponent({
  __name: "ForeignOpinionDetailModal",
  props: {
    modelValue: { type: Boolean },
    opinionId: { default: null }
  },
  emits: ["update:modelValue"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const { hasPermission } = usePermission();
    const canAnalyzeAI = computed(() => hasPermission("foreign:ai:analyze"));
    const canAdmitAI = computed(() => hasPermission("foreign:alerts:ai-admit"));
    const detailLoading = ref(false);
    const analyzing = ref(false);
    const detail = ref(null);
    const ruleTermHits = computed(
      () => (detail.value?.rule_result?.matched_terms || []).map((t) => t.word)
    );
    const admissionSaving = ref(false);
    const admissionIncluded = computed(() => detail.value?.ai_alert_admission?.status === "included");
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
      if (d.ai_alert_admission?.note) d.ai_alert_admission.note = decodeHtml(d.ai_alert_admission.note);
      return d;
    }
    async function setAdmission(included) {
      if (!canAdmitAI.value || admissionSaving.value || !detail.value) return;
      const id = detail.value.id;
      try {
        const prompt = await ElMessageBox.prompt(
          included ? "请填写纳入 AI 告警评估的备注" : "请填写取消纳入的备注",
          "AI 告警准入",
          { inputType: "textarea", inputValidator: (value) => value && value.trim() ? true : "备注不能为空" }
        );
        admissionSaving.value = true;
        await api.post("/foreign/opinions/" + id + "/ai-alert-admission", { included, note: prompt.value.trim() });
        const { data } = await api.get("/foreign/opinions/" + id + "/detail");
        detail.value = sanitizeDetail(data);
        ElMessage.success(included ? "已纳入 AI 告警评估" : "已取消 AI 告警评估");
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "AI 告警准入更新失败");
      } finally {
        admissionSaving.value = false;
      }
    }
    async function openDetail(id) {
      detailLoading.value = true;
      detail.value = null;
      try {
        const { data } = await api.get("/foreign/opinions/" + id + "/detail");
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
        const { data } = await api.get("/foreign/opinions/" + id + "/detail");
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
                _cache[2] || (_cache[2] = createBaseVNode("span", { class: "modal-kicker" }, "外网舆情详情与 AI 分析", -1)),
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
              detail.value ? (openBlock(), createElementBlock("div", _hoisted_8$1, [
                createBaseVNode("div", _hoisted_9$1, [
                  createBaseVNode("div", _hoisted_10$1, [
                    createBaseVNode("span", null, "来源：" + toDisplayString(detail.value.source_name_snapshot || "-"), 1),
                    createBaseVNode("span", null, "发布时间：" + toDisplayString(unref(formatTime)(detail.value.published_at)), 1),
                    createBaseVNode("span", null, "采集时间：" + toDisplayString(unref(formatTime)(detail.value.collected_at)), 1)
                  ]),
                  _cache[4] || (_cache[4] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                  createBaseVNode("div", _hoisted_11$1, [
                    detail.value.matched_keywords && detail.value.matched_keywords.length ? (openBlock(), createElementBlock("p", _hoisted_12$1, [
                      _cache[3] || (_cache[3] = createBaseVNode("span", { class: "kw-label" }, "命中关键词", -1)),
                      (openBlock(true), createElementBlock(Fragment, null, renderList(detail.value.matched_keywords, (k) => {
                        return openBlock(), createElementBlock("span", {
                          key: k,
                          class: "kw-tag"
                        }, toDisplayString(k), 1);
                      }), 128))
                    ])) : createCommentVNode("", true),
                    detail.value.summary && detail.value.summary !== detail.value.content ? (openBlock(), createElementBlock("p", _hoisted_13$1, toDisplayString(detail.value.summary), 1)) : createCommentVNode("", true),
                    detail.value.content ? (openBlock(), createElementBlock("p", _hoisted_14$1, toDisplayString(detail.value.content), 1)) : !detail.value.content && !detail.value.summary ? (openBlock(), createElementBlock("p", _hoisted_15$1, "暂无摘要与正文（正文抓取已关闭）。")) : createCommentVNode("", true)
                  ])
                ]),
                createBaseVNode("div", _hoisted_16$1, [
                  createBaseVNode("div", _hoisted_17$1, [
                    createBaseVNode("div", _hoisted_18$1, [
                      _cache[5] || (_cache[5] = createBaseVNode("span", { class: "section-title" }, "系统规则研判", -1)),
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(statusPill)(detail.value.rule_result?.analysis_status || "pending")])
                      }, toDisplayString(unref(statusText)(detail.value.rule_result?.analysis_status || "pending")), 3)
                    ]),
                    _cache[12] || (_cache[12] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                    createBaseVNode("div", _hoisted_19$1, [
                      createBaseVNode("span", _hoisted_20$1, [
                        _cache[6] || (_cache[6] = createTextVNode("风险评分 ", -1)),
                        createBaseVNode("b", {
                          style: normalizeStyle({ color: unref(riskColor)(detail.value.rule_result?.risk_score ?? 0) })
                        }, toDisplayString(detail.value.rule_result?.risk_score ?? "-"), 5)
                      ]),
                      _cache[9] || (_cache[9] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                      createBaseVNode("span", _hoisted_21$1, [
                        _cache[7] || (_cache[7] = createTextVNode("等级 ", -1)),
                        createBaseVNode("b", null, toDisplayString(unref(levelText)(detail.value.rule_result?.risk_level || "unknown")), 1)
                      ]),
                      _cache[10] || (_cache[10] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                      createBaseVNode("span", _hoisted_22$1, [
                        _cache[8] || (_cache[8] = createTextVNode("风险类别 ", -1)),
                        createBaseVNode("b", null, toDisplayString(detail.value.rule_result?.risk_category || "-"), 1)
                      ])
                    ]),
                    createBaseVNode("div", _hoisted_23$1, [
                      detail.value.rule_result?.explanation ? (openBlock(), createElementBlock("p", _hoisted_24$1, toDisplayString(detail.value.rule_result.explanation), 1)) : (openBlock(), createElementBlock("p", _hoisted_25$1, "暂无规则研判解释。"))
                    ]),
                    ruleTermHits.value.length ? (openBlock(), createElementBlock("div", _hoisted_26$1, [
                      _cache[11] || (_cache[11] = createBaseVNode("span", { class: "kw-label" }, "命中风险词", -1)),
                      (openBlock(true), createElementBlock(Fragment, null, renderList(ruleTermHits.value, (h) => {
                        return openBlock(), createElementBlock("span", {
                          key: h,
                          class: "re-hit-tag"
                        }, toDisplayString(h), 1);
                      }), 128))
                    ])) : createCommentVNode("", true)
                  ]),
                  createBaseVNode("div", _hoisted_27$1, [
                    createBaseVNode("div", _hoisted_28$1, [
                      _cache[13] || (_cache[13] = createBaseVNode("span", { class: "section-title" }, "AI 研判报告", -1)),
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(statusPill)(detail.value.ai_result?.status || "pending")])
                      }, toDisplayString(unref(statusText)(detail.value.ai_result?.status || "pending")), 3)
                    ]),
                    _cache[19] || (_cache[19] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                    createBaseVNode("div", _hoisted_29$1, [
                      createBaseVNode("span", _hoisted_30$1, [
                        _cache[14] || (_cache[14] = createTextVNode("风险评分 ", -1)),
                        createBaseVNode("b", {
                          style: normalizeStyle({ color: unref(riskColor)(detail.value.ai_result?.risk_score ?? 0) })
                        }, toDisplayString(detail.value.ai_result?.risk_score ?? "-"), 5)
                      ]),
                      _cache[17] || (_cache[17] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                      createBaseVNode("span", _hoisted_31$1, [
                        _cache[15] || (_cache[15] = createTextVNode("情感 ", -1)),
                        createBaseVNode("b", null, toDisplayString(unref(sentimentText)(detail.value.ai_result?.sentiment || "unknown")), 1)
                      ]),
                      _cache[18] || (_cache[18] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                      createBaseVNode("span", _hoisted_32$1, [
                        _cache[16] || (_cache[16] = createTextVNode("模型 ", -1)),
                        createBaseVNode("b", null, toDisplayString(detail.value.ai_result?.model_version || "-"), 1)
                      ])
                    ]),
                    createBaseVNode("div", _hoisted_33$1, [
                      detail.value.ai_result?.status === "completed" ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                        detail.value.ai_result.summary ? (openBlock(), createElementBlock("p", _hoisted_34$1, toDisplayString(detail.value.ai_result.summary), 1)) : createCommentVNode("", true),
                        detail.value.ai_result.suggestion ? (openBlock(), createElementBlock("p", _hoisted_35$1, toDisplayString(detail.value.ai_result.suggestion), 1)) : createCommentVNode("", true)
                      ], 64)) : detail.value.ai_result?.status === "failed" ? (openBlock(), createElementBlock("p", _hoisted_36$1, " AI 分析失败：" + toDisplayString(detail.value.ai_result.error_message || "请稍后重试"), 1)) : (openBlock(), createElementBlock("p", _hoisted_37$1, "尚未生成 AI 研判报告，点击下方按钮触发分析。"))
                    ]),
                    canAnalyzeAI.value || detail.value.ai_result?.status === "processing" ? (openBlock(), createElementBlock("div", _hoisted_38$1, [
                      canAnalyzeAI.value && detail.value.ai_result?.status !== "processing" ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "btn btn-primary btn-block",
                        disabled: analyzing.value,
                        onClick: triggerAnalyze
                      }, toDisplayString(analyzing.value ? "分析中..." : detail.value.ai_result?.status === "completed" ? "重新触发 AI 分析" : "触发 AI 分析"), 9, _hoisted_39$1)) : createCommentVNode("", true)
                    ])) : createCommentVNode("", true)
                  ]),
                  detail.value.ai_result?.status === "completed" ? (openBlock(), createElementBlock("div", _hoisted_40$1, [
                    createBaseVNode("div", _hoisted_41$1, [
                      _cache[20] || (_cache[20] = createBaseVNode("span", { class: "section-title" }, "AI 告警准入", -1)),
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", admissionIncluded.value ? "pill-green" : "pill-gray"])
                      }, toDisplayString(admissionIncluded.value ? "已纳入" : "未纳入"), 3)
                    ]),
                    _cache[21] || (_cache[21] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                    _cache[22] || (_cache[22] = createBaseVNode("p", { class: "report-p report-muted" }, "决定该外网舆情是否参与 AI 告警评估。", -1)),
                    detail.value.ai_alert_admission?.note ? (openBlock(), createElementBlock("p", _hoisted_42$1, "备注：" + toDisplayString(detail.value.ai_alert_admission.note), 1)) : createCommentVNode("", true),
                    canAdmitAI.value ? (openBlock(), createElementBlock("div", _hoisted_43$1, [
                      createBaseVNode("button", {
                        class: "btn btn-secondary",
                        disabled: admissionSaving.value,
                        onClick: _cache[0] || (_cache[0] = ($event) => setAdmission(true))
                      }, "纳入评估", 8, _hoisted_44$1),
                      createBaseVNode("button", {
                        class: "btn btn-secondary",
                        disabled: admissionSaving.value,
                        onClick: _cache[1] || (_cache[1] = ($event) => setAdmission(false))
                      }, "取消纳入", 8, _hoisted_45$1)
                    ])) : createCommentVNode("", true),
                    detail.value.ai_alert_admission_actions && detail.value.ai_alert_admission_actions.length ? (openBlock(), createElementBlock("div", _hoisted_46$1, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(detail.value.ai_alert_admission_actions, (act) => {
                        return openBlock(), createElementBlock("div", {
                          key: "adm-" + act.id,
                          class: "history-row"
                        }, [
                          createBaseVNode("span", null, toDisplayString(act.previous_status || "-") + " → " + toDisplayString(act.new_status), 1),
                          createBaseVNode("span", null, toDisplayString(act.note || ""), 1),
                          createBaseVNode("span", null, toDisplayString(unref(formatTime)(act.created_at)), 1)
                        ]);
                      }), 128))
                    ])) : createCommentVNode("", true)
                  ])) : createCommentVNode("", true),
                  detail.value.analysis_runs && detail.value.analysis_runs.length ? (openBlock(), createElementBlock("div", _hoisted_47$1, [
                    _cache[23] || (_cache[23] = createBaseVNode("div", { class: "ai-header" }, [
                      createBaseVNode("span", { class: "section-title" }, "分析运行历史")
                    ], -1)),
                    _cache[24] || (_cache[24] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                    createBaseVNode("div", _hoisted_48$1, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(detail.value.analysis_runs, (run) => {
                        return openBlock(), createElementBlock("div", {
                          key: run.id,
                          class: "history-row"
                        }, [
                          createBaseVNode("span", null, "#" + toDisplayString(run.id), 1),
                          createBaseVNode("span", null, toDisplayString(run.analyzer_type), 1),
                          createBaseVNode("span", null, toDisplayString(run.status), 1),
                          createBaseVNode("span", null, toDisplayString(unref(formatTime)(run.finished_at || run.started_at)), 1),
                          createBaseVNode("span", _hoisted_49$1, toDisplayString(run.error_message || ""), 1)
                        ]);
                      }), 128))
                    ])
                  ])) : createCommentVNode("", true)
                ])
              ])) : (openBlock(), createBlock(_component_el_empty, {
                key: 1,
                description: "未找到该外网舆情"
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

const ForeignOpinionDetailModal = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-9ab3a330"]]);

const _hoisted_1 = { class: "foreign-page" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = ["disabled"];
const _hoisted_4 = ["disabled"];
const _hoisted_5 = {
  class: "tabs",
  role: "tablist"
};
const _hoisted_6 = ["onClick"];
const _hoisted_7 = {
  key: 0,
  class: "panel visualization-panel"
};
const _hoisted_8 = { class: "fw-dash-head" };
const _hoisted_9 = {
  class: "toolbar",
  style: { "margin-bottom": "0" }
};
const _hoisted_10 = { class: "muted" };
const _hoisted_11 = {
  key: 0,
  class: "stale-badge"
};
const _hoisted_12 = {
  key: 0,
  class: "error-state"
};
const _hoisted_13 = {
  key: 1,
  class: "fw-dash"
};
const _hoisted_14 = { class: "fw-kpi-grid" };
const _hoisted_15 = { class: "fw-kpi" };
const _hoisted_16 = { class: "fw-kpi-value" };
const _hoisted_17 = { class: "fw-kpi" };
const _hoisted_18 = { class: "fw-kpi-value" };
const _hoisted_19 = { class: "fw-kpi" };
const _hoisted_20 = { class: "fw-kpi-value" };
const _hoisted_21 = { class: "fw-kpi" };
const _hoisted_22 = { class: "fw-kpi-value" };
const _hoisted_23 = { class: "fw-kpi" };
const _hoisted_24 = { class: "fw-kpi-value" };
const _hoisted_25 = { class: "fw-dash-body" };
const _hoisted_26 = { class: "fw-main" };
const _hoisted_27 = { class: "fw-card fw-card-wide" };
const _hoisted_28 = { class: "fw-card-head" };
const _hoisted_29 = { class: "muted" };
const _hoisted_30 = {
  key: 0,
  class: "empty"
};
const _hoisted_31 = { class: "fw-card fw-card-wide" };
const _hoisted_32 = { class: "fw-card-head" };
const _hoisted_33 = { class: "fw-legend" };
const _hoisted_34 = ["onClick"];
const _hoisted_35 = {
  key: 0,
  class: "empty"
};
const _hoisted_36 = { class: "fw-card fw-card-wide" };
const _hoisted_37 = { class: "fw-card-head" };
const _hoisted_38 = { class: "muted" };
const _hoisted_39 = {
  key: 0,
  class: "empty"
};
const _hoisted_40 = { class: "fw-side" };
const _hoisted_41 = { class: "fw-card fw-alert-card" };
const _hoisted_42 = { class: "fw-card-head" };
const _hoisted_43 = { class: "muted" };
const _hoisted_44 = {
  key: 0,
  class: "empty"
};
const _hoisted_45 = {
  key: 1,
  class: "fw-alert-feed"
};
const _hoisted_46 = { class: "fw-alert-summary" };
const _hoisted_47 = { class: "fw-alert-sum" };
const _hoisted_48 = { class: "fw-alert-sum" };
const _hoisted_49 = { class: "fw-alert-copy" };
const _hoisted_50 = { class: "fw-alert-list" };
const _hoisted_51 = ["onClick"];
const _hoisted_52 = { class: "fw-alert-main" };
const _hoisted_53 = { class: "fw-alert-title" };
const _hoisted_54 = { class: "fw-alert-meta" };
const _hoisted_55 = {
  key: 0,
  class: "fw-alert-copy"
};
const _hoisted_56 = { class: "fw-alert-list" };
const _hoisted_57 = ["onClick"];
const _hoisted_58 = { class: "fw-alert-main" };
const _hoisted_59 = { class: "fw-alert-title" };
const _hoisted_60 = { class: "fw-alert-meta" };
const _hoisted_61 = { class: "fw-card" };
const _hoisted_62 = {
  key: 0,
  class: "empty"
};
const _hoisted_63 = { class: "fw-card" };
const _hoisted_64 = {
  key: 0,
  class: "empty"
};
const _hoisted_65 = { class: "fw-card" };
const _hoisted_66 = {
  key: 0,
  class: "distribution-row"
};
const _hoisted_67 = { class: "distribution-row" };
const _hoisted_68 = {
  key: 1,
  class: "empty"
};
const _hoisted_69 = { class: "visualization-meta" };
const _hoisted_70 = {
  key: 2,
  class: "state"
};
const _hoisted_71 = {
  key: 1,
  class: "panel"
};
const _hoisted_72 = { class: "toolbar" };
const _hoisted_73 = ["value"];
const _hoisted_74 = { class: "table-wrap tbl-scroll" };
const _hoisted_75 = ["onClick"];
const _hoisted_76 = { class: "title-cell" };
const _hoisted_77 = {
  key: 0,
  class: "muted"
};
const _hoisted_78 = { class: "actions" };
const _hoisted_79 = ["disabled", "onClick"];
const _hoisted_80 = { key: 0 };
const _hoisted_81 = {
  key: 0,
  class: "pager"
};
const _hoisted_82 = {
  key: 2,
  class: "panel"
};
const _hoisted_83 = { class: "alert-scope-note" };
const _hoisted_84 = { class: "toolbar" };
const _hoisted_85 = ["disabled"];
const _hoisted_86 = {
  key: 0,
  class: "state error-state"
};
const _hoisted_87 = {
  key: 1,
  class: "event-failures"
};
const _hoisted_88 = { class: "subtabs" };
const _hoisted_89 = {
  key: 2,
  class: "table-wrap"
};
const _hoisted_90 = { class: "title-cell" };
const _hoisted_91 = { class: "actions" };
const _hoisted_92 = ["disabled", "onClick"];
const _hoisted_93 = ["disabled", "onClick"];
const _hoisted_94 = { key: 0 };
const _hoisted_95 = {
  key: 3,
  class: "table-wrap"
};
const _hoisted_96 = ["onClick"];
const _hoisted_97 = { class: "title-cell" };
const _hoisted_98 = ["disabled", "onClick"];
const _hoisted_99 = ["disabled", "onClick"];
const _hoisted_100 = { key: 0 };
const _hoisted_101 = {
  key: 4,
  class: "event-detail"
};
const _hoisted_102 = { class: "event-provenance" };
const _hoisted_103 = { key: 0 };
const _hoisted_104 = { class: "event-detail-head" };
const _hoisted_105 = { class: "actions" };
const _hoisted_106 = ["disabled"];
const _hoisted_107 = ["disabled"];
const _hoisted_108 = ["disabled"];
const _hoisted_109 = { class: "muted" };
const _hoisted_110 = { class: "event-metrics" };
const _hoisted_111 = { class: "muted" };
const _hoisted_112 = ["href"];
const _hoisted_113 = {
  key: 3,
  class: "panel"
};
const _hoisted_114 = { class: "alert-scope-note" };
const _hoisted_115 = { class: "toolbar" };
const _hoisted_116 = ["disabled"];
const _hoisted_117 = {
  key: 0,
  class: "state error-state"
};
const _hoisted_118 = {
  key: 1,
  class: "alert-failures"
};
const _hoisted_119 = { class: "table-wrap" };
const _hoisted_120 = { class: "title-cell" };
const _hoisted_121 = ["title", "onClick", "onKeydown"];
const _hoisted_122 = {
  key: 1,
  class: "alert-title"
};
const _hoisted_123 = { class: "muted" };
const _hoisted_124 = { class: "linked-cell" };
const _hoisted_125 = ["onClick"];
const _hoisted_126 = {
  key: 1,
  class: "muted"
};
const _hoisted_127 = { class: "actions" };
const _hoisted_128 = ["onClick"];
const _hoisted_129 = ["disabled", "onClick"];
const _hoisted_130 = ["disabled", "onClick"];
const _hoisted_131 = ["disabled", "onClick"];
const _hoisted_132 = { key: 0 };
const _hoisted_133 = {
  key: 4,
  class: "panel"
};
const _hoisted_134 = { class: "table-wrap" };
const _hoisted_135 = { class: "actions" };
const _hoisted_136 = ["onClick"];
const _hoisted_137 = ["disabled", "onClick"];
const _hoisted_138 = ["disabled", "onClick"];
const _hoisted_139 = ["disabled", "onClick"];
const _hoisted_140 = { key: 0 };
const _hoisted_141 = { class: "detail history-dialog" };
const _hoisted_142 = { class: "muted" };
const _hoisted_143 = {
  key: 0,
  class: "muted"
};
const _hoisted_144 = {
  key: 1,
  class: "empty"
};
const _hoisted_145 = {
  key: 2,
  class: "alert-action-history"
};
const _hoisted_146 = { class: "muted" };
const _hoisted_147 = { class: "detail rule-dialog" };
const _hoisted_148 = { class: "muted" };
const _hoisted_149 = ["disabled"];
const _hoisted_150 = { class: "rule-preview" };
const _hoisted_151 = { class: "actions" };
const _hoisted_152 = ["disabled"];
const opinionSize = 20;
const riskSize = 100;
const riskMaxPages = 20;
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "ForeignWorkspace",
  setup(__props) {
    const tabs = [
      { value: "dashboard", label: "外网 Dashboard" },
      { value: "opinions", label: "国外舆情" },
      { value: "events", label: "外网事件" },
      { value: "alerts", label: "外网告警" },
      { value: "alertRules", label: "告警规则" }
    ];
    const route = useRoute();
    const router = useRouter();
    const { hasPermission } = usePermission();
    function normalizeTab(value) {
      const valid = ["dashboard", "opinions", "events", "alerts", "alertRules"];
      return valid.includes(value) ? value : "dashboard";
    }
    const activeTab = ref(normalizeTab(route.query.tab));
    const loading = ref(false);
    const collecting = ref(false);
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
    const foreignAlerts = ref([]);
    const alertRunFailures = ref([]);
    const alertAutoStatus = ref(null);
    const alertLoadError = ref(null);
    const alertEvaluating = ref(false);
    const alertFilters = reactive({ status: "", severity: "" });
    const historyAlert = ref(null);
    const alertActions = ref([]);
    const alertActionsLoading = ref(false);
    const alertActionBusyId = ref(null);
    const alertRules = ref([]);
    const alertRuleBusyId = ref(null);
    const alertRuleSaving = ref(false);
    const alertRuleEditorVisible = ref(false);
    const alertRuleEditingId = ref(null);
    const alertRuleDraft = reactive({ name: "", description: "", rule_type: "risk_score", conditionsText: '{"threshold":80}', severity: "medium", cooldown_seconds: 3600, is_enabled: false });
    const rulePreview = computed(() => {
      let conditions = alertRuleDraft.conditionsText;
      try {
        conditions = JSON.parse(alertRuleDraft.conditionsText);
      } catch {
      }
      return JSON.stringify({ name: alertRuleDraft.name || "未命名规则", rule_type: alertRuleDraft.rule_type, conditions, severity: alertRuleDraft.severity, cooldown_seconds: alertRuleDraft.cooldown_seconds, is_enabled: false }, null, 2);
    });
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
    const riskByOpinion = computed(() => {
      const m = /* @__PURE__ */ new Map();
      for (const r of risks.value) m.set(r.foreign_opinion_id, r);
      return m;
    });
    function riskOf(id) {
      return riskByOpinion.value.get(id) || null;
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
    const opinionFilters = reactive({ q: "", source: "", keyword: "", date_from: "", date_to: "" });
    const riskFilters = reactive({ q: "", source: "", language: "", sentiment: "", risk_level: "", analysis_status: "", date_from: "", date_to: "" });
    const canAnalyzeRisk = hasPermission("foreign:risk:analyze");
    hasPermission("foreign:ai:analyze");
    hasPermission("foreign:alerts:ai-admit");
    const canConfirmEvents = hasPermission("foreign:events:confirm");
    const canChangeEventStatus = hasPermission("foreign:events:status");
    const canMergeEvents = hasPermission("foreign:events:merge");
    const canSplitEvents = hasPermission("foreign:events:split");
    const canEvaluateAlerts = hasPermission("foreign:alerts:evaluate");
    const canAcknowledgeAlerts = hasPermission("foreign:alerts:acknowledge");
    const canResolveAlerts = hasPermission("foreign:alerts:resolve");
    const canSuppressAlerts = hasPermission("foreign:alerts:suppress");
    const canEnableAlertRules = hasPermission("foreign:alerts:enable");
    function switchTab(tab) {
      router.push({ path: "/foreign", query: { ...route.query, tab } });
    }
    function loadTab(tab) {
      if (tab === "dashboard") loadDashboard();
      if (tab === "opinions") {
        loadOpinions();
        loadRisk();
      }
      if (tab === "events") loadEvents();
      if (tab === "alerts") loadAlerts();
      if (tab === "alertRules") loadAlertRules();
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
    const alertFeed = ref([]);
    const alertViewportEl = ref(null);
    const alertTrackEl = ref(null);
    const alertFeedOverflow = ref(false);
    const alertNeedScroll = ref(false);
    const alertPendingCount = computed(() => (alertFeed.value || []).filter((a) => a.status === "triggered").length);
    const alertDoneCount = computed(() => (alertFeed.value || []).length - alertPendingCount.value);
    const alertScrollDuration = computed(() => Math.max((alertFeed.value || []).length * 2.6, 9) + "s");
    function severityText(s) {
      return zh(s);
    }
    function severityBadge(s) {
      return { critical: "is-rose", high: "is-rose", medium: "is-amber", low: "is-teal" }[s] || "is-cyan";
    }
    function isHandled(status) {
      return status !== "triggered";
    }
    function shortTime(s) {
      if (!s) return "-";
      return s.replace("T", " ").slice(5, 16);
    }
    function measureAlertFeed() {
      if (!alertViewportEl.value || !alertTrackEl.value) return;
      const copyCount = alertNeedScroll.value ? 2 : 1;
      const oneCopy = alertTrackEl.value.scrollHeight / copyCount;
      const overflow = oneCopy > alertViewportEl.value.clientHeight + 1;
      if (overflow && !alertNeedScroll.value) {
        alertNeedScroll.value = true;
        nextTick(() => {
          if (!alertViewportEl.value || !alertTrackEl.value) return;
          const oneCopy2 = alertTrackEl.value.scrollHeight / 2;
          alertFeedOverflow.value = oneCopy2 > alertViewportEl.value.clientHeight + 1;
        });
      } else {
        alertFeedOverflow.value = overflow;
        if (!overflow) alertNeedScroll.value = false;
      }
    }
    watch(alertFeed, () => nextTick(measureAlertFeed), { deep: true });
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
    function renderSourceChart() {
      if (!sourceChart) return;
      const items = dashboardSources.value?.items || [];
      if (!items.length) {
        sourceChart.clear();
        return;
      }
      const top = [...items].sort((a, b) => (b.opinion_count || 0) - (a.opinion_count || 0)).slice(0, 10).reverse();
      sourceChart.setOption({
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          backgroundColor: "rgba(29,29,31,0.94)",
          borderColor: "transparent",
          textStyle: { color: "#fff", fontSize: 12 },
          formatter: (p) => {
            const x = Array.isArray(p) ? p[0] : p;
            return x.name + "<br/>文章量：<b>" + x.value + "</b> 条";
          }
        },
        grid: { left: 8, right: 28, top: 12, bottom: 6, containLabel: true },
        xAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        yAxis: { type: "category", data: top.map((s) => s.source), axisLabel: { color: "#1d1d1f", fontSize: 12 }, axisLine: { lineStyle: { color: "#e8e8ed" } }, axisTick: { show: false } },
        series: [{
          type: "bar",
          data: top.map((s) => s.opinion_count || 0),
          barWidth: 14,
          itemStyle: { borderRadius: [0, 6, 6, 0], color: new LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#0a84ff" }, { offset: 1, color: "#0071e3" }]) }
        }]
      }, { notMerge: true });
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
      if (trendChartRef.value && !trendChart) trendChart = init(trendChartRef.value);
      if (hotwordChartRef.value && !hotwordChart) hotwordChart = init(hotwordChartRef.value);
      if (sourceChartRef.value && !sourceChart) sourceChart = init(sourceChartRef.value);
      renderTrendChart();
      renderHotwordChart();
      renderSourceChart();
      await nextTick();
      measureAlertFeed();
    }
    function handleDashboardResize() {
      trendChart?.resize();
      hotwordChart?.resize();
      sourceChart?.resize();
    }
    onMounted(() => window.addEventListener("resize", handleDashboardResize));
    let alertResizeObserver = null;
    onMounted(() => {
      if (alertViewportEl.value && typeof ResizeObserver !== "undefined") {
        alertResizeObserver = new ResizeObserver(() => measureAlertFeed());
        alertResizeObserver.observe(alertViewportEl.value);
      }
    });
    onBeforeUnmount(() => {
      window.removeEventListener("resize", handleDashboardResize);
      trendChart?.dispose();
      trendChart = null;
      hotwordChart?.dispose();
      hotwordChart = null;
      sourceChart?.dispose();
      sourceChart = null;
      if (alertResizeObserver) {
        alertResizeObserver.disconnect();
        alertResizeObserver = null;
      }
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
          // 外网告警滚动播报：无权限或失败不影响看板其它部分
          api.get("/foreign/alerts", { params: { size: 30 } }).catch(() => ({ data: { items: [] } }))
        ]);
        dashboardSummary.value = summary.data;
        dashboardTrends.value = trends.data;
        dashboardRisk.value = risk.data;
        dashboardEvents.value = events.data;
        dashboardAlerts.value = alerts.data;
        dashboardSources.value = sourceStats.data;
        alertFeed.value = alertFeedData.data.items || [];
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
        const params = { page: opinionPage.value, size: opinionSize };
        if (opinionFilters.q) params.q = opinionFilters.q;
        if (opinionFilters.source) params.source = opinionFilters.source;
        if (opinionFilters.keyword) params.keyword = opinionFilters.keyword;
        if (opinionFilters.date_from) params.date_from = opinionFilters.date_from;
        if (opinionFilters.date_to) params.date_to = opinionFilters.date_to;
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
    async function loadAlerts() {
      loading.value = true;
      alertLoadError.value = null;
      try {
        const params = { size: 100 };
        if (alertFilters.status) params.status = alertFilters.status;
        if (alertFilters.severity) params.severity = alertFilters.severity;
        const [list, runs2, autoStatus] = await Promise.all([
          api.get("/foreign/alerts", { params }),
          api.get("/foreign/alert-runs", { params: { size: 20, status: "failed" } }),
          api.get("/foreign/alert-auto-evaluation/status")
        ]);
        foreignAlerts.value = list.data.items || [];
        alertRunFailures.value = runs2.data.items || [];
        alertAutoStatus.value = autoStatus.data;
      } catch (err) {
        alertLoadError.value = err?.response?.data?.detail || "请求失败，请稍后重试";
        foreignAlerts.value = [];
        alertRunFailures.value = [];
      } finally {
        loading.value = false;
      }
      await loadAlertRules();
    }
    async function loadAlertActions(row) {
      if (alertActionsLoading.value) return;
      historyAlert.value = row;
      alertActionsLoading.value = true;
      try {
        alertActions.value = (await api.get(`/foreign/alerts/${row.id}/actions`)).data.items || [];
      } catch (err) {
        alertActions.value = [];
        ElMessage.error(err?.response?.data?.detail || "外网告警处置历史加载失败");
      } finally {
        alertActionsLoading.value = false;
      }
    }
    async function loadAlertRules() {
      try {
        alertRules.value = (await api.get("/foreign/alert-rules", { params: { size: 100 } })).data.items || [];
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网告警规则加载失败");
      }
    }
    function beginAlertRuleCreate() {
      alertRuleEditingId.value = null;
      alertRuleDraft.name = "";
      alertRuleDraft.description = "";
      alertRuleDraft.rule_type = "risk_score";
      alertRuleDraft.conditionsText = '{"threshold":80}';
      alertRuleDraft.severity = "medium";
      alertRuleDraft.cooldown_seconds = 3600;
      alertRuleDraft.is_enabled = false;
      alertRuleEditorVisible.value = true;
    }
    function editAlertRule(rule) {
      alertRuleEditingId.value = rule.id;
      alertRuleDraft.name = rule.name;
      alertRuleDraft.description = rule.description || "";
      alertRuleDraft.rule_type = rule.rule_type;
      alertRuleDraft.conditionsText = JSON.stringify(rule.conditions || {});
      alertRuleDraft.severity = rule.severity;
      alertRuleDraft.cooldown_seconds = rule.cooldown_seconds;
      alertRuleDraft.is_enabled = rule.is_enabled;
      alertRuleEditorVisible.value = true;
    }
    async function createAlertRule() {
      if (alertRuleSaving.value) return;
      if (!alertRuleDraft.name.trim()) {
        ElMessage.warning("请输入规则名称");
        return;
      }
      let conditions;
      try {
        conditions = JSON.parse(alertRuleDraft.conditionsText);
      } catch {
        ElMessage.error("规则条件必须是合法 JSON");
        return;
      }
      alertRuleSaving.value = true;
      try {
        const payload = { name: alertRuleDraft.name.trim(), description: alertRuleDraft.description.trim(), rule_type: alertRuleDraft.rule_type, conditions, severity: alertRuleDraft.severity, cooldown_seconds: alertRuleDraft.cooldown_seconds, is_enabled: alertRuleEditingId.value ? alertRuleDraft.is_enabled : false };
        if (alertRuleEditingId.value) await api.patch(`/foreign/alert-rules/${alertRuleEditingId.value}`, payload);
        else await api.post("/foreign/alert-rules", payload);
        ElMessage.success(alertRuleEditingId.value ? "外网告警规则已更新" : "外网告警规则已创建并保持停用");
        alertRuleDraft.name = "";
        alertRuleDraft.description = "";
        alertRuleEditingId.value = null;
        alertRuleEditorVisible.value = false;
        await loadAlertRules();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "创建外网告警规则失败");
      } finally {
        alertRuleSaving.value = false;
      }
    }
    async function enableAlertRule(rule) {
      if (!canEnableAlertRules || alertRuleBusyId.value) return;
      alertRuleBusyId.value = rule.id;
      try {
        await api.post(`/foreign/alert-rules/${rule.id}/enable`);
        ElMessage.success("外网告警规则已启用");
        await loadAlertRules();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "启用外网告警规则失败");
      } finally {
        alertRuleBusyId.value = null;
      }
    }
    async function disableAlertRule(rule) {
      if (alertRuleBusyId.value) return;
      alertRuleBusyId.value = rule.id;
      try {
        await api.post(`/foreign/alert-rules/${rule.id}/disable`);
        ElMessage.success("外网告警规则已停用");
        await loadAlertRules();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "停用外网告警规则失败");
      } finally {
        alertRuleBusyId.value = null;
      }
    }
    async function deleteAlertRule(rule) {
      try {
        await ElMessageBox.confirm(`确认删除外网告警规则“${rule.name}”？`, "删除规则", { type: "warning" });
        alertRuleBusyId.value = rule.id;
        await api.delete(`/foreign/alert-rules/${rule.id}`);
        ElMessage.success("外网告警规则已删除");
        await loadAlertRules();
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "删除外网告警规则失败");
      } finally {
        alertRuleBusyId.value = null;
      }
    }
    function actionLabel(action) {
      return action === "acknowledge" ? "确认" : action === "resolve" ? "解决" : "抑制";
    }
    async function evaluateAlerts() {
      if (alertEvaluating.value || !canEvaluateAlerts) return;
      alertEvaluating.value = true;
      try {
        await api.post("/foreign/alerts/evaluate", { dry_run: true, max_items: 200 });
        ElMessage.success("外网告警 Dry-Run 已完成，未写入告警记录");
        await loadAlerts();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网告警评估失败");
      } finally {
        alertEvaluating.value = false;
      }
    }
    async function handleForeignAlert(row, action) {
      const permission = action === "acknowledge" ? canAcknowledgeAlerts : action === "resolve" ? canResolveAlerts : canSuppressAlerts;
      if (!permission || alertActionBusyId.value) return;
      alertActionBusyId.value = row.id;
      try {
        const prompt = await ElMessageBox.prompt(
          `请输入${actionLabel(action)}备注`,
          "外网告警处置",
          {
            inputType: "textarea",
            inputPlaceholder: "备注不能为空",
            inputValidator: (value) => value.trim() ? true : "备注不能为空"
          }
        );
        await api.post(`/foreign/alerts/${row.id}/${action}`, { note: prompt.value });
        ElMessage.success(`外网告警${actionLabel(action)}成功`);
        await loadAlerts();
        await loadAlertActions(row);
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "外网告警操作失败");
      } finally {
        alertActionBusyId.value = null;
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
    async function analyzeRisk(row) {
      if (!canAnalyzeRisk) {
        ElMessage.warning("当前账号没有外网规则分析权限");
        return;
      }
      try {
        await api.post(`/foreign/risk/${row.foreign_opinion_id}/analyze`, {});
        ElMessage.success("外网规则分析完成");
        await loadRisk();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网规则分析失败");
      }
    }
    const approvedSourceIds = [57, 58, 59, 60];
    async function collectNow() {
      if (collecting.value) return;
      collecting.value = true;
      try {
        const { data } = await api.post("/foreign/collect", { source_ids: approvedSourceIds });
        const result = await pollTask(data.task_id);
        if (result.status === "success") {
          ElMessage.success(`外网采集完成：新增 ${result.result?.created || 0} 条`);
          await loadOpinions();
          await loadRuns();
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
          ElMessage.success(`Full collection complete: ${result.result?.created || 0} new articles`);
          await loadOpinions();
          await loadRuns();
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
        const tab = normalizeTab(value);
        activeTab.value = tab;
        loadTab(tab);
      },
      { immediate: true }
    );
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("button", {
            class: "btn btn-primary",
            disabled: collecting.value,
            onClick: collectNow
          }, toDisplayString(collecting.value ? "采集中..." : "采集外网 RSS"), 9, _hoisted_3),
          createBaseVNode("button", {
            class: "btn btn-secondary",
            disabled: collecting.value,
            onClick: collectAll
          }, "采集全部数据源", 8, _hoisted_4),
          _cache[31] || (_cache[31] = createBaseVNode("span", { class: "source-scope-label" }, "已批准数据源：57-60", -1))
        ]),
        createBaseVNode("div", _hoisted_5, [
          (openBlock(), createElementBlock(Fragment, null, renderList(tabs, (tab) => {
            return createBaseVNode("button", {
              key: tab.value,
              class: normalizeClass(["tab", { active: activeTab.value === tab.value }]),
              onClick: ($event) => switchTab(tab.value)
            }, toDisplayString(tab.label), 11, _hoisted_6);
          }), 64))
        ]),
        activeTab.value === "dashboard" ? (openBlock(), createElementBlock("section", _hoisted_7, [
          createBaseVNode("div", _hoisted_8, [
            _cache[34] || (_cache[34] = createBaseVNode("div", null, [
              createBaseVNode("h2", { class: "fw-dash-title" }, "外网舆情看板"),
              createBaseVNode("p", { class: "muted" }, "面向外网公开来源采集的舆情概览（仅外网数据）")
            ], -1)),
            createBaseVNode("div", _hoisted_9, [
              createBaseVNode("label", _hoisted_10, [
                _cache[33] || (_cache[33] = createTextVNode("统计窗口 ", -1)),
                withDirectives(createBaseVNode("select", {
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => visualizationDays.value = $event),
                  class: "input",
                  onChange: loadDashboard
                }, [..._cache[32] || (_cache[32] = [
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
              visualizationStale.value ? (openBlock(), createElementBlock("span", _hoisted_11, "数据较旧")) : createCommentVNode("", true)
            ])
          ]),
          visualizationError.value ? (openBlock(), createElementBlock("div", _hoisted_12, [
            createBaseVNode("span", null, toDisplayString(visualizationError.value), 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadDashboard
            }, "重试")
          ])) : dashboardSummary.value ? (openBlock(), createElementBlock("div", _hoisted_13, [
            createBaseVNode("div", _hoisted_14, [
              createBaseVNode("div", _hoisted_15, [
                _cache[35] || (_cache[35] = createBaseVNode("span", { class: "fw-kpi-label" }, "文章总数", -1)),
                createBaseVNode("strong", _hoisted_16, toDisplayString(dashboardSummary.value.articles.total), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.articles.window_new) + " 条在窗口内", 1)
              ]),
              createBaseVNode("div", _hoisted_17, [
                _cache[36] || (_cache[36] = createBaseVNode("span", { class: "fw-kpi-label" }, "数据源", -1)),
                createBaseVNode("strong", _hoisted_18, toDisplayString(dashboardSummary.value.articles.sources), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.articles.languages?.en || 0) + " 英文 / " + toDisplayString(dashboardSummary.value.articles.languages?.zh || 0) + " 中文", 1)
              ]),
              createBaseVNode("div", _hoisted_19, [
                _cache[37] || (_cache[37] = createBaseVNode("span", { class: "fw-kpi-label" }, "风险已完成", -1)),
                createBaseVNode("strong", _hoisted_20, toDisplayString(dashboardSummary.value.risk.completed), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.risk.failed) + " 失败 · " + toDisplayString(dashboardSummary.value.risk.pending) + " 待处理", 1)
              ]),
              createBaseVNode("div", _hoisted_21, [
                _cache[38] || (_cache[38] = createBaseVNode("span", { class: "fw-kpi-label" }, "已确认事件", -1)),
                createBaseVNode("strong", _hoisted_22, toDisplayString(dashboardSummary.value.events.confirmed), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.events.candidate) + " 候选", 1)
              ]),
              createBaseVNode("div", _hoisted_23, [
                _cache[39] || (_cache[39] = createBaseVNode("span", { class: "fw-kpi-label" }, "外网告警", -1)),
                createBaseVNode("strong", _hoisted_24, toDisplayString(dashboardSummary.value.alerts.total), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.alerts.by_status?.triggered || 0) + " 已触发", 1)
              ])
            ]),
            createBaseVNode("div", _hoisted_25, [
              createBaseVNode("div", _hoisted_26, [
                createBaseVNode("article", _hoisted_27, [
                  createBaseVNode("header", _hoisted_28, [
                    _cache[40] || (_cache[40] = createBaseVNode("h3", null, "数据源分布", -1)),
                    createBaseVNode("span", _hoisted_29, "近 " + toDisplayString(visualizationDays.value) + " 天 · 各来源文章量", 1)
                  ]),
                  withDirectives(createBaseVNode("div", {
                    ref_key: "sourceChartRef",
                    ref: sourceChartRef,
                    class: "fw-chart fw-chart-tall"
                  }, null, 512), [
                    [vShow, (dashboardSources.value?.items || []).length]
                  ]),
                  !(dashboardSources.value?.items || []).length ? (openBlock(), createElementBlock("p", _hoisted_30, "该窗口内暂无数据源分布")) : createCommentVNode("", true)
                ]),
                createBaseVNode("article", _hoisted_31, [
                  createBaseVNode("header", _hoisted_32, [
                    _cache[41] || (_cache[41] = createBaseVNode("h3", null, "每日趋势", -1)),
                    createBaseVNode("div", _hoisted_33, [
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
                        ], 10, _hoisted_34);
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
                  !(dashboardTrends.value?.items || []).length ? (openBlock(), createElementBlock("p", _hoisted_35, "该窗口内暂无趋势数据")) : createCommentVNode("", true)
                ]),
                createBaseVNode("article", _hoisted_36, [
                  createBaseVNode("header", _hoisted_37, [
                    _cache[42] || (_cache[42] = createBaseVNode("h3", null, "外网热词", -1)),
                    createBaseVNode("span", _hoisted_38, "近 " + toDisplayString(visualizationDays.value) + " 天 · 共 " + toDisplayString(hotwordItems.value.length) + " 个热词", 1)
                  ]),
                  withDirectives(createBaseVNode("div", {
                    ref_key: "hotwordChartRef",
                    ref: hotwordChartRef,
                    class: "fw-chart"
                  }, null, 512), [
                    [vShow, hotwordItems.value.length]
                  ]),
                  !hotwordItems.value.length ? (openBlock(), createElementBlock("p", _hoisted_39, "该窗口内暂无外网热词")) : createCommentVNode("", true)
                ])
              ]),
              createBaseVNode("aside", _hoisted_40, [
                createBaseVNode("article", _hoisted_41, [
                  createBaseVNode("header", _hoisted_42, [
                    _cache[43] || (_cache[43] = createBaseVNode("h3", null, "外网告警", -1)),
                    createBaseVNode("span", _hoisted_43, "滚动播报 · 共 " + toDisplayString(alertFeed.value.length) + " 条", 1)
                  ]),
                  !alertFeed.value.length ? (openBlock(), createElementBlock("div", _hoisted_44, "该窗口内暂无外网告警")) : (openBlock(), createElementBlock("div", _hoisted_45, [
                    createBaseVNode("div", _hoisted_46, [
                      createBaseVNode("span", _hoisted_47, [
                        _cache[44] || (_cache[44] = createBaseVNode("i", { class: "fw-sum-dot is-amber" }, null, -1)),
                        createTextVNode("待处置 " + toDisplayString(alertPendingCount.value), 1)
                      ]),
                      createBaseVNode("span", _hoisted_48, [
                        _cache[45] || (_cache[45] = createBaseVNode("i", { class: "fw-sum-dot is-teal" }, null, -1)),
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
                        createBaseVNode("div", _hoisted_49, [
                          createBaseVNode("ul", _hoisted_50, [
                            (openBlock(true), createElementBlock(Fragment, null, renderList(alertFeed.value, (a) => {
                              return openBlock(), createElementBlock("li", {
                                key: "a-" + a.id,
                                class: "fw-alert-row",
                                onClick: ($event) => openAlertTarget(a)
                              }, [
                                createBaseVNode("span", {
                                  class: normalizeClass(["fw-badge fw-mono", severityBadge(a.severity)])
                                }, toDisplayString(severityText(a.severity)), 3),
                                createBaseVNode("div", _hoisted_52, [
                                  createBaseVNode("div", _hoisted_53, toDisplayString(a.title || "未命名告警"), 1),
                                  createBaseVNode("div", _hoisted_54, toDisplayString(a.rule_snapshot?.name || a.source_name_snapshot || "外网告警") + " · " + toDisplayString(shortTime(a.triggered_at)), 1)
                                ]),
                                createBaseVNode("span", {
                                  class: normalizeClass(["fw-badge", isHandled(a.status) ? "is-teal" : "is-amber"])
                                }, toDisplayString(zh(a.status)), 3)
                              ], 8, _hoisted_51);
                            }), 128))
                          ])
                        ]),
                        alertNeedScroll.value ? (openBlock(), createElementBlock("div", _hoisted_55, [
                          createBaseVNode("ul", _hoisted_56, [
                            (openBlock(true), createElementBlock(Fragment, null, renderList(alertFeed.value, (a) => {
                              return openBlock(), createElementBlock("li", {
                                key: "b-" + a.id,
                                class: "fw-alert-row",
                                onClick: ($event) => openAlertTarget(a)
                              }, [
                                createBaseVNode("span", {
                                  class: normalizeClass(["fw-badge fw-mono", severityBadge(a.severity)])
                                }, toDisplayString(severityText(a.severity)), 3),
                                createBaseVNode("div", _hoisted_58, [
                                  createBaseVNode("div", _hoisted_59, toDisplayString(a.title || "未命名告警"), 1),
                                  createBaseVNode("div", _hoisted_60, toDisplayString(a.rule_snapshot?.name || a.source_name_snapshot || "外网告警") + " · " + toDisplayString(shortTime(a.triggered_at)), 1)
                                ]),
                                createBaseVNode("span", {
                                  class: normalizeClass(["fw-badge", isHandled(a.status) ? "is-teal" : "is-amber"])
                                }, toDisplayString(zh(a.status)), 3)
                              ], 8, _hoisted_57);
                            }), 128))
                          ])
                        ])) : createCommentVNode("", true)
                      ], 6)
                    ], 512)
                  ]))
                ]),
                createBaseVNode("article", _hoisted_61, [
                  _cache[46] || (_cache[46] = createBaseVNode("h3", null, "风险分布", -1)),
                  (openBlock(true), createElementBlock(Fragment, null, renderList(dashboardRisk.value?.risk_levels, (count, label) => {
                    return openBlock(), createElementBlock("div", {
                      key: label,
                      class: "distribution-row"
                    }, [
                      createBaseVNode("span", null, toDisplayString(zh(label)), 1),
                      createBaseVNode("strong", null, toDisplayString(count), 1)
                    ]);
                  }), 128)),
                  !dashboardRisk.value || !Object.keys(dashboardRisk.value.risk_levels || {}).length ? (openBlock(), createElementBlock("p", _hoisted_62, "暂无已完成风险结果")) : createCommentVNode("", true)
                ]),
                createBaseVNode("article", _hoisted_63, [
                  _cache[47] || (_cache[47] = createBaseVNode("h3", null, "事件状态", -1)),
                  (openBlock(true), createElementBlock(Fragment, null, renderList(dashboardEvents.value?.formal_events, (count, label) => {
                    return openBlock(), createElementBlock("div", {
                      key: label,
                      class: "distribution-row"
                    }, [
                      createBaseVNode("span", null, toDisplayString(zh(label)), 1),
                      createBaseVNode("strong", null, toDisplayString(count), 1)
                    ]);
                  }), 128)),
                  !dashboardEvents.value || !Object.keys(dashboardEvents.value.formal_events || {}).length ? (openBlock(), createElementBlock("p", _hoisted_64, "暂无外网事件")) : createCommentVNode("", true)
                ]),
                createBaseVNode("article", _hoisted_65, [
                  _cache[50] || (_cache[50] = createBaseVNode("h3", null, "采集状态", -1)),
                  dashboardSummary.value.collection.latest ? (openBlock(), createElementBlock("div", _hoisted_66, [
                    _cache[48] || (_cache[48] = createBaseVNode("span", null, "最近一次", -1)),
                    createBaseVNode("strong", null, toDisplayString(zh(dashboardSummary.value.collection.latest.status)), 1)
                  ])) : createCommentVNode("", true),
                  createBaseVNode("div", _hoisted_67, [
                    _cache[49] || (_cache[49] = createBaseVNode("span", null, "成功 / 失败", -1)),
                    createBaseVNode("strong", null, toDisplayString(dashboardSummary.value.collection.success) + " / " + toDisplayString(dashboardSummary.value.collection.failed), 1)
                  ]),
                  !dashboardSummary.value.collection.latest ? (openBlock(), createElementBlock("p", _hoisted_68, "暂无外网采集记录")) : createCommentVNode("", true)
                ])
              ])
            ]),
            createBaseVNode("div", _hoisted_69, "数据范围：" + toDisplayString(formatTime(dashboardSummary.value.window_start)) + " - " + toDisplayString(formatTime(dashboardSummary.value.window_end)) + " · 更新于：" + toDisplayString(formatTime(dashboardSummary.value.data_as_of)), 1)
          ])) : (openBlock(), createElementBlock("div", _hoisted_70, "加载外网看板中..."))
        ])) : createCommentVNode("", true),
        activeTab.value === "opinions" ? (openBlock(), createElementBlock("section", _hoisted_71, [
          createBaseVNode("div", _hoisted_72, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => opinionFilters.q = $event),
              class: "input",
              placeholder: "搜索标题、摘要、正文",
              onKeyup: withKeys(loadOpinions, ["enter"])
            }, null, 544), [
              [vModelText, opinionFilters.q]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => opinionFilters.source = $event),
              class: "input",
              onChange: loadOpinions
            }, [
              _cache[51] || (_cache[51] = createBaseVNode("option", { value: "" }, "全部来源", -1)),
              (openBlock(true), createElementBlock(Fragment, null, renderList(opinionSources.value, (source) => {
                return openBlock(), createElementBlock("option", {
                  key: source,
                  value: source
                }, toDisplayString(source), 9, _hoisted_73);
              }), 128))
            ], 544), [
              [vModelSelect, opinionFilters.source]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => opinionFilters.keyword = $event),
              class: "input",
              placeholder: "命中关键词",
              onKeyup: withKeys(loadOpinions, ["enter"])
            }, null, 544), [
              [vModelText, opinionFilters.keyword]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => riskFilters.language = $event),
              class: "input",
              onChange: loadRisk
            }, [..._cache[52] || (_cache[52] = [
              createStaticVNode('<option value="" data-v-5a9f26eb>全部语言</option><option value="zh" data-v-5a9f26eb>中文</option><option value="en" data-v-5a9f26eb>英文</option><option value="mixed" data-v-5a9f26eb>中英混合</option><option value="unknown" data-v-5a9f26eb>未知</option>', 5)
            ])], 544), [
              [vModelSelect, riskFilters.language]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => riskFilters.risk_level = $event),
              class: "input",
              onChange: loadRisk
            }, [..._cache[53] || (_cache[53] = [
              createStaticVNode('<option value="" data-v-5a9f26eb>全部风险等级</option><option value="high" data-v-5a9f26eb>高</option><option value="medium" data-v-5a9f26eb>中</option><option value="low" data-v-5a9f26eb>低</option><option value="unknown" data-v-5a9f26eb>未知</option>', 5)
            ])], 544), [
              [vModelSelect, riskFilters.risk_level]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => riskFilters.analysis_status = $event),
              class: "input",
              onChange: loadRisk
            }, [..._cache[54] || (_cache[54] = [
              createBaseVNode("option", { value: "" }, "全部分析状态", -1),
              createBaseVNode("option", { value: "completed" }, "完成", -1),
              createBaseVNode("option", { value: "skipped" }, "跳过", -1),
              createBaseVNode("option", { value: "failed" }, "失败", -1)
            ])], 544), [
              [vModelSelect, riskFilters.analysis_status]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => opinionFilters.date_from = $event),
              class: "input date-input",
              type: "date",
              title: "发布时间起始",
              onChange: loadOpinions
            }, null, 544), [
              [vModelText, opinionFilters.date_from]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => opinionFilters.date_to = $event),
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
            _cache[55] || (_cache[55] = createBaseVNode("span", { class: "muted" }, "以舆情为主，右侧为已关联的风险研判（未分析显示 -）", -1))
          ]),
          createBaseVNode("div", _hoisted_74, [
            createBaseVNode("table", null, [
              _cache[57] || (_cache[57] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "标题"),
                  createBaseVNode("th", null, "来源快照"),
                  createBaseVNode("th", null, "命中关键词"),
                  createBaseVNode("th", null, "发布时间"),
                  createBaseVNode("th", null, "采集时间"),
                  createBaseVNode("th", null, "风险分"),
                  createBaseVNode("th", null, "等级"),
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
                    createBaseVNode("td", _hoisted_76, toDisplayString(row.title || "无标题"), 1),
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
                    createBaseVNode("td", null, toDisplayString(riskOf(row.id)?.risk_score ?? "-"), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: riskOf(row.id)?.risk_level === "high" }])
                      }, toDisplayString(zh(riskOf(row.id)?.risk_level)), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(zh(riskOf(row.id)?.sentiment)), 1),
                    createBaseVNode("td", null, toDisplayString(zh(riskOf(row.id)?.risk_category)), 1),
                    createBaseVNode("td", null, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(riskOf(row.id)?.matched_terms || [], (term) => {
                        return openBlock(), createElementBlock("span", {
                          key: term.word,
                          class: "tag"
                        }, toDisplayString(term.word), 1);
                      }), 128)),
                      !(riskOf(row.id)?.matched_terms || []).length ? (openBlock(), createElementBlock("span", _hoisted_77, "无")) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: riskOf(row.id)?.analysis_status === "completed" }])
                      }, toDisplayString(zh(riskOf(row.id)?.analysis_status)), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(formatTime(riskOf(row.id)?.analyzed_at)), 1),
                    createBaseVNode("td", null, toDisplayString(riskOf(row.id)?.model_version || "-"), 1),
                    createBaseVNode("td", _hoisted_78, [
                      riskOf(row.id) ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "link-btn",
                        disabled: !unref(canAnalyzeRisk),
                        onClick: withModifiers(($event) => analyzeRisk(riskOf(row.id)), ["stop"])
                      }, "重新分析", 8, _hoisted_79)) : createCommentVNode("", true)
                    ])
                  ], 8, _hoisted_75);
                }), 128)),
                !opinions.value.length ? (openBlock(), createElementBlock("tr", _hoisted_80, [..._cache[56] || (_cache[56] = [
                  createBaseVNode("td", {
                    colspan: "14",
                    class: "empty"
                  }, "暂无外网舆情", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ]),
          opinionTotal.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_81, [
            createVNode(_sfc_main$2, {
              total: opinionTotal.value,
              "current-page": opinionPage.value,
              "onUpdate:currentPage": _cache[9] || (_cache[9] = ($event) => opinionPage.value = $event),
              "page-size": opinionSize,
              onCurrentChange: loadOpinions
            }, null, 8, ["total", "current-page"])
          ])) : createCommentVNode("", true)
        ])) : activeTab.value === "events" ? (openBlock(), createElementBlock("section", _hoisted_82, [
          createBaseVNode("div", _hoisted_83, "外网自动聚合：" + toDisplayString(eventAutoStatus.value?.enabled ? "已启用" : "已停用") + " · 调度已注册：" + toDisplayString(eventAutoStatus.value?.scheduler_registered ? "是" : "否") + " · 置信度阈值 " + toDisplayString(eventAutoStatus.value?.confidence_threshold ?? "-") + " · 时间窗口 " + toDisplayString(eventAutoStatus.value?.time_window_hours ?? "-") + " 小时", 1),
          createBaseVNode("div", _hoisted_84, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadEvents
            }, "刷新外网事件"),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: rebuildingEvents.value,
              onClick: rebuildEvents
            }, toDisplayString(rebuildingEvents.value ? "重建中..." : "候选 Dry-Run"), 9, _hoisted_85),
            _cache[58] || (_cache[58] = createBaseVNode("span", { class: "muted" }, "候选只进入外网事件表，必须人工确认后才形成正式事件", -1))
          ]),
          eventLoadError.value ? (openBlock(), createElementBlock("div", _hoisted_86, [
            createBaseVNode("span", null, "外网事件加载失败：" + toDisplayString(eventLoadError.value), 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadEvents
            }, "重试")
          ])) : createCommentVNode("", true),
          eventRunFailures.value.length ? (openBlock(), createElementBlock("div", _hoisted_87, [
            _cache[60] || (_cache[60] = createBaseVNode("strong", null, "外网事件运行失败", -1)),
            (openBlock(true), createElementBlock(Fragment, null, renderList(eventRunFailures.value, (run) => {
              return openBlock(), createElementBlock("div", {
                key: run.id,
                class: "event-failure-row"
              }, [
                _cache[59] || (_cache[59] = createBaseVNode("span", { class: "status failed" }, "失败", -1)),
                createBaseVNode("span", null, toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
                createBaseVNode("span", null, toDisplayString(run.error_message || "运行失败，未提供错误摘要"), 1)
              ]);
            }), 128))
          ])) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_88, [
            createBaseVNode("button", {
              class: normalizeClass(["tab", { active: eventSection.value === "candidates" }]),
              onClick: _cache[10] || (_cache[10] = ($event) => eventSection.value = "candidates")
            }, "事件候选", 2),
            createBaseVNode("button", {
              class: normalizeClass(["tab", { active: eventSection.value === "confirmed" }]),
              onClick: _cache[11] || (_cache[11] = ($event) => eventSection.value = "confirmed")
            }, "外网事件", 2)
          ]),
          eventSection.value === "candidates" ? (openBlock(), createElementBlock("div", _hoisted_89, [
            createBaseVNode("table", null, [
              _cache[62] || (_cache[62] = createBaseVNode("thead", null, [
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
                    createBaseVNode("td", _hoisted_90, toDisplayString(row.title || "无标题"), 1),
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
                    createBaseVNode("td", _hoisted_91, [
                      row.candidate_status === "candidate" ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "link-btn",
                        disabled: !unref(canConfirmEvents) || eventActionKey.value === `candidate-confirm-${row.id}`,
                        onClick: ($event) => confirmCandidate(row)
                      }, "确认", 8, _hoisted_92)) : createCommentVNode("", true),
                      row.candidate_status === "candidate" ? (openBlock(), createElementBlock("button", {
                        key: 1,
                        class: "link-btn danger",
                        disabled: !unref(canConfirmEvents) || eventActionKey.value === `candidate-reject-${row.id}`,
                        onClick: ($event) => rejectCandidate(row)
                      }, "拒绝", 8, _hoisted_93)) : createCommentVNode("", true)
                    ])
                  ]);
                }), 128)),
                !eventCandidates.value.length ? (openBlock(), createElementBlock("tr", _hoisted_94, [..._cache[61] || (_cache[61] = [
                  createBaseVNode("td", {
                    colspan: "8",
                    class: "empty"
                  }, "暂无外网事件候选", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])) : (openBlock(), createElementBlock("div", _hoisted_95, [
            createBaseVNode("table", null, [
              _cache[64] || (_cache[64] = createBaseVNode("thead", null, [
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
                    createBaseVNode("td", _hoisted_97, toDisplayString(row.title || "无标题"), 1),
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
                      }, "关闭", 8, _hoisted_98),
                      createBaseVNode("button", {
                        class: "link-btn",
                        disabled: !unref(canChangeEventStatus) || eventActionKey.value === `event-archive-${row.id}`,
                        onClick: withModifiers(($event) => archiveEvent(row), ["stop"])
                      }, "归档", 8, _hoisted_99)
                    ])
                  ], 8, _hoisted_96);
                }), 128)),
                !foreignEvents.value.length ? (openBlock(), createElementBlock("tr", _hoisted_100, [..._cache[63] || (_cache[63] = [
                  createBaseVNode("td", {
                    colspan: "12",
                    class: "empty"
                  }, "暂无已确认外网事件", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])),
          selectedForeignEvent.value ? (openBlock(), createElementBlock("article", _hoisted_101, [
            createBaseVNode("div", _hoisted_102, [
              _cache[66] || (_cache[66] = createBaseVNode("strong", null, "事件溯源", -1)),
              createBaseVNode("span", null, "确认来源：" + toDisplayString(zh(selectedForeignEvent.value.confirmation_source || "manual")), 1),
              createBaseVNode("span", null, "审核来源：" + toDisplayString(zh(selectedForeignEvent.value.auto_aggregation?.review_source)), 1),
              createBaseVNode("span", null, "置信度：" + toDisplayString(Math.round((selectedForeignEvent.value.confidence || 0) * 100)) + "%", 1),
              createBaseVNode("span", null, "文章数：" + toDisplayString(selectedForeignEvent.value.opinion_count) + " · 来源数：" + toDisplayString(selectedForeignEvent.value.source_count), 1),
              selectedForeignEvent.value.auto_aggregation?.evidence ? (openBlock(), createElementBlock("details", _hoisted_103, [
                _cache[65] || (_cache[65] = createBaseVNode("summary", null, "聚合证据", -1)),
                createBaseVNode("pre", null, toDisplayString(JSON.stringify(selectedForeignEvent.value.auto_aggregation.evidence, null, 2)), 1)
              ])) : createCommentVNode("", true)
            ]),
            createBaseVNode("div", _hoisted_104, [
              createBaseVNode("h3", null, toDisplayString(selectedForeignEvent.value.title), 1),
              createBaseVNode("div", _hoisted_105, [
                createBaseVNode("button", {
                  class: "link-btn",
                  disabled: !unref(canChangeEventStatus) || eventActionKey.value,
                  onClick: _cache[12] || (_cache[12] = ($event) => closeEvent(selectedForeignEvent.value))
                }, "关闭事件", 8, _hoisted_106),
                createBaseVNode("button", {
                  class: "link-btn",
                  disabled: !unref(canMergeEvents) || eventActionKey.value,
                  onClick: _cache[13] || (_cache[13] = ($event) => mergeEvent(selectedForeignEvent.value))
                }, "合并", 8, _hoisted_107),
                createBaseVNode("button", {
                  class: "link-btn",
                  disabled: !unref(canSplitEvents) || eventActionKey.value,
                  onClick: _cache[14] || (_cache[14] = ($event) => splitEvent(selectedForeignEvent.value))
                }, "拆分", 8, _hoisted_108),
                createBaseVNode("button", {
                  class: "link-btn",
                  onClick: _cache[15] || (_cache[15] = ($event) => selectedForeignEvent.value = null)
                }, "关闭详情")
              ])
            ]),
            createBaseVNode("p", _hoisted_109, toDisplayString(zh(selectedForeignEvent.value.language)) + " · " + toDisplayString(zh(selectedForeignEvent.value.event_status)) + " · " + toDisplayString(selectedForeignEvent.value.opinion_count) + " 篇文章", 1),
            createBaseVNode("div", _hoisted_110, [
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
                createBaseVNode("span", _hoisted_111, toDisplayString(opinion.source_name_snapshot) + " · " + toDisplayString(formatTime(opinion.published_at)), 1),
                createBaseVNode("a", {
                  href: opinion.url,
                  target: "_blank",
                  rel: "noreferrer",
                  class: "original"
                }, "原文", 8, _hoisted_112)
              ]);
            }), 128))
          ])) : createCommentVNode("", true)
        ])) : activeTab.value === "alerts" ? (openBlock(), createElementBlock("section", _hoisted_113, [
          createBaseVNode("div", _hoisted_114, "外网自动告警评估：" + toDisplayString(alertAutoStatus.value?.enabled ? "已启用" : "已停用") + " · 调度已注册：" + toDisplayString(alertAutoStatus.value?.scheduler_registered ? "是" : "否") + " · 外部通知：" + toDisplayString(alertAutoStatus.value?.external_notifications_enabled ? "已启用" : "已停用"), 1),
          createBaseVNode("div", _hoisted_115, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadAlerts
            }, "刷新外网告警"),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: alertEvaluating.value || !unref(canEvaluateAlerts),
              onClick: evaluateAlerts
            }, toDisplayString(alertEvaluating.value ? "评估中..." : "手动 Dry-Run"), 9, _hoisted_116),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => alertFilters.status = $event),
              class: "input",
              onChange: loadAlerts
            }, [..._cache[67] || (_cache[67] = [
              createStaticVNode('<option value="" data-v-5a9f26eb>全部状态</option><option value="triggered" data-v-5a9f26eb>待处理</option><option value="acknowledged" data-v-5a9f26eb>已确认</option><option value="resolved" data-v-5a9f26eb>已解决</option><option value="suppressed" data-v-5a9f26eb>已抑制</option><option value="failed" data-v-5a9f26eb>失败</option>', 6)
            ])], 544), [
              [vModelSelect, alertFilters.status]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => alertFilters.severity = $event),
              class: "input",
              onChange: loadAlerts
            }, [..._cache[68] || (_cache[68] = [
              createStaticVNode('<option value="" data-v-5a9f26eb>全部严重度</option><option value="low" data-v-5a9f26eb>低</option><option value="medium" data-v-5a9f26eb>中</option><option value="high" data-v-5a9f26eb>高</option><option value="critical" data-v-5a9f26eb>紧急</option>', 5)
            ])], 544), [
              [vModelSelect, alertFilters.severity]
            ]),
            _cache[69] || (_cache[69] = createBaseVNode("span", { class: "muted" }, "告警评估默认关闭 · 外部通知默认关闭 · 当前仅保存站内记录", -1))
          ]),
          _cache[74] || (_cache[74] = createBaseVNode("div", { class: "alert-scope-note" }, " 外网告警只读取外网风险和已确认外网事件；不会进入国内告警、Dashboard、地图、热词或事件链路。 ", -1)),
          alertLoadError.value ? (openBlock(), createElementBlock("div", _hoisted_117, [
            createBaseVNode("span", null, "外网告警加载失败：" + toDisplayString(alertLoadError.value), 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadAlerts
            }, "重试")
          ])) : createCommentVNode("", true),
          alertRunFailures.value.length ? (openBlock(), createElementBlock("div", _hoisted_118, [
            _cache[71] || (_cache[71] = createBaseVNode("strong", null, "外网告警评估失败", -1)),
            (openBlock(true), createElementBlock(Fragment, null, renderList(alertRunFailures.value, (run) => {
              return openBlock(), createElementBlock("div", {
                key: run.id,
                class: "alert-failure-row"
              }, [
                _cache[70] || (_cache[70] = createBaseVNode("span", { class: "status failed" }, "失败", -1)),
                createBaseVNode("span", null, toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
                createBaseVNode("span", null, toDisplayString(run.error_message || "评估失败，未提供错误摘要"), 1)
              ]);
            }), 128))
          ])) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_119, [
            createBaseVNode("table", null, [
              _cache[73] || (_cache[73] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "告警标题"),
                  createBaseVNode("th", null, "严重度"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "触发规则"),
                  createBaseVNode("th", null, "关联文章"),
                  createBaseVNode("th", null, "关联事件"),
                  createBaseVNode("th", null, "风险分/等级"),
                  createBaseVNode("th", null, "触发时间"),
                  createBaseVNode("th", null, "确认时间"),
                  createBaseVNode("th", null, "解决时间"),
                  createBaseVNode("th", null, "抑制"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(foreignAlerts.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", _hoisted_120, [
                      row.foreign_opinion_id || row.foreign_event_id ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        type: "button",
                        class: "alert-title alert-title-link",
                        title: "查看详情：" + (row.title || "无标题告警"),
                        onClick: withModifiers(($event) => openAlertTarget(row), ["stop"]),
                        onKeydown: [
                          withKeys(withModifiers(($event) => openAlertTarget(row), ["prevent"]), ["enter"]),
                          withKeys(withModifiers(($event) => openAlertTarget(row), ["prevent"]), ["space"])
                        ]
                      }, toDisplayString(row.title || "无标题告警"), 41, _hoisted_121)) : (openBlock(), createElementBlock("strong", _hoisted_122, toDisplayString(row.title || "无标题告警"), 1)),
                      createBaseVNode("div", _hoisted_123, toDisplayString(row.message), 1)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { failed: row.severity === "critical" || row.severity === "high" }])
                      }, toDisplayString(zh(row.severity)), 3)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.status === "acknowledged" || row.status === "resolved", failed: row.status === "failed" || row.status === "suppressed" }])
                      }, toDisplayString(zh(row.status)), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.rule_snapshot?.name || "规则 #" + row.rule_id), 1),
                    createBaseVNode("td", _hoisted_124, [
                      row.foreign_opinion_id ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "link-btn",
                        title: "查看关联舆情详情",
                        onClick: withModifiers(($event) => openOpinion(row.foreign_opinion_id), ["stop"])
                      }, toDisplayString(row.opinion_title_snapshot || "#" + row.foreign_opinion_id), 9, _hoisted_125)) : (openBlock(), createElementBlock("span", _hoisted_126, "-"))
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.event_title_snapshot || (row.foreign_event_id ? "#" + row.foreign_event_id : "-")), 1),
                    createBaseVNode("td", null, toDisplayString(row.risk_score === null ? "-" : row.risk_score) + " / " + toDisplayString(zh(row.risk_level)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.triggered_at)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.acknowledged_at)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.resolved_at)), 1),
                    createBaseVNode("td", null, toDisplayString(row.suppressed_at ? formatTime(row.suppressed_at) : "-"), 1),
                    createBaseVNode("td", _hoisted_127, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        onClick: withModifiers(($event) => loadAlertActions(row), ["stop"])
                      }, "处置历史", 8, _hoisted_128),
                      row.status === "triggered" ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "link-btn",
                        disabled: !unref(canAcknowledgeAlerts) || alertActionBusyId.value === row.id,
                        onClick: withModifiers(($event) => handleForeignAlert(row, "acknowledge"), ["stop"])
                      }, "确认", 8, _hoisted_129)) : createCommentVNode("", true),
                      row.status === "triggered" || row.status === "acknowledged" ? (openBlock(), createElementBlock("button", {
                        key: 1,
                        class: "link-btn",
                        disabled: !unref(canResolveAlerts) || alertActionBusyId.value === row.id,
                        onClick: withModifiers(($event) => handleForeignAlert(row, "resolve"), ["stop"])
                      }, "解决", 8, _hoisted_130)) : createCommentVNode("", true),
                      row.status === "triggered" || row.status === "acknowledged" ? (openBlock(), createElementBlock("button", {
                        key: 2,
                        class: "link-btn danger",
                        disabled: !unref(canSuppressAlerts) || alertActionBusyId.value === row.id,
                        onClick: withModifiers(($event) => handleForeignAlert(row, "suppress"), ["stop"])
                      }, "抑制", 8, _hoisted_131)) : createCommentVNode("", true)
                    ])
                  ]);
                }), 128)),
                !foreignAlerts.value.length ? (openBlock(), createElementBlock("tr", _hoisted_132, [..._cache[72] || (_cache[72] = [
                  createBaseVNode("td", {
                    colspan: "12",
                    class: "empty"
                  }, "暂无外网告警记录", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])
        ])) : activeTab.value === "alertRules" ? (openBlock(), createElementBlock("section", _hoisted_133, [
          createBaseVNode("div", { class: "toolbar" }, [
            createBaseVNode("button", {
              class: "btn btn-primary",
              onClick: beginAlertRuleCreate
            }, "新增告警规则"),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadAlertRules
            }, "刷新规则"),
            _cache[75] || (_cache[75] = createBaseVNode("span", { class: "muted" }, "外网规则独立管理；新规则保存后默认停用。", -1))
          ]),
          createBaseVNode("div", _hoisted_134, [
            createBaseVNode("table", null, [
              _cache[77] || (_cache[77] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "名称"),
                  createBaseVNode("th", null, "类型"),
                  createBaseVNode("th", null, "条件"),
                  createBaseVNode("th", null, "严重度"),
                  createBaseVNode("th", null, "冷却"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(alertRules.value, (rule) => {
                  return openBlock(), createElementBlock("tr", {
                    key: rule.id
                  }, [
                    createBaseVNode("td", null, toDisplayString(rule.name), 1),
                    createBaseVNode("td", null, toDisplayString(zh(rule.rule_type)), 1),
                    createBaseVNode("td", null, toDisplayString(JSON.stringify(rule.conditions)), 1),
                    createBaseVNode("td", null, toDisplayString(zh(rule.severity)), 1),
                    createBaseVNode("td", null, toDisplayString(rule.cooldown_seconds) + " 秒", 1),
                    createBaseVNode("td", null, toDisplayString(rule.is_enabled ? "启用" : "停用"), 1),
                    createBaseVNode("td", _hoisted_135, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        onClick: ($event) => editAlertRule(rule)
                      }, "编辑", 8, _hoisted_136),
                      rule.is_enabled ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "link-btn",
                        disabled: alertRuleBusyId.value === rule.id,
                        onClick: ($event) => disableAlertRule(rule)
                      }, "停用", 8, _hoisted_137)) : (openBlock(), createElementBlock("button", {
                        key: 1,
                        class: "link-btn",
                        disabled: alertRuleBusyId.value === rule.id || !unref(canEnableAlertRules),
                        onClick: ($event) => enableAlertRule(rule)
                      }, "启用", 8, _hoisted_138)),
                      !rule.is_enabled ? (openBlock(), createElementBlock("button", {
                        key: 2,
                        class: "link-btn danger",
                        disabled: alertRuleBusyId.value === rule.id,
                        onClick: ($event) => deleteAlertRule(rule)
                      }, "删除", 8, _hoisted_139)) : createCommentVNode("", true)
                    ])
                  ]);
                }), 128)),
                !alertRules.value.length ? (openBlock(), createElementBlock("tr", _hoisted_140, [..._cache[76] || (_cache[76] = [
                  createBaseVNode("td", {
                    colspan: "7",
                    class: "empty"
                  }, "暂无外网告警规则", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])
        ])) : createCommentVNode("", true),
        historyAlert.value ? (openBlock(), createElementBlock("div", {
          key: 5,
          class: "detail-mask",
          onClick: _cache[19] || (_cache[19] = withModifiers(($event) => historyAlert.value = null, ["self"]))
        }, [
          createBaseVNode("article", _hoisted_141, [
            createBaseVNode("button", {
              class: "close",
              title: "关闭处置历史",
              onClick: _cache[18] || (_cache[18] = ($event) => historyAlert.value = null)
            }, "×"),
            _cache[78] || (_cache[78] = createBaseVNode("h3", null, "外网告警处置历史", -1)),
            createBaseVNode("p", _hoisted_142, toDisplayString(historyAlert.value.title || "告警 #" + historyAlert.value.id) + " · 当前状态：" + toDisplayString(zh(historyAlert.value.status)), 1),
            alertActionsLoading.value ? (openBlock(), createElementBlock("div", _hoisted_143, "处置历史加载中...")) : !alertActions.value.length ? (openBlock(), createElementBlock("div", _hoisted_144, "暂无处置历史")) : (openBlock(), createElementBlock("div", _hoisted_145, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(alertActions.value, (action) => {
                return openBlock(), createElementBlock("div", {
                  key: action.id,
                  class: "alert-action-row"
                }, [
                  createBaseVNode("strong", null, toDisplayString(actionLabel(action.action_type)), 1),
                  createBaseVNode("span", null, toDisplayString(zh(action.previous_status)) + " → " + toDisplayString(zh(action.new_status)), 1),
                  createBaseVNode("span", null, toDisplayString(action.note), 1),
                  createBaseVNode("span", _hoisted_146, "操作人 #" + toDisplayString(action.actor_id ?? "-") + " · " + toDisplayString(formatTime(action.created_at)), 1)
                ]);
              }), 128))
            ]))
          ])
        ])) : createCommentVNode("", true),
        alertRuleEditorVisible.value ? (openBlock(), createElementBlock("div", {
          key: 6,
          class: "detail-mask",
          onClick: _cache[29] || (_cache[29] = withModifiers(($event) => alertRuleEditorVisible.value = false, ["self"]))
        }, [
          createBaseVNode("article", _hoisted_147, [
            createBaseVNode("button", {
              class: "close",
              title: "关闭规则编辑",
              onClick: _cache[20] || (_cache[20] = ($event) => alertRuleEditorVisible.value = false)
            }, "×"),
            createBaseVNode("h3", null, toDisplayString(alertRuleEditingId.value ? "编辑外网告警规则" : "新增外网告警规则"), 1),
            createBaseVNode("label", null, [
              _cache[79] || (_cache[79] = createTextVNode("规则名称", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[21] || (_cache[21] = ($event) => alertRuleDraft.name = $event),
                class: "input",
                placeholder: "规则名称"
              }, null, 512), [
                [vModelText, alertRuleDraft.name]
              ])
            ]),
            createBaseVNode("label", null, [
              _cache[81] || (_cache[81] = createTextVNode("规则类型", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[22] || (_cache[22] = ($event) => alertRuleDraft.rule_type = $event),
                class: "input"
              }, [..._cache[80] || (_cache[80] = [
                createStaticVNode('<option value="risk_score" data-v-5a9f26eb>风险分</option><option value="risk_level" data-v-5a9f26eb>风险等级</option><option value="risk_category" data-v-5a9f26eb>风险类别</option><option value="confirmed_event" data-v-5a9f26eb>确认事件</option><option value="keyword_combo" data-v-5a9f26eb>关键词组合</option>', 5)
              ])], 512), [
                [vModelSelect, alertRuleDraft.rule_type]
              ])
            ]),
            createBaseVNode("label", null, [
              _cache[82] || (_cache[82] = createTextVNode("风险阈值或条件", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[23] || (_cache[23] = ($event) => alertRuleDraft.conditionsText = $event),
                class: "input",
                placeholder: '条件 JSON，例如 {"threshold":80}'
              }, null, 512), [
                [vModelText, alertRuleDraft.conditionsText]
              ])
            ]),
            createBaseVNode("label", null, [
              _cache[84] || (_cache[84] = createTextVNode("严重等级", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[24] || (_cache[24] = ($event) => alertRuleDraft.severity = $event),
                class: "input"
              }, [..._cache[83] || (_cache[83] = [
                createBaseVNode("option", { value: "low" }, "低", -1),
                createBaseVNode("option", { value: "medium" }, "中", -1),
                createBaseVNode("option", { value: "high" }, "高", -1),
                createBaseVNode("option", { value: "critical" }, "紧急", -1)
              ])], 512), [
                [vModelSelect, alertRuleDraft.severity]
              ])
            ]),
            createBaseVNode("label", null, [
              _cache[85] || (_cache[85] = createTextVNode("冷却时间", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[25] || (_cache[25] = ($event) => alertRuleDraft.cooldown_seconds = $event),
                class: "input number-input",
                type: "number",
                min: "0"
              }, null, 512), [
                [
                  vModelText,
                  alertRuleDraft.cooldown_seconds,
                  void 0,
                  { number: true }
                ]
              ])
            ]),
            createBaseVNode("label", null, [
              _cache[86] || (_cache[86] = createTextVNode("规则说明", -1)),
              withDirectives(createBaseVNode("textarea", {
                "onUpdate:modelValue": _cache[26] || (_cache[26] = ($event) => alertRuleDraft.description = $event),
                class: "input",
                rows: "3",
                placeholder: "规则用途和处置说明"
              }, null, 512), [
                [vModelText, alertRuleDraft.description]
              ])
            ]),
            createBaseVNode("label", _hoisted_148, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[27] || (_cache[27] = ($event) => alertRuleDraft.is_enabled = $event),
                type: "checkbox",
                disabled: !alertRuleEditingId.value || !unref(canEnableAlertRules)
              }, null, 8, _hoisted_149), [
                [vModelCheckbox, alertRuleDraft.is_enabled]
              ]),
              _cache[87] || (_cache[87] = createTextVNode(" 编辑时启用状态（新规则默认停用，启用仍需外网启用权限）", -1))
            ]),
            createBaseVNode("div", _hoisted_150, [
              _cache[88] || (_cache[88] = createBaseVNode("strong", null, "规则预览", -1)),
              createBaseVNode("pre", null, toDisplayString(rulePreview.value), 1)
            ]),
            createBaseVNode("div", _hoisted_151, [
              createBaseVNode("button", {
                class: "btn btn-secondary",
                onClick: _cache[28] || (_cache[28] = ($event) => alertRuleEditorVisible.value = false)
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-primary",
                disabled: alertRuleSaving.value,
                onClick: createAlertRule
              }, toDisplayString(alertRuleSaving.value ? "保存中..." : "保存规则"), 9, _hoisted_152)
            ])
          ])
        ])) : createCommentVNode("", true),
        createVNode(ForeignOpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[30] || (_cache[30] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const ForeignWorkspace = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-5a9f26eb"]]);

export { ForeignWorkspace as default };
