import { r as ref, d as defineComponent, z as usePermission, C as onMounted, y as resolveComponent, o as openBlock, c as createElementBlock, a as createBaseVNode, n as normalizeClass, m as createVNode, p as withCtx, H as unref, q as createBlock, e as createTextVNode, s as createCommentVNode, F as Fragment, i as renderList, w as withDirectives, O as vModelCheckbox, t as toDisplayString, R as _sfc_main$3, S as isRef, j as computed, g as api, Q as ElMessageBox, E as ElMessage, _ as _export_sfc, f as reactive, P as withModifiers, N as vModelSelect, v as vModelText, L as useRoute, h as useRouter, G as onBeforeUnmount, B as resolveDirective, b as withKeys, T as createStaticVNode, k as normalizeStyle } from './index-BNJql6Jy.js';
import { F as ForeignOpinionDetailModal } from './ForeignOpinionDetailModal-pn0PyzDI.js';

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
function formatTime(value) {
  return value ? new Date(value).toLocaleString() : "-";
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
function useForeignDetailState() {
  const detailVisible = ref(false);
  const detailId = ref(null);
  function openOpinion(id) {
    detailId.value = id;
    detailVisible.value = true;
  }
  return { detailVisible, detailId, openOpinion };
}

const _hoisted_1$2 = { key: 0 };
const _hoisted_2$2 = { class: "review-filter" };
const _hoisted_3$2 = {
  key: 0,
  class: "review-batch"
};
const _hoisted_4$2 = ["disabled"];
const _hoisted_5$2 = { class: "card table-card review-table-card" };
const _hoisted_6$2 = { class: "tbl-scroll" };
const _hoisted_7$2 = { class: "tbl review-table" };
const _hoisted_8$2 = ["checked"];
const _hoisted_9$2 = ["value"];
const _hoisted_10$2 = { class: "review-title-cell" };
const _hoisted_11$2 = ["title", "onClick"];
const _hoisted_12$2 = { class: "muted" };
const _hoisted_13$2 = { class: "risk-num" };
const _hoisted_14$2 = { class: "risk-num" };
const _hoisted_15$2 = { class: "risk-num" };
const _hoisted_16$2 = { class: "risk-num" };
const _hoisted_17$2 = { class: "col-center" };
const _hoisted_18$2 = {
  key: 0,
  class: "pill pill-green"
};
const _hoisted_19$2 = { key: 1 };
const _hoisted_20$2 = { class: "col-center" };
const _hoisted_21$1 = {
  key: 0,
  class: "pill pill-green"
};
const _hoisted_22$1 = { key: 1 };
const _hoisted_23$1 = {
  key: 0,
  class: "review-op-cell"
};
const _hoisted_24$1 = ["disabled", "onClick"];
const _hoisted_25$1 = ["disabled", "onClick"];
const _hoisted_26$1 = ["disabled"];
const _hoisted_27$1 = {
  key: 1,
  class: "muted"
};
const _hoisted_28$1 = { key: 0 };
const _hoisted_29$1 = {
  colspan: "12",
  class: "empty-row"
};
const _hoisted_30$1 = {
  key: 0,
  class: "pager"
};
const reviewSize = 10;
const _sfc_main$2 = /* @__PURE__ */ defineComponent({
  __name: "ForeignAIReviewView",
  setup(__props) {
    const { hasPermission } = usePermission();
    const { openOpinion, detailVisible, detailId } = useForeignDetailState();
    const riskSource = ref("current");
    function setRiskSource(v) {
      riskSource.value = v;
    }
    const manualReviews = ref([]);
    const reviewStatusFilter = ref("pending_review");
    const reviewActionId = ref(null);
    const selectedReviewIds = ref([]);
    const reviewPage = ref(1);
    const reviewTotal = ref(0);
    const canReviewAI = hasPermission("foreign:ai:review:read");
    const canReadEventReview = hasPermission("foreign:events:review:read");
    const canReadAlertReview = hasPermission("foreign:alerts:review:read");
    const canReadReviewSection = computed(() => canReviewAI || canReadEventReview || canReadAlertReview);
    const canConfirmEventReview = hasPermission("foreign:events:review:confirm");
    const canConfirmAlertReview = hasPermission("foreign:alerts:review:confirm");
    const canRejectAIReview = hasPermission("foreign:ai:review:reject");
    const canCompleteReview = hasPermission("foreign:ai:review:complete");
    const canFullConfirmAI = hasPermission("foreign:ai:full-confirm");
    async function loadManualReviews() {
      try {
        const params = { page: reviewPage.value, size: reviewSize };
        if (reviewStatusFilter.value && reviewStatusFilter.value !== "all") params.status = reviewStatusFilter.value;
        const { data } = await api.get("/foreign/ai-analysis/reviews", { params });
        manualReviews.value = data.items || [];
        reviewTotal.value = data.total || 0;
        selectedReviewIds.value = selectedReviewIds.value.filter((id) => manualReviews.value.some((row) => row.id === id));
      } catch {
        manualReviews.value = [];
      }
    }
    function toggleAllReviews(event) {
      selectedReviewIds.value = event.target.checked ? manualReviews.value.map((row) => row.id) : [];
    }
    function setReviewFilter(f) {
      reviewStatusFilter.value = f;
      reviewPage.value = 1;
      loadManualReviews();
    }
    function reviewResultSummary(body) {
      if (!body) return "";
      const parts = [];
      if (body.message) parts.push(body.message.replace(/[。.．]\s*$/, ""));
      const er = body.event_result;
      const ar = body.alert_result;
      if (er && (er.created_count || er.existing_count || er.skipped_count)) {
        parts.push(`事件：新建 ${er.created_count ?? 0}，已有 ${er.existing_count ?? 0}，跳过 ${er.skipped_count ?? 0}`);
      }
      if (ar && (ar.matched || ar.created_count || ar.deduplicated_count)) {
        const bits = [`新建 ${ar.created_count ?? 0} 条`];
        if (ar.deduplicated_count) bits.push(`去重 ${ar.deduplicated_count} 条`);
        parts.push(`预警：${bits.join("，")}`);
      }
      if (body.idempotent) parts.push("（幂等：本次未产生新正式记录）");
      return parts.join("；");
    }
    const REVIEW_DECISION_HINT = {
      use_ai_display: "将把该舆情展示用的风险分切换为 AI 风险分（不改变正式规则风险，仅影响展示）。此操作不可撤销。",
      keep_rule: "将保留系统规则风险分作为展示用风险。此操作不可撤销。",
      confirm_event_change: "将为该舆情簇创建正式外网事件并生成正式记录。此操作不可撤销。",
      confirm_alert_change: "将依据 AI 预警候选生成正式外网预警（站内告警，不发送外部通知）。此操作不可撤销。",
      reject_change: "将驳回该条复核的全部 AI 变更（状态置为已驳回），不再生成正式事件或预警。此操作不可撤销。",
      complete_review: "完成复核后该条舆情将进入「已确认」。仅关闭复核，不会自动创建事件或预警。"
    };
    async function decideReview(review, decision) {
      reviewActionId.value = review.id;
      const hint = REVIEW_DECISION_HINT[decision] || "确认执行该复核操作？";
      let reason = "Foreign AI review";
      if (decision === "complete_review") {
        try {
          const p = await ElMessageBox.prompt("可填写完成复核的说明（选填）：", "完成复核", {
            inputType: "textarea",
            confirmButtonText: "确认完成",
            cancelButtonText: "取消"
          });
          reason = (p.value || "").trim() || reason;
        } catch {
          reviewActionId.value = null;
          return;
        }
      } else {
        try {
          await ElMessageBox.confirm(hint, "人工复核操作确认", { type: "warning", confirmButtonText: "确认", cancelButtonText: "取消" });
        } catch {
          reviewActionId.value = null;
          return;
        }
      }
      try {
        const { data } = await api.post(`/foreign/ai-analysis/reviews/${review.id}/decision`, { decision, reason });
        const updated = data?.review;
        if (updated && updated.review_status !== "pending_review") {
          manualReviews.value = manualReviews.value.filter((r) => r.id !== review.id);
          if (reviewTotal.value > 0) reviewTotal.value -= 1;
        } else if (updated) {
          const idx = manualReviews.value.findIndex((r) => r.id === review.id);
          if (idx >= 0) manualReviews.value[idx] = { ...manualReviews.value[idx], ...updated };
        } else {
          await loadManualReviews();
        }
        const summary = reviewResultSummary(data);
        if (data?.idempotent) ElMessage.info(summary || "该复核记录已处理，本次未产生新的正式事件或预警");
        else if (summary) ElMessage.success(summary);
        else ElMessage.success("人工复核已完成");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "人工复核失败");
      } finally {
        reviewActionId.value = null;
      }
    }
    async function batchDecideReviews(decision, confirmAll = false) {
      if (!confirmAll && !selectedReviewIds.value.length || !manualReviews.value.length || reviewActionId.value) return;
      const hint = REVIEW_DECISION_HINT[decision] || "确认批量执行该复核操作？";
      const scope = confirmAll ? "全部待复核结果" : `选中的 ${selectedReviewIds.value.length} 条待复核结果`;
      try {
        await ElMessageBox.confirm(`确认对${scope}执行：${hint}`, "批量复核操作确认", { type: "warning", confirmButtonText: "确认", cancelButtonText: "取消" });
      } catch {
        return;
      }
      reviewActionId.value = -1;
      try {
        const { data } = await api.post("/foreign/ai-analysis/reviews/batch", { decision, confirm_all: confirmAll, review_ids: confirmAll ? void 0 : selectedReviewIds.value, reason: "Foreign batch review" });
        await loadManualReviews();
        selectedReviewIds.value = [];
        const items = data?.items || [];
        const processed = items.length;
        let eventsCreated = 0, alertsCreated = 0, existing = 0, skipped = 0, missed = 0;
        for (const it of items) {
          const er = it.event_result || {};
          const ar = it.alert_result || {};
          eventsCreated += er.created_count ?? 0;
          alertsCreated += ar.created_count ?? 0;
          existing += (er.existing_count ?? 0) + (ar.deduplicated_count ?? 0);
          skipped += er.skipped_count ?? 0;
          if (it.idempotent) skipped += 1;
          if (it.review_status === "pending_review") missed += 1;
        }
        if (data?.transaction === "committed") {
          ElMessage.success(`批量复核完成：共 ${processed} 条，事件新建 ${eventsCreated}，预警新建 ${alertsCreated}，既有/去重 ${existing}，跳过/幂等 ${skipped}` + (missed ? `，未处理 ${missed}` : ""));
        } else {
          ElMessage.warning("批量复核部分完成：事务未提交，详见列表");
        }
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "批量复核失败");
      } finally {
        reviewActionId.value = null;
      }
    }
    function onBatchCommand(cmd) {
      if (cmd === "confirm_event_all") return batchDecideReviews("confirm_event_change", true);
      if (cmd === "reject_all") return batchDecideReviews("reject_change", true);
      return batchDecideReviews(cmd);
    }
    function statusPill(s) {
      return { pending_review: "pill-orange", confirmed: "pill-green", rejected: "pill-red", superseded: "pill-gray" }[s] || "pill-gray";
    }
    onMounted(() => {
      loadManualReviews();
    });
    return (_ctx, _cache) => {
      const _component_el_dropdown_item = resolveComponent("el-dropdown-item");
      const _component_el_dropdown_menu = resolveComponent("el-dropdown-menu");
      const _component_el_dropdown = resolveComponent("el-dropdown");
      return canReadReviewSection.value ? (openBlock(), createElementBlock("div", _hoisted_1$2, [
        createBaseVNode("div", _hoisted_2$2, [
          createBaseVNode("button", {
            class: normalizeClass(["seg", { active: reviewStatusFilter.value === "pending_review" }]),
            onClick: _cache[0] || (_cache[0] = ($event) => setReviewFilter("pending_review"))
          }, "待复核", 2),
          createBaseVNode("button", {
            class: normalizeClass(["seg", { active: reviewStatusFilter.value === "confirmed" }]),
            onClick: _cache[1] || (_cache[1] = ($event) => setReviewFilter("confirmed"))
          }, "已确认", 2),
          createBaseVNode("button", {
            class: normalizeClass(["seg", { active: reviewStatusFilter.value === "rejected" }]),
            onClick: _cache[2] || (_cache[2] = ($event) => setReviewFilter("rejected"))
          }, "已驳回", 2),
          createBaseVNode("button", {
            class: normalizeClass(["seg", { active: reviewStatusFilter.value === "all" }]),
            onClick: _cache[3] || (_cache[3] = ($event) => setReviewFilter("all"))
          }, "全部", 2),
          _cache[14] || (_cache[14] = createBaseVNode("span", { class: "muted review-filter-tip" }, "操作后不会丢失：已处理的舆情可在「已确认 / 已驳回 / 全部」中回看与追溯", -1)),
          reviewStatusFilter.value === "pending_review" ? (openBlock(), createElementBlock("div", _hoisted_3$2, [
            createVNode(_component_el_dropdown, {
              trigger: "click",
              disabled: !!reviewActionId.value,
              onCommand: onBatchCommand
            }, {
              dropdown: withCtx(() => [
                createVNode(_component_el_dropdown_menu, null, {
                  default: withCtx(() => [
                    unref(canReviewAI) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                      key: 0,
                      command: "use_ai_display",
                      disabled: !selectedReviewIds.value.length
                    }, {
                      default: withCtx(() => [..._cache[7] || (_cache[7] = [
                        createTextVNode("确认选中采用 AI 展示", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"])) : createCommentVNode("", true),
                    unref(canConfirmEventReview) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                      key: 1,
                      command: "confirm_event_change",
                      disabled: !selectedReviewIds.value.length
                    }, {
                      default: withCtx(() => [..._cache[8] || (_cache[8] = [
                        createTextVNode("确认选中事件影响", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"])) : createCommentVNode("", true),
                    unref(canConfirmAlertReview) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                      key: 2,
                      command: "confirm_alert_change",
                      disabled: !selectedReviewIds.value.length
                    }, {
                      default: withCtx(() => [..._cache[9] || (_cache[9] = [
                        createTextVNode("确认选中预警影响", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"])) : createCommentVNode("", true),
                    unref(canRejectAIReview) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                      key: 3,
                      command: "reject_change",
                      disabled: !selectedReviewIds.value.length
                    }, {
                      default: withCtx(() => [..._cache[10] || (_cache[10] = [
                        createTextVNode("驳回选中（全部 AI 变更）", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"])) : createCommentVNode("", true),
                    unref(canFullConfirmAI) && unref(canConfirmEventReview) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                      key: 4,
                      command: "confirm_event_all",
                      divided: "",
                      disabled: !manualReviews.value.length
                    }, {
                      default: withCtx(() => [..._cache[11] || (_cache[11] = [
                        createTextVNode("全量确认事件", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"])) : createCommentVNode("", true),
                    unref(canFullConfirmAI) && unref(canRejectAIReview) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                      key: 5,
                      command: "reject_all",
                      disabled: !manualReviews.value.length
                    }, {
                      default: withCtx(() => [..._cache[12] || (_cache[12] = [
                        createTextVNode("全量驳回", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"])) : createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              default: withCtx(() => [
                createBaseVNode("button", {
                  class: "btn btn-primary",
                  disabled: !!reviewActionId.value
                }, "批量操作 ▾", 8, _hoisted_4$2)
              ]),
              _: 1
            }, 8, ["disabled"]),
            _cache[13] || (_cache[13] = createBaseVNode("span", { class: "muted review-toolbar-hint" }, "先勾选左侧复选框，再从「批量操作」中选择动作", -1))
          ])) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_5$2, [
          createBaseVNode("div", _hoisted_6$2, [
            createBaseVNode("table", _hoisted_7$2, [
              createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, [
                    createBaseVNode("input", {
                      type: "checkbox",
                      checked: selectedReviewIds.value.length === manualReviews.value.length && manualReviews.value.length > 0,
                      onChange: toggleAllReviews
                    }, null, 40, _hoisted_8$2)
                  ]),
                  _cache[15] || (_cache[15] = createBaseVNode("th", null, "舆情标题", -1)),
                  _cache[16] || (_cache[16] = createBaseVNode("th", null, "舆情 ID", -1)),
                  _cache[17] || (_cache[17] = createBaseVNode("th", null, "规则风险", -1)),
                  _cache[18] || (_cache[18] = createBaseVNode("th", null, "AI 风险", -1)),
                  _cache[19] || (_cache[19] = createBaseVNode("th", null, "事件影响", -1)),
                  _cache[20] || (_cache[20] = createBaseVNode("th", null, "预警影响", -1)),
                  _cache[21] || (_cache[21] = createBaseVNode("th", null, "状态", -1)),
                  _cache[22] || (_cache[22] = createBaseVNode("th", null, "决策", -1)),
                  _cache[23] || (_cache[23] = createBaseVNode("th", null, "操作人", -1)),
                  _cache[24] || (_cache[24] = createBaseVNode("th", null, "操作时间", -1)),
                  _cache[25] || (_cache[25] = createBaseVNode("th", null, "操作", -1))
                ])
              ]),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(manualReviews.value, (review) => {
                  return openBlock(), createElementBlock("tr", {
                    key: review.id
                  }, [
                    createBaseVNode("td", null, [
                      withDirectives(createBaseVNode("input", {
                        "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => selectedReviewIds.value = $event),
                        type: "checkbox",
                        value: review.id
                      }, null, 8, _hoisted_9$2), [
                        [vModelCheckbox, selectedReviewIds.value]
                      ])
                    ]),
                    createBaseVNode("td", _hoisted_10$2, [
                      createBaseVNode("button", {
                        class: "title-link",
                        type: "button",
                        title: review.opinion_title || "打开舆情详情",
                        onClick: ($event) => unref(openOpinion)(review.foreign_opinion_id)
                      }, toDisplayString(review.opinion_title || `舆情 #${review.foreign_opinion_id}`), 9, _hoisted_11$2),
                      createBaseVNode("span", _hoisted_12$2, toDisplayString(review.opinion_source || "-"), 1)
                    ]),
                    createBaseVNode("td", null, toDisplayString(review.foreign_opinion_id), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", _hoisted_13$2, toDisplayString(review.rule_risk_snapshot?.risk_score ?? "-"), 1),
                      _cache[26] || (_cache[26] = createTextVNode(" / ", -1)),
                      createBaseVNode("span", _hoisted_14$2, toDisplayString(unref(zh)(review.rule_risk_snapshot?.risk_level)), 1)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", _hoisted_15$2, toDisplayString(review.ai_risk_snapshot?.risk_score ?? "-"), 1),
                      _cache[27] || (_cache[27] = createTextVNode(" / ", -1)),
                      createBaseVNode("span", _hoisted_16$2, toDisplayString(unref(zh)(review.ai_risk_snapshot?.risk_level)), 1)
                    ]),
                    createBaseVNode("td", _hoisted_17$2, [
                      review.event_review_status === "confirmed" ? (openBlock(), createElementBlock("span", _hoisted_18$2, "已确认")) : (openBlock(), createElementBlock("span", _hoisted_19$2, toDisplayString(review.event_candidate_count || review.event_preview?.candidate_count || 0) + " 候选", 1))
                    ]),
                    createBaseVNode("td", _hoisted_20$2, [
                      review.alert_review_status === "confirmed" ? (openBlock(), createElementBlock("span", _hoisted_21$1, "已确认")) : (openBlock(), createElementBlock("span", _hoisted_22$1, toDisplayString(review.alert_candidate_count || review.alert_preview?.candidate_count || 0) + " 候选", 1))
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", statusPill(review.review_status)])
                      }, toDisplayString(unref(zh)(review.review_status)), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(unref(zh)(review.review_decision)), 1),
                    createBaseVNode("td", null, toDisplayString(review.reviewed_by_name || (review.reviewed_by ? "#" + review.reviewed_by : "-")), 1),
                    createBaseVNode("td", null, toDisplayString(review.reviewed_at ? unref(formatTime)(review.reviewed_at) : "-"), 1),
                    review.review_status === "pending_review" ? (openBlock(), createElementBlock("td", _hoisted_23$1, [
                      unref(canConfirmEventReview) ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "review-op-btn",
                        disabled: reviewActionId.value === review.id,
                        onClick: ($event) => decideReview(review, "confirm_event_change")
                      }, "确认事件影响", 8, _hoisted_24$1)) : createCommentVNode("", true),
                      unref(canConfirmAlertReview) ? (openBlock(), createElementBlock("button", {
                        key: 1,
                        class: "review-op-btn",
                        disabled: reviewActionId.value === review.id,
                        onClick: ($event) => decideReview(review, "confirm_alert_change")
                      }, "确认预警影响", 8, _hoisted_25$1)) : createCommentVNode("", true),
                      createVNode(_component_el_dropdown, {
                        trigger: "click",
                        onCommand: (cmd) => decideReview(review, cmd)
                      }, {
                        dropdown: withCtx(() => [
                          createVNode(_component_el_dropdown_menu, null, {
                            default: withCtx(() => [
                              unref(canReviewAI) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                                key: 0,
                                command: "use_ai_display"
                              }, {
                                default: withCtx(() => [..._cache[28] || (_cache[28] = [
                                  createTextVNode("采用 AI 展示", -1)
                                ])]),
                                _: 1
                              })) : createCommentVNode("", true),
                              unref(canReviewAI) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                                key: 1,
                                command: "keep_rule"
                              }, {
                                default: withCtx(() => [..._cache[29] || (_cache[29] = [
                                  createTextVNode("保留规则", -1)
                                ])]),
                                _: 1
                              })) : createCommentVNode("", true),
                              unref(canCompleteReview) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                                key: 2,
                                command: "complete_review",
                                divided: ""
                              }, {
                                default: withCtx(() => [..._cache[30] || (_cache[30] = [
                                  createTextVNode("完成复核", -1)
                                ])]),
                                _: 1
                              })) : createCommentVNode("", true),
                              unref(canRejectAIReview) ? (openBlock(), createBlock(_component_el_dropdown_item, {
                                key: 3,
                                command: "reject_change"
                              }, {
                                default: withCtx(() => [..._cache[31] || (_cache[31] = [
                                  createTextVNode("驳回全部 AI 变更", -1)
                                ])]),
                                _: 1
                              })) : createCommentVNode("", true)
                            ]),
                            _: 1
                          })
                        ]),
                        default: withCtx(() => [
                          unref(canReviewAI) || unref(canCompleteReview) || unref(canRejectAIReview) ? (openBlock(), createElementBlock("button", {
                            key: 0,
                            class: "review-op-btn",
                            type: "button",
                            disabled: reviewActionId.value === review.id
                          }, "更多 ▾", 8, _hoisted_26$1)) : createCommentVNode("", true)
                        ]),
                        _: 2
                      }, 1032, ["onCommand"])
                    ])) : (openBlock(), createElementBlock("td", _hoisted_27$1, toDisplayString(review.review_reason || "-"), 1))
                  ]);
                }), 128)),
                !manualReviews.value.length ? (openBlock(), createElementBlock("tr", _hoisted_28$1, [
                  createBaseVNode("td", _hoisted_29$1, toDisplayString(reviewStatusFilter.value === "pending_review" ? "暂无待复核结果" : "该筛选下暂无复核记录"), 1)
                ])) : createCommentVNode("", true)
              ])
            ])
          ]),
          reviewTotal.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_30$1, [
            createVNode(_sfc_main$3, {
              total: reviewTotal.value,
              "current-page": reviewPage.value,
              "onUpdate:currentPage": _cache[5] || (_cache[5] = ($event) => reviewPage.value = $event),
              "page-size": reviewSize,
              onCurrentChange: loadManualReviews
            }, null, 8, ["total", "current-page"])
          ])) : createCommentVNode("", true)
        ]),
        createVNode(ForeignOpinionDetailModal, {
          modelValue: unref(detailVisible),
          "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => isRef(detailVisible) ? detailVisible.value = $event : null),
          "opinion-id": unref(detailId),
          "risk-source": riskSource.value,
          "onUpdate:riskSource": setRiskSource
        }, null, 8, ["modelValue", "opinion-id", "risk-source"])
      ])) : createCommentVNode("", true);
    };
  }
});

const ForeignAIReviewView = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-9e7d87ee"]]);

const _hoisted_1$1 = { class: "modal-card compact-modal" };
const _hoisted_2$1 = { class: "modal-header" };
const _hoisted_3$1 = { class: "modal-title-wrap" };
const _hoisted_4$1 = { class: "modal-kicker" };
const _hoisted_5$1 = { class: "modal-title" };
const _hoisted_6$1 = { class: "modal-body batch-form" };
const _hoisted_7$1 = ["value"];
const _hoisted_8$1 = { key: 0 };
const _hoisted_9$1 = {
  key: 1,
  class: "date-range"
};
const _hoisted_10$1 = {
  key: 2,
  class: "form-note"
};
const _hoisted_11$1 = {
  key: 3,
  class: "form-note warning-text"
};
const _hoisted_12$1 = { class: "check-line" };
const _hoisted_13$1 = { class: "check-line" };
const _hoisted_14$1 = {
  key: 4,
  class: "preview-box"
};
const _hoisted_15$1 = {
  key: 0,
  class: "warning-text"
};
const _hoisted_16$1 = {
  key: 1,
  class: "warning-text"
};
const _hoisted_17$1 = {
  key: 5,
  class: "warning-text"
};
const _hoisted_18$1 = { class: "modal-footer" };
const _hoisted_19$1 = ["disabled"];
const _hoisted_20$1 = ["disabled"];
const _sfc_main$1 = /* @__PURE__ */ defineComponent({
  __name: "BatchAIModal",
  props: {
    visible: { type: Boolean },
    kicker: {},
    title: {},
    previewEndpoint: {},
    submitEndpoint: {},
    buildPayload: { type: Function },
    scopeOptions: {},
    fullScopeValue: {},
    selectedCount: {}
  },
  emits: ["update:visible", "submitted"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const form = reactive({
      scope: props.scopeOptions?.[0]?.value ?? "recent",
      recent_n: 100,
      date_from: "",
      date_to: "",
      only_unanalyzed: true,
      force: false
    });
    const preview = ref(null);
    const previewLoading = ref(false);
    const submitting = ref(false);
    const error = ref("");
    function close() {
      emit("update:visible", false);
    }
    function clearPreview() {
      preview.value = null;
      error.value = "";
    }
    function onScopeChange() {
      clearPreview();
    }
    async function previewBatch() {
      previewLoading.value = true;
      error.value = "";
      try {
        const { data } = await api.post(props.previewEndpoint, props.buildPayload(form, false));
        preview.value = data;
      } catch (err) {
        preview.value = null;
        error.value = err?.response?.data?.detail || "批量研判预览失败";
      } finally {
        previewLoading.value = false;
      }
    }
    async function doSubmit(fullConfirmation) {
      if (!preview.value) return;
      submitting.value = true;
      error.value = "";
      try {
        const { data } = await api.post(props.submitEndpoint, props.buildPayload(form, fullConfirmation));
        emit("submitted", data);
        close();
      } catch (err) {
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail || "批量 AI 研判提交失败";
        if (status === 403) error.value = `权限不足，无法提交批量 AI 研判：${detail}`;
        else if (status === 422 && /[Tt]oken/.test(detail)) error.value = `Token 超出预算，已拦截提交：${detail}`;
        else if (status === 422) error.value = `提交被拒绝：${detail}`;
        else if (status === 409) error.value = `已有等价批量任务在运行：${detail}`;
        else error.value = detail;
      } finally {
        submitting.value = false;
      }
    }
    async function submitBatch() {
      if (form.scope === props.fullScopeValue) {
        try {
          await ElMessageBox.confirm(
            `确认提交全量 AI 研判？当前匹配 ${preview.value.matched_count} 条，预计消耗 ${preview.value.estimated_token_usage} Token，可能运行较长时间。`,
            "全量 AI 研判二次确认",
            { type: "warning", confirmButtonText: "确认提交", cancelButtonText: "取消" }
          );
        } catch {
          return;
        }
        await doSubmit(true);
      } else {
        await doSubmit(false);
      }
    }
    function reset() {
      preview.value = null;
      error.value = "";
    }
    __expose({ reset });
    return (_ctx, _cache) => {
      return __props.visible ? (openBlock(), createElementBlock("div", {
        key: 0,
        class: "modal-mask",
        onClick: withModifiers(close, ["self"])
      }, [
        createBaseVNode("div", _hoisted_1$1, [
          createBaseVNode("div", _hoisted_2$1, [
            createBaseVNode("div", _hoisted_3$1, [
              createBaseVNode("span", _hoisted_4$1, toDisplayString(__props.kicker), 1),
              createBaseVNode("h3", _hoisted_5$1, toDisplayString(__props.title), 1)
            ]),
            createBaseVNode("button", {
              class: "modal-close",
              onClick: close
            }, "✕")
          ]),
          createBaseVNode("div", _hoisted_6$1, [
            createBaseVNode("label", null, [
              _cache[6] || (_cache[6] = createTextVNode("研判范围 ", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => form.scope = $event),
                class: "select",
                onChange: onScopeChange
              }, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(__props.scopeOptions, (opt) => {
                  return openBlock(), createElementBlock("option", {
                    key: opt.value,
                    value: opt.value
                  }, toDisplayString(opt.label), 9, _hoisted_7$1);
                }), 128))
              ], 544), [
                [vModelSelect, form.scope]
              ])
            ]),
            form.scope === "recent" || form.scope === "count" ? (openBlock(), createElementBlock("label", _hoisted_8$1, [
              _cache[7] || (_cache[7] = createTextVNode("最近条数 ", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => form.recent_n = $event),
                class: "select",
                type: "number",
                min: "1",
                max: "100000"
              }, null, 512), [
                [
                  vModelText,
                  form.recent_n,
                  void 0,
                  { number: true }
                ]
              ])
            ])) : createCommentVNode("", true),
            form.scope === "time" ? (openBlock(), createElementBlock("div", _hoisted_9$1, [
              createBaseVNode("label", null, [
                _cache[8] || (_cache[8] = createTextVNode("开始", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => form.date_from = $event),
                  class: "select",
                  type: "date",
                  onChange: clearPreview
                }, null, 544), [
                  [vModelText, form.date_from]
                ])
              ]),
              createBaseVNode("label", null, [
                _cache[9] || (_cache[9] = createTextVNode("结束", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => form.date_to = $event),
                  class: "select",
                  type: "date",
                  onChange: clearPreview
                }, null, 544), [
                  [vModelText, form.date_to]
                ])
              ])
            ])) : createCommentVNode("", true),
            form.scope === "selected" ? (openBlock(), createElementBlock("p", _hoisted_10$1, "将处理当前选中的 " + toDisplayString(__props.selectedCount) + " 条舆情。", 1)) : createCommentVNode("", true),
            form.scope === "full" || form.scope === "filters" ? (openBlock(), createElementBlock("p", _hoisted_11$1, " 全量任务可能消耗大量 Token 并运行较长时间。AI 结果仍须人工复核后才会进入正式事件或预警。 ")) : createCommentVNode("", true),
            createBaseVNode("label", _hoisted_12$1, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => form.only_unanalyzed = $event),
                type: "checkbox",
                onChange: clearPreview
              }, null, 544), [
                [vModelCheckbox, form.only_unanalyzed]
              ]),
              _cache[10] || (_cache[10] = createTextVNode(" 仅处理未完成 AI 研判", -1))
            ]),
            createBaseVNode("label", _hoisted_13$1, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => form.force = $event),
                type: "checkbox",
                onChange: clearPreview
              }, null, 544), [
                [vModelCheckbox, form.force]
              ]),
              _cache[11] || (_cache[11] = createTextVNode(" 强制重新研判已有 AI 结果", -1))
            ]),
            preview.value ? (openBlock(), createElementBlock("div", _hoisted_14$1, [
              createBaseVNode("b", null, "符合条件舆情 " + toDisplayString(preview.value.matched_count) + " 条", 1),
              createBaseVNode("span", null, "已有 AI 结果 " + toDisplayString(preview.value.existing_ai_result_count ?? 0) + " 条 · 待分析 " + toDisplayString(preview.value.pending_analysis_count) + " 条", 1),
              createBaseVNode("span", null, "预计 Token：" + toDisplayString(preview.value.estimated_token_usage), 1),
              createBaseVNode("span", null, "预计耗时：" + toDisplayString(preview.value.estimated_duration_seconds) + " 秒", 1),
              createBaseVNode("span", null, "风险分布：高 " + toDisplayString(preview.value.risk_level_counts?.high ?? 0) + " · 中 " + toDisplayString(preview.value.risk_level_counts?.medium ?? 0) + " · 低 " + toDisplayString(preview.value.risk_level_counts?.low ?? 0), 1),
              createBaseVNode("span", null, "可能影响：事件候选 " + toDisplayString(preview.value.possible_event_count ?? 0) + " 个 · 预警 " + toDisplayString(preview.value.possible_alert_count ?? 0) + " 个", 1),
              preview.value.preview_warning ? (openBlock(), createElementBlock("span", _hoisted_15$1, "⚠ " + toDisplayString(preview.value.preview_warning), 1)) : createCommentVNode("", true),
              preview.value.token_budget_exceeded ? (openBlock(), createElementBlock("span", _hoisted_16$1, "⚠ 预计 Token 超出预算，提交将被拦截，请缩小范围或调高预算。")) : createCommentVNode("", true)
            ])) : createCommentVNode("", true),
            error.value ? (openBlock(), createElementBlock("p", _hoisted_17$1, toDisplayString(error.value), 1)) : createCommentVNode("", true),
            createBaseVNode("div", _hoisted_18$1, [
              createBaseVNode("button", {
                class: "btn btn-ghost",
                onClick: close
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-ghost",
                disabled: previewLoading.value,
                onClick: previewBatch
              }, "预览", 8, _hoisted_19$1),
              createBaseVNode("button", {
                class: "btn btn-primary",
                disabled: submitting.value || !preview.value || preview.value.token_budget_exceeded,
                onClick: submitBatch
              }, "提交任务", 8, _hoisted_20$1)
            ])
          ])
        ])
      ])) : createCommentVNode("", true);
    };
  }
});

