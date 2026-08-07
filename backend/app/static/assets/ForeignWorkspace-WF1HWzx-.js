import { d as defineComponent, C as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, t as toDisplayString, F as Fragment, i as renderList, b as withKeys, v as vModelText, J as vModelSelect, s as createCommentVNode, L as withModifiers, r as ref, f as reactive, g as api, E as ElMessage, N as pollTask, B as resolveDirective, o as openBlock, n as normalizeClass, e as createTextVNode, _ as _export_sfc } from './index-C0Ka1V5k.js';

const _hoisted_1 = { class: "foreign-page" };
const _hoisted_2 = { class: "workspace-head" };
const _hoisted_3 = ["disabled"];
const _hoisted_4 = {
  class: "tabs",
  role: "tablist"
};
const _hoisted_5 = ["onClick"];
const _hoisted_6 = {
  key: 0,
  class: "panel"
};
const _hoisted_7 = { class: "toolbar" };
const _hoisted_8 = ["value"];
const _hoisted_9 = { class: "table-wrap" };
const _hoisted_10 = ["onClick"];
const _hoisted_11 = { class: "title-cell" };
const _hoisted_12 = { key: 0 };
const _hoisted_13 = {
  key: 0,
  class: "pager"
};
const _hoisted_14 = ["disabled"];
const _hoisted_15 = ["disabled"];
const _hoisted_16 = {
  key: 1,
  class: "panel"
};
const _hoisted_17 = { class: "toolbar" };
const _hoisted_18 = { class: "table-wrap" };
const _hoisted_19 = { class: "actions" };
const _hoisted_20 = ["onClick"];
const _hoisted_21 = ["onClick"];
const _hoisted_22 = { key: 0 };
const _hoisted_23 = {
  key: 2,
  class: "panel"
};
const _hoisted_24 = { class: "table-wrap" };
const _hoisted_25 = { class: "muted" };
const _hoisted_26 = ["onClick"];
const _hoisted_27 = {
  key: 0,
  class: "proxy-mark"
};
const _hoisted_28 = { key: 0 };
const _hoisted_29 = {
  key: 3,
  class: "panel"
};
const _hoisted_30 = { class: "table-wrap" };
const _hoisted_31 = { class: "error-cell" };
const _hoisted_32 = { key: 0 };
const _hoisted_33 = { class: "detail" };
const _hoisted_34 = { class: "detail-meta" };
const _hoisted_35 = { class: "detail-text" };
const _hoisted_36 = ["href"];
const opinionSize = 20;
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "ForeignWorkspace",
  setup(__props) {
    const tabs = [
      { value: "opinions", label: "国外舆情" },
      { value: "keywords", label: "外网关键词" },
      { value: "sources", label: "外网数据源" },
      { value: "runs", label: "外网采集日志" }
    ];
    const activeTab = ref("opinions");
    const loading = ref(false);
    const collecting = ref(false);
    const keywords = ref([]);
    const sources = ref([]);
    const opinions = ref([]);
    const runs = ref([]);
    const opinionSources = ref([]);
    const opinionTotal = ref(0);
    const opinionPage = ref(1);
    const selectedOpinion = ref(null);
    const keywordDraft = reactive({ word: "" });
    const opinionFilters = reactive({ q: "", source: "", keyword: "" });
    function switchTab(tab) {
      activeTab.value = tab;
      if (tab === "opinions") loadOpinions();
      if (tab === "keywords") loadKeywords();
      if (tab === "sources") loadSources();
      if (tab === "runs") loadRuns();
    }
    function formatTime(value) {
      return value ? new Date(value).toLocaleString() : "-";
    }
    async function loadKeywords() {
      loading.value = true;
      try {
        keywords.value = (await api.get("/foreign/keywords", { params: { size: 100 } })).data.items;
      } finally {
        loading.value = false;
      }
    }
    async function loadSources() {
      loading.value = true;
      try {
        sources.value = (await api.get("/foreign/sources")).data.items;
      } finally {
        loading.value = false;
      }
    }
    async function loadOpinions() {
      loading.value = true;
      try {
        const params = { page: opinionPage.value, size: opinionSize };
        if (opinionFilters.q) params.q = opinionFilters.q;
        if (opinionFilters.source) params.source = opinionFilters.source;
        if (opinionFilters.keyword) params.keyword = opinionFilters.keyword;
        const [list, sourceList] = await Promise.all([
          api.get("/foreign/opinions", { params }),
          api.get("/foreign/opinions/sources")
        ]);
        opinions.value = list.data.items;
        opinionTotal.value = list.data.total;
        opinionSources.value = sourceList.data;
      } finally {
        loading.value = false;
      }
    }
    async function loadRuns() {
      loading.value = true;
      try {
        runs.value = (await api.get("/foreign/collection-runs", { params: { size: 100 } })).data.items;
      } finally {
        loading.value = false;
      }
    }
    async function createKeyword() {
      const word = keywordDraft.word.trim();
      if (!word) return;
      try {
        await api.post("/foreign/keywords", { word, category: "general", is_enabled: true });
        keywordDraft.word = "";
        await loadKeywords();
        ElMessage.success("外网关键词已新增");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "新增失败");
      }
    }
    async function toggleKeyword(row) {
      try {
        await api.patch(`/foreign/keywords/${row.id}`, { word: row.word, category: row.category, is_enabled: !row.is_enabled });
        await loadKeywords();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "更新失败");
      }
    }
    async function removeKeyword(id) {
      try {
        await api.delete(`/foreign/keywords/${id}`);
        await loadKeywords();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "删除失败");
      }
    }
    async function toggleSource(row) {
      try {
        await api.patch(`/foreign/sources/${row.id}`, { enabled: !row.enabled });
        await loadSources();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "数据源状态更新失败");
      }
    }
    async function collectNow() {
      if (collecting.value) return;
      collecting.value = true;
      try {
        const { data } = await api.post("/foreign/collect", { source_ids: null });
        const result = await pollTask(data.task_id);
        if (result.status === "success") {
          ElMessage.success(`外网采集完成：新增 ${result.result?.created || 0} 条`);
          await loadOpinions();
          await loadRuns();
        } else ElMessage.error(result.error || "外网采集失败");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || err?.message || "外网采集失败");
      } finally {
        collecting.value = false;
      }
    }
    onMounted(loadOpinions);
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          _cache[8] || (_cache[8] = createBaseVNode("div", null, [
            createBaseVNode("h2", null, "外网舆情"),
            createBaseVNode("p", null, "独立采集、去重和展示链路；不会进入国内舆情、风险、事件或告警。")
          ], -1)),
          createBaseVNode("button", {
            class: "btn btn-primary",
            disabled: collecting.value,
            onClick: collectNow
          }, toDisplayString(collecting.value ? "采集中..." : "采集外网 RSS"), 9, _hoisted_3)
        ]),
        createBaseVNode("div", _hoisted_4, [
          (openBlock(), createElementBlock(Fragment, null, renderList(tabs, (tab) => {
            return createBaseVNode("button", {
              key: tab.value,
              class: normalizeClass(["tab", { active: activeTab.value === tab.value }]),
              onClick: ($event) => switchTab(tab.value)
            }, toDisplayString(tab.label), 11, _hoisted_5);
          }), 64))
        ]),
        activeTab.value === "opinions" ? (openBlock(), createElementBlock("section", _hoisted_6, [
          createBaseVNode("div", _hoisted_7, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => opinionFilters.q = $event),
              class: "input",
              placeholder: "搜索标题、摘要、正文",
              onKeyup: withKeys(loadOpinions, ["enter"])
            }, null, 544), [
              [vModelText, opinionFilters.q]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => opinionFilters.source = $event),
              class: "input",
              onChange: loadOpinions
            }, [
              _cache[9] || (_cache[9] = createBaseVNode("option", { value: "" }, "全部来源", -1)),
              (openBlock(true), createElementBlock(Fragment, null, renderList(opinionSources.value, (source) => {
                return openBlock(), createElementBlock("option", {
                  key: source,
                  value: source
                }, toDisplayString(source), 9, _hoisted_8);
              }), 128))
            ], 544), [
              [vModelSelect, opinionFilters.source]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => opinionFilters.keyword = $event),
              class: "input",
              placeholder: "命中关键词",
              onKeyup: withKeys(loadOpinions, ["enter"])
            }, null, 544), [
              [vModelText, opinionFilters.keyword]
            ]),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadOpinions
            }, "搜索")
          ]),
          createBaseVNode("div", _hoisted_9, [
            createBaseVNode("table", null, [
              _cache[11] || (_cache[11] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "标题"),
                  createBaseVNode("th", null, "来源快照"),
                  createBaseVNode("th", null, "命中关键词"),
                  createBaseVNode("th", null, "发布时间"),
                  createBaseVNode("th", null, "采集时间")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(opinions.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id,
                    onClick: ($event) => selectedOpinion.value = row
                  }, [
                    createBaseVNode("td", _hoisted_11, toDisplayString(row.title || "无标题"), 1),
                    createBaseVNode("td", null, toDisplayString(row.source_name_snapshot), 1),
                    createBaseVNode("td", null, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(row.matched_keywords, (word) => {
                        return openBlock(), createElementBlock("span", {
                          key: word,
                          class: "tag"
                        }, toDisplayString(word), 1);
                      }), 128))
                    ]),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.published_at)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.collected_at)), 1)
                  ], 8, _hoisted_10);
                }), 128)),
                !opinions.value.length ? (openBlock(), createElementBlock("tr", _hoisted_12, [..._cache[10] || (_cache[10] = [
                  createBaseVNode("td", {
                    colspan: "5",
                    class: "empty"
                  }, "暂无外网舆情", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ]),
          opinionTotal.value > opinionSize ? (openBlock(), createElementBlock("div", _hoisted_13, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: opinionPage.value <= 1,
              onClick: _cache[3] || (_cache[3] = ($event) => {
                opinionPage.value--;
                loadOpinions();
              })
            }, "上一页", 8, _hoisted_14),
            createBaseVNode("span", null, "第 " + toDisplayString(opinionPage.value) + " 页 / 共 " + toDisplayString(opinionTotal.value) + " 条", 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: opinionPage.value * opinionSize >= opinionTotal.value,
              onClick: _cache[4] || (_cache[4] = ($event) => {
                opinionPage.value++;
                loadOpinions();
              })
            }, "下一页", 8, _hoisted_15)
          ])) : createCommentVNode("", true)
        ])) : activeTab.value === "keywords" ? (openBlock(), createElementBlock("section", _hoisted_16, [
          createBaseVNode("div", _hoisted_17, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => keywordDraft.word = $event),
              class: "input",
              placeholder: "新增外网关键词",
              onKeyup: withKeys(createKeyword, ["enter"])
            }, null, 544), [
              [vModelText, keywordDraft.word]
            ]),
            createBaseVNode("button", {
              class: "btn btn-primary",
              onClick: createKeyword
            }, "新增关键词"),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadKeywords
            }, "刷新")
          ]),
          createBaseVNode("div", _hoisted_18, [
            createBaseVNode("table", null, [
              _cache[13] || (_cache[13] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "关键词"),
                  createBaseVNode("th", null, "分类"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(keywords.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", null, toDisplayString(row.word), 1),
                    createBaseVNode("td", null, toDisplayString(row.category), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.is_enabled }])
                      }, toDisplayString(row.is_enabled ? "启用" : "停用"), 3)
                    ]),
                    createBaseVNode("td", _hoisted_19, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        onClick: ($event) => toggleKeyword(row)
                      }, toDisplayString(row.is_enabled ? "停用" : "启用"), 9, _hoisted_20),
                      createBaseVNode("button", {
                        class: "link-btn danger",
                        onClick: ($event) => removeKeyword(row.id)
                      }, "删除", 8, _hoisted_21)
                    ])
                  ]);
                }), 128)),
                !keywords.value.length ? (openBlock(), createElementBlock("tr", _hoisted_22, [..._cache[12] || (_cache[12] = [
                  createBaseVNode("td", {
                    colspan: "4",
                    class: "empty"
                  }, "暂无外网关键词", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])
        ])) : activeTab.value === "sources" ? (openBlock(), createElementBlock("section", _hoisted_23, [
          _cache[16] || (_cache[16] = createBaseVNode("div", { class: "source-note" }, "首批来源默认停用，代理只读取环境变量名，不在前端展示地址、账号或密钥。", -1)),
          createBaseVNode("div", _hoisted_24, [
            createBaseVNode("table", null, [
              _cache[15] || (_cache[15] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "来源"),
                  createBaseVNode("th", null, "RSS"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "调度"),
                  createBaseVNode("th", null, "代理")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(sources.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", null, [
                      createBaseVNode("strong", null, toDisplayString(row.name), 1),
                      createBaseVNode("div", _hoisted_25, toDisplayString(row.key), 1)
                    ]),
                    createBaseVNode("td", null, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(row.feeds, (feed) => {
                        return openBlock(), createElementBlock("div", {
                          key: feed,
                          class: "feed"
                        }, toDisplayString(feed), 1);
                      }), 128))
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("button", {
                        class: normalizeClass(["status-toggle", { on: row.enabled }]),
                        onClick: ($event) => toggleSource(row)
                      }, toDisplayString(row.enabled ? "已启用" : "已停用"), 11, _hoisted_26)
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.schedule_enabled ? "自动" : "手动"), 1),
                    createBaseVNode("td", null, [
                      createTextVNode(toDisplayString(row.proxy_env || "直连"), 1),
                      row.proxy_configured ? (openBlock(), createElementBlock("span", _hoisted_27, "已配置")) : createCommentVNode("", true)
                    ])
                  ]);
                }), 128)),
                !sources.value.length ? (openBlock(), createElementBlock("tr", _hoisted_28, [..._cache[14] || (_cache[14] = [
                  createBaseVNode("td", {
                    colspan: "5",
                    class: "empty"
                  }, "暂无外网数据源", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])
        ])) : (openBlock(), createElementBlock("section", _hoisted_29, [
          createBaseVNode("div", { class: "toolbar" }, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadRuns
            }, "刷新日志"),
            _cache[17] || (_cache[17] = createBaseVNode("span", { class: "muted" }, "仅显示 scope=foreign 的采集记录", -1))
          ]),
          createBaseVNode("div", _hoisted_30, [
            createBaseVNode("table", null, [
              _cache[19] || (_cache[19] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "来源"),
                  createBaseVNode("th", null, "开始"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "抓取"),
                  createBaseVNode("th", null, "命中"),
                  createBaseVNode("th", null, "新增"),
                  createBaseVNode("th", null, "去重"),
                  createBaseVNode("th", null, "代理"),
                  createBaseVNode("th", null, "失败原因")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(runs.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", null, toDisplayString(row.collector_name), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.start_time)), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.status === "success" }])
                      }, toDisplayString(row.status), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.fetched_raw), 1),
                    createBaseVNode("td", null, toDisplayString(row.matched), 1),
                    createBaseVNode("td", null, toDisplayString(row.created), 1),
                    createBaseVNode("td", null, toDisplayString(row.duplicate), 1),
                    createBaseVNode("td", null, toDisplayString(row.proxy_used ? "是" : "否"), 1),
                    createBaseVNode("td", _hoisted_31, toDisplayString(row.error_msg || "-"), 1)
                  ]);
                }), 128)),
                !runs.value.length ? (openBlock(), createElementBlock("tr", _hoisted_32, [..._cache[18] || (_cache[18] = [
                  createBaseVNode("td", {
                    colspan: "9",
                    class: "empty"
                  }, "暂无外网采集日志", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])
        ])),
        selectedOpinion.value ? (openBlock(), createElementBlock("div", {
          key: 4,
          class: "detail-mask",
          onClick: _cache[7] || (_cache[7] = withModifiers(($event) => selectedOpinion.value = null, ["self"]))
        }, [
          createBaseVNode("article", _hoisted_33, [
            createBaseVNode("button", {
              class: "close",
              title: "关闭详情",
              onClick: _cache[6] || (_cache[6] = ($event) => selectedOpinion.value = null)
            }, "×"),
            createBaseVNode("h3", null, toDisplayString(selectedOpinion.value.title), 1),
            createBaseVNode("div", _hoisted_34, toDisplayString(selectedOpinion.value.source_name_snapshot) + " · 命中 " + toDisplayString(selectedOpinion.value.matched_keywords.join("、")), 1),
            createBaseVNode("p", _hoisted_35, toDisplayString(selectedOpinion.value.content || selectedOpinion.value.summary || "暂无正文"), 1),
            selectedOpinion.value.url ? (openBlock(), createElementBlock("a", {
              key: 0,
              href: selectedOpinion.value.url,
              target: "_blank",
              rel: "noreferrer",
              class: "original"
            }, "打开原文", 8, _hoisted_36)) : createCommentVNode("", true)
          ])
        ])) : createCommentVNode("", true)
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const ForeignWorkspace = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-d14b716d"]]);

export { ForeignWorkspace as default };
