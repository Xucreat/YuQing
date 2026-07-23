import { d as defineComponent, L as useAlertNotifier, p as onMounted, m as watch, w as withDirectives, c as createElementBlock, B as createVNode, z as withCtx, r as ref, H as useRoute, g as api, E as ElMessage, C as resolveComponent, D as resolveDirective, o as openBlock, e as createTextVNode, t as toDisplayString, A as createCommentVNode, x as unref, M as riskTag, N as riskText, a as createBaseVNode, y as createBlock, f as reactive, O as ElMessageBox, _ as _export_sfc } from './index-Cm6t4PDU.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-BEs64aB5.js';

const _hoisted_1 = { class: "alerts" };
const _hoisted_2 = {
  key: 0,
  class: "eval-result"
};
const _hoisted_3 = { class: "pagination" };
const _hoisted_4 = ["onClick"];
const _hoisted_5 = { key: 1 };
const _hoisted_6 = { key: 1 };
const _hoisted_7 = {
  key: 1,
  style: { "color": "#86868b", "font-size": "13px" }
};
const _hoisted_8 = { class: "pagination" };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Alerts",
  setup(__props) {
    const detailVisible = ref(false);
    const detailId = ref(null);
    function openOpinion(id) {
      detailId.value = id;
      detailVisible.value = true;
    }
    const activeTab = ref("rules");
    const loading = ref(false);
    const saving = ref(false);
    const evaluating = ref(false);
    const route = useRoute();
    const notifier = useAlertNotifier();
    const rules = ref([]);
    const rulesTotal = ref(0);
    const rulesPage = ref(1);
    const rulesSize = ref(20);
    const records = ref([]);
    const recordsTotal = ref(0);
    const recordsPage = ref(1);
    const recordsSize = ref(20);
    const recFilterRisk = ref(null);
    const recFilterHandled = ref(null);
    const ruleDialogVisible = ref(false);
    const isEditing = ref(false);
    const editingId = ref(null);
    const ruleForm = reactive({ name: "", description: "", risk_threshold: 70, keywords: "", sources: "", risk_level: "high", enabled: true });
    const evalResult = ref(null);
    function formatTime(t) {
      if (!t) return "-";
      return t.replace("T", " ").slice(0, 19);
    }
    async function loadRules() {
      loading.value = true;
      try {
        const { data } = await api.get("/alerts/rules", { params: { page: rulesPage.value, size: rulesSize.value } });
        rules.value = data.items;
        rulesTotal.value = data.total;
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载规则失败");
      } finally {
        loading.value = false;
      }
    }
    async function loadRecords() {
      loading.value = true;
      try {
        const params = { page: recordsPage.value, size: recordsSize.value };
        if (recFilterRisk.value) params.risk_level = recFilterRisk.value;
        if (recFilterHandled.value !== null) params.handled = recFilterHandled.value;
        const { data } = await api.get("/alerts/records", { params });
        records.value = data.items;
        recordsTotal.value = data.total;
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载记录失败");
      } finally {
        loading.value = false;
      }
    }
    function openRuleDialog(rule) {
      if (rule) {
        isEditing.value = true;
        editingId.value = rule.id;
        ruleForm.name = rule.name;
        ruleForm.description = rule.description;
        ruleForm.risk_threshold = rule.risk_threshold;
        ruleForm.keywords = rule.keywords;
        ruleForm.sources = rule.sources;
        ruleForm.risk_level = rule.risk_level;
        ruleForm.enabled = rule.enabled;
      } else {
        isEditing.value = false;
        editingId.value = null;
        ruleForm.name = "";
        ruleForm.description = "";
        ruleForm.risk_threshold = 70;
        ruleForm.keywords = "";
        ruleForm.sources = "";
        ruleForm.risk_level = "high";
        ruleForm.enabled = true;
      }
      ruleDialogVisible.value = true;
    }
    async function saveRule() {
      if (!ruleForm.name.trim()) {
        ElMessage.warning("请输入规则名称");
        return;
      }
      saving.value = true;
      try {
        if (isEditing.value && editingId.value) {
          await api.put(`/alerts/rules/${editingId.value}`, ruleForm);
          ElMessage.success("规则已更新");
        } else {
          await api.post("/alerts/rules", ruleForm);
          ElMessage.success("规则已创建");
        }
        ruleDialogVisible.value = false;
        await loadRules();
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "保存失败");
      } finally {
        saving.value = false;
      }
    }
    async function toggleRule(rule, val) {
      try {
        await api.put(`/alerts/rules/${rule.id}`, { enabled: val });
        rule.enabled = val;
        ElMessage.success(val ? "规则已启用" : "规则已禁用");
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "操作失败");
      }
    }
    async function deleteRule(rule) {
      try {
        await ElMessageBox.confirm(`确认删除规则「${rule.name}」？`, "提示", { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" });
        await api.delete(`/alerts/rules/${rule.id}`);
        ElMessage.success("规则已删除");
        await loadRules();
      } catch {
      }
    }
    async function handleEvaluate() {
      if (evaluating.value) return;
      evaluating.value = true;
      try {
        const { data } = await api.post("/alerts/evaluate");
        evalResult.value = data;
        ElMessage.success(`评估完成：检查 ${data.total_checked} 条，生成 ${data.alerts_created} 条预警`);
        if (activeTab.value === "records") await loadRecords();
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "评估失败");
      } finally {
        evaluating.value = false;
      }
    }
    async function handleRecord(rec) {
      try {
        await api.put(`/alerts/records/${rec.id}/handle`);
        rec.handled = true;
        ElMessage.success("已标记为已处理");
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "操作失败");
      }
    }
    function handleRulesPage(p) {
      rulesPage.value = p;
      loadRules();
    }
    function handleRecordsPage(p) {
      recordsPage.value = p;
      loadRecords();
    }
    onMounted(() => {
      loadRules();
      if (route.query.tab === "records") {
        activeTab.value = "records";
        notifier.markVisited();
      }
    });
    watch(activeTab, (tab) => {
      if (tab === "records") {
        loadRecords();
        notifier.markVisited();
      }
    });
    watch(() => route.query.tab, (tab) => {
      if (tab === "records") {
        activeTab.value = "records";
        notifier.markVisited();
      }
    });
    return (_ctx, _cache) => {
      const _component_el_button = resolveComponent("el-button");
      const _component_el_card = resolveComponent("el-card");
      const _component_el_table_column = resolveComponent("el-table-column");
      const _component_el_tag = resolveComponent("el-tag");
      const _component_el_switch = resolveComponent("el-switch");
      const _component_el_table = resolveComponent("el-table");
      const _component_el_pagination = resolveComponent("el-pagination");
      const _component_el_tab_pane = resolveComponent("el-tab-pane");
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_router_link = resolveComponent("router-link");
      const _component_el_tabs = resolveComponent("el-tabs");
      const _component_el_input = resolveComponent("el-input");
      const _component_el_form_item = resolveComponent("el-form-item");
      const _component_el_input_number = resolveComponent("el-input-number");
      const _component_el_form = resolveComponent("el-form");
      const _component_el_dialog = resolveComponent("el-dialog");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createVNode(_component_el_tabs, {
          modelValue: activeTab.value,
          "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => activeTab.value = $event)
        }, {
          default: withCtx(() => [
            createVNode(_component_el_tab_pane, {
              label: "预警规则",
              name: "rules"
            }, {
              default: withCtx(() => [
                createVNode(_component_el_card, {
                  shadow: "never",
                  class: "filter-card"
                }, {
                  default: withCtx(() => [
                    createVNode(_component_el_button, {
                      type: "primary",
                      onClick: _cache[0] || (_cache[0] = ($event) => openRuleDialog(null))
                    }, {
                      default: withCtx(() => [..._cache[14] || (_cache[14] = [
                        createTextVNode("新增规则", -1)
                      ])]),
                      _: 1
                    }),
                    createVNode(_component_el_button, { onClick: loadRules }, {
                      default: withCtx(() => [..._cache[15] || (_cache[15] = [
                        createTextVNode("刷新", -1)
                      ])]),
                      _: 1
                    }),
                    createVNode(_component_el_button, {
                      type: "warning",
                      loading: evaluating.value,
                      onClick: handleEvaluate
                    }, {
                      default: withCtx(() => [..._cache[16] || (_cache[16] = [
                        createTextVNode("执行评估", -1)
                      ])]),
                      _: 1
                    }, 8, ["loading"]),
                    evalResult.value ? (openBlock(), createElementBlock("span", _hoisted_2, "评估完成：检查 " + toDisplayString(evalResult.value.total_checked) + " 条，生成 " + toDisplayString(evalResult.value.alerts_created) + " 条预警", 1)) : createCommentVNode("", true)
                  ]),
                  _: 1
                }),
                createVNode(_component_el_card, {
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
                          index: (idx) => (rulesPage.value - 1) * rulesSize.value + idx + 1,
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
                          width: "100",
                          align: "center"
                        }, {
                          default: withCtx(({ row }) => [
                            createTextVNode(toDisplayString(row.risk_threshold), 1)
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "预警等级",
                          width: "120",
                          align: "center"
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
                          width: "100",
                          align: "center"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_switch, {
                              "model-value": row.enabled,
                              onChange: (val) => toggleRule(row, val)
                            }, null, 8, ["model-value", "onChange"])
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "操作",
                          width: "180",
                          align: "center"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_button, {
                              type: "primary",
                              size: "small",
                              link: "",
                              onClick: ($event) => openRuleDialog(row)
                            }, {
                              default: withCtx(() => [..._cache[17] || (_cache[17] = [
                                createTextVNode("编辑", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"]),
                            createVNode(_component_el_button, {
                              type: "danger",
                              size: "small",
                              link: "",
                              onClick: ($event) => deleteRule(row)
                            }, {
                              default: withCtx(() => [..._cache[18] || (_cache[18] = [
                                createTextVNode("删除", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"])
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }, 8, ["data"]),
                    createBaseVNode("div", _hoisted_3, [
                      createVNode(_component_el_pagination, {
                        background: "",
                        layout: "total, prev, pager, next",
                        total: rulesTotal.value,
                        "current-page": rulesPage.value,
                        "page-size": rulesSize.value,
                        onCurrentChange: handleRulesPage
                      }, null, 8, ["total", "current-page", "page-size"])
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            createVNode(_component_el_tab_pane, {
              label: "预警记录",
              name: "records"
            }, {
              default: withCtx(() => [
                createVNode(_component_el_card, {
                  shadow: "never",
                  class: "filter-card"
                }, {
                  default: withCtx(() => [
                    createVNode(_component_el_select, {
                      modelValue: recFilterRisk.value,
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => recFilterRisk.value = $event),
                      placeholder: "预警等级",
                      clearable: "",
                      style: { "width": "160px" },
                      onChange: loadRecords
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
                      modelValue: recFilterHandled.value,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => recFilterHandled.value = $event),
                      placeholder: "处理状态",
                      clearable: "",
                      style: { "width": "160px", "margin-left": "12px" },
                      onChange: loadRecords
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          label: "未处理",
                          value: false
                        }),
                        createVNode(_component_el_option, {
                          label: "已处理",
                          value: true
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"]),
                    createVNode(_component_el_button, {
                      onClick: loadRecords,
                      style: { "margin-left": "12px" }
                    }, {
                      default: withCtx(() => [..._cache[19] || (_cache[19] = [
                        createTextVNode("刷新", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                createVNode(_component_el_card, {
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
                          index: (idx) => (recordsPage.value - 1) * recordsSize.value + idx + 1,
                          label: "ID",
                          width: "70"
                        }, null, 8, ["index"]),
                        createVNode(_component_el_table_column, {
                          prop: "rule_name",
                          label: "触发规则",
                          width: "200",
                          "show-overflow-tooltip": ""
                        }),
                        createVNode(_component_el_table_column, {
                          label: "预警等级",
                          width: "120",
                          align: "center"
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
                              style: { "cursor": "pointer" },
                              onClick: ($event) => openOpinion(row.opinion_id)
                            }, toDisplayString(row.opinion_title), 9, _hoisted_4)) : (openBlock(), createElementBlock("span", _hoisted_5, toDisplayString(row.opinion_title || "-"), 1))
                          ]),
                          _: 1
                        }),
                        createVNode(_component_el_table_column, {
                          label: "关联事件",
                          width: "180"
                        }, {
                          default: withCtx(({ row }) => [
                            row.event_id ? (openBlock(), createBlock(_component_router_link, {
                              key: 0,
                              to: "/event/" + row.event_id,
                              class: "nav-link"
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(row.event_title), 1)
                              ]),
                              _: 2
                            }, 1032, ["to"])) : (openBlock(), createElementBlock("span", _hoisted_6, toDisplayString(row.event_title || "-"), 1))
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
                          label: "状态",
                          width: "100",
                          align: "center"
                        }, {
                          default: withCtx(({ row }) => [
                            createVNode(_component_el_tag, {
                              type: row.handled ? "success" : "danger",
                              size: "small"
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(row.handled ? "已处理" : "未处理"), 1)
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
                        createVNode(_component_el_table_column, {
                          label: "操作",
                          width: "100",
                          align: "center"
                        }, {
                          default: withCtx(({ row }) => [
                            !row.handled ? (openBlock(), createBlock(_component_el_button, {
                              key: 0,
                              type: "success",
                              size: "small",
                              onClick: ($event) => handleRecord(row)
                            }, {
                              default: withCtx(() => [..._cache[20] || (_cache[20] = [
                                createTextVNode("标记处理", -1)
                              ])]),
                              _: 1
                            }, 8, ["onClick"])) : (openBlock(), createElementBlock("span", _hoisted_7, "已处理"))
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }, 8, ["data"]),
                    createBaseVNode("div", _hoisted_8, [
                      createVNode(_component_el_pagination, {
                        background: "",
                        layout: "total, prev, pager, next",
                        total: recordsTotal.value,
                        "current-page": recordsPage.value,
                        "page-size": recordsSize.value,
                        onCurrentChange: handleRecordsPage
                      }, null, 8, ["total", "current-page", "page-size"])
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        createVNode(_component_el_dialog, {
          modelValue: ruleDialogVisible.value,
          "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => ruleDialogVisible.value = $event),
          title: isEditing.value ? "编辑规则" : "新增规则",
          width: "600px"
        }, {
          footer: withCtx(() => [
            createVNode(_component_el_button, {
              onClick: _cache[11] || (_cache[11] = ($event) => ruleDialogVisible.value = false)
            }, {
              default: withCtx(() => [..._cache[21] || (_cache[21] = [
                createTextVNode("取消", -1)
              ])]),
              _: 1
            }),
            createVNode(_component_el_button, {
              type: "primary",
              loading: saving.value,
              onClick: saveRule
            }, {
              default: withCtx(() => [..._cache[22] || (_cache[22] = [
                createTextVNode("保存", -1)
              ])]),
              _: 1
            }, 8, ["loading"])
          ]),
          default: withCtx(() => [
            createVNode(_component_el_form, {
              model: ruleForm,
              "label-width": "100px"
            }, {
              default: withCtx(() => [
                createVNode(_component_el_form_item, { label: "规则名称" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: ruleForm.name,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => ruleForm.name = $event),
                      placeholder: "请输入规则名称"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "描述" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: ruleForm.description,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => ruleForm.description = $event),
                      type: "textarea",
                      rows: 2,
                      placeholder: "描述该规则的用途"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "风险阈值" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input_number, {
                      modelValue: ruleForm.risk_threshold,
                      "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => ruleForm.risk_threshold = $event),
                      min: 0,
                      max: 100
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "关键词匹配" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: ruleForm.keywords,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => ruleForm.keywords = $event),
                      placeholder: "多个关键词用逗号分隔"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "来源过滤" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: ruleForm.sources,
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => ruleForm.sources = $event),
                      placeholder: "多个来源用逗号分隔，留空表示不限"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "预警等级" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_select, {
                      modelValue: ruleForm.risk_level,
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => ruleForm.risk_level = $event)
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
                      modelValue: ruleForm.enabled,
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => ruleForm.enabled = $event)
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
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Alerts = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-1c582d96"]]);

export { Alerts as default };
