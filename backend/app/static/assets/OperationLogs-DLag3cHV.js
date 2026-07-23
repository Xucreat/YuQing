import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, B as createVNode, z as withCtx, r as ref, g as api, E as ElMessage, C as resolveComponent, D as resolveDirective, o as openBlock, b as withKeys, e as createTextVNode, t as toDisplayString, a as createBaseVNode, _ as _export_sfc } from './index-DlEJu5JL.js';

const _hoisted_1 = { class: "logs-page" };
const _hoisted_2 = { class: "pagination" };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "OperationLogs",
  setup(__props) {
    const loading = ref(false);
    const logs = ref([]);
    const total = ref(0);
    const page = ref(1);
    const size = ref(20);
    const operator = ref("");
    const action = ref("");
    const result = ref("");
    function fmt(t) {
      return t ? t.replace("T", " ").slice(0, 19) : "-";
    }
    function actionTag(a) {
      if (a === "DELETE" || a === "ROLE_DELETE") return "danger";
      if (a === "CREATE" || a === "ROLE_CREATE") return "success";
      if (a === "PASSWORD_RESET") return "warning";
      return "info";
    }
    function idxFn(i) {
      return (page.value - 1) * size.value + i + 1;
    }
    async function reload() {
      loading.value = true;
      try {
        const params = { page: page.value, size: size.value };
        if (operator.value) params.operator = operator.value;
        if (action.value) params.action = action.value;
        if (result.value) params.result = result.value;
        const { data } = await api.get("/operation-logs", { params });
        logs.value = data.items || [];
        total.value = data.total || 0;
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载操作日志失败");
      } finally {
        loading.value = false;
      }
    }
    function onPage(p) {
      page.value = p;
      reload();
    }
    function resetFilters() {
      operator.value = "";
      action.value = "";
      result.value = "";
      page.value = 1;
      reload();
    }
    onMounted(reload);
    return (_ctx, _cache) => {
      const _component_el_input = resolveComponent("el-input");
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_button = resolveComponent("el-button");
      const _component_el_card = resolveComponent("el-card");
      const _component_el_table_column = resolveComponent("el-table-column");
      const _component_el_tag = resolveComponent("el-tag");
      const _component_el_table = resolveComponent("el-table");
      const _component_el_pagination = resolveComponent("el-pagination");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createVNode(_component_el_card, {
          shadow: "never",
          class: "filter-card"
        }, {
          default: withCtx(() => [
            createVNode(_component_el_input, {
              modelValue: operator.value,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => operator.value = $event),
              placeholder: "操作人",
              clearable: "",
              style: { "width": "180px" },
              onKeyup: withKeys(reload, ["enter"]),
              onClear: reload
            }, null, 8, ["modelValue"]),
            createVNode(_component_el_input, {
              modelValue: action.value,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => action.value = $event),
              placeholder: "操作类型 (如 CREATE/UPDATE/DELETE)",
              clearable: "",
              style: { "width": "260px", "margin-left": "12px" },
              onKeyup: withKeys(reload, ["enter"]),
              onClear: reload
            }, null, 8, ["modelValue"]),
            createVNode(_component_el_select, {
              modelValue: result.value,
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => result.value = $event),
              placeholder: "操作结果",
              clearable: "",
              style: { "width": "160px", "margin-left": "12px" },
              onChange: reload
            }, {
              default: withCtx(() => [
                createVNode(_component_el_option, {
                  label: "成功",
                  value: "success"
                }),
                createVNode(_component_el_option, {
                  label: "失败",
                  value: "failed"
                })
              ]),
              _: 1
            }, 8, ["modelValue"]),
            createVNode(_component_el_button, {
              type: "primary",
              style: { "margin-left": "12px" },
              onClick: reload
            }, {
              default: withCtx(() => [..._cache[3] || (_cache[3] = [
                createTextVNode("查询", -1)
              ])]),
              _: 1
            }),
            createVNode(_component_el_button, { onClick: resetFilters }, {
              default: withCtx(() => [..._cache[4] || (_cache[4] = [
                createTextVNode("重置", -1)
              ])]),
              _: 1
            })
          ]),
          _: 1
        }),
        createVNode(_component_el_card, {
          shadow: "never",
          class: "table-card"
        }, {
          default: withCtx(() => [
            createVNode(_component_el_table, {
              data: logs.value,
              stripe: "",
              "empty-text": "暂无操作日志"
            }, {
              default: withCtx(() => [
                createVNode(_component_el_table_column, {
                  type: "index",
                  index: idxFn,
                  label: "ID",
                  width: "70"
                }),
                createVNode(_component_el_table_column, {
                  prop: "operator_username_snapshot",
                  label: "操作人",
                  "min-width": "140",
                  "show-overflow-tooltip": ""
                }),
                createVNode(_component_el_table_column, {
                  label: "操作类型",
                  width: "150"
                }, {
                  default: withCtx(({ row }) => [
                    createVNode(_component_el_tag, {
                      type: actionTag(row.action),
                      size: "small"
                    }, {
                      default: withCtx(() => [
                        createTextVNode(toDisplayString(row.action), 1)
                      ]),
                      _: 2
                    }, 1032, ["type"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_table_column, {
                  prop: "resource_type",
                  label: "资源类型",
                  "min-width": "130",
                  "show-overflow-tooltip": ""
                }),
                createVNode(_component_el_table_column, {
                  prop: "resource_id",
                  label: "资源 ID",
                  "min-width": "110",
                  "show-overflow-tooltip": ""
                }),
                createVNode(_component_el_table_column, {
                  label: "操作结果",
                  width: "110",
                  align: "center"
                }, {
                  default: withCtx(({ row }) => [
                    createVNode(_component_el_tag, {
                      type: row.result === "success" ? "success" : "danger",
                      size: "small"
                    }, {
                      default: withCtx(() => [
                        createTextVNode(toDisplayString(row.result === "success" ? "成功" : "失败"), 1)
                      ]),
                      _: 2
                    }, 1032, ["type"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_table_column, {
                  label: "操作时间",
                  "min-width": "180"
                }, {
                  default: withCtx(({ row }) => [
                    createTextVNode(toDisplayString(fmt(row.created_at)), 1)
                  ]),
                  _: 1
                }),
                createVNode(_component_el_table_column, {
                  prop: "ip_address",
                  label: "IP 地址",
                  "min-width": "140",
                  "show-overflow-tooltip": ""
                }),
                createVNode(_component_el_table_column, {
                  prop: "details_json",
                  label: "详情",
                  "min-width": "220",
                  "show-overflow-tooltip": ""
                })
              ]),
              _: 1
            }, 8, ["data"]),
            createBaseVNode("div", _hoisted_2, [
              createVNode(_component_el_pagination, {
                background: "",
                layout: "total, prev, pager, next",
                total: total.value,
                "current-page": page.value,
                "page-size": size.value,
                onCurrentChange: onPage
              }, null, 8, ["total", "current-page", "page-size"])
            ])
          ]),
          _: 1
        })
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const OperationLogs = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-fc9a4a9a"]]);

export { OperationLogs as default };
