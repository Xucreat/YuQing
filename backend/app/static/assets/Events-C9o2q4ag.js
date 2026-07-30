const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/index-B0lgOxr-.css"])))=>i.map(i=>d[i]);
import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, n as normalizeClass, b as withKeys, v as vModelText, B as createVNode, z as withCtx, T as Transition, A as createCommentVNode, e as createTextVNode, t as toDisplayString, F as Fragment, i as renderList, G as vModelSelect, x as unref, N as createStaticVNode, r as ref, j as computed, g as api, E as ElMessage, O as pollTask, D as resolveDirective, o as openBlock, J as withModifiers, k as normalizeStyle, P as __vitePreload, _ as _export_sfc } from './index-BITUQ8Oa.js';
import { E as EVENT_STATUS_OPTIONS, e as eventStatusPill, a as eventStatusLabel } from './event-yO6dSWTH.js';

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
const _hoisted_9 = ["value"];
const _hoisted_10 = ["value"];
const _hoisted_11 = ["disabled"];
const _hoisted_12 = {
  key: 0,
  class: "agg-result"
};
const _hoisted_13 = { class: "card table-card" };
const _hoisted_14 = { class: "tbl" };
const _hoisted_15 = ["onClick"];
const _hoisted_16 = { class: "t-title" };
const _hoisted_17 = { class: "nowrap" };
const _hoisted_18 = { class: "col-center" };
const _hoisted_19 = {
  key: 0,
  class: "focus-mark"
};
const _hoisted_20 = { class: "col-center risk-num" };
const _hoisted_21 = { class: "col-center" };
const _hoisted_22 = { class: "col-center risk-num" };
const _hoisted_23 = { class: "col-center" };
const _hoisted_24 = { class: "nowrap" };
const _hoisted_25 = { class: "nowrap" };
const _hoisted_26 = { class: "row-actions" };
const _hoisted_27 = ["onClick"];
const _hoisted_28 = ["onClick"];
const _hoisted_29 = { key: 0 };
const _hoisted_30 = {
  key: 0,
  class: "pager"
};
const _hoisted_31 = { class: "p-info" };
const _hoisted_32 = ["disabled"];
const _hoisted_33 = ["onClick"];
const _hoisted_34 = ["disabled"];
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
    const regionFilter = ref("");
    const topicFilter = ref("");
    const statusFilter = ref("");
    const trendFilter = ref("");
    const heatMin = ref("");
    const heatMax = ref("");
    const searchFocused = ref(false);
    const riskOpen = ref(false);
    const riskOptions = [
      { value: "", label: "全部风险" },
      { value: "low", label: "低风险" },
      { value: "medium", label: "中风险" },
      { value: "high", label: "高风险" }
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
    let searchTimer;
    const maxPage = computed(() => Math.ceil(total.value / size.value) || 1);
    const pages = computed(() => {
      const p = [];
      const mp = maxPage.value;
      const start = Math.max(1, page.value - 2);
      const end = Math.min(mp, page.value + 2);
      for (let i = start; i <= end; i++) p.push(i);
      return p;
    });
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
        if (regionFilter.value) params.region_id = Number(regionFilter.value);
        if (topicFilter.value) params.topic_category = topicFilter.value;
        if (statusFilter.value) params.status = statusFilter.value;
        if (trendFilter.value) params.trend = trendFilter.value;
        if (heatMin.value) params.heat_min = Number(heatMin.value);
        if (heatMax.value) params.heat_max = Number(heatMax.value);
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
        ElMessage.error(err?.response?.data?.detail || "聚合失败");
      } finally {
        aggregating.value = false;
      }
    }
    async function handleDelete(row) {
      try {
        const { ElMessageBox } = await __vitePreload(async () => { const { ElMessageBox } = await import('./index-BITUQ8Oa.js').then(n => n.Z);return { ElMessageBox }},true?__vite__mapDeps([0]):void 0);
        await ElMessageBox.confirm(
          `确认删除事件「${row.title}」？关联的舆情不会被删除，仅解除关联。`,
          "删除确认",
          { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" }
        );
        await api.delete("/events/" + row.id);
        ElMessage.success("事件已删除");
        await loadData();
      } catch {
      }
    }
    onMounted(loadData);
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", {
            class: normalizeClass(["search-box", { "is-focused": searchFocused.value }])
          }, [
            _cache[17] || (_cache[17] = createBaseVNode("svg", {
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
                }, [..._cache[16] || (_cache[16] = [
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
              _cache[18] || (_cache[18] = createBaseVNode("svg", {
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
                      riskFilter.value === opt.value ? (openBlock(), createElementBlock("svg", _hoisted_8, [..._cache[19] || (_cache[19] = [
                        createBaseVNode("polyline", { points: "20 6 9 17 4 12" }, null, -1)
                      ])])) : createCommentVNode("", true)
                    ], 10, _hoisted_6);
                  }), 64))
                ])) : createCommentVNode("", true)
              ]),
              _: 1
            })
          ]),
          withDirectives(createBaseVNode("input", {
            "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => regionFilter.value = $event),
            class: "compact-input",
            type: "number",
            min: "1",
            placeholder: "地区 ID",
            title: "按地区 ID 筛选",
            onChange: applyFilters
          }, null, 544), [
            [vModelText, regionFilter.value]
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => topicFilter.value = $event),
            class: "compact-select",
            title: "按主题筛选",
            onChange: applyFilters
          }, [
            _cache[20] || (_cache[20] = createBaseVNode("option", { value: "" }, "全部主题", -1)),
            (openBlock(), createElementBlock(Fragment, null, renderList(topicOptions, (option) => {
              return createBaseVNode("option", {
                key: option.value,
                value: option.value
              }, toDisplayString(option.label), 9, _hoisted_9);
            }), 64))
          ], 544), [
            [vModelSelect, topicFilter.value]
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => statusFilter.value = $event),
            class: "compact-select",
            title: "按处置状态筛选",
            onChange: applyFilters
          }, [
            _cache[21] || (_cache[21] = createBaseVNode("option", { value: "" }, "全部处置状态", -1)),
            (openBlock(true), createElementBlock(Fragment, null, renderList(unref(EVENT_STATUS_OPTIONS), (option) => {
              return openBlock(), createElementBlock("option", {
                key: option.value,
                value: option.value
              }, toDisplayString(option.label), 9, _hoisted_10);
            }), 128))
          ], 544), [
            [vModelSelect, statusFilter.value]
          ]),
          withDirectives(createBaseVNode("select", {
            "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => trendFilter.value = $event),
            class: "compact-select",
            title: "按趋势筛选",
            onChange: applyFilters
          }, [..._cache[22] || (_cache[22] = [
            createStaticVNode('<option value="" data-v-fa45363a>全部趋势</option><option value="rising" data-v-fa45363a>↑ 升温</option><option value="stable" data-v-fa45363a>→ 平稳</option><option value="falling" data-v-fa45363a>↓ 下降</option><option value="unknown" data-v-fa45363a>未知</option>', 5)
          ])], 544), [
            [vModelSelect, trendFilter.value]
          ]),
          withDirectives(createBaseVNode("input", {
            "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => heatMin.value = $event),
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
            "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => heatMax.value = $event),
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
          createBaseVNode("button", {
            class: "btn btn-ghost",
            disabled: aggregating.value,
            onClick: handleAggregate
          }, toDisplayString(aggregating.value ? "聚合中..." : "手动聚合"), 9, _hoisted_11),
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: loadData
          }, "刷新"),
          lastResult.value ? (openBlock(), createElementBlock("span", _hoisted_12, " 聚合成功：新建 " + toDisplayString(lastResult.value.created) + " · 更新 " + toDisplayString(lastResult.value.updated) + " · 关联 " + toDisplayString(lastResult.value.linked), 1)) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_13, [
          createBaseVNode("table", _hoisted_14, [
            _cache[26] || (_cache[26] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", { style: { "width": "70px" } }, "ID"),
                createBaseVNode("th", { style: { "width": "280px" } }, "事件标题"),
                createBaseVNode("th", { style: { "width": "110px" } }, "主题"),
                createBaseVNode("th", {
                  style: { "width": "110px" },
                  class: "col-center"
                }, "风险等级"),
                createBaseVNode("th", {
                  style: { "width": "80px" },
                  class: "col-center"
                }, "风险分"),
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
                  style: { "width": "100px" },
                  class: "col-center"
                }, "处置状态"),
                createBaseVNode("th", { style: { "width": "190px" } }, "首次发现"),
                createBaseVNode("th", { style: { "width": "190px" } }, "最后更新"),
                createBaseVNode("th", { class: "col-center operation-col" }, "操作")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(rows.value, (row, idx) => {
                return openBlock(), createElementBlock("tr", {
                  key: row.id,
                  onClick: ($event) => _ctx.$router.push("/event/" + row.id),
                  style: { "cursor": "pointer" }
                }, [
                  createBaseVNode("td", null, toDisplayString((page.value - 1) * size.value + idx + 1), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", _hoisted_16, toDisplayString(row.title), 1)
                  ]),
                  createBaseVNode("td", _hoisted_17, toDisplayString(topicText(row.topic_category)), 1),
                  createBaseVNode("td", _hoisted_18, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", riskPill(row.risk_level)])
                    }, [
                      _cache[23] || (_cache[23] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(riskText(row.risk_level)), 1)
                    ], 2),
                    isKeyEvent(row) ? (openBlock(), createElementBlock("span", _hoisted_19, "重点关注")) : createCommentVNode("", true)
                  ]),
                  createBaseVNode("td", {
                    class: "col-center risk-num",
                    style: normalizeStyle({ color: riskColor(row.risk_score) })
                  }, toDisplayString(row.risk_score), 5),
                  createBaseVNode("td", _hoisted_20, toDisplayString(row.heat_score), 1),
                  createBaseVNode("td", _hoisted_21, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", trendPill(row.trend)])
                    }, toDisplayString(trendText(row.trend)), 3)
                  ]),
                  createBaseVNode("td", _hoisted_22, toDisplayString(row.opinion_count), 1),
                  createBaseVNode("td", _hoisted_23, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", unref(eventStatusPill)(row.status)])
                    }, [
                      _cache[24] || (_cache[24] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(unref(eventStatusLabel)(row.status)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", _hoisted_24, toDisplayString(formatTime(row.first_time)), 1),
                  createBaseVNode("td", _hoisted_25, toDisplayString(formatTime(row.last_time)), 1),
                  createBaseVNode("td", {
                    class: "col-center operation-col",
                    onClick: _cache[13] || (_cache[13] = withModifiers(() => {
                    }, ["stop"]))
                  }, [
                    createBaseVNode("div", _hoisted_26, [
                      createBaseVNode("button", {
                        class: "btn-operate",
                        title: "查看事件并进行人工处置",
                        onClick: ($event) => _ctx.$router.push("/event/" + row.id)
                      }, "处置", 8, _hoisted_27),
                      createBaseVNode("button", {
                        class: "btn-icon btn-delete",
                        title: "删除事件",
                        onClick: ($event) => handleDelete(row)
                      }, "🗑", 8, _hoisted_28)
                    ])
                  ])
                ], 8, _hoisted_15);
              }), 128)),
              rows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_29, [..._cache[25] || (_cache[25] = [
                createBaseVNode("td", {
                  colspan: "12",
                  class: "empty-row"
                }, "暂无事件数据", -1)
              ])])) : createCommentVNode("", true)
            ])
          ]),
          total.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_30, [
            createBaseVNode("span", _hoisted_31, "共 " + toDisplayString(total.value) + " 条", 1),
            createBaseVNode("button", {
              disabled: page.value <= 1,
              onClick: _cache[14] || (_cache[14] = ($event) => {
                page.value--;
                loadData();
              })
            }, "‹", 8, _hoisted_32),
            (openBlock(true), createElementBlock(Fragment, null, renderList(pages.value, (p) => {
              return openBlock(), createElementBlock("button", {
                key: p,
                class: normalizeClass({ active: p === page.value }),
                onClick: ($event) => {
                  page.value = p;
                  loadData();
                }
              }, toDisplayString(p), 11, _hoisted_33);
            }), 128)),
            createBaseVNode("button", {
              disabled: page.value >= maxPage.value,
              onClick: _cache[15] || (_cache[15] = ($event) => {
                page.value++;
                loadData();
              })
            }, "›", 8, _hoisted_34)
          ])) : createCommentVNode("", true)
        ])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Events = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-fa45363a"]]);

export { Events as default };
