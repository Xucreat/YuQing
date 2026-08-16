const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/index-bXER3CUw.css"])))=>i.map(i=>d[i]);
import { d as defineComponent, r as ref, z as usePermission, A as watch, C as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, m as createVNode, p as withCtx, F as Fragment, n as normalizeClass, b as withKeys, v as vModelText, Y as Transition, s as createCommentVNode, e as createTextVNode, t as toDisplayString, i as renderList, N as vModelSelect, H as unref, T as createStaticVNode, q as createBlock, L as useRoute, j as computed, g as api, E as ElMessage, Z as pollTask, X as isPermissionDenied, y as resolveComponent, B as resolveDirective, o as openBlock, P as withModifiers, k as normalizeStyle, $ as __vitePreload, h as useRouter, _ as _export_sfc } from './index-BM77BkLw.js';
import { E as EVENT_STATUS_OPTIONS, b as EventDispositionDialog, e as eventStatusPill, a as eventStatusLabel } from './EventDispositionDialog-zPJjeAZs.js';
import { F as ForeignEventsView } from './ForeignEventsView-BkTkUW4i.js';

const _hoisted_1 = { class: "events" };
const _hoisted_2 = { class: "top-scope-switch" };
const _hoisted_3 = { class: "toolbar" };
const _hoisted_4 = { class: "risk-filter" };
const _hoisted_5 = { class: "risk-trigger-label" };
const _hoisted_6 = {
  key: 0,
  class: "risk-menu",
  role: "listbox"
};
const _hoisted_7 = ["onClick"];
const _hoisted_8 = { class: "risk-opt-text" };
const _hoisted_9 = {
  key: 1,
  class: "check",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  "stroke-width": "2.6",
  "stroke-linecap": "round",
  "stroke-linejoin": "round"
};
const _hoisted_10 = { class: "risk-filter" };
const _hoisted_11 = { class: "risk-trigger-label" };
const _hoisted_12 = {
  key: 0,
  class: "risk-menu",
  role: "listbox"
};
const _hoisted_13 = ["onClick"];
const _hoisted_14 = { class: "risk-opt-text" };
const _hoisted_15 = {
  key: 1,
  class: "check",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  "stroke-width": "2.6",
  "stroke-linecap": "round",
  "stroke-linejoin": "round"
};
const _hoisted_16 = ["value"];
const _hoisted_17 = ["value"];
const _hoisted_18 = {
  key: 0,
  class: "more-filters"
};
const _hoisted_19 = { class: "time-range" };
const _hoisted_20 = { class: "time-range" };
const _hoisted_21 = ["disabled"];
const _hoisted_22 = {
  key: 2,
  class: "agg-result"
};
const _hoisted_23 = { class: "quick-filters" };
const _hoisted_24 = ["onClick"];
const _hoisted_25 = { class: "card table-card" };
const _hoisted_26 = { class: "tbl" };
const _hoisted_27 = ["onClick"];
const _hoisted_28 = { class: "t-title" };
const _hoisted_29 = { class: "nowrap" };
const _hoisted_30 = { class: "col-center" };
const _hoisted_31 = {
  key: 0,
  class: "focus-mark"
};
const _hoisted_32 = { class: "col-center risk-num" };
const _hoisted_33 = { class: "legacy-risk" };
const _hoisted_34 = { key: 1 };
const _hoisted_35 = { class: "col-center risk-num" };
const _hoisted_36 = { class: "col-center" };
const _hoisted_37 = { class: "col-center risk-num" };
const _hoisted_38 = { class: "col-center risk-num" };
const _hoisted_39 = { class: "col-center" };
const _hoisted_40 = { class: "nowrap" };
const _hoisted_41 = { class: "nowrap" };
const _hoisted_42 = { class: "row-actions" };
const _hoisted_43 = ["onClick"];
const _hoisted_44 = ["onClick"];
const _hoisted_45 = ["onClick"];
const _hoisted_46 = { key: 0 };
const _hoisted_47 = {
  key: 0,
  class: "pager"
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
    const route = useRoute();
    const router = useRouter();
    const scope = ref(route.query.section === "foreign" ? "foreign" : "domestic");
    const foreignRows = ref([]);
    const foreignLoading = ref(false);
    const foreignPage = ref(1);
    const foreignSize = ref(20);
    const foreignTotal = ref(0);
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
    const { hasPermission } = usePermission();
    const canUpdateEvent = computed(() => hasPermission("events:write"));
    const handleScope = ref("domestic");
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
      return (row.formal_risk_score ?? row.risk_score) >= 70 && row.heat_score >= 60;
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
    async function loadForeignEvents() {
      foreignLoading.value = true;
      try {
        const { data } = await api.get("/foreign/events", { params: { page: foreignPage.value, size: foreignSize.value } });
        foreignRows.value = data.items || [];
        foreignTotal.value = data.total ?? 0;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载外网事件失败");
      } finally {
        foreignLoading.value = false;
      }
    }
    function loadByScope() {
      if (scope.value === "foreign") {
        foreignPage.value = 1;
        loadForeignEvents();
      } else {
        loadData();
      }
    }
    function loadScope() {
      router.replace({ path: "/events", query: scope.value === "foreign" ? { section: "foreign" } : {} });
    }
    watch(
      () => route.query.section,
      (sec) => {
        const foreign = sec === "foreign";
        scope.value = foreign ? "foreign" : "domestic";
        loadByScope();
      }
    );
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
      const { ElMessageBox } = await __vitePreload(async () => { const { ElMessageBox } = await import('./index-BM77BkLw.js').then(n => n.a6);return { ElMessageBox }},true?__vite__mapDeps([0]):void 0);
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
    onMounted(loadByScope);
    function openHandle(row) {
      handleScope.value = "domestic";
      handleEventId.value = row.id;
      handleDialogVisible.value = true;
    }
    return (_ctx, _cache) => {
      const _component_el_radio_button = resolveComponent("el-radio-button");
      const _component_el_radio_group = resolveComponent("el-radio-group");
      const _component_Pager = resolveComponent("Pager");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createVNode(_component_el_radio_group, {
            modelValue: scope.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => scope.value = $event),
            onChange: loadScope
          }, {
            default: withCtx(() => [
              createVNode(_component_el_radio_button, { value: "domestic" }, {
                default: withCtx(() => [..._cache[25] || (_cache[25] = [
                  createTextVNode("国内", -1)
                ])]),
                _: 1
              }),
              createVNode(_component_el_radio_button, { value: "foreign" }, {
                default: withCtx(() => [..._cache[26] || (_cache[26] = [
                  createTextVNode("外网", -1)
                ])]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        scope.value === "domestic" ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
          createBaseVNode("div", _hoisted_3, [
            createBaseVNode("div", {
              class: normalizeClass(["search-box", { "is-focused": searchFocused.value }])
            }, [
              _cache[28] || (_cache[28] = createBaseVNode("svg", {
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
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => title.value = $event),
                type: "text",
                placeholder: "搜索事件标题",
                onFocus: _cache[2] || (_cache[2] = ($event) => searchFocused.value = true),
                onBlur: _cache[3] || (_cache[3] = ($event) => searchFocused.value = false),
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
                    onMousedown: _cache[4] || (_cache[4] = withModifiers(() => {
                    }, ["prevent"]))
                  }, [..._cache[27] || (_cache[27] = [
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
            createBaseVNode("div", _hoisted_4, [
              createBaseVNode("button", {
                class: normalizeClass(["risk-trigger", { open: riskOpen.value, active: !!riskFilter.value }]),
                onClick: _cache[5] || (_cache[5] = ($event) => riskOpen.value = !riskOpen.value),
                onKeydown: _cache[6] || (_cache[6] = withKeys(($event) => riskOpen.value = false, ["esc"]))
              }, [
                createBaseVNode("span", _hoisted_5, [
                  riskFilter.value ? (openBlock(), createElementBlock("span", {
                    key: 0,
                    class: normalizeClass(["risk-trigger-dot", "dot-" + riskFilter.value])
                  }, null, 2)) : createCommentVNode("", true),
                  createTextVNode(" " + toDisplayString(riskLabel.value), 1)
                ]),
                _cache[29] || (_cache[29] = createBaseVNode("svg", {
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
                onClick: _cache[7] || (_cache[7] = ($event) => riskOpen.value = false)
              })) : createCommentVNode("", true),
              createVNode(Transition, { name: "pop" }, {
                default: withCtx(() => [
                  riskOpen.value ? (openBlock(), createElementBlock("div", _hoisted_6, [
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
                        createBaseVNode("span", _hoisted_8, toDisplayString(opt.label), 1),
                        riskFilter.value === opt.value ? (openBlock(), createElementBlock("svg", _hoisted_9, [..._cache[30] || (_cache[30] = [
                          createBaseVNode("polyline", { points: "20 6 9 17 4 12" }, null, -1)
                        ])])) : createCommentVNode("", true)
                      ], 10, _hoisted_7);
                    }), 64))
                  ])) : createCommentVNode("", true)
                ]),
                _: 1
              })
            ]),
            createBaseVNode("div", _hoisted_10, [
              createBaseVNode("button", {
                class: normalizeClass(["risk-trigger", { open: shadowRiskOpen.value, active: !!shadowRiskFilter.value }]),
                onClick: _cache[8] || (_cache[8] = ($event) => shadowRiskOpen.value = !shadowRiskOpen.value),
                onKeydown: _cache[9] || (_cache[9] = withKeys(($event) => shadowRiskOpen.value = false, ["esc"]))
              }, [
                createBaseVNode("span", _hoisted_11, [
                  shadowRiskFilter.value ? (openBlock(), createElementBlock("span", {
                    key: 0,
                    class: normalizeClass(["risk-trigger-dot", "dot-" + shadowRiskFilter.value])
                  }, null, 2)) : createCommentVNode("", true),
                  createTextVNode(" " + toDisplayString(shadowRiskLabel.value), 1)
                ]),
                _cache[31] || (_cache[31] = createBaseVNode("svg", {
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
                onClick: _cache[10] || (_cache[10] = ($event) => shadowRiskOpen.value = false)
              })) : createCommentVNode("", true),
              createVNode(Transition, { name: "pop" }, {
                default: withCtx(() => [
                  shadowRiskOpen.value ? (openBlock(), createElementBlock("div", _hoisted_12, [
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
                        createBaseVNode("span", _hoisted_14, toDisplayString(opt.label), 1),
                        shadowRiskFilter.value === opt.value ? (openBlock(), createElementBlock("svg", _hoisted_15, [..._cache[32] || (_cache[32] = [
                          createBaseVNode("polyline", { points: "20 6 9 17 4 12" }, null, -1)
                        ])])) : createCommentVNode("", true)
                      ], 10, _hoisted_13);
                    }), 64))
                  ])) : createCommentVNode("", true)
                ]),
                _: 1
              })
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => topicFilter.value = $event),
              class: "compact-select",
              title: "按主题筛选",
              onChange: applyFilters
            }, [
              _cache[33] || (_cache[33] = createBaseVNode("option", { value: "" }, "全部主题", -1)),
              (openBlock(), createElementBlock(Fragment, null, renderList(topicOptions, (option) => {
                return createBaseVNode("option", {
                  key: option.value,
                  value: option.value
                }, toDisplayString(option.label), 9, _hoisted_16);
              }), 64))
            ], 544), [
              [vModelSelect, topicFilter.value]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => statusFilter.value = $event),
              class: "compact-select",
              title: "按处置状态筛选",
              onChange: applyFilters
            }, [
              _cache[34] || (_cache[34] = createBaseVNode("option", { value: "" }, "全部处置状态", -1)),
              (openBlock(true), createElementBlock(Fragment, null, renderList(unref(EVENT_STATUS_OPTIONS), (option) => {
                return openBlock(), createElementBlock("option", {
                  key: option.value,
                  value: option.value
                }, toDisplayString(option.label), 9, _hoisted_17);
              }), 128))
            ], 544), [
              [vModelSelect, statusFilter.value]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => trendFilter.value = $event),
              class: "compact-select",
              title: "按趋势筛选",
              onChange: applyFilters
            }, [..._cache[35] || (_cache[35] = [
              createStaticVNode('<option value="" data-v-a1f0c727>全部趋势</option><option value="rising" data-v-a1f0c727>↑ 升温</option><option value="stable" data-v-a1f0c727>→ 平稳</option><option value="falling" data-v-a1f0c727>↓ 下降</option><option value="unknown" data-v-a1f0c727>未知</option>', 5)
            ])], 544), [
              [vModelSelect, trendFilter.value]
            ]),
            createBaseVNode("button", {
              class: normalizeClass(["btn btn-ghost more-toggle", { active: moreOpen.value }]),
              onClick: _cache[14] || (_cache[14] = ($event) => moreOpen.value = !moreOpen.value)
            }, toDisplayString(moreOpen.value ? "收起更多操作" : "更多操作"), 3),
            moreOpen.value ? (openBlock(), createElementBlock("div", _hoisted_18, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => regionFilter.value = $event),
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
                "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => heatMin.value = $event),
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
                "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => heatMax.value = $event),
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
              _cache[40] || (_cache[40] = createBaseVNode("span", { class: "filter-sep" }, null, -1)),
              createBaseVNode("div", _hoisted_19, [
                _cache[36] || (_cache[36] = createBaseVNode("label", { class: "time-range-label" }, "首次发现", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[18] || (_cache[18] = ($event) => firstTimeStart.value = $event),
                  type: "datetime-local",
                  class: "compact-input time-input",
                  title: "首次发现起始时间",
                  onChange: applyFilters
                }, null, 544), [
                  [vModelText, firstTimeStart.value]
                ]),
                _cache[37] || (_cache[37] = createBaseVNode("span", { class: "time-range-sep" }, "~", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[19] || (_cache[19] = ($event) => firstTimeEnd.value = $event),
                  type: "datetime-local",
                  class: "compact-input time-input",
                  title: "首次发现截止时间",
                  onChange: applyFilters
                }, null, 544), [
                  [vModelText, firstTimeEnd.value]
                ])
              ]),
              createBaseVNode("div", _hoisted_20, [
                _cache[38] || (_cache[38] = createBaseVNode("label", { class: "time-range-label" }, "最后更新", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[20] || (_cache[20] = ($event) => lastTimeStart.value = $event),
                  type: "datetime-local",
                  class: "compact-input time-input",
                  title: "最后更新起始时间",
                  onChange: applyFilters
                }, null, 544), [
                  [vModelText, lastTimeStart.value]
                ]),
                _cache[39] || (_cache[39] = createBaseVNode("span", { class: "time-range-sep" }, "~", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[21] || (_cache[21] = ($event) => lastTimeEnd.value = $event),
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
            }, toDisplayString(aggregating.value ? "聚合中..." : "手动聚合"), 9, _hoisted_21)) : createCommentVNode("", true),
            createBaseVNode("button", {
              class: "btn btn-ghost",
              onClick: loadData
            }, "刷新"),
            lastResult.value ? (openBlock(), createElementBlock("span", _hoisted_22, " 聚合成功：新建 " + toDisplayString(lastResult.value.created) + " · 更新 " + toDisplayString(lastResult.value.updated) + " · 关联 " + toDisplayString(lastResult.value.linked), 1)) : createCommentVNode("", true)
          ]),
          createBaseVNode("div", _hoisted_23, [
            (openBlock(), createElementBlock(Fragment, null, renderList(statusGroups, (g) => {
              return createBaseVNode("button", {
                key: g.value || "all",
                class: normalizeClass(["chip", { active: statusGroup.value === g.value }]),
                onClick: ($event) => statusGroup.value = g.value
              }, toDisplayString(g.label), 11, _hoisted_24);
            }), 64)),
            _cache[41] || (_cache[41] = createBaseVNode("span", { class: "quick-filters-note" }, "（仅过滤当前页）", -1))
          ]),
          createBaseVNode("div", _hoisted_25, [
            createBaseVNode("table", _hoisted_26, [
              _cache[47] || (_cache[47] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", { style: { "width": "70px" } }, "ID"),
                  createBaseVNode("th", { style: { "width": "280px" } }, "事件标题"),
                  createBaseVNode("th", { style: { "width": "110px" } }, "主题"),
                  createBaseVNode("th", {
                    style: { "width": "140px" },
                    class: "col-center"
                  }, "正式记录风险"),
                  createBaseVNode("th", {
                    style: { "width": "160px" },
                    class: "col-center"
                  }, "关联舆情当前风险"),
                  createBaseVNode("th", {
                    style: { "width": "130px" },
                    class: "col-center"
                  }, "影子风险"),
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
                    createBaseVNode("td", null, toDisplayString(row.id), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", _hoisted_28, toDisplayString(row.title), 1)
                    ]),
                    createBaseVNode("td", _hoisted_29, toDisplayString(topicText(row.topic_category)), 1),
                    createBaseVNode("td", _hoisted_30, [
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", riskPill(row.formal_risk_level || row.risk_level)])
                      }, [
                        _cache[42] || (_cache[42] = createBaseVNode("span", { class: "dot" }, null, -1)),
                        createTextVNode(toDisplayString(riskText(row.formal_risk_level || row.risk_level)), 1)
                      ], 2),
                      createBaseVNode("span", {
                        class: "risk-num",
                        style: normalizeStyle({ color: riskColor(row.formal_risk_score ?? row.risk_score) })
                      }, toDisplayString(row.formal_risk_score ?? row.risk_score), 5),
                      _cache[43] || (_cache[43] = createBaseVNode("span", { class: "risk-source" }, "正式快照", -1)),
                      isKeyEvent(row) ? (openBlock(), createElementBlock("span", _hoisted_31, "重点关注")) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("td", _hoisted_32, [
                      row.linked_opinion_current_risk ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                        createBaseVNode("span", {
                          style: normalizeStyle({ color: riskColor(row.linked_opinion_current_risk.risk_score ?? 0) })
                        }, toDisplayString(row.linked_opinion_current_risk.risk_score ?? "-"), 5),
                        createBaseVNode("small", _hoisted_33, toDisplayString(riskText(row.linked_opinion_current_risk.risk_level)), 1)
                      ], 64)) : (openBlock(), createElementBlock("span", _hoisted_34, "-"))
                    ]),
                    createBaseVNode("td", {
                      class: "col-center risk-num",
                      style: normalizeStyle({ color: riskColor(row.risk_shadow_score ?? 0) })
                    }, [
                      createTextVNode(toDisplayString(row.risk_shadow_score ?? "-") + " ", 1),
                      _cache[44] || (_cache[44] = createBaseVNode("small", { class: "legacy-risk" }, "参考", -1))
                    ], 4),
                    createBaseVNode("td", _hoisted_35, toDisplayString(row.heat_score), 1),
                    createBaseVNode("td", _hoisted_36, [
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", trendPill(row.trend)])
                      }, toDisplayString(trendText(row.trend)), 3)
                    ]),
                    createBaseVNode("td", _hoisted_37, toDisplayString(row.opinion_count), 1),
                    createBaseVNode("td", _hoisted_38, toDisplayString(row.source_count ?? "-"), 1),
                    createBaseVNode("td", _hoisted_39, [
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(eventStatusPill)(row.status)])
                      }, [
                        _cache[45] || (_cache[45] = createBaseVNode("span", { class: "dot" }, null, -1)),
                        createTextVNode(toDisplayString(unref(eventStatusLabel)(row.status)), 1)
                      ], 2)
                    ]),
                    createBaseVNode("td", _hoisted_40, toDisplayString(formatTime(row.first_time)), 1),
                    createBaseVNode("td", _hoisted_41, toDisplayString(formatTime(row.last_time)), 1),
                    createBaseVNode("td", {
                      class: "col-center operation-col",
                      onClick: _cache[22] || (_cache[22] = withModifiers(() => {
                      }, ["stop"]))
                    }, [
                      createBaseVNode("div", _hoisted_42, [
                        createBaseVNode("button", {
                          class: "btn-operate",
                          title: "查看事件详情",
                          onClick: withModifiers(($event) => _ctx.$router.push("/event/" + row.id), ["stop"])
                        }, "查看", 8, _hoisted_43),
                        canUpdateEvent.value ? (openBlock(), createElementBlock("button", {
                          key: 0,
                          class: "btn-operate",
                          title: "打开事件处置弹窗",
                          onClick: withModifiers(($event) => openHandle(row), ["stop"])
                        }, "处置", 8, _hoisted_44)) : createCommentVNode("", true),
                        canUpdateEvent.value ? (openBlock(), createElementBlock("button", {
                          key: 1,
                          class: "btn-icon btn-delete",
                          title: "删除事件",
                          onClick: withModifiers(($event) => handleDelete(row), ["stop"])
                        }, "🗑", 8, _hoisted_45)) : createCommentVNode("", true)
                      ])
                    ])
                  ], 8, _hoisted_27);
                }), 128)),
                displayedRows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_46, [..._cache[46] || (_cache[46] = [
                  createBaseVNode("td", {
                    colspan: "14",
                    class: "empty-row"
                  }, "暂无事件数据", -1)
                ])])) : createCommentVNode("", true)
              ])
            ]),
            total.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_47, [
              createVNode(_component_Pager, {
                total: total.value,
                "current-page": page.value,
                "onUpdate:currentPage": _cache[23] || (_cache[23] = ($event) => page.value = $event),
                "page-size": size.value,
                onCurrentChange: loadData
              }, null, 8, ["total", "current-page", "page-size"])
            ])) : createCommentVNode("", true)
          ])
        ], 64)) : createCommentVNode("", true),
        scope.value === "foreign" ? (openBlock(), createBlock(ForeignEventsView, {
          key: 1,
          "show-disposition-actions": true
        })) : createCommentVNode("", true),
        createVNode(EventDispositionDialog, {
          modelValue: handleDialogVisible.value,
          "onUpdate:modelValue": _cache[24] || (_cache[24] = ($event) => handleDialogVisible.value = $event),
          "event-id": handleEventId.value,
          scope: handleScope.value,
          onUpdated: loadByScope
        }, null, 8, ["modelValue", "event-id", "scope"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Events = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-a1f0c727"]]);

export { Events as default };
