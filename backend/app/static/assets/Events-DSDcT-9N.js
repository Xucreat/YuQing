const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/index-kW2pJJHk.css"])))=>i.map(i=>d[i]);
import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, t as toDisplayString, A as createCommentVNode, F as Fragment, i as renderList, r as ref, j as computed, g as api, E as ElMessage, D as resolveDirective, o as openBlock, n as normalizeClass, e as createTextVNode, I as withModifiers, J as __vitePreload, _ as _export_sfc } from './index-C6UycfoG.js';

const _hoisted_1 = { class: "events" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = ["disabled"];
const _hoisted_4 = {
  key: 0,
  class: "agg-result"
};
const _hoisted_5 = { class: "card table-card" };
const _hoisted_6 = { class: "tbl" };
const _hoisted_7 = ["onClick"];
const _hoisted_8 = { class: "t-title" };
const _hoisted_9 = { class: "col-center" };
const _hoisted_10 = { class: "col-center risk-num" };
const _hoisted_11 = { class: "col-center" };
const _hoisted_12 = { class: "pill pill-green" };
const _hoisted_13 = ["onClick"];
const _hoisted_14 = { key: 0 };
const _hoisted_15 = {
  key: 0,
  class: "pager"
};
const _hoisted_16 = { class: "p-info" };
const _hoisted_17 = ["disabled"];
const _hoisted_18 = ["onClick"];
const _hoisted_19 = ["disabled"];
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
    function formatTime(t) {
      if (!t) return "-";
      return t.replace("T", " ").slice(0, 19);
    }
    async function loadData() {
      loading.value = true;
      try {
        const { data } = await api.get("/events", { params: { page: page.value, size: size.value } });
        rows.value = data.items;
        total.value = data.total;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载事件列表失败");
      } finally {
        loading.value = false;
      }
    }
    async function handleAggregate() {
      if (aggregating.value) return;
      aggregating.value = true;
      try {
        const { data } = await api.post("/events/aggregate");
        lastResult.value = data;
        ElMessage.success("聚合完成：新建 " + data.created + "，更新 " + data.updated + "，关联 " + data.linked);
        page.value = 1;
        await loadData();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "聚合失败");
      } finally {
        aggregating.value = false;
      }
    }
    async function handleDelete(row) {
      try {
        const { ElMessageBox } = await __vitePreload(async () => { const { ElMessageBox } = await import('./index-C6UycfoG.js').then(n => n.M);return { ElMessageBox }},true?__vite__mapDeps([0]):void 0);
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
          createBaseVNode("button", {
            class: "btn btn-ghost",
            disabled: aggregating.value,
            onClick: handleAggregate
          }, toDisplayString(aggregating.value ? "聚合中..." : "手动聚合"), 9, _hoisted_3),
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: loadData
          }, "刷新"),
          lastResult.value ? (openBlock(), createElementBlock("span", _hoisted_4, " 聚合成功：新建 " + toDisplayString(lastResult.value.created) + " · 更新 " + toDisplayString(lastResult.value.updated) + " · 关联 " + toDisplayString(lastResult.value.linked), 1)) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_5, [
          createBaseVNode("table", _hoisted_6, [
            _cache[6] || (_cache[6] = createBaseVNode("thead", null, [
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
                    createBaseVNode("span", _hoisted_8, toDisplayString(row.title), 1)
                  ]),
                  createBaseVNode("td", _hoisted_9, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", riskPill(row.risk_level)])
                    }, [
                      _cache[3] || (_cache[3] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(riskText(row.risk_level)), 1)
                    ], 2)
                  ]),
                  createBaseVNode("td", _hoisted_10, toDisplayString(row.opinion_count), 1),
                  createBaseVNode("td", _hoisted_11, [
                    createBaseVNode("span", _hoisted_12, [
                      _cache[4] || (_cache[4] = createBaseVNode("span", { class: "dot" }, null, -1)),
                      createTextVNode(toDisplayString(row.status), 1)
                    ])
                  ]),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.first_time)), 1),
                  createBaseVNode("td", null, toDisplayString(formatTime(row.last_time)), 1),
                  createBaseVNode("td", {
                    class: "col-center",
                    onClick: _cache[0] || (_cache[0] = withModifiers(() => {
                    }, ["stop"]))
                  }, [
                    createBaseVNode("button", {
                      class: "btn-icon btn-delete",
                      title: "删除事件",
                      onClick: ($event) => handleDelete(row)
                    }, "🗑", 8, _hoisted_13)
                  ])
                ], 8, _hoisted_7);
              }), 128)),
              rows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_14, [..._cache[5] || (_cache[5] = [
                createBaseVNode("td", {
                  colspan: "8",
                  class: "empty-row"
                }, "暂无事件数据", -1)
              ])])) : createCommentVNode("", true)
            ])
          ]),
          total.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_15, [
            createBaseVNode("span", _hoisted_16, "共 " + toDisplayString(total.value) + " 条", 1),
            createBaseVNode("button", {
              disabled: page.value <= 1,
              onClick: _cache[1] || (_cache[1] = ($event) => {
                page.value--;
                loadData();
              })
            }, "‹", 8, _hoisted_17),
            (openBlock(true), createElementBlock(Fragment, null, renderList(pages.value, (p) => {
              return openBlock(), createElementBlock("button", {
                key: p,
                class: normalizeClass({ active: p === page.value }),
                onClick: ($event) => {
                  page.value = p;
                  loadData();
                }
              }, toDisplayString(p), 11, _hoisted_18);
            }), 128)),
            createBaseVNode("button", {
              disabled: page.value >= maxPage.value,
              onClick: _cache[2] || (_cache[2] = ($event) => {
                page.value++;
                loadData();
              })
            }, "›", 8, _hoisted_19)
          ])) : createCommentVNode("", true)
        ])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Events = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-a6634619"]]);

export { Events as default };
