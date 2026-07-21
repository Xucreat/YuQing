import { d as defineComponent, p as onMounted, G as onUnmounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, F as Fragment, i as renderList, H as vModelSelect, v as vModelText, b as withKeys, A as createCommentVNode, t as toDisplayString, I as withModifiers, n as normalizeClass, e as createTextVNode, k as normalizeStyle, y as createBlock, r as ref, f as reactive, j as computed, g as api, E as ElMessage, D as resolveDirective, o as openBlock, C as resolveComponent, _ as _export_sfc } from './index-CmsIrjs7.js';

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
const _hoisted_21 = { class: "modal-card" };
const _hoisted_22 = { class: "modal-header" };
const _hoisted_23 = { class: "modal-title-wrap" };
const _hoisted_24 = { class: "modal-title" };
const _hoisted_25 = { class: "modal-header-right" };
const _hoisted_26 = ["href"];
const _hoisted_27 = { class: "modal-body" };
const _hoisted_28 = {
  key: 0,
  class: "detail-grid"
};
const _hoisted_29 = { class: "card card-pad" };
const _hoisted_30 = { class: "detail-meta" };
const _hoisted_31 = {
  class: "detail-content",
  "element-loading-text": "正在抓取来源页原文…"
};
const _hoisted_32 = { key: 1 };
const _hoisted_33 = {
  key: 2,
  class: "orig-empty"
};
const _hoisted_34 = {
  key: 0,
  class: "detail-foot-note"
};
const _hoisted_35 = { class: "card card-pad ai-card" };
const _hoisted_36 = { class: "ai-header" };
const _hoisted_37 = { class: "report-meta" };
const _hoisted_38 = { class: "meta-item" };
const _hoisted_39 = { class: "meta-item" };
const _hoisted_40 = { class: "meta-item" };
const _hoisted_41 = { class: "report-body" };
const _hoisted_42 = {
  key: 0,
  class: "report-p"
};
const _hoisted_43 = {
  key: 1,
  class: "report-p report-muted"
};
const _hoisted_44 = {
  key: 2,
  class: "report-p"
};
const _hoisted_45 = {
  key: 0,
  class: "report-keywords"
};
const _hoisted_46 = {
  key: 1,
  class: "report-time"
};
const _hoisted_47 = { class: "ai-actions" };
const _hoisted_48 = ["disabled"];
const _hoisted_49 = {
  key: 1,
  class: "ai-status-line"
};
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
    const showDetail = ref(false);
    const detailLoading = ref(false);
    const originalLoading = ref(false);
    const analyzing = ref(false);
    const detail = ref(null);
    const originalParas = ref([]);
    const originalFetched = ref(false);
    const maxPage = computed(() => Math.ceil(total.value / size.value) || 1);
    const pages = computed(() => {
      const p = [];
      const mp = maxPage.value;
      const start = Math.max(1, page.value - 2);
      const end = Math.min(mp, page.value + 2);
      for (let i = start; i <= end; i++) p.push(i);
      return p;
    });
    const keywordList = computed(
      () => (detail.value?.keywords || "").split(",").map((k) => k.trim()).filter(Boolean)
    );
    function riskColor(score) {
      if (score >= 70) return "#ff3b30";
      if (score >= 40) return "#ff9f0a";
      return "#34c759";
    }
    function levelPill(score) {
      if (score >= 70) return "pill-red";
      if (score >= 40) return "pill-orange";
      return "pill-green";
    }
    function levelText(score) {
      if (score >= 70) return "高危";
      if (score >= 40) return "中危";
      return "低危";
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
    async function openDetail(id) {
      showDetail.value = true;
      detailLoading.value = true;
      originalLoading.value = true;
      detail.value = null;
      originalParas.value = [];
      originalFetched.value = false;
      try {
        const { data } = await api.get("/opinions/" + id);
        detail.value = data;
      } catch (err) {
        if (err?.response?.status === 404) {
          detail.value = null;
        } else {
          ElMessage.error(err?.response?.data?.detail || "加载详情失败");
        }
      } finally {
        detailLoading.value = false;
      }
      try {
        const { data } = await api.get("/opinions/" + id + "/original");
        originalParas.value = Array.isArray(data.original) ? data.original : [];
        originalFetched.value = true;
      } catch {
        originalFetched.value = true;
      } finally {
        originalLoading.value = false;
      }
    }
    function closeDetail() {
      showDetail.value = false;
    }
    async function triggerAnalyze() {
      if (analyzing.value || !detail.value) return;
      const id = detail.value.id;
      analyzing.value = true;
      try {
        const { data } = await api.post("/analyze/" + id);
        detail.value = data;
        ElMessage.success("AI 分析完成");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "AI 分析失败，请稍后重试");
        openDetail(id);
      } finally {
        analyzing.value = false;
      }
    }
    function onKeydown(e) {
      if (e.key === "Escape" && showDetail.value) closeDetail();
    }
    onMounted(() => {
      loadData();
      loadSources();
      window.addEventListener("data-refresh", loadData);
      window.addEventListener("keydown", onKeydown);
    });
    onUnmounted(() => {
      window.removeEventListener("data-refresh", loadData);
      window.removeEventListener("keydown", onKeydown);
    });
    return (_ctx, _cache) => {
      const _component_el_empty = resolveComponent("el-empty");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => filters.source = $event),
              class: "select",
              onChange: handleSearch
            }, [
              _cache[9] || (_cache[9] = createBaseVNode("option", { value: "" }, "来源（全部）", -1)),
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
            }, [..._cache[10] || (_cache[10] = [
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
            }, [..._cache[11] || (_cache[11] = [
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
              _cache[12] || (_cache[12] = createBaseVNode("span", { class: "date-sep" }, "至", -1)),
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
            _cache[15] || (_cache[15] = createBaseVNode("thead", null, [
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
                      class: normalizeClass(["pill", sentimentPill(row.sentiment)])
                    }, [
                      _cache[13] || (_cache[13] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(sentimentText(row.sentiment)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", _hoisted_12, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", levelPill(row.risk_score)])
                    }, toDisplayString(levelText(row.risk_score)), 3)
                  ]),
                  createBaseVNode("td", _hoisted_13, [
                    createBaseVNode("span", {
                      class: "risk-num",
                      style: normalizeStyle({ color: riskColor(row.risk_score) })
                    }, toDisplayString(row.risk_score), 5)
                  ]),
                  createBaseVNode("td", _hoisted_14, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", statusPill(row.analysis_status)])
                    }, toDisplayString(statusText(row.analysis_status)), 3)
                  ]),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.publish_time)), 1)
                ], 8, _hoisted_9);
              }), 128)),
              rows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_15, [..._cache[14] || (_cache[14] = [
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
        showDetail.value ? (openBlock(), createElementBlock("div", {
          key: 0,
          class: "modal-mask",
          onClick: withModifiers(closeDetail, ["self"])
        }, [
          createBaseVNode("div", _hoisted_21, [
            createBaseVNode("div", _hoisted_22, [
              createBaseVNode("div", _hoisted_23, [
                _cache[16] || (_cache[16] = createBaseVNode("span", { class: "modal-kicker" }, "舆情详情与 AI 分析", -1)),
                createBaseVNode("h3", _hoisted_24, toDisplayString(detail.value?.title || "加载中…"), 1)
              ]),
              createBaseVNode("div", _hoisted_25, [
                detail.value?.url ? (openBlock(), createElementBlock("a", {
                  key: 0,
                  class: "jump-link",
                  href: detail.value.url,
                  target: "_blank",
                  rel: "noopener"
                }, "🔗 跳转原文", 8, _hoisted_26)) : createCommentVNode("", true),
                createBaseVNode("button", {
                  class: "modal-close",
                  title: "关闭",
                  onClick: closeDetail
                }, "✕")
              ])
            ]),
            withDirectives((openBlock(), createElementBlock("div", _hoisted_27, [
              detail.value ? (openBlock(), createElementBlock("div", _hoisted_28, [
                createBaseVNode("div", _hoisted_29, [
                  createBaseVNode("div", _hoisted_30, [
                    createBaseVNode("span", null, "来源：" + toDisplayString(detail.value.source), 1),
                    createBaseVNode("span", null, "发布时间：" + toDisplayString(formatTime(detail.value.publish_time)), 1)
                  ]),
                  _cache[17] || (_cache[17] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                  withDirectives((openBlock(), createElementBlock("div", _hoisted_31, [
                    originalParas.value.length ? (openBlock(true), createElementBlock(Fragment, { key: 0 }, renderList(originalParas.value, (p, i) => {
                      return openBlock(), createElementBlock("p", {
                        key: i,
                        class: "orig-p"
                      }, toDisplayString(p), 1);
                    }), 128)) : detail.value.content && !originalLoading.value ? (openBlock(), createElementBlock("p", _hoisted_32, toDisplayString(detail.value.content), 1)) : !originalLoading.value ? (openBlock(), createElementBlock("p", _hoisted_33, "暂无原文内容。")) : createCommentVNode("", true)
                  ])), [
                    [_directive_loading, originalLoading.value]
                  ]),
                  originalFetched.value && !originalParas.value.length && detail.value.content ? (openBlock(), createElementBlock("div", _hoisted_34, " 来源页暂无可抓取正文，已显示摘要。 ")) : createCommentVNode("", true)
                ]),
                createBaseVNode("div", _hoisted_35, [
                  createBaseVNode("div", _hoisted_36, [
                    _cache[18] || (_cache[18] = createBaseVNode("span", { class: "section-title" }, "AI 研判报告", -1)),
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", statusPill(detail.value.analysis_status)])
                    }, toDisplayString(statusText(detail.value.analysis_status)), 3)
                  ]),
                  _cache[26] || (_cache[26] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                  createBaseVNode("div", _hoisted_37, [
                    createBaseVNode("span", _hoisted_38, [
                      _cache[19] || (_cache[19] = createTextVNode("风险评分 ", -1)),
                      createBaseVNode("b", {
                        style: normalizeStyle({ color: riskColor(detail.value.risk_score) })
                      }, toDisplayString(detail.value.risk_score), 5)
                    ]),
                    _cache[22] || (_cache[22] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                    createBaseVNode("span", _hoisted_39, [
                      _cache[20] || (_cache[20] = createTextVNode("级别 ", -1)),
                      createBaseVNode("b", null, toDisplayString(levelText(detail.value.risk_score)), 1)
                    ]),
                    _cache[23] || (_cache[23] = createBaseVNode("span", { class: "meta-sep" }, "·", -1)),
                    createBaseVNode("span", _hoisted_40, [
                      _cache[21] || (_cache[21] = createTextVNode("情感 ", -1)),
                      createBaseVNode("b", null, toDisplayString(sentimentText(detail.value.sentiment)), 1)
                    ])
                  ]),
                  createBaseVNode("div", _hoisted_41, [
                    detail.value.summary ? (openBlock(), createElementBlock("p", _hoisted_42, toDisplayString(detail.value.summary), 1)) : (openBlock(), createElementBlock("p", _hoisted_43, "暂无 AI 摘要。")),
                    detail.value.analysis_suggestion ? (openBlock(), createElementBlock("p", _hoisted_44, toDisplayString(detail.value.analysis_suggestion), 1)) : createCommentVNode("", true)
                  ]),
                  keywordList.value.length ? (openBlock(), createElementBlock("div", _hoisted_45, [
                    _cache[24] || (_cache[24] = createBaseVNode("span", { class: "kw-label" }, "关键词", -1)),
                    (openBlock(true), createElementBlock(Fragment, null, renderList(keywordList.value, (k) => {
                      return openBlock(), createElementBlock("span", {
                        key: k,
                        class: "kw-tag"
                      }, toDisplayString(k), 1);
                    }), 128))
                  ])) : createCommentVNode("", true),
                  detail.value.analysis_time ? (openBlock(), createElementBlock("div", _hoisted_46, " 分析时间：" + toDisplayString(formatTime(detail.value.analysis_time)), 1)) : createCommentVNode("", true),
                  _cache[27] || (_cache[27] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
                  createBaseVNode("div", _hoisted_47, [
                    detail.value.analysis_status !== "processing" ? (openBlock(), createElementBlock("button", {
                      key: 0,
                      class: "btn btn-primary btn-block",
                      disabled: analyzing.value,
                      onClick: triggerAnalyze
                    }, toDisplayString(analyzing.value ? "分析中..." : "触发 AI 分析"), 9, _hoisted_48)) : (openBlock(), createElementBlock("div", _hoisted_49, [..._cache[25] || (_cache[25] = [
                      createBaseVNode("span", { class: "spinner" }, null, -1),
                      createBaseVNode("span", { class: "ai-text" }, "AI 分析进行中...", -1)
                    ])]))
                  ])
                ])
              ])) : (openBlock(), createBlock(_component_el_empty, {
                key: 1,
                description: "未找到该舆情"
              }))
            ])), [
              [_directive_loading, detailLoading.value]
            ])
          ])
        ])) : createCommentVNode("", true)
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Opinions = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-5453cc8c"]]);

export { Opinions as default };
