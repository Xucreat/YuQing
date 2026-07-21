import { d as defineComponent, p as onMounted, s as onBeforeUnmount, w as withDirectives, c as createElementBlock, B as createVNode, z as withCtx, r as ref, g as api, E as ElMessage, q as nextTick, C as resolveComponent, D as resolveDirective, o as openBlock, a as createBaseVNode, F as Fragment, i as renderList, x as unref, n as normalizeClass, t as toDisplayString, e as createTextVNode, A as createCommentVNode, y as createBlock, h as useRouter, j as computed, _ as _export_sfc } from './index-C6UycfoG.js';
import { n as init } from './index-C0N1mBNY.js';

const _hoisted_1 = { class: "propagation" };
const _hoisted_2 = { class: "event-list" };
const _hoisted_3 = ["onClick", "onDblclick"];
const _hoisted_4 = { class: "ei-title" };
const _hoisted_5 = { class: "ei-meta" };
const _hoisted_6 = { class: "ei-count" };
const _hoisted_7 = {
  key: 0,
  class: "ei-nodes"
};
const _hoisted_8 = {
  key: 0,
  class: "no-selection"
};
const _hoisted_9 = {
  key: 1,
  class: "detail-panel"
};
const _hoisted_10 = { class: "detail-header" };
const _hoisted_11 = {
  key: 0,
  class: "metrics-strip"
};
const _hoisted_12 = { class: "metric" };
const _hoisted_13 = { class: "m-val" };
const _hoisted_14 = { class: "metric" };
const _hoisted_15 = { class: "m-val" };
const _hoisted_16 = { class: "metric" };
const _hoisted_17 = { class: "m-val" };
const _hoisted_18 = { class: "metric" };
const _hoisted_19 = { class: "m-val" };
const _hoisted_20 = { class: "metric" };
const _hoisted_21 = { class: "m-val danger" };
const _hoisted_22 = {
  key: 0,
  class: "source-list"
};
const _hoisted_23 = { class: "source-name" };
const _hoisted_24 = { class: "source-num" };
const _hoisted_25 = {
  key: 0,
  class: "timeline-list"
};
const _hoisted_26 = { class: "tl-content" };
const _hoisted_27 = { class: "tl-time" };
const _hoisted_28 = { class: "tl-title" };
const _hoisted_29 = { class: "tl-source" };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Propagation",
  setup(__props) {
    const router = useRouter();
    const loading = ref(false);
    const rebuilding = ref(false);
    const events = ref([]);
    const searchKeyword = ref("");
    const selectedEvent = ref(null);
    const graphData = ref(null);
    const graphRef = ref();
    let chart = null;
    const sentimentRef = ref();
    const depthRef = ref();
    const filteredEvents = computed(() => {
      if (!searchKeyword.value) return events.value;
      const kw = searchKeyword.value.toLowerCase();
      return events.value.filter((e) => e.event_title.toLowerCase().includes(kw));
    });
    const spanText = computed(() => {
      const g = graphData.value;
      if (!g || !g.first_time) return "-";
      const a = g.first_time.slice(0, 10);
      const b = (g.last_time || g.first_time).slice(0, 10);
      return a === b ? a : `${a} ~ ${b}`;
    });
    const timelineData = computed(() => {
      if (!graphData.value?.nodes) return [];
      return graphData.value.nodes.filter((n) => n.publish_time).sort((a, b) => a.publish_time > b.publish_time ? 1 : -1).slice(0, 15).map((n) => ({
        time: n.publish_time ? n.publish_time.replace("T", " ").slice(0, 19) : "-",
        title: n.title.length > 30 ? n.title.slice(0, 30) + "..." : n.title,
        source: n.source
      }));
    });
    function riskTag(level) {
      return { critical: "danger", high: "danger", medium: "warning", low: "info" }[level] || "info";
    }
    function riskText(level) {
      return { critical: "严重", high: "高", medium: "中", low: "低" }[level] || level;
    }
    async function loadEvents() {
      loading.value = true;
      try {
        const { data } = await api.get("/propagation/events");
        events.value = data;
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载事件失败");
      } finally {
        loading.value = false;
      }
    }
    async function selectEvent(ev) {
      selectedEvent.value = ev;
      graphData.value = null;
      try {
        const { data } = await api.get(`/propagation/graph/${ev.event_id}`);
        graphData.value = data;
        await nextTick();
        renderGraph();
        renderSentiment();
        renderDepth();
      } catch (_) {
      }
    }
    async function handleRebuild() {
      if (!selectedEvent.value || rebuilding.value) return;
      rebuilding.value = true;
      try {
        const { data } = await api.post(`/propagation/rebuild/${selectedEvent.value.event_id}`);
        ElMessage.success(`传播链构建完成：创建 ${data.nodes_created} 个节点`);
        await loadEvents();
        await selectEvent(selectedEvent.value);
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "构建失败");
      } finally {
        rebuilding.value = false;
      }
    }
    function filterEvents() {
    }
    function renderGraph() {
      if (!graphRef.value || !graphData.value || graphData.value.nodes.length === 0) return;
      if (!chart) chart = init(graphRef.value, void 0, { renderer: "svg" });
      const nodes = graphData.value.nodes.map((n) => ({
        id: n.id,
        name: n.source + ": " + (n.title.length > 20 ? n.title.slice(0, 20) + "..." : n.title),
        symbolSize: Math.max(12, Math.min(36, n.risk_score / 3 + 8)),
        itemStyle: {
          color: { critical: "#ff3b30", high: "#ff3b30", medium: "#c77700", low: "#0071e3", neutral: "#86868b" }[n.sentiment] || "#86868b"
        },
        category: n.depth,
        depth: n.depth
      }));
      const links = graphData.value.links.map((l) => ({
        source: l.source_id,
        target: l.target_id,
        lineStyle: { color: "#c0ccda", width: 1.5 }
      }));
      const categories = [
        { name: "源头" },
        { name: "一级传播" },
        { name: "二级传播" }
      ];
      chart.setOption({
        tooltip: { trigger: "item", formatter: (p) => p.data?.name || "" },
        series: [{
          type: "graph",
          layout: "force",
          roam: true,
          draggable: true,
          categories: categories.slice(0, 3),
          data: nodes,
          links,
          force: { repulsion: 300, edgeLength: [120, 300], gravity: 0.1 },
          label: { show: true, fontSize: 10, formatter: (p) => p.name.split(":")[0] },
          emphasis: { focus: "adjacency", label: { fontSize: 12 } }
        }]
      }, true);
    }
    function renderSentiment() {
      return;
    }
    function renderDepth() {
      return;
    }
    function handleResize() {
      if (chart && graphRef.value) chart.resize();
    }
    onMounted(async () => {
      await loadEvents();
      if (events.value.length > 0) selectEvent(events.value[0]);
      window.addEventListener("resize", handleResize);
    });
    onBeforeUnmount(() => {
      window.removeEventListener("resize", handleResize);
      if (chart) {
        chart.dispose();
        chart = null;
      }
    });
    return (_ctx, _cache) => {
      const _component_el_button = resolveComponent("el-button");
      const _component_el_input = resolveComponent("el-input");
      const _component_el_tag = resolveComponent("el-tag");
      const _component_el_empty = resolveComponent("el-empty");
      const _component_el_card = resolveComponent("el-card");
      const _component_el_col = resolveComponent("el-col");
      const _component_router_link = resolveComponent("router-link");
      const _component_el_row = resolveComponent("el-row");
      const _component_el_progress = resolveComponent("el-progress");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createVNode(_component_el_row, {
          gutter: 16,
          class: "prop-layout"
        }, {
          default: withCtx(() => [
            createVNode(_component_el_col, { span: 8 }, {
              default: withCtx(() => [
                createVNode(_component_el_card, {
                  shadow: "never",
                  class: "event-list-card"
                }, {
                  header: withCtx(() => [
                    _cache[2] || (_cache[2] = createBaseVNode("span", null, "事件列表", -1)),
                    createVNode(_component_el_button, {
                      size: "small",
                      type: "primary",
                      style: { "float": "right" },
                      onClick: loadEvents
                    }, {
                      default: withCtx(() => [..._cache[1] || (_cache[1] = [
                        createTextVNode("刷新", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: searchKeyword.value,
                      "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => searchKeyword.value = $event),
                      placeholder: "搜索事件标题",
                      clearable: "",
                      size: "small",
                      class: "search-input",
                      onInput: filterEvents
                    }, null, 8, ["modelValue"]),
                    createBaseVNode("div", _hoisted_2, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(filteredEvents.value, (ev) => {
                        return openBlock(), createElementBlock("div", {
                          key: ev.event_id,
                          class: normalizeClass(["event-item", { active: selectedEvent.value?.event_id === ev.event_id }]),
                          onClick: ($event) => selectEvent(ev),
                          onDblclick: ($event) => unref(router).push("/event/" + ev.event_id)
                        }, [
                          createBaseVNode("div", _hoisted_4, toDisplayString(ev.event_title), 1),
                          createBaseVNode("div", _hoisted_5, [
                            createVNode(_component_el_tag, {
                              type: riskTag(ev.risk_level),
                              size: "small"
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(riskText(ev.risk_level)), 1)
                              ]),
                              _: 2
                            }, 1032, ["type"]),
                            createBaseVNode("span", _hoisted_6, toDisplayString(ev.opinion_count) + " 条舆情", 1),
                            ev.node_count > 0 ? (openBlock(), createElementBlock("span", _hoisted_7, toDisplayString(ev.node_count) + " 节点", 1)) : createCommentVNode("", true)
                          ])
                        ], 42, _hoisted_3);
                      }), 128)),
                      filteredEvents.value.length === 0 && !loading.value ? (openBlock(), createBlock(_component_el_empty, {
                        key: 0,
                        description: "暂无事件"
                      })) : createCommentVNode("", true)
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            createVNode(_component_el_col, { span: 16 }, {
              default: withCtx(() => [
                !selectedEvent.value ? (openBlock(), createElementBlock("div", _hoisted_8, [
                  createVNode(_component_el_empty, { description: "请从左侧选择一个事件查看传播溯源" })
                ])) : (openBlock(), createElementBlock("div", _hoisted_9, [
                  createVNode(_component_el_card, { shadow: "never" }, {
                    header: withCtx(() => [
                      createBaseVNode("div", _hoisted_10, [
                        createVNode(_component_router_link, {
                          to: "/event/" + selectedEvent.value.event_id,
                          class: "dh-title-link"
                        }, {
                          default: withCtx(() => [
                            createTextVNode(toDisplayString(selectedEvent.value.event_title), 1)
                          ]),
                          _: 1
                        }, 8, ["to"]),
                        createVNode(_component_el_button, {
                          type: "warning",
                          size: "small",
                          loading: rebuilding.value,
                          onClick: handleRebuild
                        }, {
                          default: withCtx(() => [..._cache[3] || (_cache[3] = [
                            createTextVNode("构建传播链", -1)
                          ])]),
                          _: 1
                        }, 8, ["loading"])
                      ])
                    ]),
                    default: withCtx(() => [
                      graphData.value ? (openBlock(), createElementBlock("div", _hoisted_11, [
                        createBaseVNode("div", _hoisted_12, [
                          createBaseVNode("span", _hoisted_13, toDisplayString(graphData.value.total_opinions), 1),
                          _cache[4] || (_cache[4] = createBaseVNode("span", { class: "m-lab" }, "节点数", -1))
                        ]),
                        createBaseVNode("div", _hoisted_14, [
                          createBaseVNode("span", _hoisted_15, toDisplayString(graphData.value.max_depth), 1),
                          _cache[5] || (_cache[5] = createBaseVNode("span", { class: "m-lab" }, "最大传播深度", -1))
                        ]),
                        createBaseVNode("div", _hoisted_16, [
                          createBaseVNode("span", _hoisted_17, toDisplayString(graphData.value.distinct_sources), 1),
                          _cache[6] || (_cache[6] = createBaseVNode("span", { class: "m-lab" }, "来源平台数", -1))
                        ]),
                        createBaseVNode("div", _hoisted_18, [
                          createBaseVNode("span", _hoisted_19, toDisplayString(spanText.value), 1),
                          _cache[7] || (_cache[7] = createBaseVNode("span", { class: "m-lab" }, "时间跨度", -1))
                        ]),
                        createBaseVNode("div", _hoisted_20, [
                          createBaseVNode("span", _hoisted_21, toDisplayString(graphData.value.negative_ratio) + "%", 1),
                          _cache[8] || (_cache[8] = createBaseVNode("span", { class: "m-lab" }, "负面占比", -1))
                        ])
                      ])) : createCommentVNode("", true),
                      createVNode(_component_el_row, { gutter: 16 }, {
                        default: withCtx(() => [
                          createVNode(_component_el_col, { span: 24 }, {
                            default: withCtx(() => [
                              createBaseVNode("div", {
                                ref_key: "graphRef",
                                ref: graphRef,
                                class: "graph-box"
                              }, null, 512)
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_row, {
                        gutter: 16,
                        style: { "margin-top": "16px" }
                      }, {
                        default: withCtx(() => [
                          createVNode(_component_el_col, { span: 8 }, {
                            default: withCtx(() => [
                              createVNode(_component_el_card, {
                                shadow: "hover",
                                class: "mini-card"
                              }, {
                                header: withCtx(() => [..._cache[9] || (_cache[9] = [
                                  createBaseVNode("span", null, "来源分布", -1)
                                ])]),
                                default: withCtx(() => [
                                  graphData.value?.source_summary && graphData.value.source_summary.length > 0 ? (openBlock(), createElementBlock("div", _hoisted_22, [
                                    (openBlock(true), createElementBlock(Fragment, null, renderList(graphData.value.source_summary, (s) => {
                                      return openBlock(), createElementBlock("div", {
                                        key: s.source,
                                        class: "source-item"
                                      }, [
                                        createBaseVNode("span", _hoisted_23, toDisplayString(s.source || "未知"), 1),
                                        createVNode(_component_el_progress, {
                                          percentage: Math.round(s.count / graphData.value.total_opinions * 100),
                                          "stroke-width": 8,
                                          "show-text": false
                                        }, null, 8, ["percentage"]),
                                        createBaseVNode("span", _hoisted_24, toDisplayString(s.count), 1)
                                      ]);
                                    }), 128))
                                  ])) : (openBlock(), createBlock(_component_el_empty, {
                                    key: 1,
                                    description: "暂无传播数据"
                                  }))
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          }),
                          createVNode(_component_el_col, { span: 8 }, {
                            default: withCtx(() => [
                              createVNode(_component_el_card, {
                                shadow: "hover",
                                class: "mini-card"
                              }, {
                                header: withCtx(() => [..._cache[10] || (_cache[10] = [
                                  createBaseVNode("span", null, "情感分布", -1)
                                ])]),
                                default: withCtx(() => [
                                  createBaseVNode("div", {
                                    ref_key: "sentimentRef",
                                    ref: sentimentRef,
                                    class: "mini-chart"
                                  }, null, 512)
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          }),
                          createVNode(_component_el_col, { span: 8 }, {
                            default: withCtx(() => [
                              createVNode(_component_el_card, {
                                shadow: "hover",
                                class: "mini-card"
                              }, {
                                header: withCtx(() => [..._cache[11] || (_cache[11] = [
                                  createBaseVNode("span", null, "传播深度", -1)
                                ])]),
                                default: withCtx(() => [
                                  createBaseVNode("div", {
                                    ref_key: "depthRef",
                                    ref: depthRef,
                                    class: "mini-chart"
                                  }, null, 512)
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_card, {
                        shadow: "hover",
                        class: "timeline-card"
                      }, {
                        header: withCtx(() => [..._cache[12] || (_cache[12] = [
                          createBaseVNode("span", null, "传播时间线", -1)
                        ])]),
                        default: withCtx(() => [
                          timelineData.value.length > 0 ? (openBlock(), createElementBlock("div", _hoisted_25, [
                            (openBlock(true), createElementBlock(Fragment, null, renderList(timelineData.value, (t) => {
                              return openBlock(), createElementBlock("div", {
                                key: t.time,
                                class: "tl-item"
                              }, [
                                _cache[13] || (_cache[13] = createBaseVNode("div", { class: "tl-dot" }, null, -1)),
                                createBaseVNode("div", _hoisted_26, [
                                  createBaseVNode("div", _hoisted_27, toDisplayString(t.time), 1),
                                  createBaseVNode("div", _hoisted_28, toDisplayString(t.title), 1),
                                  createBaseVNode("div", _hoisted_29, toDisplayString(t.source), 1)
                                ])
                              ]);
                            }), 128))
                          ])) : (openBlock(), createBlock(_component_el_empty, {
                            key: 1,
                            description: "暂无时间线数据"
                          }))
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]))
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Propagation = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-06ee018f"]]);

export { Propagation as default };
