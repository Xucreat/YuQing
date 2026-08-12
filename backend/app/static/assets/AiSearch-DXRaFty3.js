import { R as defineStore, f as reactive, r as ref, A as watch, d as defineComponent, S as storeToRefs, C as onMounted, y as resolveComponent, B as resolveDirective, o as openBlock, c as createElementBlock, a as createBaseVNode, m as createVNode, p as withCtx, b as withKeys, H as unref, e as createTextVNode, L as withModifiers, t as toDisplayString, q as createBlock, s as createCommentVNode, w as withDirectives, F as Fragment, i as renderList, T as isRef, U as BochaDetailModal, j as computed, E as ElMessage, g as api, _ as _export_sfc, n as normalizeClass, N as useRoute, h as useRouter } from './index-CmcgaaTj.js';

const STORAGE_KEY$2 = "bocha_search_state_v1";
function loadStoredState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY$2);
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
        localStorage.setItem(STORAGE_KEY$2, JSON.stringify(state));
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

const _hoisted_1$3 = { class: "ai-search-page" };
const _hoisted_2$3 = { class: "search-panel" };
const _hoisted_3$3 = { class: "content-grid" };
const _hoisted_4$3 = { class: "results-column" };
const _hoisted_5$2 = { class: "section-head" };
const _hoisted_6$2 = { key: 0 };
const _hoisted_7$2 = { key: 1 };
const _hoisted_8$2 = {
  key: 0,
  class: "bulk-toolbar"
};
const _hoisted_9$2 = { class: "bulk-count" };
const _hoisted_10$2 = { class: "result-list" };
const _hoisted_11$2 = { class: "result-main" };
const _hoisted_12$2 = { class: "result-title-row" };
const _hoisted_13$2 = ["onClick"];
const _hoisted_14$2 = { class: "result-meta" };
const _hoisted_15$2 = { key: 0 };
const _hoisted_16$2 = { class: "result-text" };
const _hoisted_17$2 = ["href"];
const _hoisted_18$2 = {
  key: 1,
  class: "result-pagination"
};
const _hoisted_19$2 = { class: "side-column" };
const _hoisted_20$2 = { class: "side-panel" };
const _hoisted_21$2 = { class: "section-head compact" };
const _hoisted_22$2 = { class: "mini-list history-list" };
const _hoisted_23$2 = { class: "mini-title" };
const _hoisted_24$2 = { class: "mini-meta" };
const _hoisted_25$2 = { class: "side-panel" };
const _hoisted_26$2 = { class: "section-head compact" };
const _hoisted_27$2 = { class: "mini-list history-list" };
const _hoisted_28$2 = { class: "mini-title" };
const _hoisted_29$2 = { class: "mini-meta" };
const resultPageSize$1 = 10;
const _sfc_main$3 = /* @__PURE__ */ defineComponent({
  __name: "WebSearch",
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
      const start = (resultPage.value - 1) * resultPageSize$1;
      return results.value.slice(start, start + resultPageSize$1);
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
        const maxPage = Math.max(1, Math.ceil(total / resultPageSize$1));
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
      const _component_Pager = resolveComponent("Pager");
      const _directive_loading = resolveDirective("loading");
      return openBlock(), createElementBlock("div", _hoisted_1$3, [
        createBaseVNode("section", _hoisted_2$3, [
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
        createBaseVNode("section", _hoisted_3$3, [
          createBaseVNode("div", _hoisted_4$3, [
            createBaseVNode("div", _hoisted_5$2, [
              createBaseVNode("div", null, [
                _cache[7] || (_cache[7] = createBaseVNode("h2", null, "搜索结果", -1)),
                unref(activeSession) ? (openBlock(), createElementBlock("p", _hoisted_6$2, "本次检索返回 " + toDisplayString(unref(results).length) + " 条结果", 1)) : (openBlock(), createElementBlock("p", _hoisted_7$2, "输入关键词后开始一次主动检索"))
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
            unref(results).length ? (openBlock(), createElementBlock("div", _hoisted_8$2, [
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
              createBaseVNode("span", _hoisted_9$2, "已选择 " + toDisplayString(selectedCount.value) + " 条", 1),
              createVNode(_component_el_button, {
                class: "save-lead-button",
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
            withDirectives((openBlock(), createElementBlock("div", _hoisted_10$2, [
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
                  createBaseVNode("div", _hoisted_11$2, [
                    createBaseVNode("div", _hoisted_12$2, [
                      createBaseVNode("button", {
                        class: "result-title result-title-button",
                        type: "button",
                        onClick: ($event) => openResultDetail(item)
                      }, toDisplayString(item.title || item.url), 9, _hoisted_13$2),
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
                    createBaseVNode("div", _hoisted_14$2, [
                      createBaseVNode("span", null, toDisplayString(item.source_name || "未知来源"), 1),
                      item.publish_time ? (openBlock(), createElementBlock("span", _hoisted_15$2, toDisplayString(formatTime(item.publish_time)), 1)) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("p", _hoisted_16$2, toDisplayString(item.summary || item.snippet || "暂无摘要"), 1),
                    createBaseVNode("a", {
                      class: "source-link",
                      href: item.url,
                      target: "_blank",
                      rel: "noopener noreferrer"
                    }, toDisplayString(item.url), 9, _hoisted_17$2)
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
            unref(results).length > resultPageSize$1 ? (openBlock(), createElementBlock("div", _hoisted_18$2, [
              createVNode(_component_Pager, {
                "current-page": unref(resultPage),
                "onUpdate:currentPage": _cache[4] || (_cache[4] = ($event) => isRef(resultPage) ? resultPage.value = $event : null),
                "page-size": resultPageSize$1,
                total: unref(results).length
              }, null, 8, ["current-page", "total"])
            ])) : createCommentVNode("", true)
          ]),
          createBaseVNode("aside", _hoisted_19$2, [
            createBaseVNode("section", _hoisted_20$2, [
              createBaseVNode("div", _hoisted_21$2, [
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
              withDirectives((openBlock(), createElementBlock("div", _hoisted_22$2, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(sessions.value, (session) => {
                  return openBlock(), createElementBlock("div", {
                    key: session.id,
                    class: "mini-item"
                  }, [
                    createBaseVNode("div", _hoisted_23$2, toDisplayString(session.query), 1),
                    createBaseVNode("div", _hoisted_24$2, [
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
            createBaseVNode("section", _hoisted_25$2, [
              createBaseVNode("div", _hoisted_26$2, [
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
              withDirectives((openBlock(), createElementBlock("div", _hoisted_27$2, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(leads.value, (lead) => {
                  return openBlock(), createElementBlock("div", {
                    key: lead.id,
                    class: "mini-item"
                  }, [
                    createBaseVNode("div", _hoisted_28$2, toDisplayString(lead.title || lead.url), 1),
                    createBaseVNode("div", _hoisted_29$2, [
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

const WebSearch = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-30d39df3"]]);

const STORAGE_KEY$1 = "bocha_ai_search_state_v1";
function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY$1);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}
const useBochaAiSearchStore = defineStore("bocha-ai-search", () => {
  const saved = loadState();
  const form = reactive({
    query: saved.form?.query || "",
    freshness: saved.form?.freshness || "noLimit",
    count: Math.min(Math.max(Number(saved.form?.count || 10), 1), 50),
    answer: saved.form?.answer ?? true,
    source: saved.form?.source || "all",
    customInclude: saved.form?.customInclude || ""
  });
  const session = ref(saved.session || null);
  const pages = ref(saved.pages || []);
  const images = ref(saved.images || []);
  const modalCards = ref(saved.modalCards || []);
  const followUpQuestions = ref(saved.followUpQuestions || []);
  const savedIndexes = ref(/* @__PURE__ */ new Set());
  function setResult(nextSession, nextPages, nextImages, nextCards, nextQuestions) {
    session.value = nextSession;
    pages.value = nextPages.map((item, index) => ({ ...item, result_index: item.result_index ?? index }));
    images.value = nextImages || [];
    modalCards.value = nextCards || [];
    followUpQuestions.value = nextQuestions || [];
    savedIndexes.value = /* @__PURE__ */ new Set();
  }
  function markSaved(index) {
    savedIndexes.value = new Set(savedIndexes.value).add(index);
  }
  watch(
    () => ({ form: { ...form }, session: session.value, pages: pages.value, images: images.value, modalCards: modalCards.value, followUpQuestions: followUpQuestions.value }),
    (value) => {
      try {
        localStorage.setItem(STORAGE_KEY$1, JSON.stringify(value));
      } catch {
      }
    },
    { deep: true }
  );
  return { form, session, pages, images, modalCards, followUpQuestions, savedIndexes, setResult, markSaved };
});

const _hoisted_1$2 = { class: "ai-search-page" };
const _hoisted_2$2 = { class: "search-panel" };
const _hoisted_3$2 = { class: "ai-content" };
const _hoisted_4$2 = { class: "main-column" };
const _hoisted_5$1 = {
  key: 0,
  class: "result-section answer-section"
};
const _hoisted_6$1 = { class: "section-head" };
const _hoisted_7$1 = { key: 0 };
const _hoisted_8$1 = {
  key: 0,
  class: "answer-text"
};
const _hoisted_9$1 = { class: "result-section" };
const _hoisted_10$1 = { class: "section-head" };
const _hoisted_11$1 = {
  key: 0,
  class: "page-list"
};
const _hoisted_12$1 = { class: "page-main" };
const _hoisted_13$1 = { class: "page-title-row" };
const _hoisted_14$1 = ["href"];
const _hoisted_15$1 = { class: "page-meta" };
const _hoisted_16$1 = { key: 0 };
const _hoisted_17$1 = { class: "page-snippet" };
const _hoisted_18$1 = ["href"];
const _hoisted_19$1 = {
  key: 1,
  class: "result-section"
};
const _hoisted_20$1 = { class: "section-head" };
const _hoisted_21$1 = { class: "question-list" };
const _hoisted_22$1 = ["onClick"];
const _hoisted_23$1 = { class: "side-column" };
const _hoisted_24$1 = { class: "result-section" };
const _hoisted_25$1 = { class: "section-head" };
const _hoisted_26$1 = {
  key: 0,
  class: "image-list"
};
const _hoisted_27$1 = ["href"];
const _hoisted_28$1 = ["src", "alt"];
const _hoisted_29$1 = { class: "result-section" };
const _hoisted_30$1 = { class: "section-head" };
const _hoisted_31$1 = {
  key: 0,
  class: "modal-list"
};
const _hoisted_32$1 = {
  key: 1,
  class: "raw-section"
};
const _sfc_main$2 = /* @__PURE__ */ defineComponent({
  __name: "AiSearchPanel",
  setup(__props) {
    const store = useBochaAiSearchStore();
    const { form, session, pages, images, modalCards, followUpQuestions, savedIndexes } = storeToRefs(store);
    const searching = ref(false);
    const savingIndex = ref(null);
    const errorMessage = ref("");
    const rawResponse = ref({});
    const answer = computed(() => session.value?.answer || "");
    const platformIncludes = ref({ weibo: "", xiaohongshu: "" });
    onMounted(async () => {
      try {
        const { data } = await api.get("/bocha/ai-search/options");
        if (data.platform_includes) platformIncludes.value = { ...platformIncludes.value, ...data.platform_includes };
      } catch {
      }
    });
    function buildInclude() {
      if (form.value.source === "weibo") return platformIncludes.value.weibo || "__missing__";
      if (form.value.source === "xiaohongshu") return platformIncludes.value.xiaohongshu || "__missing__";
      if (form.value.source === "custom") return form.value.customInclude.trim();
      return void 0;
    }
    async function search() {
      const query = form.value.query.trim();
      const include = buildInclude();
      if ((form.value.source === "weibo" || form.value.source === "xiaohongshu") && include === "__missing__") return;
      if (!query) {
        ElMessage.warning("请输入查询关键词");
        return;
      }
      if (form.value.source === "custom" && !buildInclude()) {
        ElMessage.warning("请输入自定义域名");
        return;
      }
      searching.value = true;
      errorMessage.value = "";
      try {
        const { data } = await api.post("/bocha/ai-search", {
          query,
          freshness: form.value.freshness,
          include: include === "__missing__" ? void 0 : include,
          count: Math.min(Math.max(form.value.count, 1), 50),
          answer: form.value.answer,
          stream: false
        }, { timeout: 35e3 });
        store.setResult(data.session, data.web_pages || [], data.images || [], data.modal_cards || [], data.follow_up_questions || []);
        rawResponse.value = data.raw_response || {};
        ElMessage.success(`搜索完成，返回 ${data.total || 0} 条网页结果`);
      } catch (err) {
        if (err?.code === "ECONNABORTED" || err?.message?.toLowerCase().includes("timeout")) errorMessage.value = "AI Search 请求超时，请稍后重试";
        else errorMessage.value = err?.response?.data?.detail || "AI Search 暂时不可用，请稍后重试";
      } finally {
        searching.value = false;
      }
    }
    async function saveLead(item) {
      if (!session.value || item.result_index == null) return;
      savingIndex.value = item.result_index;
      try {
        await api.post("/bocha/ai-leads", { session_id: session.value.id, result_index: item.result_index });
        store.markSaved(item.result_index);
        ElMessage.success("已保存为 AI Search 线索");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "保存线索失败");
      } finally {
        savingIndex.value = null;
      }
    }
    function sourceTypeText(value) {
      return { weibo: "微博", xiaohongshu: "小红书", web: "网页" }[value] || value || "网页";
    }
    function formatTime(value) {
      if (!value) return "-";
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    }
    return (_ctx, _cache) => {
      const _component_el_input = resolveComponent("el-input");
      const _component_el_form_item = resolveComponent("el-form-item");
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_input_number = resolveComponent("el-input-number");
      const _component_el_switch = resolveComponent("el-switch");
      const _component_el_button = resolveComponent("el-button");
      const _component_el_form = resolveComponent("el-form");
      const _component_el_alert = resolveComponent("el-alert");
      const _component_el_empty = resolveComponent("el-empty");
      const _component_el_tag = resolveComponent("el-tag");
      const _directive_loading = resolveDirective("loading");
      return openBlock(), createElementBlock("div", _hoisted_1$2, [
        createBaseVNode("section", _hoisted_2$2, [
          createVNode(_component_el_form, {
            class: "search-form",
            model: unref(form),
            "label-position": "top",
            onSubmit: withModifiers(search, ["prevent"])
          }, {
            default: withCtx(() => [
              createVNode(_component_el_form_item, {
                label: "查询关键词",
                class: "keyword-field"
              }, {
                default: withCtx(() => [
                  createVNode(_component_el_input, {
                    modelValue: unref(form).query,
                    "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => unref(form).query = $event),
                    size: "large",
                    clearable: "",
                    maxlength: "512",
                    placeholder: "输入企业、事件、地点或风险关键词"
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
                        value: "noLimit"
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
                    max: 50,
                    "controls-position": "right"
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "来源范围" }, {
                default: withCtx(() => [
                  createVNode(_component_el_select, {
                    modelValue: unref(form).source,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => unref(form).source = $event),
                    size: "large"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_option, {
                        label: "全网",
                        value: "all"
                      }),
                      createVNode(_component_el_option, {
                        label: "微博",
                        value: "weibo"
                      }),
                      createVNode(_component_el_option, {
                        label: "小红书",
                        value: "xiaohongshu"
                      }),
                      createVNode(_component_el_option, {
                        label: "自定义域名",
                        value: "custom"
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                _: 1
              }),
              unref(form).source === "custom" ? (openBlock(), createBlock(_component_el_form_item, {
                key: 0,
                label: "自定义域名",
                class: "custom-field"
              }, {
                default: withCtx(() => [
                  createVNode(_component_el_input, {
                    modelValue: unref(form).customInclude,
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => unref(form).customInclude = $event),
                    size: "large",
                    placeholder: "example.com|news.example.com"
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              })) : createCommentVNode("", true),
              createVNode(_component_el_form_item, { label: "AI 总结" }, {
                default: withCtx(() => [
                  createVNode(_component_el_switch, {
                    modelValue: unref(form).answer,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => unref(form).answer = $event),
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
                onClick: search
              }, {
                default: withCtx(() => [..._cache[6] || (_cache[6] = [
                  createTextVNode("搜索", -1)
                ])]),
                _: 1
              }, 8, ["loading"])
            ]),
            _: 1
          }, 8, ["model"]),
          _cache[7] || (_cache[7] = createBaseVNode("p", { class: "source-notice" }, "include 只是搜索域名限制，不代表拥有微博或小红书官方数据权限；登录限制、反爬限制和未收录内容仍可能无法返回。", -1))
        ]),
        errorMessage.value ? (openBlock(), createBlock(_component_el_alert, {
          key: 0,
          class: "state-alert",
          type: "error",
          closable: false,
          title: errorMessage.value
        }, null, 8, ["title"])) : createCommentVNode("", true),
        withDirectives((openBlock(), createElementBlock("section", _hoisted_3$2, [
          createBaseVNode("div", _hoisted_4$2, [
            answer.value || unref(session) ? (openBlock(), createElementBlock("section", _hoisted_5$1, [
              createBaseVNode("div", _hoisted_6$1, [
                _cache[8] || (_cache[8] = createBaseVNode("h2", null, "AI 总结", -1)),
                unref(session) ? (openBlock(), createElementBlock("span", _hoisted_7$1, toDisplayString(unref(session).answer_enabled ? "已启用" : "未启用"), 1)) : createCommentVNode("", true)
              ]),
              answer.value ? (openBlock(), createElementBlock("p", _hoisted_8$1, toDisplayString(answer.value), 1)) : (openBlock(), createBlock(_component_el_empty, {
                key: 1,
                description: "本次搜索未返回 AI 总结",
                "image-size": 68
              }))
            ])) : createCommentVNode("", true),
            createBaseVNode("section", _hoisted_9$1, [
              createBaseVNode("div", _hoisted_10$1, [
                _cache[9] || (_cache[9] = createBaseVNode("h2", null, "参考网页", -1)),
                createBaseVNode("span", null, toDisplayString(unref(pages).length) + " 条", 1)
              ]),
              unref(pages).length ? (openBlock(), createElementBlock("div", _hoisted_11$1, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(unref(pages), (item) => {
                  return openBlock(), createElementBlock("article", {
                    key: item.result_index ?? item.url,
                    class: "page-item"
                  }, [
                    createBaseVNode("div", _hoisted_12$1, [
                      createBaseVNode("div", _hoisted_13$1, [
                        createBaseVNode("a", {
                          class: "page-title",
                          href: item.url,
                          target: "_blank",
                          rel: "noopener noreferrer"
                        }, toDisplayString(item.title || item.url), 9, _hoisted_14$1),
                        createVNode(_component_el_tag, {
                          size: "small",
                          effect: "plain"
                        }, {
                          default: withCtx(() => [
                            createTextVNode(toDisplayString(sourceTypeText(item.source_type)), 1)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      createBaseVNode("div", _hoisted_15$1, [
                        createBaseVNode("span", null, toDisplayString(item.source_domain || "未知来源"), 1),
                        item.publish_time ? (openBlock(), createElementBlock("span", _hoisted_16$1, toDisplayString(formatTime(item.publish_time)), 1)) : createCommentVNode("", true)
                      ]),
                      createBaseVNode("p", _hoisted_17$1, toDisplayString(item.snippet || "暂无摘要"), 1),
                      createBaseVNode("a", {
                        class: "citation-link",
                        href: item.citation_url || item.url,
                        target: "_blank",
                        rel: "noopener noreferrer"
                      }, "引用链接", 8, _hoisted_18$1)
                    ]),
                    createVNode(_component_el_button, {
                      type: "primary",
                      plain: "",
                      disabled: unref(savedIndexes).has(item.result_index ?? 0) || !unref(session),
                      loading: savingIndex.value === (item.result_index ?? 0),
                      onClick: ($event) => saveLead(item)
                    }, {
                      default: withCtx(() => [
                        createTextVNode(toDisplayString(unref(savedIndexes).has(item.result_index ?? 0) ? "已保存" : "保存为线索"), 1)
                      ]),
                      _: 2
                    }, 1032, ["disabled", "loading", "onClick"])
                  ]);
                }), 128))
              ])) : !searching.value ? (openBlock(), createBlock(_component_el_empty, {
                key: 1,
                description: "暂无参考网页",
                "image-size": 80
              })) : createCommentVNode("", true)
            ]),
            unref(followUpQuestions).length ? (openBlock(), createElementBlock("section", _hoisted_19$1, [
              createBaseVNode("div", _hoisted_20$1, [
                _cache[10] || (_cache[10] = createBaseVNode("h2", null, "追问问题", -1)),
                createBaseVNode("span", null, toDisplayString(unref(followUpQuestions).length) + " 条", 1)
              ]),
              createBaseVNode("div", _hoisted_21$1, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(unref(followUpQuestions), (question) => {
                  return openBlock(), createElementBlock("button", {
                    key: question,
                    type: "button",
                    onClick: ($event) => unref(form).query = question
                  }, toDisplayString(question), 9, _hoisted_22$1);
                }), 128))
              ])
            ])) : createCommentVNode("", true)
          ]),
          createBaseVNode("aside", _hoisted_23$1, [
            createBaseVNode("section", _hoisted_24$1, [
              createBaseVNode("div", _hoisted_25$1, [
                _cache[11] || (_cache[11] = createBaseVNode("h2", null, "图片结果", -1)),
                createBaseVNode("span", null, toDisplayString(unref(images).length) + " 条", 1)
              ]),
              unref(images).length ? (openBlock(), createElementBlock("div", _hoisted_26$1, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(unref(images), (image, index) => {
                  return openBlock(), createElementBlock("a", {
                    key: String(image.url || image.imageUrl || image.src || index),
                    href: image.url || image.imageUrl || image.src || "#",
                    target: "_blank",
                    rel: "noopener noreferrer",
                    class: "image-item"
                  }, [
                    image.url || image.imageUrl || image.src ? (openBlock(), createElementBlock("img", {
                      key: 0,
                      src: String(image.url || image.imageUrl || image.src),
                      alt: String(image.title || "搜索图片"),
                      loading: "lazy"
                    }, null, 8, _hoisted_28$1)) : createCommentVNode("", true),
                    createBaseVNode("span", null, toDisplayString(image.title || image.url || image.imageUrl || "查看图片"), 1)
                  ], 8, _hoisted_27$1);
                }), 128))
              ])) : !searching.value ? (openBlock(), createBlock(_component_el_empty, {
                key: 1,
                description: "暂无图片结果",
                "image-size": 64
              })) : createCommentVNode("", true)
            ]),
            createBaseVNode("section", _hoisted_29$1, [
              createBaseVNode("div", _hoisted_30$1, [
                _cache[12] || (_cache[12] = createBaseVNode("h2", null, "模态卡", -1)),
                createBaseVNode("span", null, toDisplayString(unref(modalCards).length) + " 条", 1)
              ]),
              unref(modalCards).length ? (openBlock(), createElementBlock("div", _hoisted_31$1, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(unref(modalCards), (card, index) => {
                  return openBlock(), createElementBlock("article", {
                    key: index,
                    class: "modal-item"
                  }, [
                    createBaseVNode("strong", null, toDisplayString(card.title || card.name || `卡片 ${index + 1}`), 1),
                    createBaseVNode("p", null, toDisplayString(card.description || card.content || card.text || JSON.stringify(card)), 1)
                  ]);
                }), 128))
              ])) : !searching.value ? (openBlock(), createBlock(_component_el_empty, {
                key: 1,
                description: "暂无模态卡",
                "image-size": 64
              })) : createCommentVNode("", true)
            ])
          ])
        ])), [
          [_directive_loading, searching.value]
        ]),
        unref(session) ? (openBlock(), createElementBlock("section", _hoisted_32$1, [
          createBaseVNode("details", null, [
            _cache[13] || (_cache[13] = createBaseVNode("summary", null, "查看原始 JSON", -1)),
            createBaseVNode("pre", null, toDisplayString(JSON.stringify(rawResponse.value, null, 2)), 1)
          ])
        ])) : createCommentVNode("", true)
      ]);
    };
  }
});

const AiSearchPanel = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-911e4000"]]);

const STORAGE_KEY = "anspire_search_state_v1";
const useAnspireSearchStore = defineStore("anspire-search", () => {
  let stored = {};
  try {
    stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
  }
  const form = reactive({ query: stored.form?.query || "", top_k: stored.form?.top_k || 10, insite: stored.form?.insite || "", from_time: stored.form?.from_time || "", to_time: stored.form?.to_time || "", region_mode: stored.form?.region_mode ?? 0 });
  const session = ref(stored.session || null);
  const results = ref(stored.results || []);
  const savedIndexes = ref(new Set(stored.savedIndexes || []));
  const selectedIndexes = ref(new Set(stored.selectedIndexes || []));
  const resultPage = ref(Math.max(Number(stored.resultPage || 1), 1));
  function setResult(nextSession, items) {
    session.value = nextSession;
    results.value = items;
    savedIndexes.value = /* @__PURE__ */ new Set();
    selectedIndexes.value = /* @__PURE__ */ new Set();
    resultPage.value = 1;
  }
  function markSaved(index) {
    savedIndexes.value = new Set(savedIndexes.value).add(index);
  }
  function setSelected(index, selected) {
    const next = new Set(selectedIndexes.value);
    selected ? next.add(index) : next.delete(index);
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
  watch(() => ({ form: { ...form }, session: session.value, results: results.value, savedIndexes: [...savedIndexes.value], selectedIndexes: [...selectedIndexes.value], resultPage: resultPage.value }), (state) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
    }
  }, { deep: true });
  return { form, session, results, savedIndexes, selectedIndexes, resultPage, setResult, markSaved, setSelected, setSelectedIndexes, clearSelected, setResultPage };
});

const _hoisted_1$1 = { class: "anspire-page" };
const _hoisted_2$1 = { class: "search-panel" };
const _hoisted_3$1 = { class: "content-grid" };
const _hoisted_4$1 = { class: "results-column" };
const _hoisted_5 = { class: "section-head" };
const _hoisted_6 = { key: 0 };
const _hoisted_7 = { key: 1 };
const _hoisted_8 = { class: "session-actions" };
const _hoisted_9 = {
  key: 0,
  class: "raw-json"
};
const _hoisted_10 = {
  key: 1,
  class: "bulk-toolbar"
};
const _hoisted_11 = { class: "bulk-count" };
const _hoisted_12 = { class: "result-list" };
const _hoisted_13 = { class: "result-main" };
const _hoisted_14 = { class: "result-title-row" };
const _hoisted_15 = ["onClick"];
const _hoisted_16 = { class: "result-meta" };
const _hoisted_17 = { key: 0 };
const _hoisted_18 = { key: 1 };
const _hoisted_19 = { class: "result-text" };
const _hoisted_20 = ["href"];
const _hoisted_21 = {
  key: 2,
  class: "result-pagination"
};
const _hoisted_22 = { class: "side-column" };
const _hoisted_23 = { class: "side-panel" };
const _hoisted_24 = { class: "section-head compact" };
const _hoisted_25 = { class: "mini-list history-list" };
const _hoisted_26 = { class: "mini-title" };
const _hoisted_27 = { class: "mini-meta" };
const _hoisted_28 = { class: "side-panel" };
const _hoisted_29 = { class: "section-head compact" };
const _hoisted_30 = { class: "mini-list" };
const _hoisted_31 = { class: "mini-title" };
const _hoisted_32 = { class: "mini-meta" };
const resultPageSize = 10;
const RESULT_PREVIEW_LENGTH = 280;
const _sfc_main$1 = /* @__PURE__ */ defineComponent({
  __name: "AnspireSearch",
  setup(__props) {
    const store = useAnspireSearchStore();
    const { form, session: activeSession, results, savedIndexes, selectedIndexes, resultPage } = storeToRefs(store);
    const searching = ref(false);
    const sessionsLoading = ref(false);
    const leadsLoading = ref(false);
    const savingIndex = ref(null);
    const bulkSaving = ref(false);
    const errorMessage = ref("");
    const showRaw = ref(false);
    const detailVisible = ref(false);
    const detailItem = ref(null);
    const sessions = ref([]);
    const leads = ref([]);
    const expandedIndexes = ref(/* @__PURE__ */ new Set());
    const pagedResults = computed(() => results.value.slice((resultPage.value - 1) * resultPageSize, resultPage.value * resultPageSize));
    const selectableResults = computed(() => results.value.filter((item) => !savedIndexes.value.has(item.result_index)));
    const selectedCount = computed(() => [...selectedIndexes.value].filter((index) => selectableResults.value.some((item) => item.result_index === index)).length);
    const allSelectableSelected = computed(() => selectableResults.value.length > 0 && selectableResults.value.every((item) => selectedIndexes.value.has(item.result_index)));
    const isSelectionIndeterminate = computed(() => selectedCount.value > 0 && !allSelectableSelected.value);
    function resultText(item) {
      return item.summary || item.snippet || "暂无摘要";
    }
    function isLongResult(item) {
      return resultText(item).length > RESULT_PREVIEW_LENGTH;
    }
    function isExpanded(index) {
      return expandedIndexes.value.has(index);
    }
    function visibleResultText(item) {
      const text = resultText(item);
      return !isLongResult(item) || isExpanded(item.result_index) ? text : `${text.slice(0, RESULT_PREVIEW_LENGTH)}…`;
    }
    function toggleExpanded(index) {
      const next = new Set(expandedIndexes.value);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      expandedIndexes.value = next;
    }
    async function handleSearch() {
      const query = form.value.query.trim();
      if (!query) {
        errorMessage.value = "请输入搜索关键词";
        return;
      }
      searching.value = true;
      errorMessage.value = "";
      try {
        const { data } = await api.post("/anspire/search", { query, top_k: form.value.top_k, insite: form.value.insite, from_time: form.value.from_time || void 0, to_time: form.value.to_time || void 0, region_mode: form.value.region_mode });
        store.setResult(data.session, data.items || []);
        ElMessage.success(`搜索完成，返回 ${data.total || 0} 条结果`);
        await loadSessions();
      } catch (err) {
        errorMessage.value = err?.response?.data?.detail || "Anspire 搜索暂时不可用";
      } finally {
        searching.value = false;
      }
    }
    async function persistLead(item, showMessage = true) {
      if (!activeSession.value) return false;
      savingIndex.value = item.result_index;
      try {
        const { data } = await api.post("/anspire/leads", { session_id: activeSession.value.id, result_index: item.result_index });
        store.markSaved(item.result_index);
        if (showMessage) ElMessage.success(data.status === "new" ? "已保存为线索" : "线索已存在");
        window.dispatchEvent(new CustomEvent("bocha-leads-refresh"));
        return true;
      } catch (err) {
        if (showMessage) ElMessage.error(err?.response?.data?.detail || "保存线索失败");
        return false;
      } finally {
        savingIndex.value = null;
      }
    }
    async function saveLead(item) {
      if (await persistLead(item)) await loadLeads();
    }
    async function saveSelectedLeads() {
      if (!activeSession.value || bulkSaving.value) return;
      const items = selectableResults.value.filter((item) => selectedIndexes.value.has(item.result_index));
      if (!items.length) return;
      bulkSaving.value = true;
      let success = 0;
      try {
        for (const item of items) if (await persistLead(item, false)) success += 1;
        if (success) {
          ElMessage.success(`已保存 ${success} 条线索`);
          await loadLeads();
        }
      } finally {
        bulkSaving.value = false;
      }
    }
    function toggleSelect(item, checked) {
      if (!savedIndexes.value.has(item.result_index)) store.setSelected(item.result_index, checked);
    }
    function toggleSelectAll(checked) {
      store.setSelectedIndexes(checked ? selectableResults.value.map((item) => item.result_index) : []);
    }
    function openResultDetail(item) {
      detailItem.value = item;
      detailVisible.value = true;
    }
    async function loadSessions() {
      sessionsLoading.value = true;
      try {
        const createdFrom = new Date(Date.now() - 3 * 24 * 60 * 60 * 1e3).toISOString();
        const { data } = await api.get("/anspire/sessions", { params: { page: 1, size: 50, created_from: createdFrom } });
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
        const { data } = await api.get("/anspire/leads", { params: { page: 1, size: 8 } });
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
      return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    }
    function statusText(status) {
      return { new: "待确认", confirmed: "已确认", rejected: "已驳回", promoted: "已晋级" }[status] || status;
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
    watch(() => results.value.length, (total) => {
      const maxPage = Math.max(1, Math.ceil(total / resultPageSize));
      if (resultPage.value > maxPage) store.setResultPage(maxPage);
    }, { immediate: true });
    return (_ctx, _cache) => {
      const _component_el_input = resolveComponent("el-input");
      const _component_el_form_item = resolveComponent("el-form-item");
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_date_picker = resolveComponent("el-date-picker");
      const _component_el_button = resolveComponent("el-button");
      const _component_el_form = resolveComponent("el-form");
      const _component_el_alert = resolveComponent("el-alert");
      const _component_el_tag = resolveComponent("el-tag");
      const _component_el_checkbox = resolveComponent("el-checkbox");
      const _component_el_empty = resolveComponent("el-empty");
      const _component_Pager = resolveComponent("Pager");
      const _directive_loading = resolveDirective("loading");
      return openBlock(), createElementBlock("div", _hoisted_1$1, [
        createBaseVNode("section", _hoisted_2$1, [
          createVNode(_component_el_form, {
            class: "search-form",
            model: unref(form),
            "label-position": "top",
            onSubmit: withModifiers(handleSearch, ["prevent"])
          }, {
            default: withCtx(() => [
              createVNode(_component_el_form_item, {
                label: "搜索关键词",
                class: "keyword-field"
              }, {
                default: withCtx(() => [
                  createVNode(_component_el_input, {
                    modelValue: unref(form).query,
                    "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => unref(form).query = $event),
                    size: "large",
                    clearable: "",
                    maxlength: "64",
                    "show-word-limit": "",
                    placeholder: "输入企业、事件、地点或风险关键词",
                    onKeyup: withKeys(handleSearch, ["enter"])
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "返回数量" }, {
                default: withCtx(() => [
                  createVNode(_component_el_select, {
                    modelValue: unref(form).top_k,
                    "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => unref(form).top_k = $event),
                    size: "large"
                  }, {
                    default: withCtx(() => [
                      (openBlock(), createElementBlock(Fragment, null, renderList([10, 20, 30, 40, 50], (value) => {
                        return createVNode(_component_el_option, {
                          key: value,
                          label: String(value),
                          value
                        }, null, 8, ["label", "value"]);
                      }), 64))
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "搜索区域" }, {
                default: withCtx(() => [
                  createVNode(_component_el_select, {
                    modelValue: unref(form).region_mode,
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => unref(form).region_mode = $event),
                    size: "large"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_option, {
                        label: "国内",
                        value: 0
                      }),
                      createVNode(_component_el_option, {
                        label: "海外",
                        value: 1
                      }),
                      createVNode(_component_el_option, {
                        label: "国内外混合",
                        value: 2
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "限定站点" }, {
                default: withCtx(() => [
                  createVNode(_component_el_input, {
                    modelValue: unref(form).insite,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => unref(form).insite = $event),
                    size: "large",
                    placeholder: "例如 gov.cn,news.cn"
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "开始时间" }, {
                default: withCtx(() => [
                  createVNode(_component_el_date_picker, {
                    modelValue: unref(form).from_time,
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => unref(form).from_time = $event),
                    class: "date-field",
                    type: "datetime",
                    "value-format": "YYYY-MM-DD HH:mm:ss",
                    placeholder: "不限"
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "结束时间" }, {
                default: withCtx(() => [
                  createVNode(_component_el_date_picker, {
                    modelValue: unref(form).to_time,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => unref(form).to_time = $event),
                    class: "date-field",
                    type: "datetime",
                    "value-format": "YYYY-MM-DD HH:mm:ss",
                    placeholder: "不限"
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
                default: withCtx(() => [..._cache[9] || (_cache[9] = [
                  createTextVNode("搜索", -1)
                ])]),
                _: 1
              }, 8, ["loading"])
            ]),
            _: 1
          }, 8, ["model"]),
          errorMessage.value ? (openBlock(), createBlock(_component_el_alert, {
            key: 0,
            class: "error-alert",
            type: "error",
            closable: false,
            title: errorMessage.value
          }, null, 8, ["title"])) : createCommentVNode("", true)
        ]),
        createBaseVNode("section", _hoisted_3$1, [
          createBaseVNode("div", _hoisted_4$1, [
            createBaseVNode("div", _hoisted_5, [
              createBaseVNode("div", null, [
                _cache[10] || (_cache[10] = createBaseVNode("h2", null, "搜索结果", -1)),
                unref(activeSession) ? (openBlock(), createElementBlock("p", _hoisted_6, "本次搜索返回 " + toDisplayString(unref(results).length) + " 条结果", 1)) : (openBlock(), createElementBlock("p", _hoisted_7, "输入关键词后开始一次 Anspire 网页搜索"))
              ]),
              createBaseVNode("div", _hoisted_8, [
                unref(activeSession) ? (openBlock(), createBlock(_component_el_tag, {
                  key: 0,
                  effect: "plain",
                  type: "info"
                }, {
                  default: withCtx(() => [
                    createTextVNode("会话 #" + toDisplayString(unref(activeSession).id), 1)
                  ]),
                  _: 1
                })) : createCommentVNode("", true),
                unref(activeSession) ? (openBlock(), createBlock(_component_el_button, {
                  key: 1,
                  text: "",
                  type: "primary",
                  onClick: _cache[6] || (_cache[6] = ($event) => showRaw.value = !showRaw.value)
                }, {
                  default: withCtx(() => [
                    createTextVNode(toDisplayString(showRaw.value ? "隐藏原始 JSON" : "查看原始 JSON"), 1)
                  ]),
                  _: 1
                })) : createCommentVNode("", true)
              ])
            ]),
            showRaw.value ? (openBlock(), createElementBlock("pre", _hoisted_9, toDisplayString(JSON.stringify(unref(results), null, 2)), 1)) : createCommentVNode("", true),
            unref(results).length ? (openBlock(), createElementBlock("div", _hoisted_10, [
              createVNode(_component_el_checkbox, {
                "model-value": allSelectableSelected.value,
                indeterminate: isSelectionIndeterminate.value,
                disabled: !selectableResults.value.length || bulkSaving.value,
                onChange: toggleSelectAll
              }, {
                default: withCtx(() => [..._cache[11] || (_cache[11] = [
                  createTextVNode(" 全选可保存结果 ", -1)
                ])]),
                _: 1
              }, 8, ["model-value", "indeterminate", "disabled"]),
              createBaseVNode("span", _hoisted_11, "已选择 " + toDisplayString(selectedCount.value) + " 条", 1),
              createVNode(_component_el_button, {
                class: "save-lead-button",
                type: "primary",
                plain: "",
                loading: bulkSaving.value,
                disabled: !selectedCount.value,
                onClick: saveSelectedLeads
              }, {
                default: withCtx(() => [..._cache[12] || (_cache[12] = [
                  createTextVNode("一键保存为线索", -1)
                ])]),
                _: 1
              }, 8, ["loading", "disabled"])
            ])) : createCommentVNode("", true),
            withDirectives((openBlock(), createElementBlock("div", _hoisted_12, [
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
                  createBaseVNode("div", _hoisted_13, [
                    createBaseVNode("div", _hoisted_14, [
                      createBaseVNode("button", {
                        class: "result-title result-title-button",
                        type: "button",
                        onClick: ($event) => openResultDetail(item)
                      }, toDisplayString(item.title || item.url), 9, _hoisted_15),
                      unref(savedIndexes).has(item.result_index) ? (openBlock(), createBlock(_component_el_tag, {
                        key: 0,
                        type: "success",
                        effect: "light"
                      }, {
                        default: withCtx(() => [..._cache[13] || (_cache[13] = [
                          createTextVNode("已保存", -1)
                        ])]),
                        _: 1
                      })) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("div", _hoisted_16, [
                      createBaseVNode("span", null, toDisplayString(item.source_name || "未知来源"), 1),
                      item.publish_time ? (openBlock(), createElementBlock("span", _hoisted_17, toDisplayString(formatTime(item.publish_time)), 1)) : createCommentVNode("", true),
                      item.provider_score != null ? (openBlock(), createElementBlock("span", _hoisted_18, "相关度 " + toDisplayString(item.provider_score), 1)) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("p", _hoisted_19, [
                      createTextVNode(toDisplayString(visibleResultText(item)) + " ", 1),
                      isLongResult(item) ? (openBlock(), createBlock(_component_el_button, {
                        key: 0,
                        class: "expand-result-button",
                        text: "",
                        type: "primary",
                        size: "small",
                        onClick: ($event) => toggleExpanded(item.result_index)
                      }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(isExpanded(item.result_index) ? "收起" : "展开全文"), 1)
                        ]),
                        _: 2
                      }, 1032, ["onClick"])) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("a", {
                      class: "source-link",
                      href: item.url,
                      target: "_blank",
                      rel: "noopener noreferrer"
                    }, toDisplayString(item.url), 9, _hoisted_20)
                  ]),
                  createVNode(_component_el_button, {
                    class: "save-lead-button",
                    type: "primary",
                    plain: "",
                    disabled: !unref(activeSession) || unref(savedIndexes).has(item.result_index),
                    loading: savingIndex.value === item.result_index,
                    onClick: ($event) => saveLead(item)
                  }, {
                    default: withCtx(() => [
                      createTextVNode(toDisplayString(unref(savedIndexes).has(item.result_index) ? "已保存" : "保存为线索"), 1)
                    ]),
                    _: 2
                  }, 1032, ["disabled", "loading", "onClick"])
                ]);
              }), 128)),
              !unref(results).length && !searching.value ? (openBlock(), createBlock(_component_el_empty, {
                key: 0,
                description: "暂无搜索结果"
              })) : createCommentVNode("", true)
            ])), [
              [_directive_loading, searching.value]
            ]),
            unref(results).length > resultPageSize ? (openBlock(), createElementBlock("div", _hoisted_21, [
              createVNode(_component_Pager, {
                "current-page": unref(resultPage),
                "onUpdate:currentPage": _cache[7] || (_cache[7] = ($event) => isRef(resultPage) ? resultPage.value = $event : null),
                "page-size": resultPageSize,
                total: unref(results).length
              }, null, 8, ["current-page", "total"])
            ])) : createCommentVNode("", true)
          ]),
          createBaseVNode("aside", _hoisted_22, [
            createBaseVNode("section", _hoisted_23, [
              createBaseVNode("div", _hoisted_24, [
                _cache[15] || (_cache[15] = createBaseVNode("div", null, [
                  createBaseVNode("h2", null, "搜索历史"),
                  createBaseVNode("p", null, "仅显示最近三天的 Anspire 搜索")
                ], -1)),
                createVNode(_component_el_button, {
                  text: "",
                  type: "primary",
                  loading: sessionsLoading.value,
                  onClick: loadSessions
                }, {
                  default: withCtx(() => [..._cache[14] || (_cache[14] = [
                    createTextVNode("刷新", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])
              ]),
              withDirectives((openBlock(), createElementBlock("div", _hoisted_25, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(sessions.value, (item) => {
                  return openBlock(), createElementBlock("div", {
                    key: item.id,
                    class: "mini-item"
                  }, [
                    createBaseVNode("div", _hoisted_26, toDisplayString(item.query), 1),
                    createBaseVNode("div", _hoisted_27, [
                      createBaseVNode("span", null, toDisplayString(formatTime(item.created_at)), 1),
                      createBaseVNode("span", null, toDisplayString(item.result_count) + " 条结果", 1)
                    ])
                  ]);
                }), 128)),
                !sessions.value.length && !sessionsLoading.value ? (openBlock(), createBlock(_component_el_empty, {
                  key: 0,
                  description: "暂无搜索历史",
                  "image-size": 72
                })) : createCommentVNode("", true)
              ])), [
                [_directive_loading, sessionsLoading.value]
              ])
            ]),
            createBaseVNode("section", _hoisted_28, [
              createBaseVNode("div", _hoisted_29, [
                _cache[17] || (_cache[17] = createBaseVNode("div", null, [
                  createBaseVNode("h2", null, "我的线索"),
                  createBaseVNode("p", null, "已保存，等待管理员确认")
                ], -1)),
                createVNode(_component_el_button, {
                  text: "",
                  type: "primary",
                  loading: leadsLoading.value,
                  onClick: loadLeads
                }, {
                  default: withCtx(() => [..._cache[16] || (_cache[16] = [
                    createTextVNode("刷新", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])
              ]),
              withDirectives((openBlock(), createElementBlock("div", _hoisted_30, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(leads.value, (lead) => {
                  return openBlock(), createElementBlock("div", {
                    key: lead.id,
                    class: "mini-item"
                  }, [
                    createBaseVNode("div", _hoisted_31, toDisplayString(lead.title || lead.url), 1),
                    createBaseVNode("div", _hoisted_32, [
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
          "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => detailVisible.value = $event),
          item: detailItem.value,
          query: unref(activeSession)?.query || unref(form).query
        }, null, 8, ["modelValue", "item", "query"])
      ]);
    };
  }
});

const AnspireSearch = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-b8e193c8"]]);

const _hoisted_1 = { class: "ai-search-shell" };
const _hoisted_2 = {
  class: "search-tabs",
  "aria-label": "AI 检索模式"
};
const _hoisted_3 = ["disabled"];
const _hoisted_4 = ["disabled"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "AiSearch",
  setup(__props) {
    const route = useRoute();
    const router = useRouter();
    const navigating = ref(false);
    const isAiSearch = computed(() => route.path === "/ai-search/ai");
    const isAnspireSearch = computed(() => route.path === "/ai-search/anspire");
    async function go(path) {
      if (route.path === path || navigating.value) return;
      navigating.value = true;
      try {
        await router.push(path);
      } finally {
        navigating.value = false;
      }
    }
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("nav", _hoisted_2, [
          createBaseVNode("button", {
            class: normalizeClass(["search-tab", { active: !isAiSearch.value && !isAnspireSearch.value }]),
            type: "button",
            disabled: !isAiSearch.value && !isAnspireSearch.value && navigating.value,
            onClick: _cache[0] || (_cache[0] = ($event) => go("/ai-search/web"))
          }, " Bocha 网页搜索 ", 10, _hoisted_3),
          createBaseVNode("button", {
            class: normalizeClass(["search-tab", { active: isAiSearch.value }]),
            type: "button",
            disabled: isAiSearch.value && navigating.value,
            onClick: _cache[1] || (_cache[1] = ($event) => go("/ai-search/ai"))
          }, " AI 搜索（Bocha） ", 10, _hoisted_4),
          createBaseVNode("button", {
            class: normalizeClass(["search-tab", { active: isAnspireSearch.value }]),
            type: "button",
            onClick: _cache[2] || (_cache[2] = ($event) => go("/ai-search/anspire"))
          }, "Anspire 网页搜索", 2)
        ]),
        createBaseVNode("div", {
          class: normalizeClass(["search-tab-content", { loading: navigating.value }])
        }, [
          isAnspireSearch.value ? (openBlock(), createBlock(AnspireSearch, { key: 0 })) : !isAiSearch.value ? (openBlock(), createBlock(WebSearch, { key: 1 })) : (openBlock(), createBlock(AiSearchPanel, { key: 2 }))
        ], 2)
      ]);
    };
  }
});

const AiSearch = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-a731fc19"]]);

export { AiSearch as default };
