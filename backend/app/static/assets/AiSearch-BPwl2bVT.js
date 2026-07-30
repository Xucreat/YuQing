import { H as defineStore, f as reactive, r as ref, m as watch, d as defineComponent, I as storeToRefs, p as onMounted, c as createElementBlock, a as createBaseVNode, B as createVNode, z as withCtx, J as withModifiers, x as unref, t as toDisplayString, y as createBlock, A as createCommentVNode, w as withDirectives, F as Fragment, i as renderList, K as isRef, L as BochaDetailModal, j as computed, g as api, E as ElMessage, C as resolveComponent, D as resolveDirective, o as openBlock, b as withKeys, e as createTextVNode, _ as _export_sfc } from './index-Bpp_HAZ2.js';

const STORAGE_KEY = "bocha_search_state_v1";
function loadStoredState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}
const useBochaSearchStore = defineStore("bocha-search", () => {
  const stored = loadStoredState();
  const form = reactive({
    query: stored.form?.query || "",
    freshness: stored.form?.freshness || "",
    summary: stored.form?.summary ?? true,
    count: Math.min(Math.max(Number(stored.form?.count || 8), 1), 100)
  });
  const activeSession = ref(stored.activeSession || null);
  const results = ref(stored.results || []);
  const savedIndexes = ref(new Set(stored.savedIndexes || []));
  const selectedIndexes = ref(new Set(stored.selectedIndexes || []));
  const resultPage = ref(Math.max(Number(stored.resultPage || 1), 1));
  function resetSearchResults() {
    activeSession.value = null;
    results.value = [];
    savedIndexes.value = /* @__PURE__ */ new Set();
    selectedIndexes.value = /* @__PURE__ */ new Set();
    resultPage.value = 1;
  }
  function setSearchResult(session, items) {
    activeSession.value = session;
    results.value = items;
    savedIndexes.value = /* @__PURE__ */ new Set();
    selectedIndexes.value = /* @__PURE__ */ new Set();
    resultPage.value = 1;
  }
  function markSaved(index) {
    savedIndexes.value = new Set(savedIndexes.value).add(index);
    selectedIndexes.value = new Set([...selectedIndexes.value].filter((i) => i !== index));
  }
  function setSelected(index, selected) {
    const next = new Set(selectedIndexes.value);
    if (selected) next.add(index);
    else next.delete(index);
    selectedIndexes.value = next;
  }
  function setSelectedIndexes(indexes) {
    selectedIndexes.value = new Set(indexes);
  }
  function clearSelected() {
    selectedIndexes.value = /* @__PURE__ */ new Set();
  }
  function setResultPage(page) {
    resultPage.value = Math.max(Number(page || 1), 1);
  }
  watch(
    () => ({
      form: { ...form },
      activeSession: activeSession.value,
      results: results.value,
      savedIndexes: [...savedIndexes.value],
      selectedIndexes: [...selectedIndexes.value],
      resultPage: resultPage.value
    }),
    (state) => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch {
      }
    },
    { deep: true }
  );
  return {
    form,
    activeSession,
    results,
    savedIndexes,
    selectedIndexes,
    resultPage,
    resetSearchResults,
    setSearchResult,
    markSaved,
    setSelected,
    setSelectedIndexes,
    clearSelected,
    setResultPage
  };
});

