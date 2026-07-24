const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/index-tYIFtOy3.css"])))=>i.map(i=>d[i]);
import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, n as normalizeClass, b as withKeys, v as vModelText, B as createVNode, z as withCtx, T as Transition, A as createCommentVNode, e as createTextVNode, t as toDisplayString, F as Fragment, i as renderList, r as ref, j as computed, g as api, E as ElMessage, I as pollTask, D as resolveDirective, o as openBlock, J as withModifiers, K as __vitePreload, _ as _export_sfc } from './index-iT_24xn-.js';

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
const _hoisted_9 = ["disabled"];
const _hoisted_10 = {
  key: 0,
  class: "agg-result"
};
const _hoisted_11 = { class: "card table-card" };
const _hoisted_12 = { class: "tbl" };
const _hoisted_13 = ["onClick"];
const _hoisted_14 = { class: "t-title" };
const _hoisted_15 = { class: "col-center" };
const _hoisted_16 = { class: "col-center risk-num" };
const _hoisted_17 = { class: "col-center" };
const _hoisted_18 = ["onClick"];
const _hoisted_19 = { key: 0 };
const _hoisted_20 = {
  key: 0,
  class: "pager"
};
const _hoisted_21 = { class: "p-info" };
const _hoisted_22 = ["disabled"];
const _hoisted_23 = ["onClick"];
const _hoisted_24 = ["disabled"];
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
    const searchFocused = ref(false);
    const riskOpen = ref(false);
    const riskOptions = [
      { value: "", label: "全部风险" },
      { value: "low", label: "低风险" },
      { value: "medium", label: "中风险" },
      { value: "high", label: "高风险" }
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
    function statusText(s) {
      return { active: "进行中", resolved: "已处置", monitoring: "监测中", closed: "已关闭" }[s] || s;
    }
    function statusPill(s) {
      return { active: "pill-green", resolved: "pill-gray", monitoring: "pill-orange", closed: "pill-gray" }[s] || "pill-gray";
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
        const { ElMessageBox } = await __vitePreload(async () => { const { ElMessageBox } = await import('./index-iT_24xn-.js').then(n => n.U);return { ElMessageBox }},true?__vite__mapDeps([0]):void 0);
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
            _cache[11] || (_cache[11] = createBaseVNode("svg", {
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
                }, [..._cache[10] || (_cache[10] = [
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
              _cache[12] || (_cache[12] = createBaseVNode("svg", {
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
                      riskFilter.value === opt.value ? (openBlock(), createElementBlock("svg", _hoisted_8, [..._cache[13] || (_cache[13] = [
                        createBaseVNode("polyline", { points: "20 6 9 17 4 12" }, null, -1)
                      ])])) : createCommentVNode("", true)
                    ], 10, _hoisted_6);
                  }), 64))
                ])) : createCommentVNode("", true)
              ]),
              _: 1
            })
          ]),
          createBaseVNode("button", {
            class: "btn btn-ghost",
            disabled: aggregating.value,
            onClick: handleAggregate
          }, toDisplayString(aggregating.value ? "聚合中..." : "手动聚合"), 9, _hoisted_9),
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: loadData
          }, "刷新"),
          lastResult.value ? (openBlock(), createElementBlock("span", _hoisted_10, " 聚合成功：新建 " + toDisplayString(lastResult.value.created) + " · 更新 " + toDisplayString(lastResult.value.updated) + " · 关联 " + toDisplayString(lastResult.value.linked), 1)) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_11, [
          createBaseVNode("table", _hoisted_12, [
            _cache[17] || (_cache[17] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", { style: { "width": "70px" } }, "ID"),
                createBaseVNode("th", { style: { "min-width": "280px" } }, "事件标题"),
                createBaseVNode("th", {
                  style: { "width": "120px" },
                  class: "col-center"
                }, "风险等级"),
                createBaseVNode("th", {
                  style: { "width": "120px" },
                  class: "col-center"
                }, "关联舆情"),
                createBaseVNode("th", {
                  style: { "width": "100px" },
                  class: "col-center"
                }, "状态"),
                createBaseVNode("th", { style: { "width": "170px" } }, "首次发现"),
                createBaseVNode("th", { style: { "width": "170px" } }, "最后更新"),
                createBaseVNode("th", {
                  style: { "width": "80px" },
                  class: "col-center"
                }, "操作")
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
                    createBaseVNode("span", _hoisted_14, toDisplayString(row.title), 1)
                  ]),
                  createBaseVNode("td", _hoisted_15, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", riskPill(row.risk_level)])
                    }, [
                      _cache[14] || (_cache[14] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(riskText(row.risk_level)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", _hoisted_16, toDisplayString(row.opinion_count), 1),
                  createBaseVNode("td", _hoisted_17, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", statusPill(row.status)])
                    }, [
                      _cache[15] || (_cache[15] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(statusText(row.status)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.first_time)), 1),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.last_time)), 1),
                  createBaseVNode("td", {
                    class: "col-center",
                    onClick: _cache[7] || (_cache[7] = withModifiers(() => {
                    }, ["stop"]))
                  }, [
                    createBaseVNode("button", {
                      class: "btn-icon btn-delete",
                      title: "删除事件",
                      onClick: ($event) => handleDelete(row)
                    }, "🗑", 8, _hoisted_18)
                  ])
                ], 8, _hoisted_13);
              }), 128)),
              rows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_19, [..._cache[16] || (_cache[16] = [
                createBaseVNode("td", {
                  colspan: "8",
                  class: "empty-row"
                }, "暂无事件数据", -1)
              ])])) : createCommentVNode("", true)
            ])
          ]),
          total.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_20, [
            createBaseVNode("span", _hoisted_21, "共 " + toDisplayString(total.value) + " 条", 1),
            createBaseVNode("button", {
              disabled: page.value <= 1,
              onClick: _cache[8] || (_cache[8] = ($event) => {
                page.value--;
                loadData();
              })
            }, "‹", 8, _hoisted_22),
            (openBlock(true), createElementBlock(Fragment, null, renderList(pages.value, (p) => {
              return openBlock(), createElementBlock("button", {
                key: p,
                class: normalizeClass({ active: p === page.value }),
                onClick: ($event) => {
                  page.value = p;
                  loadData();
                }
              }, toDisplayString(p), 11, _hoisted_23);
            }), 128)),
            createBaseVNode("button", {
              disabled: page.value >= maxPage.value,
              onClick: _cache[9] || (_cache[9] = ($event) => {
                page.value++;
                loadData();
              })
            }, "›", 8, _hoisted_24)
          ])) : createCommentVNode("", true)
        ])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Events = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-2fd5cfcc"]]);

export { Events as default };