const BatchAIModal = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-b5ca830d"]]);

const _hoisted_1 = { class: "panel" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = ["value"];
const _hoisted_4 = { class: "muted" };
const _hoisted_5 = ["disabled"];
const _hoisted_6 = ["disabled"];
const _hoisted_7 = {
  key: 0,
  class: "ai-batch-status"
};
const _hoisted_8 = { class: "ai-batch-status-head" };
const _hoisted_9 = { class: "ai-batch-count" };
const _hoisted_10 = { class: "ai-batch-step" };
const _hoisted_11 = ["aria-valuenow"];
const _hoisted_12 = { class: "ai-batch-status-meta" };
const _hoisted_13 = {
  key: 0,
  class: "muted"
};
const _hoisted_14 = {
  key: 0,
  class: "ai-batch-inline-error"
};
const _hoisted_15 = { class: "table-wrap tbl-scroll" };
const _hoisted_16 = ["onClick"];
const _hoisted_17 = { class: "title-cell" };
const _hoisted_18 = { class: "dual-cell" };
const _hoisted_19 = { class: "muted" };
const _hoisted_20 = {
  key: 0,
  class: "muted"
};
const _hoisted_21 = { class: "actions" };
const _hoisted_22 = ["disabled", "onClick"];
const _hoisted_23 = { key: 0 };
const _hoisted_24 = {
  key: 1,
  class: "pager"
};
const _hoisted_25 = {
  key: 0,
  class: "review-empty"
};
const _hoisted_26 = {
  key: 1,
  class: "ai-batch-history"
};
const _hoisted_27 = { class: "tbl" };
const _hoisted_28 = ["onClick"];
const _hoisted_29 = { key: 0 };
const _hoisted_30 = {
  key: 0,
  class: "ai-batch-details ai-batch-history-detail"
};
const _hoisted_31 = {
  key: 0,
  class: "failures"
};
const opinionSize = 20;
const riskSize = 100;
const riskMaxPages = 20;
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "ForeignOpinionListView",
  setup(__props, { expose: __expose }) {
    useRoute();
    useRouter();
    const { hasPermission } = usePermission();
    const { detailVisible, detailId, openOpinion } = useForeignDetailState();
    const loading = ref(false);
    const opinions = ref([]);
    const opinionSources = ref([]);
    const opinionTotal = ref(0);
    const opinionPage = ref(1);
    const risks = ref([]);
    const riskTotal = ref(0);
    const opinionFilters = reactive({ q: "", source: "", keyword: "", date_from: "", date_to: "" });
    const riskFilters = reactive({ q: "", source: "", language: "", sentiment: "", risk_level: "", analysis_status: "", date_from: "", date_to: "" });
    const riskSource = ref(
      window.localStorage.getItem("foreign-risk-source") === "ai" ? "ai" : window.localStorage.getItem("foreign-risk-source") === "rule" ? "rule" : "current"
    );
    function setRiskSource(value) {
      riskSource.value = value === "ai" || value === "rule" ? value : "current";
      window.localStorage.setItem("foreign-risk-source", riskSource.value);
      loadOpinions();
    }
    function displaySourceLabel() {
      return riskSource.value === "ai" ? "AI 研判" : riskSource.value === "rule" ? "系统规则" : "持久化当前风险";
    }
    const riskByOpinion = computed(() => {
      const m = /* @__PURE__ */ new Map();
      for (const r of risks.value) m.set(r.foreign_opinion_id, r);
      return m;
    });
    function riskOf(id) {
      return riskByOpinion.value.get(id) || null;
    }
    const canAnalyzeRisk = hasPermission("foreign:risk:analyze");
    const canAnalyzeAI = hasPermission("foreign:ai:analyze");
    const canReadAIBatches = hasPermission("foreign:ai:batch:read");
    const canCancelAIBatch = hasPermission("foreign:ai:batch:cancel");
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
    const aiBatchDialog = ref(false);
    const aiBatchLoading = ref(false);
    const aiBatchRun = ref(null);
    const showAIBatchDetails = ref(false);
    const aiBatchHistoryDialog = ref(false);
    const aiBatchHistory = ref([]);
    const aiBatchHistorySel = ref(null);
    const aiBatchHistoryLoading = ref(false);
    let aiBatchTimer = null;
    const AI_BATCH_TERMINAL = ["success", "partial", "failed", "cancelled", "completed"];
    function aiBatchIsTerminal(status) {
      return AI_BATCH_TERMINAL.includes(String(status || ""));
    }
    const batchScopeOptions = [
      { value: "count", label: "按数量（最近 N 条）" },
      { value: "time", label: "时间范围" },
      { value: "full", label: "全量" }
    ];
    function openAIBatch() {
      aiBatchDialog.value = true;
    }
    function buildBatchPayload(form, fullConfirmation) {
      return {
        scope: form.scope === "recent" ? "count" : form.scope,
        recent_n: form.recent_n,
        date_from: form.date_from || void 0,
        date_to: form.date_to || void 0,
        use_current_filters: true,
        current_filters: {
          q: opinionFilters.q,
          source: opinionFilters.source,
          keyword: opinionFilters.keyword,
          language: riskFilters.language,
          risk_level: riskFilters.risk_level,
          analysis_status: riskFilters.analysis_status,
          date_from: opinionFilters.date_from,
          date_to: opinionFilters.date_to,
          risk_source: riskSource.value
        },
        only_unanalyzed: form.only_unanalyzed,
        force: form.force,
        full_confirmation: fullConfirmation
      };
    }
    function onBatchSubmitted(data) {
      aiBatchRun.value = { ...data, run_id: data.run_id, status: data.status };
      localStorage.setItem("foreign-ai-batch-run-id", data.run_id);
      showAIBatchDetails.value = true;
      pollAIBatch(data.run_id);
      ElMessage.success(`任务已提交，匹配 ${data.matched_count ?? data.total_count} 条，待研判 ${data.pending_analysis_count ?? data.total_count} 条`);
    }
    function batchProgressOf(run) {
      const total = run?.total_count || 0;
      const processed = run?.processed_count || 0;
      if (!total) return 0;
      return Math.min(100, Math.round(processed / total * 100));
    }
    function aiBatchStepText(step) {
      if (!step) return "正在准备任务";
      const matched = String(step).match(/Foreign AI review\s+(\d+)\/(\d+)/i);
      return matched ? `正在研判第 ${matched[1]} / ${matched[2]} 条` : step;
    }
    const batchProgress = computed(() => {
      const total = Number(aiBatchRun.value?.total_count || 0);
      return total ? Math.round(Number(aiBatchRun.value?.processed_count || 0) / total * 100) : 0;
    });
    const isAIBatchFinished = computed(() => aiBatchIsTerminal(aiBatchRun.value?.status));
    async function pollAIBatch(runId, immediate = false, startedAt = Date.now()) {
      if (aiBatchTimer) clearTimeout(aiBatchTimer);
      aiBatchTimer = setTimeout(async () => {
        try {
          const { data } = await api.get(`/foreign/ai-analysis/batch/${runId}`);
          aiBatchRun.value = { ...aiBatchRun.value || {}, ...data, run_id: runId };
          if (aiBatchIsTerminal(data.status)) {
            aiBatchRun.value = null;
            localStorage.removeItem("foreign-ai-batch-run-id");
            ElMessage({ type: data.status === "success" ? "success" : data.status === "partial" ? "warning" : "error", message: `批量 AI 研判${zh(data.status)}：成功 ${data.success_count || 0}，失败 ${data.failed_count || 0}，跳过 ${data.skipped_count || 0}` });
            await loadOpinions();
            await loadRisk();
            return;
          }
          if (Date.now() - startedAt > 10 * 60 * 1e3) {
            aiBatchRun.value = null;
            localStorage.removeItem("foreign-ai-batch-run-id");
            ElMessage.warning("批量 AI 研判状态跟踪超时，已停止跟踪，请稍后在运行记录中查看结果");
            return;
          }
          pollAIBatch(runId, false, startedAt);
        } catch (err) {
          ElMessage.error(err?.response?.data?.detail || "批量 AI 进度查询失败");
        }
      }, immediate ? 0 : 1200);
    }
    async function cancelAIBatch() {
      const runId = aiBatchRun.value?.run_id;
      if (!runId) return;
      try {
        await ElMessageBox.confirm("确认取消此批量 AI 研判任务？已完成的记录会保留。", "取消任务确认", { type: "warning" });
        const { data } = await api.post(`/foreign/ai-analysis/batch/${runId}/cancel`);
        aiBatchRun.value = { ...aiBatchRun.value || {}, ...data, run_id: runId };
      } catch (err) {
        if (err === "cancel" || err?.toString?.().includes("cancel")) return;
        ElMessage.error(err?.response?.data?.detail || "取消批量 AI 任务失败");
      }
    }
    async function openAIBatchHistory() {
      if (!aiBatchHistoryDialog.value) aiBatchHistorySel.value = null;
      aiBatchHistoryDialog.value = true;
      aiBatchHistoryLoading.value = true;
      try {
        const { data } = await api.get("/foreign/ai-analysis/batches", { params: { size: 50 } });
        aiBatchHistory.value = data.items || [];
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "运行记录加载失败");
        aiBatchHistory.value = [];
      } finally {
        aiBatchHistoryLoading.value = false;
      }
    }
    async function openAIBatchHistoryDetail(runId) {
      try {
        const { data } = await api.get(`/foreign/ai-analysis/batch/${runId}`);
        aiBatchHistorySel.value = data;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "运行详情加载失败");
      }
    }
    async function resumeAIBatchIfRunning(runId) {
      try {
        const { data } = await api.get(`/foreign/ai-analysis/batch/${runId}`);
        if (aiBatchIsTerminal(data.status)) {
          localStorage.removeItem("foreign-ai-batch-run-id");
          return;
        }
        if (data.updated_at && !isNaN(new Date(data.updated_at).getTime()) && Date.now() - new Date(data.updated_at).getTime() > 20 * 60 * 1e3) {
          localStorage.removeItem("foreign-ai-batch-run-id");
          return;
        }
        aiBatchRun.value = { ...aiBatchRun.value || {}, ...data, run_id: runId };
        pollAIBatch(runId, true);
      } catch {
        localStorage.removeItem("foreign-ai-batch-run-id");
      }
    }
    function onForeignRefresh() {
      loadOpinions();
      loadRisk();
    }
    onMounted(() => {
      window.addEventListener("foreign-data-refresh", onForeignRefresh);
      loadOpinions();
      loadRisk();
      const runId = localStorage.getItem("foreign-ai-batch-run-id");
      if (runId) resumeAIBatchIfRunning(runId);
    });
    onBeforeUnmount(() => {
      if (aiBatchTimer) clearTimeout(aiBatchTimer);
      window.removeEventListener("foreign-data-refresh", onForeignRefresh);
    });
    __expose({ loadOpinions, loadRisk });
    return (_ctx, _cache) => {
      const _component_el_dialog = resolveComponent("el-dialog");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          withDirectives(createBaseVNode("input", {
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => opinionFilters.q = $event),
            class: "input",
            placeholder: "搜索标题、摘要、正文",
            onKeyup: withKeys(loadOpinions, ["enter"])
          }, null, 544), [
            [vModelText, opinionFilters.q]
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => opinionFilters.source = $event),
            class: "input",
            onChange: loadOpinions
          }, [
            _cache[17] || (_cache[17] = createBaseVNode("option", { value: "" }, "全部来源", -1)),
            (openBlock(true), createElementBlock(Fragment, null, renderList(opinionSources.value, (source) => {
              return openBlock(), createElementBlock("option", {
                key: source,
                value: source
              }, toDisplayString(source), 9, _hoisted_3);
            }), 128))
          ], 544), [
            [vModelSelect, opinionFilters.source]
          ]),
          withDirectives(createBaseVNode("input", {
            "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => opinionFilters.keyword = $event),
            class: "input",
            placeholder: "命中关键词",
            onKeyup: withKeys(loadOpinions, ["enter"])
          }, null, 544), [
            [vModelText, opinionFilters.keyword]
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => riskFilters.language = $event),
            class: "input",
            onChange: _cache[4] || (_cache[4] = ($event) => {
              loadOpinions();
              loadRisk();
            })
          }, [..._cache[18] || (_cache[18] = [
            createStaticVNode('<option value="" data-v-0dc8f137>全部语言</option><option value="zh" data-v-0dc8f137>中文</option><option value="en" data-v-0dc8f137>英文</option><option value="mixed" data-v-0dc8f137>中英混合</option><option value="unknown" data-v-0dc8f137>未知</option>', 5)
          ])], 544), [
            [vModelSelect, riskFilters.language]
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => riskSource.value = $event),
            class: "input",
            "aria-label": "risk view source",
            onChange: _cache[6] || (_cache[6] = ($event) => setRiskSource(riskSource.value))
          }, [..._cache[19] || (_cache[19] = [
            createBaseVNode("option", { value: "current" }, "当前风险", -1),
            createBaseVNode("option", { value: "rule" }, "系统规则", -1),
            createBaseVNode("option", { value: "ai" }, "AI 研判", -1)
          ])], 544), [
            [vModelSelect, riskSource.value]
          ]),
          createBaseVNode("span", _hoisted_4, "当前查看口径：" + toDisplayString(displaySourceLabel()), 1),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => riskFilters.risk_level = $event),
            class: "input",
            onChange: _cache[8] || (_cache[8] = ($event) => {
              loadOpinions();
              loadRisk();
            })
          }, [..._cache[20] || (_cache[20] = [
            createStaticVNode('<option value="" data-v-0dc8f137>全部风险等级</option><option value="high" data-v-0dc8f137>高</option><option value="medium" data-v-0dc8f137>中</option><option value="low" data-v-0dc8f137>低</option><option value="unknown" data-v-0dc8f137>未知</option>', 5)
          ])], 544), [
            [vModelSelect, riskFilters.risk_level]
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => riskFilters.analysis_status = $event),
            class: "input",
            onChange: _cache[10] || (_cache[10] = ($event) => {
              loadOpinions();
              loadRisk();
            })
          }, [..._cache[21] || (_cache[21] = [
            createBaseVNode("option", { value: "" }, "全部分析状态", -1),
            createBaseVNode("option", { value: "completed" }, "完成", -1),
            createBaseVNode("option", { value: "skipped" }, "跳过", -1),
            createBaseVNode("option", { value: "failed" }, "失败", -1)
          ])], 544), [
            [vModelSelect, riskFilters.analysis_status]
          ]),
          withDirectives(createBaseVNode("input", {
            "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => opinionFilters.date_from = $event),
            class: "input date-input",
            type: "date",
            title: "发布时间起始",
            onChange: loadOpinions
          }, null, 544), [
            [vModelText, opinionFilters.date_from]
          ]),
          withDirectives(createBaseVNode("input", {
            "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => opinionFilters.date_to = $event),
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
          }, "批量 AI 研判", 8, _hoisted_5)) : createCommentVNode("", true),
          unref(canReadAIBatches) ? (openBlock(), createElementBlock("button", {
            key: 1,
            class: "btn btn-secondary",
            disabled: aiBatchLoading.value,
            onClick: openAIBatchHistory
          }, "AI 研判运行记录", 8, _hoisted_6)) : createCommentVNode("", true),
          _cache[22] || (_cache[22] = createBaseVNode("span", { class: "muted" }, "AI 研判经人工采用后进入当前风险；正式预警和事件记录保留创建时的正式风险快照", -1))
        ]),
        aiBatchRun.value && !isAIBatchFinished.value ? (openBlock(), createElementBlock("div", _hoisted_7, [
          createBaseVNode("div", _hoisted_8, [
            createBaseVNode("strong", null, "AI 批量研判 " + toDisplayString(unref(zh)(aiBatchRun.value.status)), 1),
            createBaseVNode("span", _hoisted_9, toDisplayString(aiBatchRun.value.processed_count || 0) + " / " + toDisplayString(aiBatchRun.value.total_count || 0), 1),
            createBaseVNode("span", _hoisted_10, toDisplayString(aiBatchStepText(aiBatchRun.value.step)), 1),
            unref(canCancelAIBatch) && (aiBatchRun.value.status === "running" || aiBatchRun.value.status === "pending") ? (openBlock(), createElementBlock("button", {
              key: 0,
              class: "link-btn danger",
              onClick: cancelAIBatch
            }, "取消")) : createCommentVNode("", true)
          ]),
          createBaseVNode("div", {
            class: "ai-batch-progress-track",
            role: "progressbar",
            "aria-valuenow": batchProgress.value,
            "aria-valuemin": "0",
            "aria-valuemax": "100"
          }, [
            createBaseVNode("span", {
              class: "ai-batch-progress-bar",
              style: normalizeStyle({ width: `${batchProgress.value}%` })
            }, null, 4)
          ], 8, _hoisted_11),
          createBaseVNode("div", _hoisted_12, [
            createBaseVNode("span", null, toDisplayString(batchProgress.value) + "%", 1),
            createBaseVNode("span", null, "成功 " + toDisplayString(aiBatchRun.value.success_count || 0), 1),
            createBaseVNode("span", null, "失败 " + toDisplayString(aiBatchRun.value.failed_count || 0), 1),
            createBaseVNode("span", null, "跳过 " + toDisplayString(aiBatchRun.value.skipped_count || 0), 1),
            aiBatchRun.value.started_at ? (openBlock(), createElementBlock("span", _hoisted_13, "开始：" + toDisplayString(unref(formatTime)(aiBatchRun.value.started_at)), 1)) : createCommentVNode("", true)
          ]),
          (aiBatchRun.value.failures || []).length ? (openBlock(), createElementBlock("p", _hoisted_14, "失败 " + toDisplayString(aiBatchRun.value.failures.length) + " 条：" + toDisplayString((aiBatchRun.value.failures || []).map((item) => item.error || item.message || item.code || "未知错误").slice(0, 2).join("；")), 1)) : createCommentVNode("", true)
        ])) : createCommentVNode("", true),
        createBaseVNode("div", _hoisted_15, [
          createBaseVNode("table", null, [
            _cache[24] || (_cache[24] = createBaseVNode("thead", null, [
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
                  onClick: ($event) => unref(openOpinion)(row.id)
                }, [
                  createBaseVNode("td", _hoisted_17, toDisplayString(row.title || "无标题"), 1),
                  createBaseVNode("td", null, toDisplayString(row.source_name_snapshot), 1),
                  createBaseVNode("td", null, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(row.matched_keywords, (word) => {
                      return openBlock(), createElementBlock("span", {
                        key: word,
                        class: "tag"
                      }, toDisplayString(word), 1);
                    }), 128))
                  ]),
                  createBaseVNode("td", null, toDisplayString(unref(formatTime)(row.published_at)), 1),
                  createBaseVNode("td", null, toDisplayString(unref(formatTime)(row.collected_at)), 1),
                  createBaseVNode("td", null, toDisplayString(unref(displayOf)(row)?.risk_score ?? "-"), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["status", { on: unref(displayOf)(row)?.risk_level === "high" }])
                    }, toDisplayString(unref(zh)(unref(displayOf)(row)?.risk_level)), 3)
                  ]),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["src-tag", { ai: unref(displayOf)(row)?.source === "ai" }])
                    }, toDisplayString(unref(displayOf)(row)?.source === "ai" ? "AI 研判" : "系统规则"), 3)
                  ]),
                  createBaseVNode("td", _hoisted_18, [
                    createBaseVNode("span", null, "规则 " + toDisplayString(unref(ruleOf)(row)?.risk_score ?? "-"), 1),
                    createBaseVNode("span", _hoisted_19, toDisplayString(unref(aiHistoryLabel)(row)), 1)
                  ]),
                  createBaseVNode("td", null, toDisplayString(unref(zh)(unref(displayOf)(row)?.sentiment)), 1),
                  createBaseVNode("td", null, toDisplayString(unref(zh)(unref(ruleOf)(row)?.risk_category)), 1),
                  createBaseVNode("td", null, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(riskOf(row.id)?.matched_terms || [], (term) => {
                      return openBlock(), createElementBlock("span", {
                        key: term.word,
                        class: "tag"
                      }, toDisplayString(term.word), 1);
                    }), 128)),
                    !(riskOf(row.id)?.matched_terms || []).length ? (openBlock(), createElementBlock("span", _hoisted_20, "无")) : createCommentVNode("", true)
                  ]),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["status", { on: unref(ruleOf)(row)?.analysis_status === "completed" }])
                    }, toDisplayString(unref(zh)(unref(ruleOf)(row)?.analysis_status)), 3)
                  ]),
                  createBaseVNode("td", null, toDisplayString(unref(formatTime)(unref(displayOf)(row)?.evaluated_at)), 1),
                  createBaseVNode("td", null, toDisplayString(unref(displayOf)(row)?.model_version || "-"), 1),
                  createBaseVNode("td", _hoisted_21, [
                    createBaseVNode("button", {
                      class: "link-btn",
                      disabled: !unref(canAnalyzeRisk),
                      onClick: withModifiers(($event) => analyzeRisk(row.id), ["stop"])
                    }, toDisplayString(unref(ruleOf)(row) ? "重新分析" : "分析"), 9, _hoisted_22)
                  ])
                ], 8, _hoisted_16);
              }), 128)),
              !opinions.value.length ? (openBlock(), createElementBlock("tr", _hoisted_23, [..._cache[23] || (_cache[23] = [
                createBaseVNode("td", {
                  colspan: "16",
                  class: "empty"
                }, "暂无外网舆情", -1)
              ])])) : createCommentVNode("", true)
            ])
          ])
        ]),
        opinionTotal.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_24, [
          createVNode(_sfc_main$3, {
            total: opinionTotal.value,
            "current-page": opinionPage.value,
            "onUpdate:currentPage": _cache[13] || (_cache[13] = ($event) => opinionPage.value = $event),
            "page-size": opinionSize,
            onCurrentChange: loadOpinions
          }, null, 8, ["total", "current-page"])
        ])) : createCommentVNode("", true),
        createVNode(BatchAIModal, {
          visible: aiBatchDialog.value,
          kicker: "国外 AI 研判",
          title: "创建批量研判任务",
          "preview-endpoint": "/foreign/ai-analysis/batch/preview",
          "submit-endpoint": "/foreign/ai-analysis/batch",
          "scope-options": batchScopeOptions,
          "full-scope-value": "full",
          "build-payload": buildBatchPayload,
          "onUpdate:visible": _cache[14] || (_cache[14] = ($event) => aiBatchDialog.value = $event),
          onSubmitted: onBatchSubmitted
        }, null, 8, ["visible"]),
        createVNode(_component_el_dialog, {
          modelValue: aiBatchHistoryDialog.value,
          "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => aiBatchHistoryDialog.value = $event),
          title: "AI 研判运行记录",
          width: "720px"
        }, {
          default: withCtx(() => [
            aiBatchHistoryLoading.value ? (openBlock(), createElementBlock("div", _hoisted_25, "加载中…")) : (openBlock(), createElementBlock("div", _hoisted_26, [
              createBaseVNode("table", _hoisted_27, [
                _cache[26] || (_cache[26] = createBaseVNode("thead", null, [
                  createBaseVNode("tr", null, [
                    createBaseVNode("th", null, "状态"),
                    createBaseVNode("th", null, "进度"),
                    createBaseVNode("th", null, "成功/失败/跳过"),
                    createBaseVNode("th", null, "开始"),
                    createBaseVNode("th", null, "结束"),
                    createBaseVNode("th")
                  ])
                ], -1)),
                createBaseVNode("tbody", null, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(aiBatchHistory.value, (r) => {
                    return openBlock(), createElementBlock("tr", {
                      key: r.run_id
                    }, [
                      createBaseVNode("td", null, [
                        createBaseVNode("span", {
                          class: normalizeClass(["status", { on: r.status === "success" || r.status === "partial" }])
                        }, toDisplayString(unref(zh)(r.status)), 3)
                      ]),
                      createBaseVNode("td", null, toDisplayString(r.processed_count || 0) + "/" + toDisplayString(r.total_count || 0), 1),
                      createBaseVNode("td", null, toDisplayString(r.success_count || 0) + " / " + toDisplayString(r.failed_count || 0) + " / " + toDisplayString(r.skipped_count || 0), 1),
                      createBaseVNode("td", null, toDisplayString(unref(formatTime)(r.started_at)), 1),
                      createBaseVNode("td", null, toDisplayString(unref(formatTime)(r.finished_at)), 1),
                      createBaseVNode("td", null, [
                        createBaseVNode("button", {
                          class: "link-btn",
                          onClick: withModifiers(($event) => openAIBatchHistoryDetail(r.run_id), ["stop"])
                        }, "查看", 8, _hoisted_28)
                      ])
                    ]);
                  }), 128)),
                  !aiBatchHistory.value.length ? (openBlock(), createElementBlock("tr", _hoisted_29, [..._cache[25] || (_cache[25] = [
                    createBaseVNode("td", {
                      colspan: "6",
                      class: "empty-row"
                    }, "暂无运行记录", -1)
                  ])])) : createCommentVNode("", true)
                ])
              ]),
              aiBatchHistorySel.value ? (openBlock(), createElementBlock("div", _hoisted_30, [
                createBaseVNode("h4", null, "运行详情 " + toDisplayString(aiBatchHistorySel.value.run_id), 1),
                createBaseVNode("span", null, "状态：" + toDisplayString(unref(zh)(aiBatchHistorySel.value.status)), 1),
                createBaseVNode("span", null, "进度：" + toDisplayString(aiBatchHistorySel.value.processed_count || 0) + "/" + toDisplayString(aiBatchHistorySel.value.total_count || 0) + "（" + toDisplayString(batchProgressOf(aiBatchHistorySel.value)) + "%）", 1),
                createBaseVNode("span", null, "当前步骤：" + toDisplayString(aiBatchHistorySel.value.step || "-"), 1),
                createBaseVNode("span", null, "成功 " + toDisplayString(aiBatchHistorySel.value.success_count || 0) + " · 失败 " + toDisplayString(aiBatchHistorySel.value.failed_count || 0) + " · 跳过 " + toDisplayString(aiBatchHistorySel.value.skipped_count || 0), 1),
                createBaseVNode("span", null, "开始：" + toDisplayString(aiBatchHistorySel.value.started_at || "-"), 1),
                createBaseVNode("span", null, "结束：" + toDisplayString(aiBatchHistorySel.value.finished_at || "-"), 1),
                createBaseVNode("span", null, "预估 Token：" + toDisplayString(aiBatchHistorySel.value.estimated_token_usage ?? "-"), 1),
                createBaseVNode("span", null, "实际 Token：" + toDisplayString(aiBatchHistorySel.value.actual_token_usage ?? "-"), 1),
                (aiBatchHistorySel.value.failures || []).length ? (openBlock(), createElementBlock("p", _hoisted_31, "失败明细：" + toDisplayString((aiBatchHistorySel.value.failures || []).map((item) => `#${item.opinion_id}: ${item.error}`).join("；")), 1)) : createCommentVNode("", true)
              ])) : createCommentVNode("", true)
            ]))
          ]),
          _: 1
        }, 8, ["modelValue"]),
        createVNode(ForeignOpinionDetailModal, {
          modelValue: unref(detailVisible),
          "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => isRef(detailVisible) ? detailVisible.value = $event : null),
          "opinion-id": unref(detailId),
          "risk-source": riskSource.value,
          "onUpdate:riskSource": setRiskSource
        }, null, 8, ["modelValue", "opinion-id", "risk-source"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const ForeignOpinionListView = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-0dc8f137"]]);

export { BatchAIModal as B, ForeignOpinionListView as F, ForeignAIReviewView as a };
