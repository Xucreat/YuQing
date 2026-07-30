import { d as defineComponent, l as usePermission, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, t as toDisplayString, n as normalizeClass, e as createTextVNode, A as createCommentVNode, x as unref, k as normalizeStyle, F as Fragment, i as renderList, v as vModelText, B as createVNode, r as ref, j as computed, g as api, E as ElMessage, D as resolveDirective, M as useRoute, o as openBlock, h as useRouter, _ as _export_sfc } from './index-2Uvf87pQ.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-bQOs12BI.js';
import { a as eventStatusLabel, e as eventStatusPill, E as EVENT_STATUS_OPTIONS } from './event-yO6dSWTH.js';

const _hoisted_1 = { class: "event-detail" };
const _hoisted_2 = { class: "detail-back" };
const _hoisted_3 = { class: "event-header" };
const _hoisted_4 = { class: "event-title-row" };
const _hoisted_5 = { class: "detail-title" };
const _hoisted_6 = {
  key: 0,
  class: "focus-mark"
};
const _hoisted_7 = { class: "event-meta" };
const _hoisted_8 = {
  key: 0,
  class: "event-desc"
};
const _hoisted_9 = { class: "situation-strip" };
const _hoisted_10 = { class: "situation-item" };
const _hoisted_11 = { class: "situation-item" };
const _hoisted_12 = { class: "situation-item" };
const _hoisted_13 = { class: "situation-item" };
const _hoisted_14 = { class: "situation-item" };
const _hoisted_15 = { class: "situation-item" };
const _hoisted_16 = { class: "card operation-card" };
const _hoisted_17 = { class: "operation-header" };
const _hoisted_18 = { class: "operation-current" };
const _hoisted_19 = {
  key: 0,
  class: "status-actions",
  "aria-label": "变更事件处置状态"
};
const _hoisted_20 = ["disabled", "onClick"];
const _hoisted_21 = {
  key: 1,
  class: "note-editor"
};
const _hoisted_22 = ["disabled"];
const _hoisted_23 = { class: "note-submit-row" };
const _hoisted_24 = ["disabled"];
const _hoisted_25 = { class: "action-timeline" };
const _hoisted_26 = { class: "timeline-body" };
const _hoisted_27 = { class: "timeline-meta" };
const _hoisted_28 = { class: "timeline-content" };
const _hoisted_29 = {
  key: 0,
  class: "timeline-empty"
};
const _hoisted_30 = { class: "card table-card" };
const _hoisted_31 = { class: "card-header" };
const _hoisted_32 = { class: "section-title" };
const _hoisted_33 = { class: "tbl" };
const _hoisted_34 = ["onClick"];
const _hoisted_35 = { class: "t-title" };
const _hoisted_36 = { class: "col-center" };
const _hoisted_37 = { class: "col-center" };
const _hoisted_38 = { key: 0 };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "EventDetail",
  setup(__props) {
    const route = useRoute();
    useRouter();
    const loading = ref(false);
    const savingStatus = ref(false);
    const savingNote = ref(false);
    const noteContent = ref("");
    const { hasPermission } = usePermission();
    const canUpdateEvent = computed(() => hasPermission("events:write"));
    const nextStatus = {
      active: "verifying",
      verifying: "processing",
      processing: "resolved",
      resolved: "closed"
    };
    const detailVisible = ref(false);
    const detailId = ref(null);
    function openOpinion(id) {
      detailId.value = id;
      detailVisible.value = true;
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
      actions: []
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
      return target === "active" || nextStatus[current] === target;
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
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: _cache[0] || (_cache[0] = ($event) => _ctx.$router.back())
          }, "← 返回")
        ]),
        createBaseVNode("div", _hoisted_3, [
          createBaseVNode("div", _hoisted_4, [
            createBaseVNode("h2", _hoisted_5, toDisplayString(event.value.title), 1),
            createBaseVNode("span", {
              class: normalizeClass(["pill", riskPill(event.value.risk_level)])
            }, [
              _cache[3] || (_cache[3] = createBaseVNode("span", { class: "dot" }, null, -1)),
              createTextVNode(toDisplayString(riskText(event.value.risk_level)), 1)
            ], 2),
            isKeyEvent.value ? (openBlock(), createElementBlock("span", _hoisted_6, "重点关注")) : createCommentVNode("", true)
          ]),
          createBaseVNode("div", _hoisted_7, [
            createBaseVNode("span", null, [
              _cache[4] || (_cache[4] = createTextVNode("关联舆情：", -1)),
              createBaseVNode("b", null, toDisplayString(event.value.total_opinions), 1),
              _cache[5] || (_cache[5] = createTextVNode(" 条", -1))
            ]),
            createBaseVNode("span", null, "首次发现：" + toDisplayString(formatTime(event.value.first_time)), 1),
            createBaseVNode("span", null, "最后更新：" + toDisplayString(formatTime(event.value.last_time)), 1)
          ]),
          event.value.description ? (openBlock(), createElementBlock("div", _hoisted_8, toDisplayString(event.value.description), 1)) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_9, [
          createBaseVNode("div", _hoisted_10, [
            _cache[6] || (_cache[6] = createBaseVNode("span", { class: "situation-label" }, "影响区域", -1)),
            createBaseVNode("strong", null, toDisplayString(event.value.region_name || (event.value.region_id ? `地区 ${event.value.region_id}` : "未标注")), 1)
          ]),
          createBaseVNode("div", _hoisted_11, [
            _cache[7] || (_cache[7] = createBaseVNode("span", { class: "situation-label" }, "事件主题", -1)),
            createBaseVNode("strong", null, toDisplayString(topicText(event.value.topic_category)), 1)
          ]),
          createBaseVNode("div", _hoisted_12, [
            _cache[8] || (_cache[8] = createBaseVNode("span", { class: "situation-label" }, "处置状态", -1)),
            createBaseVNode("strong", null, toDisplayString(unref(eventStatusLabel)(event.value.status)), 1)
          ]),
          createBaseVNode("div", _hoisted_13, [
            _cache[9] || (_cache[9] = createBaseVNode("span", { class: "situation-label" }, "当前风险", -1)),
            createBaseVNode("strong", {
              style: normalizeStyle({ color: riskColor(event.value.risk_score) })
            }, toDisplayString(event.value.risk_score) + " 分 · " + toDisplayString(riskText(event.value.risk_level)), 5)
          ]),
          createBaseVNode("div", _hoisted_14, [
            _cache[10] || (_cache[10] = createBaseVNode("span", { class: "situation-label" }, "当前热度", -1)),
            createBaseVNode("strong", null, toDisplayString(event.value.heat_score) + " 分", 1)
          ]),
          createBaseVNode("div", _hoisted_15, [
            _cache[11] || (_cache[11] = createBaseVNode("span", { class: "situation-label" }, "发展趋势", -1)),
            createBaseVNode("strong", null, toDisplayString(trendText(event.value.trend)), 1)
          ])
        ]),
        createBaseVNode("section", _hoisted_16, [
          createBaseVNode("div", _hoisted_17, [
            createBaseVNode("div", null, [
              _cache[13] || (_cache[13] = createBaseVNode("h3", { class: "section-title" }, "事件处置", -1)),
              createBaseVNode("div", _hoisted_18, [
                _cache[12] || (_cache[12] = createTextVNode(" 当前处置状态 ", -1)),
                createBaseVNode("span", {
                  class: normalizeClass(["pill", unref(eventStatusPill)(event.value.status)])
                }, toDisplayString(unref(eventStatusLabel)(event.value.status)), 3)
              ])
            ])
          ]),
          canUpdateEvent.value ? (openBlock(), createElementBlock("div", _hoisted_19, [
            (openBlock(true), createElementBlock(Fragment, null, renderList(unref(EVENT_STATUS_OPTIONS), (option) => {
              return openBlock(), createElementBlock("button", {
                key: option.value,
                class: normalizeClass(["status-button", { current: event.value.status === option.value }]),
                disabled: savingStatus.value || !canChangeStatus(option.value),
                onClick: ($event) => changeStatus(option.value)
              }, toDisplayString(option.label), 11, _hoisted_20);
            }), 128))
          ])) : createCommentVNode("", true),
          canUpdateEvent.value ? (openBlock(), createElementBlock("div", _hoisted_21, [
            withDirectives(createBaseVNode("textarea", {
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => noteContent.value = $event),
              maxlength: "5000",
              rows: "3",
              placeholder: "填写核查、联络或处置进展",
              disabled: savingNote.value
            }, null, 8, _hoisted_22), [
              [vModelText, noteContent.value]
            ]),
            createBaseVNode("div", _hoisted_23, [
              createBaseVNode("span", null, toDisplayString(noteContent.value.length) + "/5000", 1),
              createBaseVNode("button", {
                class: "btn btn-primary",
                disabled: savingNote.value || !noteContent.value.trim(),
                onClick: addNote
              }, toDisplayString(savingNote.value ? "提交中" : "添加备注"), 9, _hoisted_24)
            ])
          ])) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_25, [
            (openBlock(true), createElementBlock(Fragment, null, renderList(event.value.actions, (action) => {
              return openBlock(), createElementBlock("div", {
                key: action.id,
                class: "timeline-item"
              }, [
                _cache[14] || (_cache[14] = createBaseVNode("span", { class: "timeline-dot" }, null, -1)),
                createBaseVNode("div", _hoisted_26, [
                  createBaseVNode("div", _hoisted_27, [
                    createBaseVNode("time", null, toDisplayString(formatTime(action.created_at)), 1),
                    createBaseVNode("strong", null, toDisplayString(action.username || (action.user_id ? `用户 ${action.user_id}` : "系统")), 1),
                    createBaseVNode("span", null, toDisplayString(actionTypeText(action.action_type)), 1)
                  ]),
                  createBaseVNode("div", _hoisted_28, [
                    action.action_type === "status_change" && action.old_status && action.new_status ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                      createTextVNode(toDisplayString(unref(eventStatusLabel)(action.old_status)) + " → " + toDisplayString(unref(eventStatusLabel)(action.new_status)), 1)
                    ], 64)) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
                      createTextVNode(toDisplayString(action.content), 1)
                    ], 64))
                  ])
                ])
              ]);
            }), 128)),
            event.value.actions.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_29, "暂无处置记录")) : createCommentVNode("", true)
          ])
        ]),
        createBaseVNode("div", _hoisted_30, [
          createBaseVNode("div", _hoisted_31, [
            createBaseVNode("h3", _hoisted_32, "关联舆情列表 (" + toDisplayString(event.value.total_opinions) + ")", 1)
          ]),
          createBaseVNode("table", _hoisted_33, [
            _cache[17] || (_cache[17] = createBaseVNode("thead", null, [
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
                    createBaseVNode("span", _hoisted_35, toDisplayString(row.title), 1)
                  ]),
                  createBaseVNode("td", null, toDisplayString(row.source), 1),
                  createBaseVNode("td", _hoisted_36, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", sentimentPill(row.sentiment)])
                    }, [
                      _cache[15] || (_cache[15] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(sentimentText(row.sentiment)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", {
                    class: "col-center risk-num",
                    style: normalizeStyle({ color: riskColor(row.risk_score) })
                  }, toDisplayString(row.risk_score), 5),
                  createBaseVNode("td", _hoisted_37, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", row.analysis_status === "completed" ? "pill-green" : "pill-gray"])
                    }, toDisplayString(row.analysis_status === "completed" ? "已完成" : row.analysis_status), 3)
                  ]),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.publish_time)), 1)
                ], 8, _hoisted_34);
              }), 128)),
              event.value.opinions.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_38, [..._cache[16] || (_cache[16] = [
                createBaseVNode("td", {
                  colspan: "7",
                  class: "empty-row"
                }, "暂无关联舆情", -1)
              ])])) : createCommentVNode("", true)
            ])
          ])
        ]),
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const EventDetail = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-11199005"]]);

export { EventDetail as default };
