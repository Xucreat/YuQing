import { d as defineComponent, $ as useAlertNotifier, z as usePermission, C as onMounted, A as watch, w as withDirectives, c as createElementBlock, a as createBaseVNode, m as createVNode, p as withCtx, r as ref, g as api, y as resolveComponent, B as resolveDirective, N as useRoute, E as ElMessage, W as isPermissionDenied, o as openBlock, e as createTextVNode, q as createBlock, s as createCommentVNode, t as toDisplayString, H as unref, a0 as riskTag, a1 as riskText, Q as _sfc_main$1, b as withKeys, F as Fragment, i as renderList, j as computed, f as reactive, M as ElMessageBox, _ as _export_sfc } from './index-CLMQIstK.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-evmKrUX7.js';
import './admission-DpEuIHXC.js';
import './opinion-Cag9WtuS.js';

const _hoisted_1 = { class: "alerts" };
const _hoisted_2 = { class: "top-scope-switch" };
const _hoisted_3 = { class: "scope-bar" };
const _hoisted_4 = {
  key: 3,
  class: "eval-result"
};
const _hoisted_5 = { class: "pagination" };
const _hoisted_6 = { class: "scope-bar" };
const _hoisted_7 = { class: "inline-switch" };
const _hoisted_8 = ["onClick"];
const _hoisted_9 = { key: 1 };
const _hoisted_10 = { class: "pagination" };
const _hoisted_11 = { key: 0 };
const _hoisted_12 = { key: 1 };
const _hoisted_13 = { class: "scope-bar" };
const _hoisted_14 = {
  key: 4,
  class: "muted"
};
const _hoisted_15 = { class: "detail-pre" };
const rulesSize = 20;
const recordsSize = 20;
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Alerts",
  setup(__props) {
    const route = useRoute();
    const notifier = useAlertNotifier();
    const { hasPermission } = usePermission();
    const activeTab = ref("rules");
    const scope = ref("domestic");
    const loading = ref(false);
    const saving = ref(false);
    const evaluating = ref(false);
    const evalResult = ref(null);
    const canWriteAlert = computed(() => hasPermission("alerts:write"));
    const canEvaluateForeign = computed(() => hasPermission("foreign:alerts:evaluate"));
    const canForeignRuleWrite = computed(() => hasPermission("foreign:alerts:rules:write"));
    const canForeignRuleEnable = computed(() => hasPermission("foreign:alerts:enable"));
    const canAcknowledgeForeign = computed(() => hasPermission("foreign:alerts:acknowledge"));
    const canResolveForeign = computed(() => hasPermission("foreign:alerts:resolve"));
    const canSuppressForeign = computed(() => hasPermission("foreign:alerts:suppress"));
    const canForeignReviewConfirm = computed(() => hasPermission("foreign:alerts:review:confirm"));
    const canForeignReviewReject = computed(() => hasPermission("foreign:ai:review:reject"));
    const foreignEvaluating = ref(false);
    const rules = ref([]);
    const rulesTotal = ref(0);
    const rulesPage = ref(1);
    const foreignRules = ref([]);
    const records = ref([]);
    const recordsTotal = ref(0);
    const recordsPage = ref(1);
    const recFilterRisk = ref(null);
    const recFilterStatus = ref("");
    const hideFalsePositive = ref(true);
    const recDateRange = ref(null);
    const foreignAlerts = ref([]);
    const foreignReviews = ref([]);
    const foreignFilters = reactive({ status: "", severity: "", source: "" });
    const foreignDateRange = ref(null);
    const domesticRuleDialog = ref(false);
    const domesticEditing = ref(false);
    const domesticId = ref(null);
    const domesticForm = reactive({ name: "", description: "", risk_threshold: 70, keywords: "", sources: "", risk_level: "high", enabled: true });
    const foreignRuleDialog = ref(false);
    const foreignEditing = ref(false);
    const foreignRuleId = ref(null);
    const foreignRuleSaving = ref(false);
    const foreignForm = reactive({ name: "", description: "", rule_type: "risk_score", conditionsText: '{"threshold":80}', severity: "medium", cooldown_seconds: 3600 });
    const handleDialogVisible = ref(false);
    const handling = ref(false);
    const handlingId = ref(null);
    const handleForm = reactive({ status: "resolved", note: "" });
    const detailVisible = ref(false);
    const detailId = ref(null);
    const foreignDetailDialog = ref(false);
    const foreignDetail = ref(null);
    const foreignHistoryDialog = ref(false);
    const foreignHistory = ref([]);
    const STATUS_TEXT = { pending: "待处理", processing: "处理中", resolved: "已解决", ignored: "已忽略", false_positive: "误报" };
    const STATUS_TAG = { pending: "danger", processing: "warning", resolved: "success", ignored: "info", false_positive: "info" };
    const FOREIGN_TEXT = { triggered: "待确认", acknowledged: "已确认", resolved: "已解决", suppressed: "已抑制", failed: "失败", critical: "紧急", high: "高", medium: "中", low: "低" };
    const statusText = (v) => STATUS_TEXT[v] || v || "待处理";
    const statusTag = (v) => STATUS_TAG[v] || "info";
    const foreignText = (v) => v ? FOREIGN_TEXT[v] || v : "-";
    const formatTime = (v) => v ? v.replace("T", " ").slice(0, 19) : "-";
    function openOpinion(id) {
      detailId.value = id;
      detailVisible.value = true;
    }
    async function loadDomesticRules() {
      loading.value = true;
      try {
        const { data } = await api.get("/alerts/rules", { params: { page: rulesPage.value, size: rulesSize } });
        rules.value = data.items;
        rulesTotal.value = data.total;
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载规则失败");
      } finally {
        loading.value = false;
      }
    }
    async function loadForeignRules() {
      loading.value = true;
      try {
        foreignRules.value = (await api.get("/foreign/alert-rules", { params: { size: 100 } })).data.items || [];
      } catch (e) {
        foreignRules.value = [];
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "加载外网规则失败");
      } finally {
        loading.value = false;
      }
    }
    async function loadDomesticRecords() {
      loading.value = true;
      try {
        const params = { page: recordsPage.value, size: recordsSize };
        if (recFilterRisk.value) params.risk_level = recFilterRisk.value;
        if (recFilterStatus.value) params.status = recFilterStatus.value;
        if (hideFalsePositive.value) params.exclude_status = "false_positive";
        if (recDateRange.value?.[0]) params.date_from = recDateRange.value[0];
        if (recDateRange.value?.[1]) params.date_to = recDateRange.value[1];
        const { data } = await api.get("/alerts/records", { params });
        records.value = data.items;
        recordsTotal.value = data.total;
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载记录失败");
      } finally {
        loading.value = false;
      }
    }
    async function loadForeignRecords() {
      loading.value = true;
      try {
        const params = { page: 1, size: 100 };
        if (foreignFilters.status) params.status = foreignFilters.status;
        if (foreignFilters.severity) params.severity = foreignFilters.severity;
        if (foreignFilters.source) params.source = foreignFilters.source;
        if (foreignDateRange.value?.[0]) params.triggered_from = foreignDateRange.value[0];
        if (foreignDateRange.value?.[1]) params.triggered_to = foreignDateRange.value[1];
        foreignAlerts.value = (await api.get("/foreign/alerts", { params })).data.items || [];
      } catch (e) {
        foreignAlerts.value = [];
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "加载外网预警失败");
      } finally {
        loading.value = false;
      }
    }
    function loadCurrentScope() {
      if (activeTab.value === "foreign-review") return loadForeignReviews();
      activeTab.value === "rules" ? scope.value === "foreign" ? loadForeignRules() : loadDomesticRules() : scope.value === "foreign" ? loadForeignRecords() : loadDomesticRecords();
    }
    async function loadForeignReviews() {
      try {
        foreignReviews.value = (await api.get("/foreign/ai-analysis/reviews", { params: { size: 100, status: "pending_review" } })).data.items || [];
      } catch {
        foreignReviews.value = [];
      }
    }
    async function decideForeignReview(row, decision) {
      try {
        await api.post(`/foreign/ai-analysis/reviews/${row.id}/decision`, { decision, reason: "Alerts workspace manual review" });
        await loadForeignReviews();
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "人工复核失败");
      }
    }
    async function batchDecideForeignReviews(decision) {
      try {
        if (decision === "reject_change") await ElMessageBox.confirm("确认批量驳回当前待复核结果？", "批量驳回确认", { type: "warning" });
        await api.post("/foreign/ai-analysis/reviews/batch", { decision, confirm_all: true, reason: "Alerts workspace batch review" });
        await loadForeignReviews();
        ElMessage.success("批量复核已完成");
      } catch (e) {
        if (e !== "cancel" && e !== "close" && !isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "批量复核失败");
      }
    }
    function loadScope() {
      loadCurrentScope();
      if (scope.value === "foreign" && activeTab.value === "foreign-review") loadForeignReviews();
    }
    function openDomesticRule(row) {
      domesticEditing.value = !!row;
      domesticId.value = row?.id || null;
      Object.assign(domesticForm, row ? { name: row.name, description: row.description, risk_threshold: row.risk_threshold, keywords: row.keywords, sources: row.sources, risk_level: row.risk_level, enabled: row.enabled } : { name: "", description: "", risk_threshold: 70, keywords: "", sources: "", risk_level: "high", enabled: true });
      domesticRuleDialog.value = true;
    }
    async function saveDomesticRule() {
      if (!domesticForm.name.trim()) return ElMessage.warning("请输入规则名称");
      saving.value = true;
      try {
        if (domesticEditing.value) await api.put(`/alerts/rules/${domesticId.value}`, domesticForm);
        else await api.post("/alerts/rules", domesticForm);
        domesticRuleDialog.value = false;
        ElMessage.success("规则已保存");
        await loadDomesticRules();
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "保存失败");
      } finally {
        saving.value = false;
      }
    }
    async function toggleDomesticRule(row, enabled) {
      try {
        await api.put(`/alerts/rules/${row.id}`, { enabled });
        row.enabled = enabled;
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "操作失败");
      }
    }
    async function deleteDomesticRule(row) {
      try {
        await ElMessageBox.confirm(`确认删除规则「${row.name}」？`, "提示", { type: "warning" });
        await api.delete(`/alerts/rules/${row.id}`);
        await loadDomesticRules();
      } catch (e) {
        if (e?.response && !isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "删除失败");
      }
    }
    async function handleEvaluate() {
      if (evaluating.value) return;
      evaluating.value = true;
      try {
        const { data } = await api.post("/alerts/evaluate");
        evalResult.value = data;
        ElMessage.success("国内预警评估完成");
        if (scope.value === "domestic") await loadDomesticRecords();
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "评估失败");
      } finally {
        evaluating.value = false;
      }
    }
    function openForeignRule(row) {
      foreignEditing.value = !!row;
      foreignRuleId.value = row?.id || null;
      Object.assign(foreignForm, row ? { name: row.name, description: row.description || "", rule_type: row.rule_type, conditionsText: JSON.stringify(row.conditions || {}), severity: row.severity, cooldown_seconds: row.cooldown_seconds || 0 } : { name: "", description: "", rule_type: "risk_score", conditionsText: '{"threshold":80}', severity: "medium", cooldown_seconds: 3600 });
      foreignRuleDialog.value = true;
    }
    async function saveForeignRule() {
      if (!foreignForm.name.trim()) return ElMessage.warning("请输入规则名称");
      let conditions;
      try {
        conditions = JSON.parse(foreignForm.conditionsText || "{}");
      } catch {
        return ElMessage.warning("条件必须是有效 JSON");
      }
      foreignRuleSaving.value = true;
      try {
        const payload = { name: foreignForm.name, description: foreignForm.description, rule_type: foreignForm.rule_type, conditions, severity: foreignForm.severity, cooldown_seconds: foreignForm.cooldown_seconds };
        if (foreignEditing.value) await api.patch(`/foreign/alert-rules/${foreignRuleId.value}`, payload);
        else await api.post("/foreign/alert-rules", payload);
        foreignRuleDialog.value = false;
        await loadForeignRules();
        ElMessage.success("外网规则已保存");
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "外网规则保存失败");
      } finally {
        foreignRuleSaving.value = false;
      }
    }
    async function toggleForeignRule(row) {
      const action = row.is_enabled ? "disable" : "enable";
      if (!row.is_enabled && !canForeignRuleEnable.value) return;
      try {
        await api.post(`/foreign/alert-rules/${row.id}/${action}`);
        await loadForeignRules();
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "外网规则更新失败");
      }
    }
    async function deleteForeignRule(row) {
      try {
        await ElMessageBox.confirm(`确认删除外网规则「${row.name}」？`, "提示", { type: "warning" });
        await api.delete(`/foreign/alert-rules/${row.id}`);
        await loadForeignRules();
      } catch (e) {
        if (e?.response && !isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "外网规则删除失败");
      }
    }
    async function evaluateForeign() {
      foreignEvaluating.value = true;
      try {
        await api.post("/foreign/alerts/evaluate", { dry_run: false, max_items: 200 });
        ElMessage.success("外网预警评估完成");
        await loadForeignRecords();
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "外网评估失败");
      } finally {
        foreignEvaluating.value = false;
      }
    }
    async function handleForeign(row, action) {
      try {
        await api.post(`/foreign/alerts/${row.id}/${action}`, { note: "预警中心处理" });
        await loadForeignRecords();
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "外网预警处理失败");
      }
    }
    async function openForeignDetail(row) {
      try {
        foreignDetail.value = (await api.get(`/foreign/alerts/${row.id}`)).data;
        foreignDetailDialog.value = true;
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "详情加载失败");
      }
    }
    async function openForeignHistory(row) {
      try {
        foreignHistory.value = (await api.get(`/foreign/alerts/${row.id}/actions`)).data.items || [];
        foreignHistoryDialog.value = true;
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "历史加载失败");
      }
    }
    function openHandleDialog(row) {
      handlingId.value = row.id;
      handleForm.status = row.status || "resolved";
      handleForm.note = row.handle_note || "";
      handleDialogVisible.value = true;
    }
    async function submitHandle() {
      if (handlingId.value == null) return;
      handling.value = true;
      try {
        const { data } = await api.put(`/alerts/records/${handlingId.value}/handle`, { status: handleForm.status, note: handleForm.note });
        const idx = records.value.findIndex((item) => item.id === handlingId.value);
        if (idx >= 0) records.value[idx] = data;
        handleDialogVisible.value = false;
      } catch (e) {
        if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || "处置失败");
      } finally {
        handling.value = false;
      }
    }
    function normalizeRoute() {
      const tab = String(route.query.tab || "rules");
      const queryScope = String(route.query.scope || "");
      activeTab.value = tab === "records" ? "records" : tab === "foreign-review" ? "foreign-review" : "rules";
      scope.value = queryScope === "foreign" || tab === "foreign" || tab === "foreign-rules" || tab === "foreign-review" ? "foreign" : "domestic";
    }
    onMounted(() => {
      normalizeRoute();
      loadCurrentScope();
      if (activeTab.value === "records") notifier.markVisited();
    });
    watch(() => [route.query.tab, route.query.scope], () => {
      normalizeRoute();
      loadCurrentScope();
    });
    watch(activeTab, (tab) => {
      if (tab === "records") notifier.markVisited();
      loadCurrentScope();
    });
    return (_ctx, _cache) => {
      const _component_el_radio_button = resolveComponent("el-radio-button");
      const _component_el_radio_group = resolveComponent("el-radio-group");
      const _component_el_button = resolveComponent("el-button");
      const _component_el_table_column = resolveComponent("el-table-column");
      const _component_el_tag = resolveComponent("el-tag");
      const _component_el_switch = resolveComponent("el-switch");
      const _component_el_table = resolveComponent("el-table");
      const _component_el_card = resolveComponent("el-card");
      const _component_el_tab_pane = resolveComponent("el-tab-pane");
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_date_picker = resolveComponent("el-date-picker");
      const _component_el_input = resolveComponent("el-input");
      const _component_el_empty = resolveComponent("el-empty");
      const _component_el_tabs = resolveComponent("el-tabs");
      const _component_el_form_item = resolveComponent("el-form-item");
      const _component_el_input_number = resolveComponent("el-input-number");
      const _component_el_form = resolveComponent("el-form");
      const _component_el_dialog = resolveComponent("el-dialog");
      const _component_el_timeline_item = resolveComponent("el-timeline-item");
      const _component_el_timeline = resolveComponent("el-timeline");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createVNode(_component_el_radio_group, {
            modelValue: scope.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => scope.value = $event),
            onChange: loadScope
          }, {
            default: withCtx(() => [
              createVNode(_component_el_radio_button, { label: "domestic" }, {
                default: withCtx(() => [..._cache[40] || (_cache[40] = [
                  createTextVNode("国内", -1)
                ])]),
                _: 1
              }),
              createVNode(_component_el_radio_button, { label: "foreign" }, {
                default: withCtx(() => [..._cache[41] || (_cache[41] = [
                  createTextVNode("外网", -1)
                ])]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        createVNode(_component_el_tabs, {
          modelValue: activeTab.value,
          "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => activeTab.value = $event)
        }, {
          default: withCtx(() => [
            createVNode(_component_el_tab_pane, {
              label: "预警规则",
              name: "rules"
            }, {
              default: withCtx(() => [
                createBaseVNode("div", _hoisted_3, [
                  createVNode(_component_el_button, { onClick: loadCurrentScope }, {
                    default: withCtx(() => [..._cache[42] || (_cache[42] = [
                      createTextVNode("刷新", -1)
                    ])]),
                    _: 1
                  }),
                  scope.value === "domestic" && canWriteAlert.value ? (openBlock(), createBlock(_component_el_button, {
                    key: 0,
                    type: "primary",
                    onClick: _cache[1] || (_cache[1] = ($event) => openDomesticRule(null))
                  }, {
                    default: withCtx(() => [..._cache[43] || (_cache[43] = [
                      createTextVNode("新增规则", -1)
                    ])]),
                    _: 1
                  })) : createCommentVNode("", true),
                  scope.value === "domestic" && canWriteAlert.value ? (openBlock(), createBlock(_component_el_button, {
                    key: 1,
                    type: "warning",
                    loading: evaluating.value,
                    onClick: handleEvaluate
                  }, {
                    default: withCtx(() => [..._cache[44] || (_cache[44] = [
                      createTextVNode("执行评估", -1)
                    ])]),
                    _: 1
                  }, 8, ["loading"])) : createCommentVNode("", true),
                  scope.value === "foreign" && canForeignRuleWrite.value ? (openBlock(), createBlock(_component_el_button, {
                    key: 2,
                    type: "primary",
                    onClick: _cache[2] || (_cache[2] = ($event) => openForeignRule(null))
                  }, {
                    default: withCtx(() => [..._cache[45] || (_cache[45] = [
                      createTextVNode("新增外网规则", -1)
                    ])]),
                    _: 1
                  })) : createCommentVNode("", true),
                  evalResult.value && scope.value === "domestic" ? (openBlock(), createElementBlock("span", _hoisted_4, "检查 " + toDisplayString(evalResult.value.total_checked) + " 条，生成 " + toDisplayString(evalResult.value.alerts_created) + " 条", 1)) : createCommentVNode("", true)
                ]),
                scope.value === "domestic" ? (openBlock(), createBlock(_component_el_card, {
                  key: 0,
                  shadow: "never",
                  class: "table-card"
                }, {
                  default: withCtx(() => [
                    createVNode(_component_el_table, {
                      data: rules.value,
                      stripe: ""
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_table_column, {
                          type: "index",
                          index: (idx) => (rulesPage.value - 1) * rulesSize + idx + 1,
                          label: "ID",
                          width: "70"
                        }, null, 8, ["index"]),
                        createVNode(_component_el_table_column, {
                          prop: "name",
                          label: "规则名称",
                          "min-width": "200",
                          "show-overflow-tooltip": ""
                        }),
                        createVNode(_component_el_table_column, {
                          prop: "description",
                          label: "描述",
                          "min-width": "200",
                          "show-overflow-tooltip": ""
                        }),
                        createVNode(_component_el_table_column, {
                          label: "风险阈值",
                          width: "100"
                        }, {
                          default: withCtx(({ row }) => [
                            createTextVNode(toDisplayString(row.risk_threshold), 1)
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "预警等级",
                          width: "120"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_tag, {
                              type: unref(riskTag)(row.risk_level),
                              size: "small"
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(unref(riskText)(row.risk_level)), 1)
                              ]),
                              _: 2
                            }, 1032, ["type"])
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "状态",
                          width: "100"
                        }, {
                          default: withCtx(({ row }) => [
                            canWriteAlert.value ? (openBlock(), createBlock(_component_el_switch, {
                              key: 0,
                              "model-value": row.enabled,
                              onChange: (val) => toggleDomesticRule(row, val)
                            }, null, 8, ["model-value", "onChange"])) : (openBlock(), createBlock(_component_el_tag, {
                              key: 1,
                              size: "small"
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(row.enabled ? "已启用" : "已停用"), 1)
                              ]),
                              _: 2
                            }, 1024))
                          ]),
                          _: 1
                        }),
                        canWriteAlert.value ? (openBlock(), createBlock(_component_el_table_column, {
                          key: 0,
                          label: "操作",
                          width: "160"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_button, {
                              link: "",
                              type: "primary",
                              onClick: ($event) => openDomesticRule(row)
                            }, {
                              default: withCtx(() => [..._cache[46] || (_cache[46] = [
                                createTextVNode("编辑", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"]),
                            createVNode(_component_el_button, {
                              link: "",
                              type: "danger",
                              onClick: ($event) => deleteDomesticRule(row)
                            }, {
                              default: withCtx(() => [..._cache[47] || (_cache[47] = [
                                createTextVNode("删除", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"])
                          ]),
                          _: 1
                        })) : createCommentVNode("", true)
                      ]),
                      _: 1
                    }, 8, ["data"]),
                    createBaseVNode("div", _hoisted_5, [
                      createVNode(_sfc_main$1, {
                        total: rulesTotal.value,
                        "current-page": rulesPage.value,
                        "page-size": rulesSize,
                        onCurrentChange: _cache[3] || (_cache[3] = (p) => {
                          rulesPage.value = p;
                          loadDomesticRules();
                        })
                      }, null, 8, ["total", "current-page"])
                    ])
                  ]),
                  _: 1
                })) : (openBlock(), createBlock(_component_el_card, {
                  key: 1,
                  shadow: "never",
                  class: "table-card"
                }, {
                  default: withCtx(() => [
                    createVNode(_component_el_table, {
                      data: foreignRules.value,
                      stripe: ""
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_table_column, {
                          prop: "name",
                          label: "规则名称",
                          "min-width": "220",
                          "show-overflow-tooltip": ""
                        }),
                        createVNode(_component_el_table_column, {
                          prop: "rule_type",
                          label: "类型",
                          width: "150"
                        }),
                        createVNode(_component_el_table_column, {
                          prop: "severity",
                          label: "严重度",
                          width: "100"
                        }),
                        createVNode(_component_el_table_column, {
                          label: "状态",
                          width: "110"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_tag, {
                              size: "small",
                              type: row.is_enabled ? "success" : "info"
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(row.is_enabled ? "已启用" : "已停用"), 1)
                              ]),
                              _: 2
                            }, 1032, ["type"])
                          ]),
                          _: 1
                        }),
                        canForeignRuleWrite.value ? (openBlock(), createBlock(_component_el_table_column, {
                          key: 0,
                          label: "操作",
                          width: "260"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_button, {
                              link: "",
                              type: "primary",
                              onClick: ($event) => openForeignRule(row)
                            }, {
                              default: withCtx(() => [..._cache[48] || (_cache[48] = [
                                createTextVNode("编辑", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"]),
                            createVNode(_component_el_button, {
                              link: "",
                              onClick: ($event) => toggleForeignRule(row)
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(row.is_enabled ? "停用" : "启用"), 1)
                              ]),
                              _: 2
                            }, 1032, ["onClick"]),
                            !row.is_enabled ? (openBlock(), createBlock(_component_el_button, {
                              key: 0,
                              link: "",
                              type: "danger",
                              onClick: ($event) => deleteForeignRule(row)
                            }, {
                              default: withCtx(() => [..._cache[49] || (_cache[49] = [
                                createTextVNode("删除", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"])) : createCommentVNode("", true)
                          ]),
                          _: 1
                        })) : createCommentVNode("", true)
                      ]),
                      _: 1
                    }, 8, ["data"])
                  ]),
                  _: 1
                }))
              ]),
              _: 1
            }),
            createVNode(_component_el_tab_pane, {
              label: "预警记录",
              name: "records"
            }, {
              default: withCtx(() => [
                createBaseVNode("div", _hoisted_6, [
                  createVNode(_component_el_button, { onClick: loadCurrentScope }, {
                    default: withCtx(() => [..._cache[50] || (_cache[50] = [
                      createTextVNode("刷新", -1)
                    ])]),
                    _: 1
                  }),
                  scope.value === "domestic" && canWriteAlert.value ? (openBlock(), createBlock(_component_el_button, {
                    key: 0,
                    type: "warning",
                    loading: evaluating.value,
                    onClick: handleEvaluate
                  }, {
                    default: withCtx(() => [..._cache[51] || (_cache[51] = [
                      createTextVNode("执行评估", -1)
                    ])]),
                    _: 1
                  }, 8, ["loading"])) : createCommentVNode("", true),
                  scope.value === "foreign" && canEvaluateForeign.value ? (openBlock(), createBlock(_component_el_button, {
                    key: 1,
                    type: "warning",
                    loading: foreignEvaluating.value,
                    onClick: evaluateForeign
                  }, {
                    default: withCtx(() => [..._cache[52] || (_cache[52] = [
                      createTextVNode("执行外网评估", -1)
                    ])]),
                    _: 1
                  }, 8, ["loading"])) : createCommentVNode("", true)
                ]),
                scope.value === "domestic" ? (openBlock(), createBlock(_component_el_card, {
                  key: 0,
                  shadow: "never",
                  class: "filter-card"
                }, {
                  default: withCtx(() => [
                    createVNode(_component_el_select, {
                      modelValue: recFilterRisk.value,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => recFilterRisk.value = $event),
                      placeholder: "预警等级",
                      clearable: "",
                      class: "filter-select",
                      onChange: loadDomesticRecords
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          label: "严重",
                          value: "critical"
                        }),
                        createVNode(_component_el_option, {
                          label: "高",
                          value: "high"
                        }),
                        createVNode(_component_el_option, {
                          label: "中",
                          value: "medium"
                        }),
                        createVNode(_component_el_option, {
                          label: "低",
                          value: "low"
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"]),
                    createVNode(_component_el_select, {
                      modelValue: recFilterStatus.value,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => recFilterStatus.value = $event),
                      placeholder: "处置状态",
                      clearable: "",
                      class: "filter-select",
                      onChange: loadDomesticRecords
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          label: "待处理",
                          value: "pending"
                        }),
                        createVNode(_component_el_option, {
                          label: "处理中",
                          value: "processing"
                        }),
                        createVNode(_component_el_option, {
                          label: "已解决",
                          value: "resolved"
                        }),
                        createVNode(_component_el_option, {
                          label: "已忽略",
                          value: "ignored"
                        }),
                        createVNode(_component_el_option, {
                          label: "误报",
                          value: "false_positive"
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"]),
                    createBaseVNode("span", _hoisted_7, [
                      createVNode(_component_el_switch, {
                        modelValue: hideFalsePositive.value,
                        "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => hideFalsePositive.value = $event),
                        onChange: loadDomesticRecords
                      }, null, 8, ["modelValue"]),
                      _cache[53] || (_cache[53] = createTextVNode("隐藏误报", -1))
                    ]),
                    createVNode(_component_el_date_picker, {
                      modelValue: recDateRange.value,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => recDateRange.value = $event),
                      type: "daterange",
                      "range-separator": "至",
                      "start-placeholder": "开始日期",
                      "end-placeholder": "结束日期",
                      "value-format": "YYYY-MM-DD",
                      onChange: loadDomesticRecords
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })) : (openBlock(), createBlock(_component_el_card, {
                  key: 1,
                  shadow: "never",
                  class: "filter-card"
                }, {
                  default: withCtx(() => [
                    createVNode(_component_el_select, {
                      modelValue: foreignFilters.status,
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => foreignFilters.status = $event),
                      placeholder: "状态",
                      clearable: "",
                      class: "filter-select",
                      onChange: loadForeignRecords
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          label: "待确认",
                          value: "triggered"
                        }),
                        createVNode(_component_el_option, {
                          label: "已确认",
                          value: "acknowledged"
                        }),
                        createVNode(_component_el_option, {
                          label: "已解决",
                          value: "resolved"
                        }),
                        createVNode(_component_el_option, {
                          label: "已抑制",
                          value: "suppressed"
                        }),
                        createVNode(_component_el_option, {
                          label: "失败",
                          value: "failed"
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"]),
                    createVNode(_component_el_select, {
                      modelValue: foreignFilters.severity,
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => foreignFilters.severity = $event),
                      placeholder: "严重度",
                      clearable: "",
                      class: "filter-select",
                      onChange: loadForeignRecords
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          label: "低",
                          value: "low"
                        }),
                        createVNode(_component_el_option, {
                          label: "中",
                          value: "medium"
                        }),
                        createVNode(_component_el_option, {
                          label: "高",
                          value: "high"
                        }),
                        createVNode(_component_el_option, {
                          label: "紧急",
                          value: "critical"
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"]),
                    createVNode(_component_el_input, {
                      modelValue: foreignFilters.source,
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => foreignFilters.source = $event),
                      placeholder: "来源",
                      clearable: "",
                      class: "filter-select",
                      onKeyup: withKeys(loadForeignRecords, ["enter"])
                    }, null, 8, ["modelValue"]),
                    createVNode(_component_el_date_picker, {
                      modelValue: foreignDateRange.value,
                      "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => foreignDateRange.value = $event),
                      type: "daterange",
                      "range-separator": "至",
                      "start-placeholder": "开始日期",
                      "end-placeholder": "结束日期",
                      "value-format": "YYYY-MM-DD",
                      onChange: loadForeignRecords
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })),
                scope.value === "domestic" ? (openBlock(), createBlock(_component_el_card, {
                  key: 2,
                  shadow: "never",
                  class: "table-card"
                }, {
                  default: withCtx(() => [
                    createVNode(_component_el_table, {
                      data: records.value,
                      stripe: ""
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_table_column, {
                          type: "index",
                          label: "ID",
                          width: "70"
                        }),
                        createVNode(_component_el_table_column, {
                          prop: "rule_name",
                          label: "触发规则",
                          width: "200",
                          "show-overflow-tooltip": ""
                        }),
                        createVNode(_component_el_table_column, {
                          label: "预警等级",
                          width: "110"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_tag, {
                              type: unref(riskTag)(row.risk_level),
                              size: "small"
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(unref(riskText)(row.risk_level)), 1)
                              ]),
                              _: 2
                            }, 1032, ["type"])
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "关联舆情",
                          "min-width": "220"
                        }, {
                          default: withCtx(({ row }) => [
                            row.opinion_id ? (openBlock(), createElementBlock("span", {
                              key: 0,
                              class: "nav-link",
                              onClick: ($event) => openOpinion(row.opinion_id)
                            }, toDisplayString(row.opinion_title), 9, _hoisted_8)) : (openBlock(), createElementBlock("span", _hoisted_9, toDisplayString(row.opinion_title || "-"), 1))
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          prop: "trigger_reason",
                          label: "触发原因",
                          "min-width": "220",
                          "show-overflow-tooltip": ""
                        }),
                        createVNode(_component_el_table_column, {
                          label: "处置状态",
                          width: "110"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_tag, {
                              type: statusTag(row.status),
                              size: "small"
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(statusText(row.status)), 1)
                              ]),
                              _: 2
                            }, 1032, ["type"])
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "触发时间",
                          width: "180"
                        }, {
                          default: withCtx(({ row }) => [
                            createTextVNode(toDisplayString(formatTime(row.created_at)), 1)
                          ]),
                          _: 1
                        }),
                        canWriteAlert.value ? (openBlock(), createBlock(_component_el_table_column, {
                          key: 0,
                          label: "操作",
                          width: "100"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_button, {
                              link: "",
                              type: "primary",
                              onClick: ($event) => openHandleDialog(row)
                            }, {
                              default: withCtx(() => [..._cache[54] || (_cache[54] = [
                                createTextVNode("处置", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"])
                          ]),
                          _: 1
                        })) : createCommentVNode("", true)
                      ]),
                      _: 1
                    }, 8, ["data"]),
                    createBaseVNode("div", _hoisted_10, [
                      createVNode(_sfc_main$1, {
                        total: recordsTotal.value,
                        "current-page": recordsPage.value,
                        "page-size": recordsSize,
                        onCurrentChange: _cache[12] || (_cache[12] = (p) => {
                          recordsPage.value = p;
                          loadDomesticRecords();
                        })
                      }, null, 8, ["total", "current-page"])
                    ])
                  ]),
                  _: 1
                })) : (openBlock(), createBlock(_component_el_card, {
                  key: 3,
                  shadow: "never",
                  class: "table-card"
                }, {
                  default: withCtx(() => [
                    createVNode(_component_el_table, {
                      data: foreignAlerts.value,
                      stripe: ""
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_table_column, {
                          prop: "title",
                          label: "预警",
                          "min-width": "240",
                          "show-overflow-tooltip": ""
                        }),
                        createVNode(_component_el_table_column, {
                          prop: "severity",
                          label: "严重度",
                          width: "100"
                        }),
                        createVNode(_component_el_table_column, {
                          prop: "status",
                          label: "状态",
                          width: "110"
                        }),
                        createVNode(_component_el_table_column, {
                          prop: "source_name_snapshot",
                          label: "来源",
                          width: "150",
                          "show-overflow-tooltip": ""
                        }),
                        createVNode(_component_el_table_column, {
                          label: "告警记录值",
                          width: "120"
                        }, {
                          default: withCtx(({ row }) => [
                            createTextVNode(toDisplayString(row.risk_score ?? "-") + " / " + toDisplayString(foreignText(row.risk_level)), 1)
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "当前有效风险",
                          width: "150"
                        }, {
                          default: withCtx(({ row }) => [
                            row.effective_risk ? (openBlock(), createElementBlock("span", _hoisted_11, toDisplayString(row.effective_risk.risk_score ?? "-") + " / " + toDisplayString(foreignText(row.effective_risk.risk_level)), 1)) : (openBlock(), createElementBlock("span", _hoisted_12, "-"))
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "触发时间",
                          width: "180"
                        }, {
                          default: withCtx(({ row }) => [
                            createTextVNode(toDisplayString(formatTime(row.triggered_at)), 1)
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "操作",
                          "min-width": "280"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_button, {
                              link: "",
                              onClick: ($event) => openForeignDetail(row)
                            }, {
                              default: withCtx(() => [..._cache[55] || (_cache[55] = [
                                createTextVNode("详情", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"]),
                            createVNode(_component_el_button, {
                              link: "",
                              onClick: ($event) => openForeignHistory(row)
                            }, {
                              default: withCtx(() => [..._cache[56] || (_cache[56] = [
                                createTextVNode("处置历史", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"]),
                            row.status === "triggered" ? (openBlock(), createBlock(_component_el_button, {
                              key: 0,
                              link: "",
                              type: "primary",
                              disabled: !canAcknowledgeForeign.value,
                              onClick: ($event) => handleForeign(row, "acknowledge")
                            }, {
                              default: withCtx(() => [..._cache[57] || (_cache[57] = [
                                createTextVNode("确认", -1)
                              ])]),
                              _: 1
                            }, 8, ["disabled", "onClick"])) : createCommentVNode("", true),
                            row.status === "triggered" || row.status === "acknowledged" ? (openBlock(), createBlock(_component_el_button, {
                              key: 1,
                              link: "",
                              type: "success",
                              disabled: !canResolveForeign.value,
                              onClick: ($event) => handleForeign(row, "resolve")
                            }, {
                              default: withCtx(() => [..._cache[58] || (_cache[58] = [
                                createTextVNode("解决", -1)
                              ])]),
                              _: 1
                            }, 8, ["disabled", "onClick"])) : createCommentVNode("", true),
                            row.status === "triggered" || row.status === "acknowledged" ? (openBlock(), createBlock(_component_el_button, {
                              key: 2,
                              link: "",
                              type: "warning",
                              disabled: !canSuppressForeign.value,
                              onClick: ($event) => handleForeign(row, "suppress")
                            }, {
                              default: withCtx(() => [..._cache[59] || (_cache[59] = [
                                createTextVNode("抑制", -1)
                              ])]),
                              _: 1
                            }, 8, ["disabled", "onClick"])) : createCommentVNode("", true)
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }, 8, ["data"])
                  ]),
                  _: 1
                }))
              ]),
              _: 1
            }),
            scope.value === "foreign" ? (openBlock(), createBlock(_component_el_tab_pane, {
              key: 0,
              label: "外网人工复核",
              name: "foreign-review"
            }, {
              default: withCtx(() => [
                createBaseVNode("div", _hoisted_13, [
                  createVNode(_component_el_button, { onClick: loadForeignReviews }, {
                    default: withCtx(() => [..._cache[60] || (_cache[60] = [
                      createTextVNode("刷新", -1)
                    ])]),
                    _: 1
                  }),
                  canForeignReviewConfirm.value ? (openBlock(), createBlock(_component_el_button, {
                    key: 0,
                    type: "primary",
                    onClick: _cache[13] || (_cache[13] = ($event) => batchDecideForeignReviews("confirm_alert_change"))
                  }, {
                    default: withCtx(() => [..._cache[61] || (_cache[61] = [
                      createTextVNode("批量确认预警", -1)
                    ])]),
                    _: 1
                  })) : createCommentVNode("", true),
                  canForeignReviewConfirm.value ? (openBlock(), createBlock(_component_el_button, {
                    key: 1,
                    type: "danger",
                    onClick: _cache[14] || (_cache[14] = ($event) => batchDecideForeignReviews("reject_change"))
                  }, {
                    default: withCtx(() => [..._cache[62] || (_cache[62] = [
                      createTextVNode("批量驳回", -1)
                    ])]),
                    _: 1
                  })) : createCommentVNode("", true),
                  _cache[63] || (_cache[63] = createBaseVNode("span", { class: "muted" }, "AI 结果仅在人工确认后进入正式业务流程", -1))
                ]),
                createVNode(_component_el_card, {
                  shadow: "never",
                  class: "table-card"
                }, {
                  default: withCtx(() => [
                    createVNode(_component_el_table, {
                      data: foreignReviews.value,
                      stripe: ""
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_table_column, {
                          prop: "foreign_opinion_id",
                          label: "舆情 ID",
                          width: "100"
                        }),
                        createVNode(_component_el_table_column, {
                          label: "规则风险",
                          "min-width": "140"
                        }, {
                          default: withCtx(({ row }) => [
                            createTextVNode(toDisplayString(row.rule_risk_snapshot?.risk_score ?? "-") + " / " + toDisplayString(row.rule_risk_snapshot?.risk_level || "-"), 1)
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "AI 风险",
                          "min-width": "140"
                        }, {
                          default: withCtx(({ row }) => [
                            createTextVNode(toDisplayString(row.ai_risk_snapshot?.risk_score ?? "-") + " / " + toDisplayString(row.ai_risk_snapshot?.risk_level || "-"), 1)
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          prop: "review_status",
                          label: "状态",
                          width: "130"
                        }),
                        createVNode(_component_el_table_column, {
                          label: "事件影响",
                          width: "120"
                        }, {
                          default: withCtx(({ row }) => [
                            createTextVNode(toDisplayString(row.event_preview?.candidate_count || 0), 1)
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "预警影响",
                          width: "120"
                        }, {
                          default: withCtx(({ row }) => [
                            createTextVNode(toDisplayString(row.alert_preview?.triggered_count || 0), 1)
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "操作",
                          "min-width": "320"
                        }, {
                          default: withCtx(({ row }) => [
                            row.review_status === "pending_review" ? (openBlock(), createBlock(_component_el_button, {
                              key: 0,
                              link: "",
                              type: "primary",
                              onClick: ($event) => decideForeignReview(row, "use_ai_display")
                            }, {
                              default: withCtx(() => [..._cache[64] || (_cache[64] = [
                                createTextVNode("采用 AI 展示", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"])) : createCommentVNode("", true),
                            row.review_status === "pending_review" ? (openBlock(), createBlock(_component_el_button, {
                              key: 1,
                              link: "",
                              onClick: ($event) => decideForeignReview(row, "keep_rule")
                            }, {
                              default: withCtx(() => [..._cache[65] || (_cache[65] = [
                                createTextVNode("保留规则", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"])) : createCommentVNode("", true),
                            row.review_status === "pending_review" && canForeignReviewConfirm.value ? (openBlock(), createBlock(_component_el_button, {
                              key: 2,
                              link: "",
                              type: "primary",
                              onClick: ($event) => decideForeignReview(row, "confirm_alert_change")
                            }, {
                              default: withCtx(() => [..._cache[66] || (_cache[66] = [
                                createTextVNode("确认预警", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"])) : createCommentVNode("", true),
                            row.review_status === "pending_review" && canForeignReviewReject.value ? (openBlock(), createBlock(_component_el_button, {
                              key: 3,
                              link: "",
                              type: "danger",
                              onClick: ($event) => decideForeignReview(row, "reject_change")
                            }, {
                              default: withCtx(() => [..._cache[67] || (_cache[67] = [
                                createTextVNode("驳回", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"])) : (openBlock(), createElementBlock("span", _hoisted_14, toDisplayString(row.review_reason || "-"), 1))
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }, 8, ["data"]),
                    !foreignReviews.value.length ? (openBlock(), createBlock(_component_el_empty, {
                      key: 0,
                      description: "暂无外网人工复核"
                    })) : createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })) : createCommentVNode("", true)
          ]),
          _: 1
        }, 8, ["modelValue"]),
        createVNode(_component_el_dialog, {
          modelValue: domesticRuleDialog.value,
          "onUpdate:modelValue": _cache[24] || (_cache[24] = ($event) => domesticRuleDialog.value = $event),
          title: domesticEditing.value ? "编辑规则" : "新增规则",
          width: "min(600px, calc(100vw - 24px))"
        }, {
          footer: withCtx(() => [
            createVNode(_component_el_button, {
              onClick: _cache[23] || (_cache[23] = ($event) => domesticRuleDialog.value = false)
            }, {
              default: withCtx(() => [..._cache[68] || (_cache[68] = [
                createTextVNode("取消", -1)
              ])]),
              _: 1
            }),
            createVNode(_component_el_button, {
              type: "primary",
              loading: saving.value,
              onClick: saveDomesticRule
            }, {
              default: withCtx(() => [..._cache[69] || (_cache[69] = [
                createTextVNode("保存", -1)
              ])]),
              _: 1
            }, 8, ["loading"])
          ]),
          default: withCtx(() => [
            createVNode(_component_el_form, {
              model: domesticForm,
              "label-width": "100px"
            }, {
              default: withCtx(() => [
                createVNode(_component_el_form_item, { label: "规则名称" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: domesticForm.name,
                      "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => domesticForm.name = $event)
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "描述" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: domesticForm.description,
                      "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => domesticForm.description = $event),
                      type: "textarea"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "风险阈值" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input_number, {
                      modelValue: domesticForm.risk_threshold,
                      "onUpdate:modelValue": _cache[18] || (_cache[18] = ($event) => domesticForm.risk_threshold = $event),
                      min: 0,
                      max: 100
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "关键词匹配" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: domesticForm.keywords,
                      "onUpdate:modelValue": _cache[19] || (_cache[19] = ($event) => domesticForm.keywords = $event)
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "来源过滤" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: domesticForm.sources,
                      "onUpdate:modelValue": _cache[20] || (_cache[20] = ($event) => domesticForm.sources = $event)
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "建议等级" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_select, {
                      modelValue: domesticForm.risk_level,
                      "onUpdate:modelValue": _cache[21] || (_cache[21] = ($event) => domesticForm.risk_level = $event)
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          label: "严重",
                          value: "critical"
                        }),
                        createVNode(_component_el_option, {
                          label: "高",
                          value: "high"
                        }),
                        createVNode(_component_el_option, {
                          label: "中",
                          value: "medium"
                        }),
                        createVNode(_component_el_option, {
                          label: "低",
                          value: "low"
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "启用" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_switch, {
                      modelValue: domesticForm.enabled,
                      "onUpdate:modelValue": _cache[22] || (_cache[22] = ($event) => domesticForm.enabled = $event)
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }, 8, ["model"])
          ]),
          _: 1
        }, 8, ["modelValue", "title"]),
        createVNode(_component_el_dialog, {
          modelValue: foreignRuleDialog.value,
          "onUpdate:modelValue": _cache[32] || (_cache[32] = ($event) => foreignRuleDialog.value = $event),
          title: foreignEditing.value ? "编辑外网告警规则" : "新增外网告警规则",
          width: "min(620px, calc(100vw - 24px))"
        }, {
          footer: withCtx(() => [
            createVNode(_component_el_button, {
              onClick: _cache[31] || (_cache[31] = ($event) => foreignRuleDialog.value = false)
            }, {
              default: withCtx(() => [..._cache[70] || (_cache[70] = [
                createTextVNode("取消", -1)
              ])]),
              _: 1
            }),
            createVNode(_component_el_button, {
              type: "primary",
              loading: foreignRuleSaving.value,
              onClick: saveForeignRule
            }, {
              default: withCtx(() => [..._cache[71] || (_cache[71] = [
                createTextVNode("保存", -1)
              ])]),
              _: 1
            }, 8, ["loading"])
          ]),
          default: withCtx(() => [
            createVNode(_component_el_form, {
              model: foreignForm,
              "label-width": "110px"
            }, {
              default: withCtx(() => [
                createVNode(_component_el_form_item, { label: "规则名称" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: foreignForm.name,
                      "onUpdate:modelValue": _cache[25] || (_cache[25] = ($event) => foreignForm.name = $event)
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "规则类型" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_select, {
                      modelValue: foreignForm.rule_type,
                      "onUpdate:modelValue": _cache[26] || (_cache[26] = ($event) => foreignForm.rule_type = $event)
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          value: "risk_score",
                          label: "风险分"
                        }),
                        createVNode(_component_el_option, {
                          value: "risk_level",
                          label: "风险等级"
                        }),
                        createVNode(_component_el_option, {
                          value: "risk_category",
                          label: "风险类别"
                        }),
                        createVNode(_component_el_option, {
                          value: "confirmed_event",
                          label: "确认事件"
                        }),
                        createVNode(_component_el_option, {
                          value: "keyword_combo",
                          label: "关键词组合"
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "条件 JSON" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: foreignForm.conditionsText,
                      "onUpdate:modelValue": _cache[27] || (_cache[27] = ($event) => foreignForm.conditionsText = $event),
                      type: "textarea",
                      rows: 3
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "严重度" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_select, {
                      modelValue: foreignForm.severity,
                      "onUpdate:modelValue": _cache[28] || (_cache[28] = ($event) => foreignForm.severity = $event)
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          value: "low",
                          label: "低"
                        }),
                        createVNode(_component_el_option, {
                          value: "medium",
                          label: "中"
                        }),
                        createVNode(_component_el_option, {
                          value: "high",
                          label: "高"
                        }),
                        createVNode(_component_el_option, {
                          value: "critical",
                          label: "紧急"
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "冷却时间" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input_number, {
                      modelValue: foreignForm.cooldown_seconds,
                      "onUpdate:modelValue": _cache[29] || (_cache[29] = ($event) => foreignForm.cooldown_seconds = $event),
                      min: 0
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "说明" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: foreignForm.description,
                      "onUpdate:modelValue": _cache[30] || (_cache[30] = ($event) => foreignForm.description = $event),
                      type: "textarea"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }, 8, ["model"])
          ]),
          _: 1
        }, 8, ["modelValue", "title"]),
        createVNode(_component_el_dialog, {
          modelValue: foreignDetailDialog.value,
          "onUpdate:modelValue": _cache[33] || (_cache[33] = ($event) => foreignDetailDialog.value = $event),
          title: "外网预警详情",
          width: "min(760px, calc(100vw - 24px))"
        }, {
          default: withCtx(() => [
            createBaseVNode("pre", _hoisted_15, toDisplayString(JSON.stringify(foreignDetail.value, null, 2)), 1)
          ]),
          _: 1
        }, 8, ["modelValue"]),
        createVNode(_component_el_dialog, {
          modelValue: foreignHistoryDialog.value,
          "onUpdate:modelValue": _cache[34] || (_cache[34] = ($event) => foreignHistoryDialog.value = $event),
          title: "外网预警处置历史",
          width: "min(680px, calc(100vw - 24px))"
        }, {
          default: withCtx(() => [
            !foreignHistory.value.length ? (openBlock(), createBlock(_component_el_empty, {
              key: 0,
              description: "暂无处置历史"
            })) : (openBlock(), createBlock(_component_el_timeline, { key: 1 }, {
              default: withCtx(() => [
                (openBlock(true), createElementBlock(Fragment, null, renderList(foreignHistory.value, (item) => {
                  return openBlock(), createBlock(_component_el_timeline_item, {
                    key: item.id,
                    timestamp: formatTime(item.created_at)
                  }, {
                    default: withCtx(() => [
                      createTextVNode(toDisplayString(foreignText(item.previous_status)) + " → " + toDisplayString(foreignText(item.new_status)) + "：" + toDisplayString(item.note || "-"), 1)
                    ]),
                    _: 2
                  }, 1032, ["timestamp"]);
                }), 128))
              ]),
              _: 1
            }))
          ]),
          _: 1
        }, 8, ["modelValue"]),
        createVNode(_component_el_dialog, {
          modelValue: handleDialogVisible.value,
          "onUpdate:modelValue": _cache[38] || (_cache[38] = ($event) => handleDialogVisible.value = $event),
          title: "预警处置",
          width: "min(480px, calc(100vw - 24px))"
        }, {
          footer: withCtx(() => [
            createVNode(_component_el_button, {
              onClick: _cache[37] || (_cache[37] = ($event) => handleDialogVisible.value = false)
            }, {
              default: withCtx(() => [..._cache[72] || (_cache[72] = [
                createTextVNode("取消", -1)
              ])]),
              _: 1
            }),
            createVNode(_component_el_button, {
              type: "primary",
              loading: handling.value,
              onClick: submitHandle
            }, {
              default: withCtx(() => [..._cache[73] || (_cache[73] = [
                createTextVNode("确认处置", -1)
              ])]),
              _: 1
            }, 8, ["loading"])
          ]),
          default: withCtx(() => [
            createVNode(_component_el_form, { "label-width": "88px" }, {
              default: withCtx(() => [
                createVNode(_component_el_form_item, { label: "处置状态" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_select, {
                      modelValue: handleForm.status,
                      "onUpdate:modelValue": _cache[35] || (_cache[35] = ($event) => handleForm.status = $event)
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          label: "待处理",
                          value: "pending"
                        }),
                        createVNode(_component_el_option, {
                          label: "处理中",
                          value: "processing"
                        }),
                        createVNode(_component_el_option, {
                          label: "已解决",
                          value: "resolved"
                        }),
                        createVNode(_component_el_option, {
                          label: "已忽略",
                          value: "ignored"
                        }),
                        createVNode(_component_el_option, {
                          label: "误报",
                          value: "false_positive"
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "处置备注" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: handleForm.note,
                      "onUpdate:modelValue": _cache[36] || (_cache[36] = ($event) => handleForm.note = $event),
                      type: "textarea"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[39] || (_cache[39] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Alerts = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-711b7a76"]]);

export { Alerts as default };
