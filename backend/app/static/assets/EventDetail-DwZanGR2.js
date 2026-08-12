import { d as defineComponent, z as usePermission, C as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, t as toDisplayString, n as normalizeClass, e as createTextVNode, s as createCommentVNode, H as unref, k as normalizeStyle, F as Fragment, i as renderList, m as createVNode, p as withCtx, r as ref, j as computed, g as api, E as ElMessage, y as resolveComponent, B as resolveDirective, N as useRoute, o as openBlock, v as vModelText, h as useRouter, _ as _export_sfc } from './index-BQugYeHy.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-BjbQHpbJ.js';
import { a as eventStatusLabel, e as eventStatusPill, E as EVENT_STATUS_OPTIONS } from './event-DY3DZBkH.js';
import './admission-DpEuIHXC.js';
import './opinion-Cag9WtuS.js';

const _hoisted_1 = { class: "event-detail" };
const _hoisted_2 = { class: "detail-back" };
const _hoisted_3 = { class: "overview-card" };
const _hoisted_4 = { class: "event-title-row" };
const _hoisted_5 = { class: "detail-title" };
const _hoisted_6 = {
  key: 0,
  class: "focus-mark"
};
const _hoisted_7 = {
  key: 0,
  class: "event-desc"
};
const _hoisted_8 = { class: "event-meta" };
const _hoisted_9 = { class: "situation-strip" };
const _hoisted_11 = { class: "situation-item" };
const _hoisted_12 = { class: "situation-item" };
const _hoisted_13 = { class: "situation-item" };
const _hoisted_14 = { class: "situation-item" };
const _hoisted_15 = { class: "situation-item" };
const _hoisted_16 = {
  key: 0,
  class: "stat-panel"
};
const _hoisted_17 = { class: "stat-grid" };
const _hoisted_18 = {
  key: 0,
  class: "stat-item"
};
const _hoisted_19 = {
  key: 1,
  class: "stat-item"
};
const _hoisted_20 = {
  key: 2,
  class: "stat-item"
};
const _hoisted_21 = { class: "dist-pills" };
const _hoisted_22 = { class: "pill pill-red" };
const _hoisted_23 = { class: "pill pill-orange" };
const _hoisted_24 = { class: "pill pill-green" };
const _hoisted_25 = {
  key: 3,
  class: "stat-item"
};
const _hoisted_26 = {
  key: 4,
  class: "stat-item"
};
const _hoisted_27 = {
  key: 0,
  class: "risk-factor-list"
};
const _hoisted_28 = { class: "op-modal-body" };
const _hoisted_29 = { class: "op-left" };
const _hoisted_30 = { class: "operation-header" };
const _hoisted_31 = { class: "operation-current" };
const _hoisted_32 = {
  key: 0,
  class: "status-actions",
  "aria-label": "变更事件处置状态"
};
const _hoisted_33 = ["disabled", "onClick"];
const _hoisted_34 = {
  key: 1,
  class: "note-editor"
};
const _hoisted_35 = ["disabled"];
const _hoisted_36 = { class: "note-submit-row" };
const _hoisted_37 = ["disabled"];
const _hoisted_38 = { class: "op-right" };
const _hoisted_39 = { class: "op-right-title" };
const _hoisted_40 = { class: "op-count" };
const _hoisted_41 = { class: "op-right-scroll" };
const _hoisted_42 = { class: "action-timeline" };
const _hoisted_43 = { class: "timeline-body" };
const _hoisted_44 = { class: "timeline-meta" };
const _hoisted_45 = { class: "timeline-content" };
const _hoisted_46 = {
  key: 0,
  class: "timeline-empty"
};
const _hoisted_47 = { class: "card table-card" };
const _hoisted_48 = { class: "tbl" };
const _hoisted_49 = ["onClick"];
const _hoisted_50 = { class: "t-title" };
const _hoisted_51 = { class: "col-center" };
const _hoisted_52 = { class: "col-center" };
const _hoisted_53 = { key: 0 };
const _hoisted_54 = { class: "tbl" };
const _hoisted_55 = { class: "t-title" };
const _hoisted_56 = { class: "col-center" };
const _hoisted_57 = { class: "col-center" };
const _hoisted_58 = { key: 0 };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "EventDetail",
  setup(__props) {
    const route = useRoute();
    useRouter();
    const loading = ref(false);
    const situation = ref(null);
    const savingStatus = ref(false);
    const savingNote = ref(false);
    const noteContent = ref("");
    const handleDialogVisible = ref(false);
    const { hasPermission } = usePermission();
    const canUpdateEvent = computed(() => hasPermission("events:write"));
    const activeRelatedTab = ref("opinions");
    const nextStatus = {
      active: "verifying",
      verifying: "processing",
      processing: "resolved",
      resolved: "closed"
    };
    const DEPRECATE_ALLOWED_FROM = ["active", "verifying", "processing"];
    const detailVisible = ref(false);
    const detailId = ref(null);
    function openOpinion(id) {
      detailId.value = id;
      detailVisible.value = true;
    }
    function sufficiencyText(value) {
      return { sufficient: "充分", limited: "有限", insufficient: "不足" }[value || ""] || "未知";
    }
    const event = ref({
      id: 0,
      title: "",
      region_id: null,
      region_name: null,
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
      total_opinions: 0,
      actions: [],
      statistics: null,
      alerts: []
    });
    function riskPill(level) {
      return { high: "pill-red", medium: "pill-orange", low: "pill-green" }[level] || "pill-gray";
    }
    function riskText(level) {
      return { high: "高风险", medium: "中风险", low: "低风险" }[level] || level;
    }
    const topicLabels = {
      livelihood: "民生",
      traffic: "交通",
      education: "教育",
      healthcare: "医疗卫生",
      environment: "环境",
      safety: "安全",
      market: "市场",
      gov_service: "政务服务",
      social_security: "社会保障",
      public_emergency: "公共突发事件",
      other: "其他"
    };
    function topicText(value) {
      return value && topicLabels[value] || "未分类";
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
      return { rising: "↑ 升温", stable: "→ 平稳", falling: "↓ 下降", unknown: "未知" }[value] || value;
    }
    const isKeyEvent = computed(() => event.value.risk_score >= 70 && event.value.heat_score >= 60);
    function formatTime(t) {
      if (!t) return "-";
      return t.replace("T", " ").slice(0, 19);
    }
    function actionTypeText(value) {
      return { status_change: "状态变更", note: "备注", assign: "指派", resolve: "解决" }[value] || value;
    }
    function canChangeStatus(target) {
      const current = event.value.status;
      if (target === current) return false;
      if (target === "active") return true;
      if (target === "deprecated") return DEPRECATE_ALLOWED_FROM.includes(current);
      return nextStatus[current] === target;
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
    function errorMessage(err, fallback) {
      const detail = err?.response?.data?.detail;
      return typeof detail === "string" ? detail : fallback;
    }
    async function loadData() {
      loading.value = true;
      try {
        const id = route.params.id;
        const { data } = await api.get("/events/" + id);
        event.value = { ...event.value, ...data };
        try {
          const situationResponse = await api.get(`/events/${id}/situation`);
          situation.value = situationResponse.data;
        } catch (_) {
          situation.value = null;
        }
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载事件详情失败");
      } finally {
        loading.value = false;
      }
    }
    async function changeStatus(target) {
      if (!canChangeStatus(target)) return;
      savingStatus.value = true;
      try {
        await api.patch(`/events/${event.value.id}/status`, { status: target });
        ElMessage.success(`处置状态已更新为${eventStatusLabel(target)}`);
        await loadData();
      } catch (err) {
        ElMessage.error(errorMessage(err, "更新处置状态失败"));
      } finally {
        savingStatus.value = false;
      }
    }
    async function addNote() {
      const content = noteContent.value.trim();
      if (!content) return;
      savingNote.value = true;
      try {
        await api.post(`/events/${event.value.id}/actions`, { action_type: "note", content });
        noteContent.value = "";
        ElMessage.success("事件备注已添加");
        await loadData();
      } catch (err) {
        ElMessage.error(errorMessage(err, "添加事件备注失败"));
      } finally {
        savingNote.value = false;
      }
    }
    onMounted(loadData);
    return (_ctx, _cache) => {
      const _component_el_dialog = resolveComponent("el-dialog");
      const _component_el_tab_pane = resolveComponent("el-tab-pane");
      const _component_el_tabs = resolveComponent("el-tabs");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: _cache[0] || (_cache[0] = ($event) => _ctx.$router.back())
          }, "← 返回")
        ]),
        createBaseVNode("section", _hoisted_3, [
          createBaseVNode("div", _hoisted_4, [
            createBaseVNode("h2", _hoisted_5, toDisplayString(event.value.title), 1),
            createBaseVNode("span", {
              class: normalizeClass(["pill", riskPill(event.value.risk_level)])
            }, [
              _cache[7] || (_cache[7] = createBaseVNode("span", { class: "dot" }, null, -1)),
              createTextVNode(toDisplayString(riskText(event.value.risk_level)), 1)
            ], 2),
            isKeyEvent.value ? (openBlock(), createElementBlock("span", _hoisted_6, "重点关注")) : createCommentVNode("", true),
            createBaseVNode("button", {
              class: "btn btn-primary handle-open-btn",
              onClick: _cache[1] || (_cache[1] = ($event) => handleDialogVisible.value = true)
            }, "处置")
          ]),
          event.value.description ? (openBlock(), createElementBlock("div", _hoisted_7, toDisplayString(event.value.description), 1)) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_8, [
            createBaseVNode("span", null, [
              _cache[8] || (_cache[8] = createTextVNode("关联舆情：", -1)),
              createBaseVNode("b", null, toDisplayString(event.value.total_opinions), 1),
              _cache[9] || (_cache[9] = createTextVNode(" 条", -1))
            ]),
            createBaseVNode("span", null, "首次发现：" + toDisplayString(formatTime(event.value.first_time)), 1),
            createBaseVNode("span", null, "最后更新：" + toDisplayString(formatTime(event.value.last_time)), 1)
          ]),
          createBaseVNode("div", _hoisted_9, [
            createCommentVNode("", true),
            createBaseVNode("div", _hoisted_11, [
              _cache[11] || (_cache[11] = createBaseVNode("span", { class: "situation-label" }, "事件主题", -1)),
              createBaseVNode("strong", null, toDisplayString(topicText(event.value.topic_category)), 1)
            ]),
            createBaseVNode("div", _hoisted_12, [
              _cache[12] || (_cache[12] = createBaseVNode("span", { class: "situation-label" }, "处置状态", -1)),
              createBaseVNode("strong", null, toDisplayString(unref(eventStatusLabel)(event.value.status)), 1)
            ]),
            createBaseVNode("div", _hoisted_13, [
              _cache[13] || (_cache[13] = createBaseVNode("span", { class: "situation-label" }, "当前风险", -1)),
              createBaseVNode("strong", {
                style: normalizeStyle({ color: riskColor(event.value.risk_score) })
              }, toDisplayString(event.value.risk_score) + " 分 · " + toDisplayString(riskText(event.value.risk_level)), 5)
            ]),
            createBaseVNode("div", _hoisted_14, [
              _cache[14] || (_cache[14] = createBaseVNode("span", { class: "situation-label" }, "当前热度", -1)),
              createBaseVNode("strong", null, toDisplayString(event.value.heat_score) + " 分", 1)
            ]),
            createBaseVNode("div", _hoisted_15, [
              _cache[15] || (_cache[15] = createBaseVNode("span", { class: "situation-label" }, "发展趋势", -1)),
              createBaseVNode("strong", null, toDisplayString(trendText(event.value.trend)), 1)
            ])
          ])
        ]),
        event.value.statistics || situation.value ? (openBlock(), createElementBlock("section", _hoisted_16, [
          _cache[24] || (_cache[24] = createBaseVNode("h3", { class: "section-title" }, "研判与统计", -1)),
          createBaseVNode("div", _hoisted_17, [
            event.value.statistics?.source_count != null || situation.value?.source_distribution?.length ? (openBlock(), createElementBlock("div", _hoisted_18, [
              _cache[16] || (_cache[16] = createBaseVNode("span", { class: "stat-label" }, "来源数量", -1)),
              createBaseVNode("strong", null, toDisplayString(event.value.statistics?.source_count ?? (situation.value?.source_distribution?.length || 0)) + " 个", 1)
            ])) : createCommentVNode("", true),
            situation.value?.data_window?.first_time || situation.value?.data_window?.last_time ? (openBlock(), createElementBlock("div", _hoisted_19, [
              _cache[17] || (_cache[17] = createBaseVNode("span", { class: "stat-label" }, "时间范围", -1)),
              createBaseVNode("strong", null, toDisplayString(formatTime(situation.value?.data_window?.first_time)) + " - " + toDisplayString(formatTime(situation.value?.data_window?.last_time)), 1)
            ])) : createCommentVNode("", true),
            event.value.statistics ? (openBlock(), createElementBlock("div", _hoisted_20, [
              _cache[21] || (_cache[21] = createBaseVNode("span", { class: "stat-label" }, "风险分布", -1)),
              createBaseVNode("span", _hoisted_21, [
                createBaseVNode("span", _hoisted_22, [
                  _cache[18] || (_cache[18] = createBaseVNode("span", { class: "dot" }, null, -1)),
                  createTextVNode("高 " + toDisplayString(event.value.statistics.risk_distribution?.high ?? 0), 1)
                ]),
                createBaseVNode("span", _hoisted_23, [
                  _cache[19] || (_cache[19] = createBaseVNode("span", { class: "dot" }, null, -1)),
                  createTextVNode("中 " + toDisplayString(event.value.statistics.risk_distribution?.medium ?? 0), 1)
                ]),
                createBaseVNode("span", _hoisted_24, [
                  _cache[20] || (_cache[20] = createBaseVNode("span", { class: "dot" }, null, -1)),
                  createTextVNode("低 " + toDisplayString(event.value.statistics.risk_distribution?.low ?? 0), 1)
                ])
              ])
            ])) : createCommentVNode("", true),
            situation.value?.risk_shadow ? (openBlock(), createElementBlock("div", _hoisted_25, [
              _cache[22] || (_cache[22] = createBaseVNode("span", { class: "stat-label" }, "影子风险", -1)),
              createBaseVNode("strong", null, toDisplayString(situation.value.risk_shadow?.score ?? "-") + " 分", 1)
            ])) : createCommentVNode("", true),
            situation.value?.data_sufficiency ? (openBlock(), createElementBlock("div", _hoisted_26, [
              _cache[23] || (_cache[23] = createBaseVNode("span", { class: "stat-label" }, "数据充分性", -1)),
              createBaseVNode("strong", null, toDisplayString(sufficiencyText(situation.value.data_sufficiency?.level)), 1)
            ])) : createCommentVNode("", true)
          ]),
          (situation.value?.risk_factors || []).length ? (openBlock(), createElementBlock("div", _hoisted_27, [
            (openBlock(true), createElementBlock(Fragment, null, renderList(situation.value.risk_factors || [], (factor) => {
              return openBlock(), createElementBlock("span", {
                key: factor.factor,
                class: "risk-factor"
              }, toDisplayString(factor.description), 1);
            }), 128))
          ])) : createCommentVNode("", true)
        ])) : createCommentVNode("", true),
        createVNode(_component_el_dialog, {
          modelValue: handleDialogVisible.value,
          "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => handleDialogVisible.value = $event),
          title: "事件处置",
          width: "820px",
          "align-center": "",
          "close-on-click-modal": true,
          class: "op-dialog"
        }, {
          footer: withCtx(() => [
            createBaseVNode("button", {
              class: "btn btn-ghost",
              onClick: _cache[3] || (_cache[3] = ($event) => handleDialogVisible.value = false)
            }, "关闭")
          ]),
          default: withCtx(() => [
            createBaseVNode("div", _hoisted_28, [
              createBaseVNode("div", _hoisted_29, [
                createBaseVNode("div", _hoisted_30, [
                  createBaseVNode("div", null, [
                    createBaseVNode("div", _hoisted_31, [
                      _cache[25] || (_cache[25] = createTextVNode(" 当前处置状态 ", -1)),
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(eventStatusPill)(event.value.status)])
                      }, toDisplayString(unref(eventStatusLabel)(event.value.status)), 3)
                    ])
                  ])
                ]),
                canUpdateEvent.value ? (openBlock(), createElementBlock("div", _hoisted_32, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(unref(EVENT_STATUS_OPTIONS), (option) => {
                    return openBlock(), createElementBlock("button", {
                      key: option.value,
                      class: normalizeClass(["status-button", { current: event.value.status === option.value }]),
                      disabled: savingStatus.value || !canChangeStatus(option.value),
                      onClick: ($event) => changeStatus(option.value)
                    }, toDisplayString(option.value === "deprecated" ? "忽略事件" : option.label), 11, _hoisted_33);
                  }), 128))
                ])) : createCommentVNode("", true),
                canUpdateEvent.value ? (openBlock(), createElementBlock("div", _hoisted_34, [
                  withDirectives(createBaseVNode("textarea", {
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => noteContent.value = $event),
                    maxlength: "5000",
                    rows: "3",
                    placeholder: "填写核查、联络或处置进展",
                    disabled: savingNote.value
                  }, null, 8, _hoisted_35), [
                    [vModelText, noteContent.value]
                  ]),
                  createBaseVNode("div", _hoisted_36, [
                    createBaseVNode("span", null, toDisplayString(noteContent.value.length) + "/5000", 1),
                    createBaseVNode("button", {
                      class: "btn btn-primary",
                      disabled: savingNote.value || !noteContent.value.trim(),
                      onClick: addNote
                    }, toDisplayString(savingNote.value ? "提交中" : "添加备注"), 9, _hoisted_37)
                  ])
                ])) : createCommentVNode("", true)
              ]),
              createBaseVNode("div", _hoisted_38, [
                createBaseVNode("div", _hoisted_39, [
                  _cache[26] || (_cache[26] = createTextVNode(" 处置记录", -1)),
                  createBaseVNode("span", _hoisted_40, toDisplayString(event.value.actions.length), 1)
                ]),
                createBaseVNode("div", _hoisted_41, [
                  createBaseVNode("div", _hoisted_42, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(event.value.actions, (action) => {
                      return openBlock(), createElementBlock("div", {
                        key: action.id,
                        class: "timeline-item"
                      }, [
                        _cache[27] || (_cache[27] = createBaseVNode("span", { class: "timeline-dot" }, null, -1)),
                        createBaseVNode("div", _hoisted_43, [
                          createBaseVNode("div", _hoisted_44, [
                            createBaseVNode("time", null, toDisplayString(formatTime(action.created_at)), 1),
                            createBaseVNode("strong", null, toDisplayString(action.username || (action.user_id ? `用户 ${action.user_id}` : "系统")), 1),
                            createBaseVNode("span", null, toDisplayString(actionTypeText(action.action_type)), 1)
                          ]),
                          createBaseVNode("div", _hoisted_45, [
                            action.action_type === "status_change" && action.old_status && action.new_status ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                              createTextVNode(toDisplayString(unref(eventStatusLabel)(action.old_status)) + " → " + toDisplayString(unref(eventStatusLabel)(action.new_status)), 1)
                            ], 64)) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
                              createTextVNode(toDisplayString(action.content), 1)
                            ], 64))
                          ])
                        ])
                      ]);
                    }), 128)),
                    event.value.actions.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_46, "暂无处置记录")) : createCommentVNode("", true)
                  ])
                ])
              ])
            ])
          ]),
          _: 1
        }, 8, ["modelValue"]),
        createBaseVNode("div", _hoisted_47, [
          createVNode(_component_el_tabs, {
            modelValue: activeRelatedTab.value,
            "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => activeRelatedTab.value = $event),
            class: "related-tabs"
          }, {
            default: withCtx(() => [
              createVNode(_component_el_tab_pane, {
                label: `关联舆情 (${event.value.total_opinions})`,
                name: "opinions"
              }, {
                default: withCtx(() => [
                  createBaseVNode("table", _hoisted_48, [
                    _cache[30] || (_cache[30] = createBaseVNode("thead", null, [
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
                            createBaseVNode("span", _hoisted_50, toDisplayString(row.title), 1)
                          ]),
                          createBaseVNode("td", null, toDisplayString(row.source), 1),
                          createBaseVNode("td", _hoisted_51, [
                            createBaseVNode("span", {
                              class: normalizeClass(["pill", sentimentPill(row.sentiment)])
                            }, [
                              _cache[28] || (_cache[28] = createBaseVNode("span", { class: "dot" }, null, -1)),
                              createTextVNode(toDisplayString(sentimentText(row.sentiment)), 1)
                            ], 2)
                          ]),
                          createBaseVNode("td", {
                            class: "col-center risk-num",
                            style: normalizeStyle({ color: riskColor(row.risk_score) })
                          }, toDisplayString(row.risk_score), 5),
                          createBaseVNode("td", _hoisted_52, [
                            createBaseVNode("span", {
                              class: normalizeClass(["pill", row.analysis_status === "completed" ? "pill-green" : "pill-gray"])
                            }, toDisplayString(row.analysis_status === "completed" ? "已完成" : row.analysis_status), 3)
                          ]),
                          createBaseVNode("td", null, toDisplayString(formatTime(row.publish_time)), 1)
                        ], 8, _hoisted_49);
                      }), 128)),
                      event.value.opinions.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_53, [..._cache[29] || (_cache[29] = [
                        createBaseVNode("td", {
                          colspan: "7",
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
                  createBaseVNode("table", _hoisted_54, [
                    _cache[33] || (_cache[33] = createBaseVNode("thead", null, [
                      createBaseVNode("tr", null, [
                        createBaseVNode("th", { style: { "min-width": "240px" } }, "标题"),
                        createBaseVNode("th", {
                          style: { "width": "110px" },
                          class: "col-center"
                        }, "风险等级"),
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
                            createBaseVNode("span", _hoisted_55, toDisplayString(a.title), 1)
                          ]),
                          createBaseVNode("td", _hoisted_56, [
                            createBaseVNode("span", {
                              class: normalizeClass(["pill", riskPill(a.risk_level)])
                            }, [
                              _cache[31] || (_cache[31] = createBaseVNode("span", { class: "dot" }, null, -1)),
                              createTextVNode(toDisplayString(riskText(a.risk_level)), 1)
                            ], 2)
                          ]),
                          createBaseVNode("td", _hoisted_57, toDisplayString(alertStatusText(a.status)), 1),
                          createBaseVNode("td", null, toDisplayString(formatTime(a.created_at)), 1)
                        ]);
                      }), 128)),
                      (event.value.alerts?.length || 0) === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_58, [..._cache[32] || (_cache[32] = [
                        createBaseVNode("td", {
                          colspan: "4",
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
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const EventDetail = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-b605fc53"]]);

export { EventDetail as default };
