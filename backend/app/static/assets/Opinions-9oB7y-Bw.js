import { d as defineComponent, z as usePermission, A as watch, C as onMounted, I as onUnmounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, F as Fragment, i as renderList, J as vModelSelect, v as vModelText, b as withKeys, s as createCommentVNode, H as unref, K as vModelCheckbox, e as createTextVNode, t as toDisplayString, m as createVNode, p as withCtx, L as withModifiers, r as ref, f as reactive, j as computed, M as ElMessageBox, g as api, E as ElMessage, y as resolveComponent, B as resolveDirective, N as useRoute, h as useRouter, o as openBlock, n as normalizeClass, q as createBlock, k as normalizeStyle, _ as _export_sfc } from './index-DHeS0ZCl.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-C2kuUcLp.js';
import { s as sentimentPill, a as sentimentText, l as levelPill, b as levelText, r as riskColor, c as statusPill, d as statusText, f as formatTime } from './opinion-Cag9WtuS.js';
import { f as formatAdmissionHits } from './admission-DpEuIHXC.js';

const _hoisted_1 = { class: "opinions" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = { class: "filters" };
const _hoisted_4 = ["value"];
const _hoisted_5 = ["value"];
const _hoisted_6 = { class: "date-range" };
const _hoisted_7 = { class: "search-wrap" };
const _hoisted_8 = {
  key: 0,
  class: "low-value-toggle",
  title: "默认列表隐藏 irrelevant / advertising 等低价值内容；勾选后可查看完整数据（含历史重算标定的低价值条目）"
};
const _hoisted_9 = {
  key: 0,
  class: "batch-bar"
};
const _hoisted_10 = { class: "batch-count" };
const _hoisted_11 = ["disabled"];
const _hoisted_12 = { class: "sent-pop" };
const _hoisted_13 = ["onClick"];
const _hoisted_14 = { class: "card table-card" };
const _hoisted_15 = { class: "tbl-scroll" };
const _hoisted_16 = { class: "tbl" };
const _hoisted_17 = {
  key: 0,
  style: { "width": "44px" },
  class: "col-center leading-check"
};
const _hoisted_18 = ["checked", "indeterminate"];
const _hoisted_19 = {
  key: 1,
  style: { "width": "90px" },
  class: "col-center"
};
const _hoisted_20 = ["onClick"];
const _hoisted_21 = {
  key: 0,
  class: "col-center leading-check"
};
const _hoisted_22 = ["checked", "onClick"];
const _hoisted_23 = { class: "leading-id" };
const _hoisted_24 = { class: "leading-title" };
const _hoisted_25 = { class: "t-title" };
const _hoisted_26 = { class: "col-center" };
const _hoisted_27 = { class: "pill pill-blue" };
const _hoisted_28 = { class: "col-center" };
const _hoisted_29 = { class: "admission-summary" };
const _hoisted_30 = { class: "col-center" };
const _hoisted_31 = ["onClick"];
const _hoisted_32 = { class: "sent-pop" };
const _hoisted_33 = ["onClick"];
const _hoisted_34 = { class: "col-center" };
const _hoisted_35 = { class: "col-center" };
const _hoisted_36 = { class: "col-center" };
const _hoisted_37 = {
  key: 1,
  class: "col-center"
};
const _hoisted_38 = ["onClick"];
const _hoisted_39 = { key: 0 };
const _hoisted_40 = ["colspan"];
const _hoisted_41 = {
  key: 0,
  class: "pager"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Opinions",
  setup(__props) {
    const route = useRoute();
    const router = useRouter();
    const loading = ref(false);
    const rows = ref([]);
    const total = ref(0);
    const page = ref(1);
    const size = ref(20);
    const sourceOptions = ref([]);
    const includeLowValue = ref(false);
    const contentTypeOptions = [
      { value: "complaint", label: "投诉举报" },
      { value: "consultation", label: "咨询求助" },
      { value: "risk_event", label: "风险事件" },
      { value: "public_affairs", label: "公共事务" },
      { value: "news", label: "新闻" },
      { value: "policy", label: "政策政务" }
    ];
    const CONTENT_TYPE_TEXT = {
      complaint: "投诉举报",
      consultation: "咨询求助",
      risk_event: "风险事件",
      public_affairs: "公共事务",
      news: "新闻",
      policy: "政策政务",
      advertising: "广告",
      entertainment: "娱乐",
      irrelevant: "无关"
    };
    const filters = reactive({
      source: "",
      risk_level: "",
      level: "",
      content_type: "",
      relevance: "",
      date_from: "",
      date_to: "",
      keyword: ""
    });
    const detailVisible = ref(false);
    const detailId = ref(null);
    const { hasPermission, isSuperuser } = usePermission();
    const canEditOpinion = computed(() => hasPermission("opinions:write"));
    const sentimentOptions = [
      { value: "positive", label: "正面" },
      { value: "neutral", label: "中性" },
      { value: "negative", label: "负面" }
    ];
    const popoverRowId = ref(null);
    function toggleSentPop(row) {
      popoverRowId.value = popoverRowId.value === row.id ? null : row.id;
    }
    function closeSentPop() {
      popoverRowId.value = null;
    }
    async function chooseSentiment(row, value) {
      if (!canEditOpinion.value) return;
      closeSentPop();
      if (row.sentiment === value) return;
      const oldVal = row.sentiment;
      row.sentiment = value;
      try {
        await api.patch(`/opinions/${row.id}`, { sentiment: value });
        ElMessage.success("情感已更新");
      } catch (err) {
        row.sentiment = oldVal;
        ElMessage.error(err?.response?.data?.detail || "情感更新失败");
      }
    }
    function onDocClick(e) {
      if (popoverRowId.value == null && !batchPopVisible.value) return;
      const t = e.target;
      if (t && t.closest(".sent-pop")) return;
      closeSentPop();
      batchPopVisible.value = false;
    }
    const canDelete = computed(() => isSuperuser.value);
    const selectedIds = ref(/* @__PURE__ */ new Set());
    const batchPopVisible = ref(false);
    const isAllSelected = computed(
      () => rows.value.length > 0 && selectedIds.value.size === rows.value.length
    );
    const isIndeterminate = computed(
      () => selectedIds.value.size > 0 && selectedIds.value.size < rows.value.length
    );
    const colCount = computed(
      () => 11 + (canEditOpinion.value || canDelete.value ? 1 : 0) + (canDelete.value ? 1 : 0)
    );
    function toggleRow(row) {
      const next = new Set(selectedIds.value);
      if (next.has(row.id)) next.delete(row.id);
      else next.add(row.id);
      selectedIds.value = next;
    }
    function toggleSelectAll() {
      if (isAllSelected.value) selectedIds.value = /* @__PURE__ */ new Set();
      else selectedIds.value = new Set(rows.value.map((r) => r.id));
    }
    function clearSelection() {
      selectedIds.value = /* @__PURE__ */ new Set();
    }
    function toggleBatchPop() {
      batchPopVisible.value = !batchPopVisible.value;
    }
    async function batchSetSentiment(value) {
      if (!canEditOpinion.value || selectedIds.value.size === 0) return;
      batchPopVisible.value = false;
      const ids = [...selectedIds.value];
      const oldMap = {};
      rows.value.forEach((r) => {
        if (ids.includes(r.id) && r.sentiment !== value) {
          oldMap[r.id] = r.sentiment;
          r.sentiment = value;
        }
      });
      try {
        const { data } = await api.patch("/opinions/batch", { ids, sentiment: value });
        ElMessage.success(
          `已更新 ${data.updated} 条，跳过 ${data.skipped} 条` + (data.failed ? `，失败 ${data.failed} 条` : "")
        );
      } catch (err) {
        rows.value.forEach((r) => {
          if (oldMap[r.id] !== void 0) r.sentiment = oldMap[r.id];
        });
        ElMessage.error(err?.response?.data?.detail || "批量修改情感失败");
      } finally {
        clearSelection();
        loadData();
      }
    }
    async function batchDelete() {
      if (!canDelete.value || selectedIds.value.size === 0) return;
      const ids = [...selectedIds.value];
      try {
        await ElMessageBox.confirm(
          `即将删除 ${ids.length} 条舆情
该操作不可恢复`,
          "删除确认",
          { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" }
        );
      } catch {
        return;
      }
      try {
        const { data } = await api.delete("/opinions/batch", { data: { ids } });
        ElMessage.success(
          `已删除 ${data.deleted} 条` + (data.not_found ? `，${data.not_found} 条不存在` : "")
        );
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "批量删除失败");
      } finally {
        clearSelection();
        loadData();
      }
    }
    async function deleteOne(row) {
      if (!canDelete.value) return;
      try {
        await ElMessageBox.confirm(
          "即将删除该条舆情\n该操作不可恢复",
          "删除确认",
          { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" }
        );
      } catch {
        return;
      }
      try {
        await api.delete(`/opinions/${row.id}`);
        ElMessage.success("已删除");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "删除失败");
      } finally {
        const next = new Set(selectedIds.value);
        next.delete(row.id);
        selectedIds.value = next;
        loadData();
      }
    }
    function levelRange(level) {
      if (level === "high") return [70, null];
      if (level === "mid") return [40, 69];
      if (level === "low") return [null, 39];
      return [null, null];
    }
    function relevanceRange(level) {
      if (level === "high") return [60, null];
      if (level === "low") return [40, 59];
      return [null, null];
    }
    function contentTypeText(type) {
      return type ? CONTENT_TYPE_TEXT[type] || type : "未标注";
    }
    function formatRelevance(score) {
      return score == null ? "-" : `${score} 分`;
    }
    function relevanceClass(score) {
      if (score == null) return "score-empty";
      if (score >= 60) return "score-high";
      if (score >= 40) return "score-low";
      return "score-filtered";
    }
    function admissionSummary(reason) {
      if (!reason || typeof reason !== "object") return "系统默认准入";
      const policy = String(reason.policy || "");
      if (policy === "default_allow_non_weibo") {
        const source = String(reason.source || "");
        return source.includes("政府") || source.includes("政务") ? "政府来源默认准入" : "新闻来源默认准入";
      }
      const parts = [];
      const add = (label, value) => {
        const text = formatAdmissionHits(value, 3);
        if (text) parts.push(`${label}：${text}`);
      };
      add("地域", reason.region_hits);
      add("公共事务", reason.public_hits);
      add("诉求", reason.demand_hits);
      add("风险", reason.risk_hits);
      return parts.length ? parts.join("；") : "系统默认准入";
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
        if (filters.content_type) params.content_type = filters.content_type;
        if (filters.keyword) params.keyword = filters.keyword;
        const [rmin, rmax] = levelRange(filters.level);
        if (rmin != null) params.risk_min = rmin;
        if (rmax != null) params.risk_max = rmax;
        const [relMin, relMax] = relevanceRange(filters.relevance);
        if (relMin != null) params.relevance_min = relMin;
        if (relMax != null) params.relevance_max = relMax;
        if (filters.date_from) params.date_from = filters.date_from;
        if (filters.date_to) params.date_to = filters.date_to;
        if (includeLowValue.value) params.include_low_value = true;
        const { data } = await api.get("/opinions", { params });
        rows.value = data.items;
        total.value = data.total;
        if (rows.value.length === 0 && page.value > 1) {
          page.value -= 1;
          syncUrl();
          return loadData();
        }
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载舆情列表失败");
      } finally {
        loading.value = false;
      }
    }
    function buildQuery() {
      const q = {};
      if (filters.source) q.source = filters.source;
      if (filters.risk_level) q.risk_level = filters.risk_level;
      if (filters.level) q.level = filters.level;
      if (filters.content_type) q.content_type = filters.content_type;
      if (filters.relevance) q.relevance = filters.relevance;
      if (filters.date_from) q.date_from = filters.date_from;
      if (filters.date_to) q.date_to = filters.date_to;
      if (filters.keyword) q.keyword = filters.keyword;
      if (page.value > 1) q.page = String(page.value);
      return q;
    }
    let syncingUrl = false;
    function syncUrl() {
      syncingUrl = true;
      router.replace({ query: buildQuery() }).finally(() => {
        syncingUrl = false;
      });
    }
    function restoreFromQuery() {
      const q = route.query;
      page.value = typeof q.page === "string" && Number(q.page) > 0 ? Number(q.page) : 1;
      filters.source = typeof q.source === "string" ? q.source : "";
      filters.risk_level = typeof q.risk_level === "string" ? q.risk_level : "";
      filters.level = typeof q.level === "string" ? q.level : "";
      filters.content_type = typeof q.content_type === "string" ? q.content_type : "";
      filters.relevance = typeof q.relevance === "string" ? q.relevance : "";
      filters.date_from = typeof q.date_from === "string" ? q.date_from : "";
      filters.date_to = typeof q.date_to === "string" ? q.date_to : "";
      filters.keyword = typeof q.keyword === "string" ? q.keyword : "";
    }
    function handleSearch() {
      page.value = 1;
      loadData();
      syncUrl();
    }
    function handleRefresh() {
      filters.source = "";
      filters.risk_level = "";
      filters.level = "";
      filters.content_type = "";
      filters.relevance = "";
      filters.date_from = "";
      filters.date_to = "";
      filters.keyword = "";
      page.value = 1;
      loadData();
      syncUrl();
    }
    function onPageChange(p) {
      page.value = p;
      loadData();
      syncUrl();
    }
    watch(() => route.query, () => {
      if (syncingUrl) return;
      restoreFromQuery();
      loadData();
    });
    function openDetail(id) {
      detailId.value = id;
      detailVisible.value = true;
    }
    onMounted(() => {
      restoreFromQuery();
      loadData();
      loadSources();
      window.addEventListener("data-refresh", loadData);
      document.addEventListener("click", onDocClick);
    });
    onUnmounted(() => {
      window.removeEventListener("data-refresh", loadData);
      document.removeEventListener("click", onDocClick);
    });
    return (_ctx, _cache) => {
      const _component_el_popover = resolveComponent("el-popover");
      const _component_Pager = resolveComponent("Pager");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => filters.source = $event),
              class: "select",
              onChange: handleSearch
            }, [
              _cache[12] || (_cache[12] = createBaseVNode("option", { value: "" }, "来源（全部）", -1)),
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
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => filters.content_type = $event),
              class: "select",
              onChange: handleSearch
            }, [
              _cache[13] || (_cache[13] = createBaseVNode("option", { value: "" }, "类型（全部）", -1)),
              (openBlock(), createElementBlock(Fragment, null, renderList(contentTypeOptions, (o) => {
                return createBaseVNode("option", {
                  key: o.value,
                  value: o.value
                }, toDisplayString(o.label), 9, _hoisted_5);
              }), 64))
            ], 544), [
              [vModelSelect, filters.content_type]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => filters.relevance = $event),
              class: "select",
              onChange: handleSearch
            }, [..._cache[14] || (_cache[14] = [
              createBaseVNode("option", { value: "" }, "相关性（全部）", -1),
              createBaseVNode("option", { value: "high" }, "高相关（≥60）", -1),
              createBaseVNode("option", { value: "low" }, "低相关（40-59）", -1)
            ])], 544), [
              [vModelSelect, filters.relevance]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => filters.risk_level = $event),
              class: "select",
              onChange: handleSearch
            }, [..._cache[15] || (_cache[15] = [
              createBaseVNode("option", { value: "" }, "情感（全部）", -1),
              createBaseVNode("option", { value: "negative" }, "负面", -1),
              createBaseVNode("option", { value: "neutral" }, "中性", -1),
              createBaseVNode("option", { value: "positive" }, "正面", -1)
            ])], 544), [
              [vModelSelect, filters.risk_level]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => filters.level = $event),
              class: "select",
              onChange: handleSearch
            }, [..._cache[16] || (_cache[16] = [
              createBaseVNode("option", { value: "" }, "级别（全部）", -1),
              createBaseVNode("option", { value: "high" }, "高危（≥70）", -1),
              createBaseVNode("option", { value: "mid" }, "中危（40-69）", -1),
              createBaseVNode("option", { value: "low" }, "低危（<40）", -1)
            ])], 544), [
              [vModelSelect, filters.level]
            ]),
            createBaseVNode("div", _hoisted_6, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => filters.date_from = $event),
                class: "select date-input",
                type: "date",
                title: "发布开始日期",
                onChange: handleSearch
              }, null, 544), [
                [vModelText, filters.date_from]
              ]),
              _cache[17] || (_cache[17] = createBaseVNode("span", { class: "date-sep" }, "至", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => filters.date_to = $event),
                class: "select date-input",
                type: "date",
                title: "发布结束日期",
                onChange: handleSearch
              }, null, 544), [
                [vModelText, filters.date_to]
              ])
            ]),
            createBaseVNode("div", _hoisted_7, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => filters.keyword = $event),
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
                onClick: _cache[8] || (_cache[8] = ($event) => {
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
            }, "刷新"),
            unref(isSuperuser) ? (openBlock(), createElementBlock("label", _hoisted_8, [
              withDirectives(createBaseVNode("input", {
                type: "checkbox",
                "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => includeLowValue.value = $event),
                onChange: handleSearch
              }, null, 544), [
                [vModelCheckbox, includeLowValue.value]
              ]),
              _cache[18] || (_cache[18] = createTextVNode(" 显示低价值内容 ", -1))
            ])) : createCommentVNode("", true)
          ])
        ]),
        selectedIds.value.size > 0 ? (openBlock(), createElementBlock("div", _hoisted_9, [
          createBaseVNode("span", _hoisted_10, [
            _cache[19] || (_cache[19] = createTextVNode("已选择 ", -1)),
            createBaseVNode("b", null, toDisplayString(selectedIds.value.size), 1),
            _cache[20] || (_cache[20] = createTextVNode(" 条", -1))
          ]),
          createVNode(_component_el_popover, {
            trigger: "manual",
            visible: batchPopVisible.value,
            placement: "bottom",
            width: 132,
            "popper-class": "sent-popper"
          }, {
            reference: withCtx(() => [
              createBaseVNode("button", {
                class: "btn btn-primary",
                disabled: !canEditOpinion.value,
                onClick: withModifiers(toggleBatchPop, ["stop"])
              }, "修改情感", 8, _hoisted_11)
            ]),
            default: withCtx(() => [
              createBaseVNode("div", _hoisted_12, [
                (openBlock(), createElementBlock(Fragment, null, renderList(sentimentOptions, (opt) => {
                  return createBaseVNode("button", {
                    key: opt.value,
                    type: "button",
                    class: normalizeClass(["sent-opt", unref(sentimentPill)(opt.value)]),
                    onClick: withModifiers(($event) => batchSetSentiment(opt.value), ["stop"])
                  }, toDisplayString(opt.label), 11, _hoisted_13);
                }), 64))
              ])
            ]),
            _: 1
          }, 8, ["visible"]),
          canDelete.value ? (openBlock(), createElementBlock("button", {
            key: 0,
            class: "btn btn-danger",
            onClick: batchDelete
          }, "删除")) : createCommentVNode("", true),
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: clearSelection
          }, "取消选择")
        ])) : createCommentVNode("", true),
        createBaseVNode("div", _hoisted_14, [
          createBaseVNode("div", _hoisted_15, [
            createBaseVNode("table", _hoisted_16, [
              createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  canEditOpinion.value || canDelete.value ? (openBlock(), createElementBlock("th", _hoisted_17, [
                    createBaseVNode("input", {
                      type: "checkbox",
                      class: "row-check",
                      checked: isAllSelected.value,
                      indeterminate: isIndeterminate.value,
                      onClick: withModifiers(toggleSelectAll, ["stop"])
                    }, null, 8, _hoisted_18)
                  ])) : createCommentVNode("", true),
                  _cache[21] || (_cache[21] = createBaseVNode("th", {
                    style: { "width": "58px" },
                    class: "leading-id"
                  }, "ID", -1)),
                  _cache[22] || (_cache[22] = createBaseVNode("th", {
                    style: { "width": "280px" },
                    class: "leading-title"
                  }, "标题", -1)),
                  _cache[23] || (_cache[23] = createBaseVNode("th", { style: { "width": "150px" } }, "来源", -1)),
                  _cache[24] || (_cache[24] = createBaseVNode("th", {
                    style: { "width": "110px" },
                    class: "col-center"
                  }, "类型", -1)),
                  _cache[25] || (_cache[25] = createBaseVNode("th", {
                    style: { "width": "110px" },
                    class: "col-center"
                  }, "相关性", -1)),
                  _cache[26] || (_cache[26] = createBaseVNode("th", { style: { "width": "200px" } }, "准入原因", -1)),
                  _cache[27] || (_cache[27] = createBaseVNode("th", {
                    style: { "width": "100px" },
                    class: "col-center"
                  }, "情感", -1)),
                  _cache[28] || (_cache[28] = createBaseVNode("th", {
                    style: { "width": "110px" },
                    class: "col-center"
                  }, "级别", -1)),
                  _cache[29] || (_cache[29] = createBaseVNode("th", {
                    style: { "width": "110px" },
                    class: "col-center"
                  }, "风险评分", -1)),
                  _cache[30] || (_cache[30] = createBaseVNode("th", {
                    style: { "width": "110px" },
                    class: "col-center"
                  }, "分析状态", -1)),
                  _cache[31] || (_cache[31] = createBaseVNode("th", { style: { "width": "170px" } }, "发布时间", -1)),
                  canDelete.value ? (openBlock(), createElementBlock("th", _hoisted_19, "操作")) : createCommentVNode("", true)
                ])
              ]),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(rows.value, (row, idx) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id,
                    onClick: ($event) => openDetail(row.id),
                    style: { "cursor": "pointer" }
                  }, [
                    canEditOpinion.value || canDelete.value ? (openBlock(), createElementBlock("td", _hoisted_21, [
                      createBaseVNode("input", {
                        type: "checkbox",
                        class: "row-check",
                        checked: selectedIds.value.has(row.id),
                        onClick: withModifiers(($event) => toggleRow(row), ["stop"])
                      }, null, 8, _hoisted_22)
                    ])) : createCommentVNode("", true),
                    createBaseVNode("td", _hoisted_23, toDisplayString((page.value - 1) * size.value + idx + 1), 1),
                    createBaseVNode("td", _hoisted_24, [
                      createBaseVNode("span", _hoisted_25, toDisplayString(row.title), 1)
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.source), 1),
                    createBaseVNode("td", _hoisted_26, [
                      createBaseVNode("span", _hoisted_27, toDisplayString(contentTypeText(row.content_type)), 1)
                    ]),
                    createBaseVNode("td", _hoisted_28, [
                      createBaseVNode("span", {
                        class: normalizeClass(["score-chip", relevanceClass(row.relevance_score)])
                      }, toDisplayString(formatRelevance(row.relevance_score)), 3)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", _hoisted_29, toDisplayString(admissionSummary(row.admission_reason)), 1)
                    ]),
                    createBaseVNode("td", _hoisted_30, [
                      canEditOpinion.value ? (openBlock(), createBlock(_component_el_popover, {
                        key: 0,
                        trigger: "manual",
                        visible: popoverRowId.value === row.id,
                        placement: "bottom",
                        width: 132,
                        "popper-class": "sent-popper"
                      }, {
                        reference: withCtx(() => [
                          createBaseVNode("span", {
                            class: normalizeClass(["pill editable", unref(sentimentPill)(row.sentiment)]),
                            onClick: withModifiers(($event) => toggleSentPop(row), ["stop"])
                          }, [
                            _cache[32] || (_cache[32] = createBaseVNode("span", { class: "dot" }, null, -1)),
                            createTextVNode(toDisplayString(unref(sentimentText)(row.sentiment)), 1)
                          ], 10, _hoisted_31)
                        ]),
                        default: withCtx(() => [
                          createBaseVNode("div", _hoisted_32, [
                            (openBlock(), createElementBlock(Fragment, null, renderList(sentimentOptions, (opt) => {
                              return createBaseVNode("button", {
                                key: opt.value,
                                type: "button",
                                class: normalizeClass(["sent-opt", [unref(sentimentPill)(opt.value), { active: row.sentiment === opt.value }]]),
                                onClick: withModifiers(($event) => chooseSentiment(row, opt.value), ["stop"])
                              }, toDisplayString(opt.label), 11, _hoisted_33);
                            }), 64))
                          ])
                        ]),
                        _: 2
                      }, 1032, ["visible"])) : (openBlock(), createElementBlock("span", {
                        key: 1,
                        class: normalizeClass(["pill", unref(sentimentPill)(row.sentiment)])
                      }, [
                        _cache[33] || (_cache[33] = createBaseVNode("span", { class: "dot" }, null, -1)),
                        createTextVNode(toDisplayString(unref(sentimentText)(row.sentiment)), 1)
                      ], 2))
                    ]),
                    createBaseVNode("td", _hoisted_34, [
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(levelPill)(row.risk_score)])
                      }, toDisplayString(unref(levelText)(row.risk_score)), 3)
                    ]),
                    createBaseVNode("td", _hoisted_35, [
                      createBaseVNode("span", {
                        class: "risk-num",
                        style: normalizeStyle({ color: unref(riskColor)(row.risk_score) })
                      }, toDisplayString(row.risk_score), 5)
                    ]),
                    createBaseVNode("td", _hoisted_36, [
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(statusPill)(row.analysis_status)])
                      }, toDisplayString(unref(statusText)(row.analysis_status)), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(unref(formatTime)(row.publish_time)), 1),
                    canDelete.value ? (openBlock(), createElementBlock("td", _hoisted_37, [
                      createBaseVNode("button", {
                        class: "op-del",
                        onClick: withModifiers(($event) => deleteOne(row), ["stop"])
                      }, "删除", 8, _hoisted_38)
                    ])) : createCommentVNode("", true)
                  ], 8, _hoisted_20);
                }), 128)),
                rows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_39, [
                  createBaseVNode("td", {
                    colspan: colCount.value,
                    class: "empty-row"
                  }, "暂无舆情数据", 8, _hoisted_40)
                ])) : createCommentVNode("", true)
              ])
            ])
          ]),
          total.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_41, [
            createVNode(_component_Pager, {
              total: total.value,
              "current-page": page.value,
              "onUpdate:currentPage": _cache[10] || (_cache[10] = ($event) => page.value = $event),
              "page-size": size.value,
              onCurrentChange: onPageChange
            }, null, 8, ["total", "current-page", "page-size"])
          ])) : createCommentVNode("", true)
        ]),
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Opinions = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-a611f3be"]]);

export { Opinions as default };