const _hoisted_1 = { class: "ai-search-page" };
const _hoisted_2 = { class: "search-panel" };
const _hoisted_3 = { class: "content-grid" };
const _hoisted_4 = { class: "results-column" };
const _hoisted_5 = { class: "section-head" };
const _hoisted_6 = { key: 0 };
const _hoisted_7 = { key: 1 };
const _hoisted_8 = {
  key: 0,
  class: "bulk-toolbar"
};
const _hoisted_9 = { class: "bulk-count" };
const _hoisted_10 = { class: "result-list" };
const _hoisted_11 = { class: "result-main" };
const _hoisted_12 = { class: "result-title-row" };
const _hoisted_13 = ["onClick"];
const _hoisted_14 = { class: "result-meta" };
const _hoisted_15 = { key: 0 };
const _hoisted_16 = { class: "result-text" };
const _hoisted_17 = ["href"];
const _hoisted_18 = {
  key: 1,
  class: "result-pagination"
};
const _hoisted_19 = { class: "side-column" };
const _hoisted_20 = { class: "side-panel" };
const _hoisted_21 = { class: "section-head compact" };
const _hoisted_22 = { class: "mini-list history-list" };
const _hoisted_23 = { class: "mini-title" };
const _hoisted_24 = { class: "mini-meta" };
const _hoisted_25 = { class: "side-panel" };
const _hoisted_26 = { class: "section-head compact" };
const _hoisted_27 = { class: "mini-list" };
const _hoisted_28 = { class: "mini-title" };
const _hoisted_29 = { class: "mini-meta" };
const resultPageSize = 10;
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "AiSearch",
  setup(__props) {
    const bochaStore = useBochaSearchStore();
    const form = bochaStore.form;
    const searching = ref(false);
    const sessionsLoading = ref(false);
    const leadsLoading = ref(false);
    const savingIndex = ref(null);
    const bulkSaving = ref(false);
    const detailVisible = ref(false);
    const detailItem = ref(null);
    const { activeSession, results, savedIndexes, selectedIndexes, resultPage } = storeToRefs(bochaStore);
    const sessions = ref([]);
    const leads = ref([]);
    const pagedResults = computed(() => {
      const start = (resultPage.value - 1) * resultPageSize;
      return results.value.slice(start, start + resultPageSize);
    });
    const selectableResults = computed(
      () => results.value.filter((item) => !savedIndexes.value.has(item.result_index))
    );
    const selectedCount = computed(
      () => [...selectedIndexes.value].filter(
        (index) => selectableResults.value.some((item) => item.result_index === index)
      ).length
    );
    const allSelectableSelected = computed(
      () => selectableResults.value.length > 0 && selectableResults.value.every((item) => selectedIndexes.value.has(item.result_index))
    );
    const isSelectionIndeterminate = computed(
      () => selectedCount.value > 0 && !allSelectableSelected.value
    );
    async function handleSearch() {
      const query = form.query.trim();
      if (!query) {
        ElMessage.warning("请输入检索关键词");
        return;
      }
      searching.value = true;
      try {
        const payload = {
          query,
          summary: form.summary,
          count: form.count
        };
        if (form.freshness) payload.freshness = form.freshness;
        const { data } = await api.post("/bocha/search", payload);
        bochaStore.setSearchResult(data.session, data.items || []);
        ElMessage.success(`检索完成，返回 ${data.total} 条结果`);
        await loadSessions();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "检索失败");
      } finally {
        searching.value = false;
      }
    }
    async function persistLead(item, showMessage = true) {
      if (!activeSession.value) return false;
      savingIndex.value = item.result_index;
      try {
        const { data } = await api.post("/bocha/leads", {
          session_id: activeSession.value.id,
          result_index: item.result_index
        });
        bochaStore.markSaved(item.result_index);
        if (showMessage) {
          ElMessage.success(data.status === "new" ? "已保存为线索" : "线索已存在");
        }
        window.dispatchEvent(new CustomEvent("bocha-leads-refresh"));
        return true;
      } catch (err) {
        if (showMessage) {
          ElMessage.error(err?.response?.data?.detail || "保存线索失败");
        }
        return false;
      } finally {
        savingIndex.value = null;
      }
    }
    async function saveLead(item) {
      const ok = await persistLead(item);
      if (ok) await loadLeads();
    }
    async function saveSelectedLeads() {
      if (!activeSession.value || bulkSaving.value) return;
      const items = selectableResults.value.filter((item) => selectedIndexes.value.has(item.result_index));
      if (!items.length) return;
      bulkSaving.value = true;
      let success = 0;
      let failed = 0;
      try {
        for (const item of items) {
          const ok = await persistLead(item, false);
          if (ok) success += 1;
          else failed += 1;
        }
        if (success > 0) {
          ElMessage.success(`已保存 ${success} 条线索${failed ? `，${failed} 条失败` : ""}`);
          await loadLeads();
        } else {
          ElMessage.error("批量保存线索失败");
        }
      } finally {
        bulkSaving.value = false;
      }
    }
    function toggleSelect(item, checked) {
      if (savedIndexes.value.has(item.result_index)) return;
      bochaStore.setSelected(item.result_index, checked);
    }
    function toggleSelectAll(checked) {
      if (checked) {
        bochaStore.setSelectedIndexes(selectableResults.value.map((item) => item.result_index));
      } else {
        bochaStore.clearSelected();
      }
    }
    function openResultDetail(item) {
      detailItem.value = item;
      detailVisible.value = true;
    }
    async function loadSessions() {
      sessionsLoading.value = true;
      try {
        const createdFrom = new Date(Date.now() - 3 * 24 * 60 * 60 * 1e3).toISOString();
        const { data } = await api.get("/bocha/sessions", {
          params: { page: 1, size: 50, created_from: createdFrom }
        });
        const cutoff = Date.now() - 3 * 24 * 60 * 60 * 1e3;
        sessions.value = (data.items || []).filter((item) => new Date(item.created_at).getTime() >= cutoff);
      } catch {
        ElMessage.error("搜索历史加载失败");
      } finally {
        sessionsLoading.value = false;
      }
    }
    async function loadLeads() {
      leadsLoading.value = true;
      try {
        const { data } = await api.get("/bocha/leads", {
          params: { page: 1, size: 8 }
        });
        leads.value = data.items || [];
      } catch {
        ElMessage.error("我的线索加载失败");
      } finally {
        leadsLoading.value = false;
      }
    }
    function formatTime(value) {
      if (!value) return "-";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit"
      });
    }
    function statusText(status) {
      const map = {
        new: "待确认",
        confirmed: "已确认",
        rejected: "已驳回",
        promoted: "已晋级"
      };
      return map[status] || status;
    }
    function statusType(status) {
      if (status === "confirmed") return "success";
      if (status === "rejected") return "danger";
      if (status === "promoted") return "warning";
      return "info";
    }
    onMounted(() => {
      loadSessions();
      loadLeads();
    });
    watch(
      () => results.value.length,
      (total) => {
        const maxPage = Math.max(1, Math.ceil(total / resultPageSize));
        if (resultPage.value > maxPage) bochaStore.setResultPage(maxPage);
      },
      { immediate: true }
    );
    return (_ctx, _cache) => {
      const _component_el_input = resolveComponent("el-input");
      const _component_el_form_item = resolveComponent("el-form-item");
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_input_number = resolveComponent("el-input-number");
      const _component_el_switch = resolveComponent("el-switch");
      const _component_el_button = resolveComponent("el-button");
      const _component_el_form = resolveComponent("el-form");
      const _component_el_tag = resolveComponent("el-tag");
      const _component_el_checkbox = resolveComponent("el-checkbox");
      const _component_el_empty = resolveComponent("el-empty");
      const _component_el_pagination = resolveComponent("el-pagination");
      const _directive_loading = resolveDirective("loading");
      return openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("section", _hoisted_2, [
          createVNode(_component_el_form, {
            class: "search-form",
            model: unref(form),
            "label-position": "top",
            onSubmit: withModifiers(handleSearch, ["prevent"])
          }, {
            default: withCtx(() => [
              createVNode(_component_el_form_item, {
                label: "检索关键词",
                class: "keyword-field"
              }, {
                default: withCtx(() => [
                  createVNode(_component_el_input, {
                    modelValue: unref(form).query,
                    "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => unref(form).query = $event),
                    size: "large",
                    clearable: "",
                    maxlength: "512",
                    placeholder: "输入企业、事件、地点或风险关键词",
                    onKeyup: withKeys(handleSearch, ["enter"])
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "时间范围" }, {
                default: withCtx(() => [
                  createVNode(_component_el_select, {
                    modelValue: unref(form).freshness,
                    "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => unref(form).freshness = $event),
                    size: "large"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_option, {
                        label: "不限时间",
                        value: ""
                      }),
                      createVNode(_component_el_option, {
                        label: "最近一天",
                        value: "oneDay"
                      }),
                      createVNode(_component_el_option, {
                        label: "最近一周",
                        value: "oneWeek"
                      }),
                      createVNode(_component_el_option, {
                        label: "最近一月",
                        value: "oneMonth"
                      }),
                      createVNode(_component_el_option, {
                        label: "最近一年",
                        value: "oneYear"
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "返回数量" }, {
                default: withCtx(() => [
                  createVNode(_component_el_input_number, {
                    modelValue: unref(form).count,
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => unref(form).count = $event),
                    size: "large",
                    min: 1,
                    max: 100,
                    "controls-position": "right"
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "摘要" }, {
                default: withCtx(() => [
                  createVNode(_component_el_switch, {
                    modelValue: unref(form).summary,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => unref(form).summary = $event),
                    "active-text": "开启",
                    "inactive-text": "关闭"
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_button, {
                class: "search-button",
                type: "primary",
                size: "large",
                loading: searching.value,
                onClick: handleSearch
              }, {
                default: withCtx(() => [..._cache[6] || (_cache[6] = [
                  createTextVNode(" 检索 ", -1)
                ])]),
                _: 1
              }, 8, ["loading"])
            ]),
            _: 1
          }, 8, ["model"])
        ]),
        createBaseVNode("section", _hoisted_3, [
          createBaseVNode("div", _hoisted_4, [
            createBaseVNode("div", _hoisted_5, [
              createBaseVNode("div", null, [
                _cache[7] || (_cache[7] = createBaseVNode("h2", null, "搜索结果", -1)),
                unref(activeSession) ? (openBlock(), createElementBlock("p", _hoisted_6, "本次检索返回 " + toDisplayString(unref(results).length) + " 条结果", 1)) : (openBlock(), createElementBlock("p", _hoisted_7, "输入关键词后开始一次主动检索"))
              ]),
              unref(activeSession) ? (openBlock(), createBlock(_component_el_tag, {
                key: 0,
                effect: "plain",
                type: "info"
              }, {
                default: withCtx(() => [
                  createTextVNode("Session #" + toDisplayString(unref(activeSession).id), 1)
                ]),
                _: 1
              })) : createCommentVNode("", true)
            ]),
            unref(results).length ? (openBlock(), createElementBlock("div", _hoisted_8, [
              createVNode(_component_el_checkbox, {
                "model-value": allSelectableSelected.value,
                indeterminate: isSelectionIndeterminate.value,
                disabled: !selectableResults.value.length || bulkSaving.value,
                onChange: toggleSelectAll
              }, {
                default: withCtx(() => [..._cache[8] || (_cache[8] = [
                  createTextVNode(" 全选可保存结果 ", -1)
                ])]),
                _: 1
              }, 8, ["model-value", "indeterminate", "disabled"]),
              createBaseVNode("span", _hoisted_9, "已选择 " + toDisplayString(selectedCount.value) + " 条", 1),
              createVNode(_component_el_button, {
                type: "primary",
                plain: "",
                loading: bulkSaving.value,
                disabled: !selectedCount.value,
                onClick: saveSelectedLeads
              }, {
                default: withCtx(() => [..._cache[9] || (_cache[9] = [
                  createTextVNode(" 一键保存为线索 ", -1)
                ])]),
                _: 1
              }, 8, ["loading", "disabled"])
            ])) : createCommentVNode("", true),
            withDirectives((openBlock(), createElementBlock("div", _hoisted_10, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(pagedResults.value, (item) => {
                return openBlock(), createElementBlock("article", {
                  key: item.result_index,
                  class: "result-item"
                }, [
                  createVNode(_component_el_checkbox, {
                    class: "result-check",
                    "model-value": unref(selectedIndexes).has(item.result_index),
                    disabled: unref(savedIndexes).has(item.result_index) || bulkSaving.value,
                    onChange: (checked) => toggleSelect(item, Boolean(checked))
                  }, null, 8, ["model-value", "disabled", "onChange"]),
                  createBaseVNode("div", _hoisted_11, [
                    createBaseVNode("div", _hoisted_12, [
                      createBaseVNode("button", {
                        class: "result-title result-title-button",
                        type: "button",
                        onClick: ($event) => openResultDetail(item)
                      }, toDisplayString(item.title || item.url), 9, _hoisted_13),
                      unref(savedIndexes).has(item.result_index) ? (openBlock(), createBlock(_component_el_tag, {
                        key: 0,
                        type: "success",
                        effect: "light"
                      }, {
                        default: withCtx(() => [..._cache[10] || (_cache[10] = [
                          createTextVNode("已保存", -1)
                        ])]),
                        _: 1
                      })) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("div", _hoisted_14, [
                      createBaseVNode("span", null, toDisplayString(item.source_name || "未知来源"), 1),
                      item.publish_time ? (openBlock(), createElementBlock("span", _hoisted_15, toDisplayString(formatTime(item.publish_time)), 1)) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("p", _hoisted_16, toDisplayString(item.summary || item.snippet || "暂无摘要"), 1),
                    createBaseVNode("a", {
                      class: "source-link",
                      href: item.url,
                      target: "_blank",
                      rel: "noopener noreferrer"
                    }, toDisplayString(item.url), 9, _hoisted_17)
                  ]),
                  createVNode(_component_el_button, {
                    class: "save-lead-button",
                    type: "primary",
                    plain: "",
                    disabled: !unref(activeSession) || unref(savedIndexes).has(item.result_index),
                    loading: savingIndex.value === item.result_index,
                    onClick: ($event) => saveLead(item)
                  }, {
                    default: withCtx(() => [..._cache[11] || (_cache[11] = [
                      createTextVNode(" 保存为线索 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["disabled", "loading", "onClick"])
                ]);
              }), 128)),
              !unref(results).length && !searching.value ? (openBlock(), createBlock(_component_el_empty, {
                key: 0,
                description: "暂无搜索结果"
              })) : createCommentVNode("", true)
            ])), [
              [_directive_loading, searching.value]
            ]),
            unref(results).length > resultPageSize ? (openBlock(), createElementBlock("div", _hoisted_18, [
              createVNode(_component_el_pagination, {
                "current-page": unref(resultPage),
                "onUpdate:currentPage": _cache[4] || (_cache[4] = ($event) => isRef(resultPage) ? resultPage.value = $event : null),
                background: "",
                layout: "prev, pager, next",
                "page-size": resultPageSize,
                total: unref(results).length
              }, null, 8, ["current-page", "total"])
            ])) : createCommentVNode("", true)
          ]),
          createBaseVNode("aside", _hoisted_19, [
            createBaseVNode("section", _hoisted_20, [
              createBaseVNode("div", _hoisted_21, [
                _cache[13] || (_cache[13] = createBaseVNode("div", null, [
                  createBaseVNode("h2", null, "搜索历史"),
                  createBaseVNode("p", null, "仅展示三天内的主动检索记录")
                ], -1)),
                createVNode(_component_el_button, {
                  text: "",
                  type: "primary",
                  loading: sessionsLoading.value,
                  onClick: loadSessions
                }, {
                  default: withCtx(() => [..._cache[12] || (_cache[12] = [
                    createTextVNode("刷新", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])
              ]),
              withDirectives((openBlock(), createElementBlock("div", _hoisted_22, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(sessions.value, (session) => {
                  return openBlock(), createElementBlock("div", {
                    key: session.id,
                    class: "mini-item"
                  }, [
                    createBaseVNode("div", _hoisted_23, toDisplayString(session.query), 1),
                    createBaseVNode("div", _hoisted_24, [
                      createBaseVNode("span", null, toDisplayString(formatTime(session.created_at)), 1),
                      createBaseVNode("span", null, toDisplayString(session.result_count) + " 条", 1)
                    ])
                  ]);
                }), 128)),
                !sessions.value.length && !sessionsLoading.value ? (openBlock(), createBlock(_component_el_empty, {
                  key: 0,
                  description: "暂无历史",
                  "image-size": 72
                })) : createCommentVNode("", true)
              ])), [
                [_directive_loading, sessionsLoading.value]
              ])
            ]),
            createBaseVNode("section", _hoisted_25, [
              createBaseVNode("div", _hoisted_26, [
                _cache[15] || (_cache[15] = createBaseVNode("div", null, [
                  createBaseVNode("h2", null, "我的线索"),
                  createBaseVNode("p", null, "已保存，等待管理员确认")
                ], -1)),
                createVNode(_component_el_button, {
                  text: "",
                  type: "primary",
                  loading: leadsLoading.value,
                  onClick: loadLeads
                }, {
                  default: withCtx(() => [..._cache[14] || (_cache[14] = [
                    createTextVNode("刷新", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])
              ]),
              withDirectives((openBlock(), createElementBlock("div", _hoisted_27, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(leads.value, (lead) => {
                  return openBlock(), createElementBlock("div", {
                    key: lead.id,
                    class: "mini-item"
                  }, [
                    createBaseVNode("div", _hoisted_28, toDisplayString(lead.title || lead.url), 1),
                    createBaseVNode("div", _hoisted_29, [
                      createVNode(_component_el_tag, {
                        size: "small",
                        type: statusType(lead.status),
                        effect: "light"
                      }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(statusText(lead.status)), 1)
                        ]),
                        _: 2
                      }, 1032, ["type"]),
                      createBaseVNode("span", null, toDisplayString(formatTime(lead.created_at)), 1)
                    ])
                  ]);
                }), 128)),
                !leads.value.length && !leadsLoading.value ? (openBlock(), createBlock(_component_el_empty, {
                  key: 0,
                  description: "暂无线索",
                  "image-size": 72
                })) : createCommentVNode("", true)
              ])), [
                [_directive_loading, leadsLoading.value]
              ])
            ])
          ])
        ]),
        createVNode(BochaDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => detailVisible.value = $event),
          item: detailItem.value,
          query: unref(activeSession)?.query || unref(form).query
        }, null, 8, ["modelValue", "item", "query"])
      ]);
    };
  }
});

const AiSearch = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-9c77e6fc"]]);

export { AiSearch as default };
