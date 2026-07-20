import { d as defineComponent, m as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, F as Fragment, i as renderList, y as vModelSelect, b as withKeys, v as vModelText, z as createCommentVNode, t as toDisplayString, r as ref, f as reactive, j as computed, g as api, E as ElMessage, x as resolveDirective, o as openBlock, n as normalizeClass, e as createTextVNode, k as normalizeStyle, h as useRouter, _ as _export_sfc } from './index-CX2gy79j.js';

const _hoisted_1 = { class: "opinions" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = { class: "filters" };
const _hoisted_4 = ["value"];
const _hoisted_5 = { class: "search-wrap" };
const _hoisted_6 = { class: "card table-card" };
const _hoisted_7 = { class: "tbl" };
const _hoisted_8 = ["onClick"];
const _hoisted_9 = { class: "t-title" };
const _hoisted_10 = { class: "col-center" };
const _hoisted_11 = { class: "col-center" };
const _hoisted_12 = { class: "col-center" };
const _hoisted_13 = { key: 0 };
const _hoisted_14 = {
  key: 0,
  class: "pager"
};
const _hoisted_15 = { class: "p-info" };
const _hoisted_16 = ["disabled"];
const _hoisted_17 = ["onClick"];
const _hoisted_18 = ["disabled"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Opinions",
  setup(__props) {
    const router = useRouter();
    const loading = ref(false);
    const rows = ref([]);
    const total = ref(0);
    const page = ref(1);
    const size = ref(20);
    const sourceOptions = ref([]);
    const filters = reactive({
      source: "",
      risk_level: "",
      keyword: ""
    });
    const maxPage = computed(() => Math.ceil(total.value / size.value) || 1);
    const pages = computed(() => {
      const p = [];
      const mp = maxPage.value;
      const start = Math.max(1, page.value - 2);
      const end = Math.min(mp, page.value + 2);
      for (let i = start; i <= end; i++) p.push(i);
      return p;
    });
    function riskColor(score) {
      if (score >= 70) return "#ff3b30";
      if (score >= 40) return "#ff9f0a";
      return "#34c759";
    }
    function sentimentPill(s) {
      return { negative: "pill-red", positive: "pill-green", neutral: "pill-gray" }[s] || "pill-gray";
    }
    function sentimentText(s) {
      return { negative: "负面", positive: "正面", neutral: "中性" }[s] || s;
    }
    function statusPill(s) {
      return { completed: "pill-green", failed: "pill-red", processing: "pill-orange", pending: "pill-gray" }[s] || "pill-gray";
    }
    function statusText(s) {
      return { completed: "已完成", failed: "失败", processing: "分析中", pending: "待分析" }[s] || s;
    }
    function formatTime(t) {
      if (!t) return "-";
      return t.replace("T", " ").slice(0, 19);
    }
    async function loadData() {
      loading.value = true;
      try {
        const params = { page: page.value, size: size.value };
        if (filters.source) params.source = filters.source;
        if (filters.risk_level) params.risk_level = filters.risk_level;
        if (filters.keyword) params.keyword = filters.keyword;
        const { data } = await api.get("/opinions", { params });
        rows.value = data.items;
        total.value = data.total;
        const set = new Set(sourceOptions.value);
        data.items.forEach((o) => o.source && set.add(o.source));
        sourceOptions.value = Array.from(set);
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载舆情列表失败");
      } finally {
        loading.value = false;
      }
    }
    function handleSearch() {
      page.value = 1;
      loadData();
    }
    function handleRefresh() {
      filters.source = "";
      filters.risk_level = "";
      filters.keyword = "";
      page.value = 1;
      loadData();
    }
    function goDetail(id) {
      router.push("/opinion/" + id);
    }
    onMounted(() => {
      loadData();
      window.addEventListener("data-refresh", loadData);
    });
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => filters.source = $event),
              class: "select",
              onChange: handleSearch
            }, [
              _cache[6] || (_cache[6] = createBaseVNode("option", { value: "" }, "来源（全部）", -1)),
              (openBlock(true), createElementBlock(Fragment, null, renderList(sourceOptions.value, (s) => {
                return openBlock(), createElementBlock("option", {
                  key: s,
                  value: s
                }, toDisplayString(s), 9, _hoisted_4);
              }), 128))
            ], 544), [
              [vModelSelect, filters.source]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => filters.risk_level = $event),
              class: "select",
              onChange: handleSearch
            }, [..._cache[7] || (_cache[7] = [
              createBaseVNode("option", { value: "" }, "情感（全部）", -1),
              createBaseVNode("option", { value: "negative" }, "负面", -1),
              createBaseVNode("option", { value: "neutral" }, "中性", -1),
              createBaseVNode("option", { value: "positive" }, "正面", -1)
            ])], 544), [
              [vModelSelect, filters.risk_level]
            ]),
            createBaseVNode("div", _hoisted_5, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => filters.keyword = $event),
                class: "search",
                type: "text",
                placeholder: "关键词 / 标题 / 内容",
                onKeyup: withKeys(handleSearch, ["enter"])
              }, null, 544), [
                [vModelText, filters.keyword]
              ]),
              filters.keyword ? (openBlock(), createElementBlock("button", {
                key: 0,
                class: "search-clear",
                onClick: _cache[3] || (_cache[3] = ($event) => {
                  filters.keyword = "";
                  handleSearch();
                })
              }, "✕")) : createCommentVNode("", true)
            ]),
            createBaseVNode("button", {
              class: "btn btn-ghost",
              onClick: handleSearch
            }, "搜索"),
            createBaseVNode("button", {
              class: "btn btn-ghost",
              onClick: handleRefresh
            }, "刷新")
          ])
        ]),
        createBaseVNode("div", _hoisted_6, [
          createBaseVNode("table", _hoisted_7, [
            _cache[10] || (_cache[10] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", { style: { "width": "70px" } }, "ID"),
                createBaseVNode("th", { style: { "min-width": "260px" } }, "标题"),
                createBaseVNode("th", { style: { "width": "150px" } }, "来源"),
                createBaseVNode("th", {
                  style: { "width": "100px" },
                  class: "col-center"
                }, "情感"),
                createBaseVNode("th", {
                  style: { "width": "110px" },
                  class: "col-center"
                }, "风险评分"),
                createBaseVNode("th", {
                  style: { "width": "110px" },
                  class: "col-center"
                }, "分析状态"),
                createBaseVNode("th", { style: { "width": "170px" } }, "发布时间")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(rows.value, (row, idx) => {
                return openBlock(), createElementBlock("tr", {
                  key: row.id,
                  onClick: ($event) => goDetail(row.id),
                  style: { "cursor": "pointer" }
                }, [
                  createBaseVNode("td", null, toDisplayString((page.value - 1) * size.value + idx + 1), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", _hoisted_9, toDisplayString(row.title), 1)
                  ]),
                  createBaseVNode("td", null, toDisplayString(row.source), 1),
                  createBaseVNode("td", _hoisted_10, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", sentimentPill(row.sentiment)])
                    }, [
                      _cache[8] || (_cache[8] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(sentimentText(row.sentiment)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", _hoisted_11, [
                    createBaseVNode("span", {
                      class: "risk-num",
                      style: normalizeStyle({ color: riskColor(row.risk_score) })
                    }, toDisplayString(row.risk_score), 5)
                  ]),
                  createBaseVNode("td", _hoisted_12, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", statusPill(row.analysis_status)])
                    }, toDisplayString(statusText(row.analysis_status)), 3)
                  ]),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.publish_time)), 1)
                ], 8, _hoisted_8);
              }), 128)),
              rows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_13, [..._cache[9] || (_cache[9] = [
                createBaseVNode("td", {
                  colspan: "7",
                  class: "empty-row"
                }, "暂无舆情数据", -1)
              ])])) : createCommentVNode("", true)
            ])
          ]),
          total.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_14, [
            createBaseVNode("span", _hoisted_15, "共 " + toDisplayString(total.value) + " 条", 1),
            createBaseVNode("button", {
              disabled: page.value <= 1,
              onClick: _cache[4] || (_cache[4] = ($event) => {
                page.value--;
                loadData();
              })
            }, "‹", 8, _hoisted_16),
            (openBlock(true), createElementBlock(Fragment, null, renderList(pages.value, (p) => {
              return openBlock(), createElementBlock("button", {
                key: p,
                class: normalizeClass({ active: p === page.value }),
                onClick: ($event) => {
                  page.value = p;
                  loadData();
                }
              }, toDisplayString(p), 11, _hoisted_17);
            }), 128)),
            createBaseVNode("button", {
              disabled: page.value >= maxPage.value,
              onClick: _cache[5] || (_cache[5] = ($event) => {
                page.value++;
                loadData();
              })
            }, "›", 8, _hoisted_18)
          ])) : createCommentVNode("", true)
        ])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Opinions = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-155cc579"]]);

export { Opinions as default };
