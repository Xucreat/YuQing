import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, F as Fragment, i as renderList, G as vModelSelect, v as vModelText, b as withKeys, A as createCommentVNode, t as toDisplayString, B as createVNode, r as ref, f as reactive, j as computed, g as api, E as ElMessage, D as resolveDirective, o as openBlock, n as normalizeClass, x as unref, e as createTextVNode, k as normalizeStyle, _ as _export_sfc } from './index-Cm6t4PDU.js';
import { O as OpinionDetailModal, s as sentimentPill, a as sentimentText, l as levelPill, b as levelText, r as riskColor, c as statusPill, d as statusText, f as formatTime } from './OpinionDetailModal-BEs64aB5.js';

const _hoisted_1 = { class: "opinions" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = { class: "filters" };
const _hoisted_4 = ["value"];
const _hoisted_5 = { class: "date-range" };
const _hoisted_6 = { class: "search-wrap" };
const _hoisted_7 = { class: "card table-card" };
const _hoisted_8 = { class: "tbl" };
const _hoisted_9 = ["onClick"];
const _hoisted_10 = { class: "t-title" };
const _hoisted_11 = { class: "col-center" };
const _hoisted_12 = { class: "col-center" };
const _hoisted_13 = { class: "col-center" };
const _hoisted_14 = { class: "col-center" };
const _hoisted_15 = { key: 0 };
const _hoisted_16 = {
  key: 0,
  class: "pager"
};
const _hoisted_17 = { class: "p-info" };
const _hoisted_18 = ["disabled"];
const _hoisted_19 = ["onClick"];
const _hoisted_20 = ["disabled"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Opinions",
  setup(__props) {
    const loading = ref(false);
    const rows = ref([]);
    const total = ref(0);
    const page = ref(1);
    const size = ref(20);
    const sourceOptions = ref([]);
    const filters = reactive({
      source: "",
      risk_level: "",
      level: "",
      date_from: "",
      date_to: "",
      keyword: ""
    });
    const detailVisible = ref(false);
    const detailId = ref(null);
    const maxPage = computed(() => Math.ceil(total.value / size.value) || 1);
    const pages = computed(() => {
      const p = [];
      const mp = maxPage.value;
      const start = Math.max(1, page.value - 2);
      const end = Math.min(mp, page.value + 2);
      for (let i = start; i <= end; i++) p.push(i);
      return p;
    });
    function levelRange(level) {
      if (level === "high") return [70, null];
      if (level === "mid") return [40, 69];
      if (level === "low") return [null, 39];
      return [null, null];
    }
    async function loadSources() {
      try {
        const { data } = await api.get("/opinions/sources");
        sourceOptions.value = Array.isArray(data) ? data : [];
      } catch {
        sourceOptions.value = [];
      }
    }
    async function loadData() {
      loading.value = true;
      try {
        const params = { page: page.value, size: size.value };
        if (filters.source) params.source = filters.source;
        if (filters.risk_level) params.risk_level = filters.risk_level;
        if (filters.keyword) params.keyword = filters.keyword;
        const [rmin, rmax] = levelRange(filters.level);
        if (rmin != null) params.risk_min = rmin;
        if (rmax != null) params.risk_max = rmax;
        if (filters.date_from) params.date_from = filters.date_from;
        if (filters.date_to) params.date_to = filters.date_to;
        const { data } = await api.get("/opinions", { params });
        rows.value = data.items;
        total.value = data.total;
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
      filters.level = "";
      filters.date_from = "";
      filters.date_to = "";
      filters.keyword = "";
      page.value = 1;
      loadData();
    }
    function openDetail(id) {
      detailId.value = id;
      detailVisible.value = true;
    }
    onMounted(() => {
      loadData();
      loadSources();
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
              _cache[10] || (_cache[10] = createBaseVNode("option", { value: "" }, "来源（全部）", -1)),
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
            }, [..._cache[11] || (_cache[11] = [
              createBaseVNode("option", { value: "" }, "情感（全部）", -1),
              createBaseVNode("option", { value: "negative" }, "负面", -1),
              createBaseVNode("option", { value: "neutral" }, "中性", -1),
              createBaseVNode("option", { value: "positive" }, "正面", -1)
            ])], 544), [
              [vModelSelect, filters.risk_level]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => filters.level = $event),
              class: "select",
              onChange: handleSearch
            }, [..._cache[12] || (_cache[12] = [
              createBaseVNode("option", { value: "" }, "级别（全部）", -1),
              createBaseVNode("option", { value: "high" }, "高危（≥70）", -1),
              createBaseVNode("option", { value: "mid" }, "中危（40-69）", -1),
              createBaseVNode("option", { value: "low" }, "低危（<40）", -1)
            ])], 544), [
              [vModelSelect, filters.level]
            ]),
            createBaseVNode("div", _hoisted_5, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => filters.date_from = $event),
                class: "select date-input",
                type: "date",
                title: "发布开始日期",
                onChange: handleSearch
              }, null, 544), [
                [vModelText, filters.date_from]
              ]),
              _cache[13] || (_cache[13] = createBaseVNode("span", { class: "date-sep" }, "至", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => filters.date_to = $event),
                class: "select date-input",
                type: "date",
                title: "发布结束日期",
                onChange: handleSearch
              }, null, 544), [
                [vModelText, filters.date_to]
              ])
            ]),
            createBaseVNode("div", _hoisted_6, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => filters.keyword = $event),
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
                onClick: _cache[6] || (_cache[6] = ($event) => {
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
        createBaseVNode("div", _hoisted_7, [
          createBaseVNode("table", _hoisted_8, [
            _cache[16] || (_cache[16] = createBaseVNode("thead", null, [
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
                }, "级别"),
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
                  onClick: ($event) => openDetail(row.id),
                  style: { "cursor": "pointer" }
                }, [
                  createBaseVNode("td", null, toDisplayString((page.value - 1) * size.value + idx + 1), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", _hoisted_10, toDisplayString(row.title), 1)
                  ]),
                  createBaseVNode("td", null, toDisplayString(row.source), 1),
                  createBaseVNode("td", _hoisted_11, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", unref(sentimentPill)(row.sentiment)])
                    }, [
                      _cache[14] || (_cache[14] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(unref(sentimentText)(row.sentiment)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", _hoisted_12, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", unref(levelPill)(row.risk_score)])
                    }, toDisplayString(unref(levelText)(row.risk_score)), 3)
                  ]),
                  createBaseVNode("td", _hoisted_13, [
                    createBaseVNode("span", {
                      class: "risk-num",
                      style: normalizeStyle({ color: unref(riskColor)(row.risk_score) })
                    }, toDisplayString(row.risk_score), 5)
                  ]),
                  createBaseVNode("td", _hoisted_14, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", unref(statusPill)(row.analysis_status)])
                    }, toDisplayString(unref(statusText)(row.analysis_status)), 3)
                  ]),
                  createBaseVNode("td", null, toDisplayString(unref(formatTime)(row.publish_time)), 1)
                ], 8, _hoisted_9);
              }), 128)),
              rows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_15, [..._cache[15] || (_cache[15] = [
                createBaseVNode("td", {
                  colspan: "8",
                  class: "empty-row"
                }, "暂无舆情数据", -1)
              ])])) : createCommentVNode("", true)
            ])
          ]),
          total.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_16, [
            createBaseVNode("span", _hoisted_17, "共 " + toDisplayString(total.value) + " 条", 1),
            createBaseVNode("button", {
              disabled: page.value <= 1,
              onClick: _cache[7] || (_cache[7] = ($event) => {
                page.value--;
                loadData();
              })
            }, "‹", 8, _hoisted_18),
            (openBlock(true), createElementBlock(Fragment, null, renderList(pages.value, (p) => {
              return openBlock(), createElementBlock("button", {
                key: p,
                class: normalizeClass({ active: p === page.value }),
                onClick: ($event) => {
                  page.value = p;
                  loadData();
                }
              }, toDisplayString(p), 11, _hoisted_19);
            }), 128)),
            createBaseVNode("button", {
              disabled: page.value >= maxPage.value,
              onClick: _cache[8] || (_cache[8] = ($event) => {
                page.value++;
                loadData();
              })
            }, "›", 8, _hoisted_20)
          ])) : createCommentVNode("", true)
        ]),
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Opinions = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-af03476f"]]);

export { Opinions as default };
