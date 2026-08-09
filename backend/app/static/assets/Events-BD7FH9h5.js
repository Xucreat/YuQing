const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/index-BqUf_dkv.css"])))=>i.map(i=>d[i]);
import { d as defineComponent, z as usePermission, C as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, n as normalizeClass, b as withKeys, v as vModelText, m as createVNode, p as withCtx, V as Transition, s as createCommentVNode, e as createTextVNode, t as toDisplayString, F as Fragment, i as renderList, J as vModelSelect, H as unref, N as createStaticVNode, r as ref, j as computed, g as api, E as ElMessage, P as pollTask, U as isPermissionDenied, y as resolveComponent, B as resolveDirective, o as openBlock, L as withModifiers, k as normalizeStyle, W as __vitePreload, _ as _export_sfc } from './index-BdaNukLP.js';
import { E as EVENT_STATUS_OPTIONS, e as eventStatusPill, a as eventStatusLabel } from './event-DY3DZBkH.js';

const _hoisted_1 = { class: "events" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = { class: "risk-filter" };
const _hoisted_4 = { class: "risk-trigger-label" };
const _hoisted_5 = {
  key: 0,
  class: "risk-menu",
  role: "listbox"
};
const _hoisted_6 = ["onClick"];
const _hoisted_7 = { class: "risk-opt-text" };
const _hoisted_8 = {
  key: 1,
  class: "check",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  "stroke-width": "2.6",
  "stroke-linecap": "round",
  "stroke-linejoin": "round"
};
const _hoisted_9 = { class: "risk-filter" };
const _hoisted_10 = { class: "risk-trigger-label" };
const _hoisted_11 = {
  key: 0,
  class: "risk-menu",
  role: "listbox"
};
const _hoisted_12 = ["onClick"];
const _hoisted_13 = { class: "risk-opt-text" };
const _hoisted_14 = {
  key: 1,
  class: "check",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  "stroke-width": "2.6",
  "stroke-linecap": "round",
  "stroke-linejoin": "round"
};
const _hoisted_15 = ["value"];
const _hoisted_16 = ["value"];
const _hoisted_17 = {
  key: 0,
  class: "more-filters"
};
const _hoisted_18 = { class: "time-range" };
const _hoisted_19 = { class: "time-range" };
const _hoisted_20 = ["disabled"];
const _hoisted_21 = {
  key: 2,
  class: "agg-result"
};
const _hoisted_22 = { class: "quick-filters" };
const _hoisted_23 = ["onClick"];
const _hoisted_24 = { class: "card table-card" };
const _hoisted_25 = { class: "tbl" };
const _hoisted_26 = ["onClick"];
const _hoisted_27 = { class: "t-title" };
const _hoisted_28 = { class: "nowrap" };
const _hoisted_29 = { class: "col-center" };
const _hoisted_30 = ["title"];
const _hoisted_31 = {
  key: 0,
  class: "focus-mark"
};
const _hoisted_32 = ["title"];
const _hoisted_33 = { class: "col-center risk-num" };
const _hoisted_34 = { class: "col-center" };
const _hoisted_35 = { class: "col-center risk-num" };
const _hoisted_36 = { class: "col-center risk-num" };
const _hoisted_37 = { class: "col-center" };
const _hoisted_38 = { class: "nowrap" };
const _hoisted_39 = { class: "nowrap" };
const _hoisted_40 = { class: "row-actions" };
const _hoisted_41 = ["onClick"];
const _hoisted_42 = ["onClick"];
const _hoisted_43 = {
  key: 2,
  class: "row-actions-empty"
};
const _hoisted_44 = { key: 0 };
const _hoisted_45 = {
  key: 0,
  class: "pager"
};
const _hoisted_46 = {
  key: 0,
  class: "op-modal-body"
};
const _hoisted_47 = { class: "op-left" };
const _hoisted_48 = { class: "operation-header" };
const _hoisted_49 = { class: "operation-current" };
const _hoisted_50 = {
  key: 0,
  class: "status-actions",
  "aria-label": "变更事件处置状态"
};
const _hoisted_51 = ["disabled", "onClick"];
const _hoisted_52 = {
  key: 1,
  class: "note-editor"
};
const _hoisted_53 = ["disabled"];
const _hoisted_54 = { class: "note-submit-row" };
const _hoisted_55 = ["disabled"];
const _hoisted_56 = { class: "op-right" };
const _hoisted_57 = { class: "op-right-title" };
const _hoisted_58 = { class: "op-count" };
const _hoisted_59 = { class: "op-right-scroll" };
const _hoisted_60 = { class: "action-timeline" };
const _hoisted_61 = { class: "timeline-body" };
const _hoisted_62 = { class: "timeline-meta" };
const _hoisted_63 = { class: "timeline-content" };
const _hoisted_64 = {
  key: 0,
  class: "timeline-empty"
};
const _hoisted_65 = {
  key: 1,
  class: "op-loading"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Events",
  setup(__props) {
    const loading = ref(false);
    const aggregating = ref(false);
    const rows = ref([]);
    const total = ref(0);
    const page = ref(1);
    const size = ref(20);
    const lastResult = ref(null);
    const title = ref("");
    const riskFilter = ref("");
    const shadowRiskFilter = ref("");
    const regionFilter = ref("");
    const topicFilter = ref("");
    const statusFilter = ref("");
    const trendFilter = ref("");
    const heatMin = ref("");
    const heatMax = ref("");
    const firstTimeStart = ref("");
    const firstTimeEnd = ref("");
    const lastTimeStart = ref("");
    const lastTimeEnd = ref("");
    const searchFocused = ref(false);
    const riskOpen = ref(false);
    const shadowRiskOpen = ref(false);
    const moreOpen = ref(false);
    const statusGroups = [
      { value: "", label: "全部" },
      { value: "active", label: "关注中" },
      { value: "verifying", label: "核查中" },
      { value: "processing", label: "处理中" },
      { value: "resolved", label: "已解决" },
      { value: "closed", label: "已关闭" },
      { value: "deprecated", label: "已忽略" }
    ];
    const statusGroup = ref("");
    const displayedRows = computed(() => {
      if (!statusGroup.value) return rows.value;
      return rows.value.filter((r) => r.status === statusGroup.value);
    });
    const handleDialogVisible = ref(false);
    const handleEventId = ref(null);
    const handleEvent = ref(null);
    const savingStatus = ref(false);
    const savingNote = ref(false);
    const noteContent = ref("");
    const { hasPermission } = usePermission();
    const canUpdateEvent = computed(() => hasPermission("events:write"));
    const riskOptions = [
      { value: "", label: "全部现行风险" },
      { value: "low", label: "现行低风险" },
      { value: "medium", label: "现行中风险" },
      { value: "high", label: "现行高风险" }
    ];
    const shadowRiskOptions = [
      { value: "", label: "全部影子风险" },
      { value: "low", label: "影子低风险" },
      { value: "medium", label: "影子中风险" },
      { value: "high", label: "影子高风险" }
    ];
    const topicOptions = [
      { value: "livelihood", label: "民生" },
      { value: "traffic", label: "交通" },
      { value: "education", label: "教育" },
      { value: "healthcare", label: "医疗卫生" },
      { value: "environment", label: "环境" },
      { value: "safety", label: "安全" },
      { value: "market", label: "市场" },
      { value: "gov_service", label: "政务服务" },
      { value: "social_security", label: "社会保障" },
      { value: "public_emergency", label: "公共突发事件" },
      { value: "other", label: "其他" }
    ];
    const riskLabel = computed(() => (riskOptions.find((o) => o.value === riskFilter.value) || riskOptions[0]).label);
    const shadowRiskLabel = computed(() => (shadowRiskOptions.find((o) => o.value === shadowRiskFilter.value) || shadowRiskOptions[0]).label);
    let searchTimer;
    function riskPill(level) {
      return { high: "pill-red", medium: "pill-orange", low: "pill-green" }[level] || "pill-gray";
    }
    function riskText(level) {
      return { high: "高风险", medium: "中风险", low: "低风险" }[level] || level;
    }
    function topicText(value) {
      return topicOptions.find((option) => option.value === value)?.label || "未分类";
    }
    function isKeyEvent(row) {
      return row.risk_score >= 70 && row.heat_score >= 60;
    }
    function riskColor(score) {
      if (score >= 70) return "#ff3b30";
      if (score >= 40) return "#c77700";
      return "#1a8e3c";
    }
    function trendText(value) {
      return { rising: "↑ 升温", stable: "→ 平稳", falling: "↓ 下降", unknown: "未知" }[value] || value;
    }
    function trendPill(value) {
      return { rising: "pill-red", stable: "pill-gray", falling: "pill-green", unknown: "pill-gray" }[value] || "pill-gray";
    }
    function formatTime(t) {
      if (!t) return "-";
      return t.replace("T", " ").slice(0, 19);
    }
    async function loadData() {
      loading.value = true;
      try {
        const params = { page: page.value, size: size.value };
        const kw = title.value.trim();
        if (kw) params.title = kw;
        if (riskFilter.value) params.risk_level = riskFilter.value;
        if (shadowRiskFilter.value) params.risk_shadow_level = shadowRiskFilter.value;
        if (regionFilter.value) params.region_id = Number(regionFilter.value);
        if (topicFilter.value) params.topic_category = topicFilter.value;
        if (statusFilter.value) params.status = statusFilter.value;
        if (trendFilter.value) params.trend = trendFilter.value;
        if (heatMin.value) params.heat_min = Number(heatMin.value);
        if (heatMax.value) params.heat_max = Number(heatMax.value);
        if (firstTimeStart.value) params.first_time_start = firstTimeStart.value;
        if (firstTimeEnd.value) params.first_time_end = firstTimeEnd.value;
        if (lastTimeStart.value) params.last_time_start = lastTimeStart.value;
        if (lastTimeEnd.value) params.last_time_end = lastTimeEnd.value;
        const { data } = await api.get("/events", { params });
        rows.value = data.items;
        total.value = data.total;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载事件列表失败");
      } finally {
        loading.value = false;
      }
    }
    function onSearchInput() {
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        page.value = 1;
        loadData();
      }, 350);
    }
    function clearSearch() {
      title.value = "";
      page.value = 1;
      loadData();
    }
    function onSearchEnter() {
      if (searchTimer) clearTimeout(searchTimer);
      page.value = 1;
      loadData();
    }
    function selectRisk(v) {
      riskFilter.value = v;
      riskOpen.value = false;
      page.value = 1;
      loadData();
    }
    function selectShadowRisk(v) {
      shadowRiskFilter.value = v;
      shadowRiskOpen.value = false;
      page.value = 1;
      loadData();
    }
    function applyFilters() {
      page.value = 1;
      loadData();
    }
    async function handleAggregate() {
      if (aggregating.value) return;
      aggregating.value = true;
      try {
        const { data } = await api.post("/events/aggregate");
        ElMessage.info("聚合任务已启动，后台运行中…");
        const res = await pollTask(data.task_id);
        if (res.status === "success") {
          const r = res.result || {};
          lastResult.value = r;
          const tag = r.incremental ? "（增量）" : "";
          ElMessage.success("聚合完成" + tag + "：新建 " + r.created + "，更新 " + r.updated + "，关联 " + r.linked);
          page.value = 1;
          await loadData();
        } else if (res.status === "failed") {
          ElMessage.error("聚合失败：" + (res.error || res.message || "未知错误"));
        }
      } catch (err) {
        if (!isPermissionDenied(err)) ElMessage.error(err?.response?.data?.detail || "聚合失败");
      } finally {
        aggregating.value = false;
      }
    }
    async function handleDelete(row) {
      if (!canUpdateEvent.value) {
        ElMessage.error("权限不足，无法删除事件");
        return;
      }
      const { ElMessageBox } = await __vitePreload(async () => { const { ElMessageBox } = await import('./index-BdaNukLP.js').then(n => n.a2);return { ElMessageBox }},true?__vite__mapDeps([0]):void 0);
      try {
        await ElMessageBox.confirm(
          `确认删除事件「${row.title}」？关联的舆情不会被删除，仅解除关联。`,
          "删除确认",
          { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" }
        );
      } catch {
        return;
      }
      try {
        await api.delete("/events/" + row.id);
        ElMessage.success("事件已删除");
        await loadData();
      } catch (err) {
        if (!isPermissionDenied(err)) {
          ElMessage.error(err?.response?.data?.detail || "删除事件失败，请稍后重试");
        }
      }
    }
    onMounted(loadData);
    const nextStatus = {
      active: "verifying",
      verifying: "processing",
      processing: "resolved",
      resolved: "closed"
    };
    const DEPRECATE_ALLOWED_FROM = ["active", "verifying", "processing"];
    function actionTypeText(value) {
      return { status_change: "状态变更", note: "备注", assign: "指派", resolve: "解决" }[value] || value;
    }
    function canChangeStatus(target) {
      const current = handleEvent.value?.status;
      if (!current || target === current) return false;
      if (target === "active") return true;
      if (target === "deprecated") return DEPRECATE_ALLOWED_FROM.includes(current);
      return nextStatus[current] === target;
    }
    function openHandle(row) {
      handleEventId.value = row.id;
      handleEvent.value = null;
      handleDialogVisible.value = true;
      loadHandleEvent();
    }
    async function loadHandleEvent() {
      if (!handleEventId.value) return;
      try {
        const { data } = await api.get("/events/" + handleEventId.value);
        handleEvent.value = data;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载事件详情失败");
      }
    }
    async function changeStatus(target) {
      if (!canChangeStatus(target) || !handleEvent.value) return;
      savingStatus.value = true;
      try {
        await api.patch(`/events/${handleEvent.value.id}/status`, { status: target });
        ElMessage.success(`处置状态已更新为${eventStatusLabel(target)}`);
        await loadHandleEvent();
        const r = rows.value.find((x) => x.id === handleEvent.value.id);
        if (r) r.status = target;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "更新处置状态失败");
      } finally {
        savingStatus.value = false;
      }
    }
    async function addNote() {
      const content = noteContent.value.trim();
      if (!content || !handleEvent.value) return;
      savingNote.value = true;
      try {
        await api.post(`/events/${handleEvent.value.id}/actions`, { action_type: "note", content });
        noteContent.value = "";
        ElMessage.success("事件备注已添加");
        await loadHandleEvent();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "添加事件备注失败");
      } finally {
        savingNote.value = false;
      }
    }
    return (_ctx, _cache) => {
      const _component_Pager = resolveComponent("Pager");
      const _component_el_dialog = resolveComponent("el-dialog");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", {
            class: normalizeClass(["search-box", { "is-focused": searchFocused.value }])
          }, [
            _cache[27] || (_cache[27] = createBaseVNode("svg", {
              class: "search-ico",
              viewBox: "0 0 24 24",
              fill: "none",
              stroke: "currentColor",
              "stroke-width": "2",
              "stroke-linecap": "round",
              "stroke-linejoin": "round"
            }, [
              createBaseVNode("circle", {
                cx: "11",
                cy: "11",
                r: "7"
              }),
              createBaseVNode("line", {
                x1: "21",
                y1: "21",
                x2: "16.65",
                y2: "16.65"
              })
            ], -1)),
            withDirectives(createBaseVNode("input", {
              class: "search-input",
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => title.value = $event),
              type: "text",
              placeholder: "搜索事件标题",
              onFocus: _cache[1] || (_cache[1] = ($event) => searchFocused.value = true),
              onBlur: _cache[2] || (_cache[2] = ($event) => searchFocused.value = false),
              onInput: onSearchInput,
              onKeydown: withKeys(onSearchEnter, ["enter"])
            }, null, 544), [
              [vModelText, title.value]
            ]),
            createVNode(Transition, { name: "fade" }, {
              default: withCtx(() => [
                title.value ? (openBlock(), createElementBlock("button", {
                  key: 0,
                  class: "search-clear",
                  title: "清除",
                  onClick: clearSearch,
                  onMousedown: _cache[3] || (_cache[3] = withModifiers(() => {
                  }, ["prevent"]))
                }, [..._cache[26] || (_cache[26] = [
                  createBaseVNode("svg", {
                    viewBox: "0 0 24 24",
                    fill: "none",
                    stroke: "currentColor",
                    "stroke-width": "2.2",
                    "stroke-linecap": "round",
                    "stroke-linejoin": "round"
                  }, [
                    createBaseVNode("line", {
                      x1: "18",
                      y1: "6",
                      x2: "6",
                      y2: "18"
                    }),
                    createBaseVNode("line", {
                      x1: "6",
                      y1: "6",
                      x2: "18",
                      y2: "18"
                    })
                  ], -1)
                ])], 32)) : createCommentVNode("", true)
              ]),
              _: 1
            })
          ], 2),
          createBaseVNode("div", _hoisted_3, [
            createBaseVNode("button", {
              class: normalizeClass(["risk-trigger", { open: riskOpen.value, active: !!riskFilter.value }]),
              onClick: _cache[4] || (_cache[4] = ($event) => riskOpen.value = !riskOpen.value),
              onKeydown: _cache[5] || (_cache[5] = withKeys(($event) => riskOpen.value = false, ["esc"]))
            }, [
              createBaseVNode("span", _hoisted_4, [
                riskFilter.value ? (openBlock(), createElementBlock("span", {
                  key: 0,
                  class: normalizeClass(["risk-trigger-dot", "dot-" + riskFilter.value])
                }, null, 2)) : createCommentVNode("", true),
                createTextVNode(" " + toDisplayString(riskLabel.value), 1)
              ]),
              _cache[28] || (_cache[28] = createBaseVNode("svg", {
                class: "chev",
                viewBox: "0 0 24 24",
                fill: "none",
                stroke: "currentColor",
                "stroke-width": "2",
                "stroke-linecap": "round",
                "stroke-linejoin": "round"
              }, [
                createBaseVNode("polyline", { points: "6 9 12 15 18 9" })
              ], -1))
            ], 34),
            riskOpen.value ? (openBlock(), createElementBlock("div", {
              key: 0,
              class: "risk-backdrop",
              onClick: _cache[6] || (_cache[6] = ($event) => riskOpen.value = false)
            })) : createCommentVNode("", true),
            createVNode(Transition, { name: "pop" }, {
              default: withCtx(() => [
                riskOpen.value ? (openBlock(), createElementBlock("div", _hoisted_5, [
                  (openBlock(), createElementBlock(Fragment, null, renderList(riskOptions, (opt) => {
                    return createBaseVNode("button", {
                      key: opt.value,
                      class: normalizeClass(["risk-opt", { active: riskFilter.value === opt.value }]),
                      onClick: ($event) => selectRisk(opt.value)
                    }, [
                      opt.value ? (openBlock(), createElementBlock("span", {
                        key: 0,
                        class: normalizeClass(["risk-opt-dot", "dot-" + opt.value])
                      }, null, 2)) : createCommentVNode("", true),
                      createBaseVNode("span", _hoisted_7, toDisplayString(opt.label), 1),
                      riskFilter.value === opt.value ? (openBlock(), createElementBlock("svg", _hoisted_8, [..._cache[29] || (_cache[29] = [
                        createBaseVNode("polyline", { points: "20 6 9 17 4 12" }, null, -1)
                      ])])) : createCommentVNode("", true)
                    ], 10, _hoisted_6);
                  }), 64))
                ])) : createCommentVNode("", true)
              ]),
              _: 1
            })
          ]),
          createBaseVNode("div", _hoisted_9, [
            createBaseVNode("button", {
              class: normalizeClass(["risk-trigger", { open: shadowRiskOpen.value, active: !!shadowRiskFilter.value }]),
              onClick: _cache[7] || (_cache[7] = ($event) => shadowRiskOpen.value = !shadowRiskOpen.value),
              onKeydown: _cache[8] || (_cache[8] = withKeys(($event) => shadowRiskOpen.value = false, ["esc"]))
            }, [
              createBaseVNode("span", _hoisted_10, [
                shadowRiskFilter.value ? (openBlock(), createElementBlock("span", {
                  key: 0,
                  class: normalizeClass(["risk-trigger-dot", "dot-" + shadowRiskFilter.value])
                }, null, 2)) : createCommentVNode("", true),
                createTextVNode(" " + toDisplayString(shadowRiskLabel.value), 1)
              ]),
              _cache[30] || (_cache[30] = createBaseVNode("svg", {
                class: "chev",
                viewBox: "0 0 24 24",
                fill: "none",
                stroke: "currentColor",
                "stroke-width": "2",
                "stroke-linecap": "round",
                "stroke-linejoin": "round"
              }, [
                createBaseVNode("polyline", { points: "6 9 12 15 18 9" })
              ], -1))
            ], 34),
            shadowRiskOpen.value ? (openBlock(), createElementBlock("div", {
              key: 0,
              class: "risk-backdrop",
              onClick: _cache[9] || (_cache[9] = ($event) => shadowRiskOpen.value = false)
            })) : createCommentVNode("", true),
            createVNode(Transition, { name: "pop" }, {
              default: withCtx(() => [
                shadowRiskOpen.value ? (openBlock(), createElementBlock("div", _hoisted_11, [
                  (openBlock(), createElementBlock(Fragment, null, renderList(shadowRiskOptions, (opt) => {
                    return createBaseVNode("button", {
                      key: opt.value,
                      class: normalizeClass(["risk-opt", { active: shadowRiskFilter.value === opt.value }]),
                      onClick: ($event) => selectShadowRisk(opt.value)
                    }, [
                      opt.value ? (openBlock(), createElementBlock("span", {
                        key: 0,
                        class: normalizeClass(["risk-opt-dot", "dot-" + opt.value])
                      }, null, 2)) : createCommentVNode("", true),
                      createBaseVNode("span", _hoisted_13, toDisplayString(opt.label), 1),
                      shadowRiskFilter.value === opt.value ? (openBlock(), createElementBlock("svg", _hoisted_14, [..._cache[31] || (_cache[31] = [
                        createBaseVNode("polyline", { points: "20 6 9 17 4 12" }, null, -1)
                      ])])) : createCommentVNode("", true)
                    ], 10, _hoisted_12);
                  }), 64))
                ])) : createCommentVNode("", true)
              ]),
              _: 1
            })
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => topicFilter.value = $event),
            class: "compact-select",
            title: "按主题筛选",
            onChange: applyFilters
          }, [
            _cache[32] || (_cache[32] = createBaseVNode("option", { value: "" }, "全部主题", -1)),
            (openBlock(), createElementBlock(Fragment, null, renderList(topicOptions, (option) => {
              return createBaseVNode("option", {
                key: option.value,
                value: option.value
              }, toDisplayString(option.label), 9, _hoisted_15);
            }), 64))
          ], 544), [
            [vModelSelect, topicFilter.value]
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => statusFilter.value = $event),
            class: "compact-select",
            title: "按处置状态筛选",
            onChange: applyFilters
          }, [
            _cache[33] || (_cache[33] = createBaseVNode("option", { value: "" }, "全部处置状态", -1)),
            (openBlock(true), createElementBlock(Fragment, null, renderList(unref(EVENT_STATUS_OPTIONS), (option) => {
              return openBlock(), createElementBlock("option", {
                key: option.value,
                value: option.value
              }, toDisplayString(option.label), 9, _hoisted_16);
            }), 128))
          ], 544), [
            [vModelSelect, statusFilter.value]
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => trendFilter.value = $event),
            class: "compact-select",
            title: "按趋势筛选",
            onChange: applyFilters
          }, [..._cache[34] || (_cache[34] = [
            createStaticVNode('<option value="" data-v-887c6c96>全部趋势</option><option value="rising" data-v-887c6c96>↑ 升温</option><option value="stable" data-v-887c6c96>→ 平稳</option><option value="falling" data-v-887c6c96>↓ 下降</option><option value="unknown" data-v-887c6c96>未知</option>', 5)
          ])], 544), [
            [vModelSelect, trendFilter.value]
          ]),
          createBaseVNode("button", {
            class: normalizeClass(["btn btn-ghost more-toggle", { active: moreOpen.value }]),
            onClick: _cache[13] || (_cache[13] = ($event) => moreOpen.value = !moreOpen.value)
          }, toDisplayString(moreOpen.value ? "收起更多操作" : "更多操作"), 3),
          moreOpen.value ? (openBlock(), createElementBlock("div", _hoisted_17, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => regionFilter.value = $event),
              class: "compact-input",
              type: "number",
              min: "1",
              placeholder: "地区 ID",
              title: "按地区 ID 筛选",
              onChange: applyFilters
            }, null, 544), [
              [vModelText, regionFilter.value]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => heatMin.value = $event),
              class: "compact-input heat-input",
              type: "number",
              min: "0",
              max: "100",
              placeholder: "热度 ≥",
              title: "最低热度",
              onChange: applyFilters
            }, null, 544), [
              [vModelText, heatMin.value]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => heatMax.value = $event),
              class: "compact-input heat-input",
              type: "number",
              min: "0",
              max: "100",
              placeholder: "热度 ≤",
              title: "最高热度",
              onChange: applyFilters
            }, null, 544), [
              [vModelText, heatMax.value]
            ]),
            _cache[39] || (_cache[39] = createBaseVNode("span", { class: "filter-sep" }, null, -1)),
            createBaseVNode("div", _hoisted_18, [
              _cache[35] || (_cache[35] = createBaseVNode("label", { class: "time-range-label" }, "首次发现", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => firstTimeStart.value = $event),
                type: "datetime-local",
                class: "compact-input time-input",
                title: "首次发现起始时间",
                onChange: applyFilters
              }, null, 544), [
                [vModelText, firstTimeStart.value]
              ]),
              _cache[36] || (_cache[36] = createBaseVNode("span", { class: "time-range-sep" }, "~", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[18] || (_cache[18] = ($event) => firstTimeEnd.value = $event),
                type: "datetime-local",
                class: "compact-input time-input",
                title: "首次发现截止时间",
                onChange: applyFilters
              }, null, 544), [
                [vModelText, firstTimeEnd.value]
              ])
            ]),
            createBaseVNode("div", _hoisted_19, [
              _cache[37] || (_cache[37] = createBaseVNode("label", { class: "time-range-label" }, "最后更新", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[19] || (_cache[19] = ($event) => lastTimeStart.value = $event),
                type: "datetime-local",
                class: "compact-input time-input",
                title: "最后更新起始时间",
                onChange: applyFilters
              }, null, 544), [
                [vModelText, lastTimeStart.value]
              ]),
              _cache[38] || (_cache[38] = createBaseVNode("span", { class: "time-range-sep" }, "~", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[20] || (_cache[20] = ($event) => lastTimeEnd.value = $event),
                type: "datetime-local",
                class: "compact-input time-input",
                title: "最后更新截止时间",
                onChange: applyFilters
              }, null, 544), [
                [vModelText, lastTimeEnd.value]
              ])
            ])
          ])) : createCommentVNode("", true),
          canUpdateEvent.value ? (openBlock(), createElementBlock("button", {
            key: 1,
            class: "btn btn-ghost",
            disabled: aggregating.value,
            onClick: handleAggregate
          }, toDisplayString(aggregating.value ? "聚合中..." : "手动聚合"), 9, _hoisted_20)) : createCommentVNode("", true),
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: loadData
          }, "刷新"),
          lastResult.value ? (openBlock(), createElementBlock("span", _hoisted_21, " 聚合成功：新建 " + toDisplayString(lastResult.value.created) + " · 更新 " + toDisplayString(lastResult.value.updated) + " · 关联 " + toDisplayString(lastResult.value.linked), 1)) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_22, [
          (openBlock(), createElementBlock(Fragment, null, renderList(statusGroups, (g) => {
            return createBaseVNode("button", {
              key: g.value || "all",
              class: normalizeClass(["chip", { active: statusGroup.value === g.value }]),
              onClick: ($event) => statusGroup.value = g.value
            }, toDisplayString(g.label), 11, _hoisted_23);
          }), 64)),
          _cache[40] || (_cache[40] = createBaseVNode("span", { class: "quick-filters-note" }, "（仅过滤当前页）", -1))
        ]),
        createBaseVNode("div", _hoisted_24, [
          createBaseVNode("table", _hoisted_25, [
            _cache[44] || (_cache[44] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", { style: { "width": "70px" } }, "ID"),
                createBaseVNode("th", { style: { "width": "280px" } }, "事件标题"),
                createBaseVNode("th", { style: { "width": "110px" } }, "主题"),
                createBaseVNode("th", {
                  style: { "width": "130px" },
                  class: "col-center"
                }, "研判风险（影子）"),
                createBaseVNode("th", {
                  style: { "width": "110px" },
                  class: "col-center"
                }, "研判分"),
                createBaseVNode("th", {
                  style: { "width": "80px" },
                  class: "col-center"
                }, "热度"),
                createBaseVNode("th", {
                  style: { "width": "90px" },
                  class: "col-center"
                }, "趋势"),
                createBaseVNode("th", {
                  style: { "width": "100px" },
                  class: "col-center"
                }, "关联舆情"),
                createBaseVNode("th", {
                  style: { "width": "90px" },
                  class: "col-center"
                }, "来源数"),
                createBaseVNode("th", {
                  style: { "width": "100px" },
                  class: "col-center"
                }, "处置状态"),
                createBaseVNode("th", { style: { "width": "190px" } }, "首次发现"),
                createBaseVNode("th", { style: { "width": "190px" } }, "最后更新"),
                createBaseVNode("th", { class: "col-center operation-col" }, "操作")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(displayedRows.value, (row, idx) => {
                return openBlock(), createElementBlock("tr", {
                  key: row.id,
                  onClick: ($event) => _ctx.$router.push("/event/" + row.id),
                  style: { "cursor": "pointer" }
                }, [
                  createBaseVNode("td", null, toDisplayString((page.value - 1) * size.value + idx + 1), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", _hoisted_27, toDisplayString(row.title), 1)
                  ]),
                  createBaseVNode("td", _hoisted_28, toDisplayString(topicText(row.topic_category)), 1),
                  createBaseVNode("td", _hoisted_29, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", riskPill(row.risk_shadow_level || "low")])
                    }, [
                      _cache[41] || (_cache[41] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(riskText(row.risk_shadow_level || "low")), 1)
                    ], 2),
                    createBaseVNode("span", {
                      class: "risk-source",
                      title: row.risk_shadow_version || "event-risk-shadow-v1"
                    }, "只读参考", 8, _hoisted_30),
                    isKeyEvent(row) ? (openBlock(), createElementBlock("span", _hoisted_31, "重点关注")) : createCommentVNode("", true)
                  ]),
                  createBaseVNode("td", {
                    class: "col-center risk-num",
                    style: normalizeStyle({ color: riskColor(row.risk_shadow_score ?? 0) })
                  }, [
                    createTextVNode(toDisplayString(row.risk_shadow_score ?? "-") + " ", 1),
                    createBaseVNode("small", {
                      class: "legacy-risk",
                      title: "现行风险分：" + row.risk_score
                    }, "现行 " + toDisplayString(row.risk_score), 9, _hoisted_32)
                  ], 4),
                  createBaseVNode("td", _hoisted_33, toDisplayString(row.heat_score), 1),
                  createBaseVNode("td", _hoisted_34, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", trendPill(row.trend)])
                    }, toDisplayString(trendText(row.trend)), 3)
                  ]),
                  createBaseVNode("td", _hoisted_35, toDisplayString(row.opinion_count), 1),
                  createBaseVNode("td", _hoisted_36, toDisplayString(row.source_count ?? "-"), 1),
                  createBaseVNode("td", _hoisted_37, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", unref(eventStatusPill)(row.status)])
                    }, [
                      _cache[42] || (_cache[42] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(unref(eventStatusLabel)(row.status)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", _hoisted_38, toDisplayString(formatTime(row.first_time)), 1),
                  createBaseVNode("td", _hoisted_39, toDisplayString(formatTime(row.last_time)), 1),
                  createBaseVNode("td", {
                    class: "col-center operation-col",
                    onClick: _cache[21] || (_cache[21] = withModifiers(() => {
                    }, ["stop"]))
                  }, [
                    createBaseVNode("div", _hoisted_40, [
                      canUpdateEvent.value ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "btn-operate",
                        title: "打开事件处置弹窗",
                        onClick: withModifiers(($event) => openHandle(row), ["stop"])
                      }, "处置", 8, _hoisted_41)) : createCommentVNode("", true),
                      canUpdateEvent.value ? (openBlock(), createElementBlock("button", {
                        key: 1,
                        class: "btn-icon btn-delete",
                        title: "删除事件",
                        onClick: ($event) => handleDelete(row)
                      }, "🗑", 8, _hoisted_42)) : createCommentVNode("", true),
                      !canUpdateEvent.value ? (openBlock(), createElementBlock("span", _hoisted_43, "—")) : createCommentVNode("", true)
                    ])
                  ])
                ], 8, _hoisted_26);
              }), 128)),
              displayedRows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_44, [..._cache[43] || (_cache[43] = [
                createBaseVNode("td", {
                  colspan: "13",
                  class: "empty-row"
                }, "暂无事件数据", -1)
              ])])) : createCommentVNode("", true)
            ])
          ]),
          total.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_45, [
            createVNode(_component_Pager, {
              total: total.value,
              "current-page": page.value,
              "onUpdate:currentPage": _cache[22] || (_cache[22] = ($event) => page.value = $event),
              "page-size": size.value,
              onCurrentChange: loadData
            }, null, 8, ["total", "current-page", "page-size"])
          ])) : createCommentVNode("", true)
        ]),
        createVNode(_component_el_dialog, {
          modelValue: handleDialogVisible.value,
          "onUpdate:modelValue": _cache[25] || (_cache[25] = ($event) => handleDialogVisible.value = $event),
          title: "事件处置",
          width: "820px",
          top: "6vh",
          "close-on-click-modal": true,
          class: "op-dialog"
        }, {
          footer: withCtx(() => [
            createBaseVNode("button", {
              class: "btn btn-ghost",
              onClick: _cache[24] || (_cache[24] = ($event) => handleDialogVisible.value = false)
            }, "关闭")
          ]),
          default: withCtx(() => [
            handleEvent.value ? (openBlock(), createElementBlock("div", _hoisted_46, [
              createBaseVNode("div", _hoisted_47, [
                createBaseVNode("div", _hoisted_48, [
                  createBaseVNode("div", null, [
                    createBaseVNode("div", _hoisted_49, [
                      _cache[45] || (_cache[45] = createTextVNode(" 当前处置状态 ", -1)),
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(eventStatusPill)(handleEvent.value.status)])
                      }, toDisplayString(unref(eventStatusLabel)(handleEvent.value.status)), 3)
                    ])
                  ])
                ]),
                canUpdateEvent.value ? (openBlock(), createElementBlock("div", _hoisted_50, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(unref(EVENT_STATUS_OPTIONS), (option) => {
                    return openBlock(), createElementBlock("button", {
                      key: option.value,
                      class: normalizeClass(["status-button", { current: handleEvent.value.status === option.value }]),
                      disabled: savingStatus.value || !canChangeStatus(option.value),
                      onClick: ($event) => changeStatus(option.value)
                    }, toDisplayString(option.value === "deprecated" ? "忽略事件" : option.label), 11, _hoisted_51);
                  }), 128))
                ])) : createCommentVNode("", true),
                canUpdateEvent.value ? (openBlock(), createElementBlock("div", _hoisted_52, [
                  withDirectives(createBaseVNode("textarea", {
                    "onUpdate:modelValue": _cache[23] || (_cache[23] = ($event) => noteContent.value = $event),
                    maxlength: "5000",
                    rows: "3",
                    placeholder: "填写核查、联络或处置进展",
                    disabled: savingNote.value
                  }, null, 8, _hoisted_53), [
                    [vModelText, noteContent.value]
                  ]),
                  createBaseVNode("div", _hoisted_54, [
                    createBaseVNode("span", null, toDisplayString(noteContent.value.length) + "/5000", 1),
                    createBaseVNode("button", {
                      class: "btn btn-primary",
                      disabled: savingNote.value || !noteContent.value.trim(),
                      onClick: addNote
                    }, toDisplayString(savingNote.value ? "提交中" : "添加备注"), 9, _hoisted_55)
                  ])
                ])) : createCommentVNode("", true)
              ]),
              createBaseVNode("div", _hoisted_56, [
                createBaseVNode("div", _hoisted_57, [
                  _cache[46] || (_cache[46] = createTextVNode(" 处置记录", -1)),
                  createBaseVNode("span", _hoisted_58, toDisplayString(handleEvent.value.actions.length), 1)
                ]),
                createBaseVNode("div", _hoisted_59, [
                  createBaseVNode("div", _hoisted_60, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(handleEvent.value.actions, (action) => {
                      return openBlock(), createElementBlock("div", {
                        key: action.id,
                        class: "timeline-item"
                      }, [
                        _cache[47] || (_cache[47] = createBaseVNode("span", { class: "timeline-dot" }, null, -1)),
                        createBaseVNode("div", _hoisted_61, [
                          createBaseVNode("div", _hoisted_62, [
                            createBaseVNode("time", null, toDisplayString(formatTime(action.created_at)), 1),
                            createBaseVNode("strong", null, toDisplayString(action.username || (action.user_id ? `用户 ${action.user_id}` : "系统")), 1),
                            createBaseVNode("span", null, toDisplayString(actionTypeText(action.action_type)), 1)
                          ]),
                          createBaseVNode("div", _hoisted_63, [
                            action.action_type === "status_change" && action.old_status && action.new_status ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                              createTextVNode(toDisplayString(unref(eventStatusLabel)(action.old_status)) + " → " + toDisplayString(unref(eventStatusLabel)(action.new_status)), 1)
                            ], 64)) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
                              createTextVNode(toDisplayString(action.content), 1)
                            ], 64))
                          ])
                        ])
                      ]);
                    }), 128)),
                    handleEvent.value.actions.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_64, "暂无处置记录")) : createCommentVNode("", true)
                  ])
                ])
              ])
            ])) : (openBlock(), createElementBlock("div", _hoisted_65, "加载中…"))
          ]),
          _: 1
        }, 8, ["modelValue"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Events = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-887c6c96"]]);

export { Events as default };
