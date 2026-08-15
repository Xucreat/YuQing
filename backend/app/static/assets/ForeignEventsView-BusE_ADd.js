import { d as defineComponent, z as usePermission, h as useRouter, C as onMounted, o as openBlock, c as createElementBlock, a as createBaseVNode, t as toDisplayString, s as createCommentVNode, F as Fragment, i as renderList, n as normalizeClass, H as unref, e as createTextVNode, P as withModifiers, m as createVNode, r as ref, E as ElMessage, Q as ElMessageBox, g as api, _ as _export_sfc } from './index-Bt1_Mwuw.js';
import { b as EventDispositionDialog } from './EventDispositionDialog-PmoihkPk.js';

const _hoisted_1 = { class: "panel" };
const _hoisted_2 = { class: "alert-scope-note" };
const _hoisted_3 = { class: "toolbar" };
const _hoisted_4 = ["disabled"];
const _hoisted_5 = {
  key: 0,
  class: "state error-state"
};
const _hoisted_6 = {
  key: 1,
  class: "event-failures"
};
const _hoisted_7 = { class: "subtabs" };
const _hoisted_8 = {
  key: 2,
  class: "table-wrap"
};
const _hoisted_9 = { class: "title-cell" };
const _hoisted_10 = { class: "actions" };
const _hoisted_11 = ["disabled", "onClick"];
const _hoisted_12 = ["disabled", "onClick"];
const _hoisted_13 = { key: 0 };
const _hoisted_14 = {
  key: 3,
  class: "table-wrap"
};
const _hoisted_15 = ["onClick"];
const _hoisted_16 = { class: "title-cell" };
const _hoisted_17 = { key: 0 };
const _hoisted_18 = { class: "muted" };
const _hoisted_19 = { key: 1 };
const _hoisted_20 = { class: "row-actions" };
const _hoisted_21 = ["onClick"];
const _hoisted_22 = ["onClick"];
const _hoisted_23 = ["onClick"];
const _hoisted_24 = { key: 0 };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "ForeignEventsView",
  props: {
    showDispositionActions: { type: Boolean }
  },
  setup(__props) {
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
    function operationRequestId(prefix) {
      const random = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      return `${prefix}-${random}`.slice(0, 128);
    }
    const { hasPermission } = usePermission();
    const router = useRouter();
    const canConfirmEvents = hasPermission("foreign:events:confirm");
    const canDisposition = hasPermission("foreign:events:write");
    const dispositionVisible = ref(false);
    const dispositionEventId = ref(null);
    function openHandle(row) {
      dispositionEventId.value = row.id;
      dispositionVisible.value = true;
    }
    async function handleDelete(row) {
      if (!canDisposition) {
        ElMessage.error("权限不足，无法删除外网事件");
        return;
      }
      try {
        await ElMessageBox.confirm(
          `确认删除外网事件「${row.title || "无标题"}」？关联的舆情不会被删除。`,
          "删除确认",
          { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" }
        );
      } catch {
        return;
      }
      try {
        await api.delete("/foreign/events/" + row.id);
        ElMessage.success("外网事件已删除");
        await loadEvents();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "删除外网事件失败，请稍后重试");
      }
    }
    function goDetail(row) {
      router.push("/foreign/event/" + row.id);
    }
    const eventCandidates = ref([]);
    const foreignEvents = ref([]);
    const eventRunFailures = ref([]);
    const eventAutoStatus = ref(null);
    const eventLoadError = ref(null);
    const eventSection = ref("candidates");
    const rebuildingEvents = ref(false);
    const eventActionKey = ref(null);
    async function loadEvents() {
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
    onMounted(loadEvents);
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("section", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, "外网自动聚合：" + toDisplayString(eventAutoStatus.value?.enabled ? "已启用" : "已停用") + " · 调度已注册：" + toDisplayString(eventAutoStatus.value?.scheduler_registered ? "是" : "否") + " · 置信度阈值 " + toDisplayString(eventAutoStatus.value?.confidence_threshold ?? "-") + " · 时间窗口 " + toDisplayString(eventAutoStatus.value?.time_window_hours ?? "-") + " 小时", 1),
        createBaseVNode("div", _hoisted_3, [
          createBaseVNode("button", {
            class: "btn btn-secondary",
            onClick: loadEvents
          }, "刷新外网事件"),
          createBaseVNode("button", {
            class: "btn btn-secondary",
            disabled: rebuildingEvents.value,
            onClick: rebuildEvents
          }, toDisplayString(rebuildingEvents.value ? "重建中..." : "候选 Dry-Run"), 9, _hoisted_4),
          _cache[4] || (_cache[4] = createBaseVNode("span", { class: "muted" }, "候选只进入外网事件表，必须人工确认后才形成正式事件", -1))
        ]),
        eventLoadError.value ? (openBlock(), createElementBlock("div", _hoisted_5, [
          createBaseVNode("span", null, "外网事件加载失败：" + toDisplayString(eventLoadError.value), 1),
          createBaseVNode("button", {
            class: "btn btn-secondary",
            onClick: loadEvents
          }, "重试")
        ])) : createCommentVNode("", true),
        eventRunFailures.value.length ? (openBlock(), createElementBlock("div", _hoisted_6, [
          _cache[6] || (_cache[6] = createBaseVNode("strong", null, "外网事件运行失败", -1)),
          (openBlock(true), createElementBlock(Fragment, null, renderList(eventRunFailures.value, (run) => {
            return openBlock(), createElementBlock("div", {
              key: run.id,
              class: "event-failure-row"
            }, [
              _cache[5] || (_cache[5] = createBaseVNode("span", { class: "status failed" }, "失败", -1)),
              createBaseVNode("span", null, toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
              createBaseVNode("span", null, toDisplayString(run.error_message || "运行失败，未提供错误摘要"), 1)
            ]);
          }), 128))
        ])) : createCommentVNode("", true),
        createBaseVNode("div", _hoisted_7, [
          createBaseVNode("button", {
            class: normalizeClass(["tab", { active: eventSection.value === "candidates" }]),
            onClick: _cache[0] || (_cache[0] = ($event) => eventSection.value = "candidates")
          }, "事件候选", 2),
          createBaseVNode("button", {
            class: normalizeClass(["tab", { active: eventSection.value === "confirmed" }]),
            onClick: _cache[1] || (_cache[1] = ($event) => eventSection.value = "confirmed")
          }, "外网事件", 2)
        ]),
        eventSection.value === "candidates" ? (openBlock(), createElementBlock("div", _hoisted_8, [
          createBaseVNode("table", null, [
            _cache[8] || (_cache[8] = createBaseVNode("thead", null, [
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
                  createBaseVNode("td", _hoisted_9, toDisplayString(row.title || "无标题"), 1),
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
                  createBaseVNode("td", _hoisted_10, [
                    row.candidate_status === "candidate" ? (openBlock(), createElementBlock("button", {
                      key: 0,
                      class: "link-btn",
                      disabled: !unref(canConfirmEvents) || eventActionKey.value === `candidate-confirm-${row.id}`,
                      onClick: ($event) => confirmCandidate(row)
                    }, "确认", 8, _hoisted_11)) : createCommentVNode("", true),
                    row.candidate_status === "candidate" ? (openBlock(), createElementBlock("button", {
                      key: 1,
                      class: "link-btn danger",
                      disabled: !unref(canConfirmEvents) || eventActionKey.value === `candidate-reject-${row.id}`,
                      onClick: ($event) => rejectCandidate(row)
                    }, "拒绝", 8, _hoisted_12)) : createCommentVNode("", true)
                  ])
                ]);
              }), 128)),
              !eventCandidates.value.length ? (openBlock(), createElementBlock("tr", _hoisted_13, [..._cache[7] || (_cache[7] = [
                createBaseVNode("td", {
                  colspan: "8",
                  class: "empty"
                }, "暂无外网事件候选", -1)
              ])])) : createCommentVNode("", true)
            ])
          ])
        ])) : eventSection.value === "confirmed" ? (openBlock(), createElementBlock("div", _hoisted_14, [
          createBaseVNode("table", null, [
            _cache[10] || (_cache[10] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "标题"),
                createBaseVNode("th", null, "语言"),
                createBaseVNode("th", null, "确认来源"),
                createBaseVNode("th", null, "状态"),
                createBaseVNode("th", null, "正式记录风险"),
                createBaseVNode("th", null, "关联舆情当前风险"),
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
                  onClick: ($event) => goDetail(row)
                }, [
                  createBaseVNode("td", _hoisted_16, toDisplayString(row.title || "无标题"), 1),
                  createBaseVNode("td", null, toDisplayString(zh(row.language)), 1),
                  createBaseVNode("td", null, toDisplayString(zh(row.confirmation_source || "manual")), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["status", { on: row.event_status === "monitoring", failed: row.event_status === "failed" }])
                    }, toDisplayString(zh(row.event_status)), 3)
                  ]),
                  createBaseVNode("td", null, toDisplayString(zh(row.formal_risk_level || row.risk_level)), 1),
                  createBaseVNode("td", null, [
                    row.linked_opinion_current_risk ? (openBlock(), createElementBlock("span", _hoisted_17, [
                      createTextVNode(toDisplayString(row.linked_opinion_current_risk.risk_score ?? "-") + " · " + toDisplayString(zh(row.linked_opinion_current_risk.risk_level)) + " ", 1),
                      createBaseVNode("small", _hoisted_18, "（" + toDisplayString(row.linked_opinion_current_risk.source === "ai" ? "AI" : "规则") + "）", 1)
                    ])) : (openBlock(), createElementBlock("span", _hoisted_19, "-"))
                  ]),
                  createBaseVNode("td", null, toDisplayString(row.heat_score ?? "-"), 1),
                  createBaseVNode("td", null, toDisplayString(row.opinion_count), 1),
                  createBaseVNode("td", null, toDisplayString(row.source_count), 1),
                  createBaseVNode("td", null, toDisplayString(Math.round(row.confidence * 100)) + "%", 1),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.first_seen_at)), 1),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.last_seen_at)), 1),
                  createBaseVNode("td", {
                    class: "col-center operation-col",
                    onClick: _cache[2] || (_cache[2] = withModifiers(() => {
                    }, ["stop"]))
                  }, [
                    createBaseVNode("div", _hoisted_20, [
                      createBaseVNode("button", {
                        class: "btn-operate",
                        title: "查看事件详情",
                        onClick: withModifiers(($event) => goDetail(row), ["stop"])
                      }, "查看", 8, _hoisted_21),
                      createBaseVNode("button", {
                        class: "btn-operate",
                        title: "打开事件处置弹窗",
                        onClick: withModifiers(($event) => openHandle(row), ["stop"])
                      }, "处置", 8, _hoisted_22),
                      createBaseVNode("button", {
                        class: "btn-icon btn-delete",
                        title: "删除事件",
                        onClick: withModifiers(($event) => handleDelete(row), ["stop"])
                      }, "🗑", 8, _hoisted_23)
                    ])
                  ])
                ], 8, _hoisted_15);
              }), 128)),
              !foreignEvents.value.length ? (openBlock(), createElementBlock("tr", _hoisted_24, [..._cache[9] || (_cache[9] = [
                createBaseVNode("td", {
                  colspan: "13",
                  class: "empty"
                }, "暂无已确认外网事件", -1)
              ])])) : createCommentVNode("", true)
            ])
          ])
        ])) : createCommentVNode("", true),
        createVNode(EventDispositionDialog, {
          modelValue: dispositionVisible.value,
          "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => dispositionVisible.value = $event),
          "event-id": dispositionEventId.value,
          scope: "foreign",
          onUpdated: loadEvents
        }, null, 8, ["modelValue", "event-id"])
      ]);
    };
  }
});

const ForeignEventsView = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-5a270a56"]]);

export { ForeignEventsView as F };
