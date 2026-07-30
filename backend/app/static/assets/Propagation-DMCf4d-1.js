import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, B as createVNode, z as withCtx, y as createBlock, r as ref, g as api, E as ElMessage, C as resolveComponent, D as resolveDirective, o as openBlock, F as Fragment, i as renderList, n as normalizeClass, t as toDisplayString, A as createCommentVNode, e as createTextVNode, j as computed, _ as _export_sfc } from './index-Dq0JQtV9.js';

const _hoisted_1 = { class: "source-time-view" };
const _hoisted_2 = { class: "layout" };
const _hoisted_3 = { class: "card-title-row" };
const _hoisted_4 = { class: "event-list" };
const _hoisted_5 = ["onClick"];
const _hoisted_6 = { class: "event-title" };
const _hoisted_7 = { class: "event-meta" };
const _hoisted_8 = {
  key: 0,
  class: "summary-grid"
};
const _hoisted_9 = {
  key: 1,
  class: "columns"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Propagation",
  setup(__props) {
    const loading = ref(false);
    const searchKeyword = ref("");
    const events = ref([]);
    const selectedEvent = ref(null);
    const graphData = ref(null);
    const filteredEvents = computed(() => {
      const value = searchKeyword.value.trim().toLowerCase();
      return value ? events.value.filter((item) => item.event_title.toLowerCase().includes(value)) : events.value;
    });
    const spanText = computed(() => {
      if (!graphData.value?.first_time) return "-";
      const first = formatDate(graphData.value.first_time);
      const last = formatDate(graphData.value.last_time || graphData.value.first_time);
      return first === last ? first : `${first} ~ ${last}`;
    });
    const timelineData = computed(() => (graphData.value?.nodes || []).filter((node) => node.publish_time).sort((a, b) => String(a.publish_time).localeCompare(String(b.publish_time))).slice(0, 30).map((node) => ({ key: node.id, time: formatDate(node.publish_time), title: node.title, source: node.source })));
    function formatDate(value) {
      return value ? value.replace("T", " ").slice(0, 19) : "-";
    }
    async function loadEvents() {
      loading.value = true;
      try {
        const { data } = await api.get("/propagation/events");
        events.value = data || [];
        if (!selectedEvent.value && events.value.length) await selectEvent(events.value[0]);
      } catch (error) {
        ElMessage.error(error?.response?.data?.detail || "加载事件失败");
      } finally {
        loading.value = false;
      }
    }
    async function selectEvent(event) {
      selectedEvent.value = event;
      try {
        const { data } = await api.get(`/propagation/graph/${event.event_id}`);
        graphData.value = data;
      } catch (error) {
        graphData.value = null;
        ElMessage.error(error?.response?.data?.detail || "加载来源态势失败");
      }
    }
    onMounted(loadEvents);
    return (_ctx, _cache) => {
      const _component_el_button = resolveComponent("el-button");
      const _component_el_input = resolveComponent("el-input");
      const _component_el_empty = resolveComponent("el-empty");
      const _component_el_card = resolveComponent("el-card");
      const _component_router_link = resolveComponent("router-link");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        _cache[8] || (_cache[8] = createBaseVNode("div", { class: "page-note" }, "当前关系根据来源与时间推断，不代表真实转发关系", -1)),
        createBaseVNode("div", _hoisted_2, [
          createVNode(_component_el_card, {
            shadow: "never",
            class: "event-list-card"
          }, {
            header: withCtx(() => [
              createBaseVNode("div", _hoisted_3, [
                _cache[2] || (_cache[2] = createBaseVNode("span", null, "事件列表", -1)),
                createVNode(_component_el_button, {
                  size: "small",
                  onClick: loadEvents
                }, {
                  default: withCtx(() => [..._cache[1] || (_cache[1] = [
                    createTextVNode("刷新", -1)
                  ])]),
                  _: 1
                })
              ])
            ]),
            default: withCtx(() => [
              createVNode(_component_el_input, {
                modelValue: searchKeyword.value,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => searchKeyword.value = $event),
                placeholder: "搜索事件标题",
                clearable: "",
                size: "small"
              }, null, 8, ["modelValue"]),
              createBaseVNode("div", _hoisted_4, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(filteredEvents.value, (ev) => {
                  return openBlock(), createElementBlock("button", {
                    key: ev.event_id,
                    class: normalizeClass(["event-item", { active: selectedEvent.value?.event_id === ev.event_id }]),
                    onClick: ($event) => selectEvent(ev)
                  }, [
                    createBaseVNode("span", _hoisted_6, toDisplayString(ev.event_title), 1),
                    createBaseVNode("span", _hoisted_7, toDisplayString(ev.opinion_count) + " 条内容 · " + toDisplayString(formatDate(ev.last_time)), 1)
                  ], 10, _hoisted_5);
                }), 128)),
                !filteredEvents.value.length ? (openBlock(), createBlock(_component_el_empty, {
                  key: 0,
                  description: "暂无事件"
                })) : createCommentVNode("", true)
              ])
            ]),
            _: 1
          }),
          selectedEvent.value ? (openBlock(), createBlock(_component_el_card, {
            key: 0,
            shadow: "never",
            class: "detail-card"
          }, {
            header: withCtx(() => [
              createVNode(_component_router_link, {
                to: "/event/" + selectedEvent.value.event_id
              }, {
                default: withCtx(() => [
                  createTextVNode(toDisplayString(selectedEvent.value.event_title), 1)
                ]),
                _: 1
              }, 8, ["to"])
            ]),
            default: withCtx(() => [
              graphData.value ? (openBlock(), createElementBlock("div", _hoisted_8, [
                createBaseVNode("div", null, [
                  _cache[3] || (_cache[3] = createBaseVNode("span", null, "内容数量", -1)),
                  createBaseVNode("strong", null, toDisplayString(graphData.value.total_opinions), 1)
                ]),
                createBaseVNode("div", null, [
                  _cache[4] || (_cache[4] = createBaseVNode("span", null, "来源数量", -1)),
                  createBaseVNode("strong", null, toDisplayString(graphData.value.distinct_sources), 1)
                ]),
                createBaseVNode("div", null, [
                  _cache[5] || (_cache[5] = createBaseVNode("span", null, "时间范围", -1)),
                  createBaseVNode("strong", null, toDisplayString(spanText.value), 1)
                ])
              ])) : createCommentVNode("", true),
              graphData.value ? (openBlock(), createElementBlock("div", _hoisted_9, [
                createBaseVNode("section", null, [
                  _cache[6] || (_cache[6] = createBaseVNode("h3", null, "来源分布", -1)),
                  (openBlock(true), createElementBlock(Fragment, null, renderList(graphData.value.source_summary, (item) => {
                    return openBlock(), createElementBlock("div", {
                      key: item.source,
                      class: "source-row"
                    }, [
                      createBaseVNode("span", null, toDisplayString(item.source || "未知"), 1),
                      createBaseVNode("b", null, toDisplayString(item.count), 1)
                    ]);
                  }), 128)),
                  !graphData.value.source_summary.length ? (openBlock(), createBlock(_component_el_empty, {
                    key: 0,
                    description: "暂无来源数据"
                  })) : createCommentVNode("", true)
                ]),
                createBaseVNode("section", null, [
                  _cache[7] || (_cache[7] = createBaseVNode("h3", null, "时间态势", -1)),
                  (openBlock(true), createElementBlock(Fragment, null, renderList(timelineData.value, (item) => {
                    return openBlock(), createElementBlock("div", {
                      key: item.key,
                      class: "timeline-row"
                    }, [
                      createBaseVNode("time", null, toDisplayString(item.time), 1),
                      createBaseVNode("span", null, toDisplayString(item.title), 1),
                      createBaseVNode("small", null, toDisplayString(item.source), 1)
                    ]);
                  }), 128)),
                  !timelineData.value.length ? (openBlock(), createBlock(_component_el_empty, {
                    key: 0,
                    description: "暂无时间数据"
                  })) : createCommentVNode("", true)
                ])
              ])) : createCommentVNode("", true)
            ]),
            _: 1
          })) : (openBlock(), createBlock(_component_el_empty, {
            key: 1,
            description: "请选择一个事件查看来源与时间态势",
            class: "empty-detail"
          }))
        ])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Propagation = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-d1971b87"]]);

export { Propagation as default };
