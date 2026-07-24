import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, B as createVNode, z as withCtx, r as ref, g as api, E as ElMessage, C as resolveComponent, D as resolveDirective, o as openBlock, b as withKeys, e as createTextVNode, t as toDisplayString, a as createBaseVNode, _ as _export_sfc } from './index-iT_24xn-.js';

const _hoisted_1 = { class: "logs-page" };
const _hoisted_2 = { class: "pagination" };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "LoginLogs",
  setup(__props) {
    const loading = ref(false);
    const logs = ref([]);
    const total = ref(0);
    const page = ref(1);
    const size = ref(20);
    const username = ref("");
    const status = ref("");
    function fmt(t) {
      return t ? t.replace("T", " ").slice(0, 19) : "-";
    }
    function statusTag(s) {
      if (s === "success") return "success";
      if (s === "failed") return "danger";
      return "info";
    }
    function statusText(s) {
      return { success: "成功", failed: "失败", logout: "退出" }[s] || s;
    }
    function idxFn(i) {
      return (page.value - 1) * size.value + i + 1;
    }
    async function reload() {
      loading.value = true;
      try {
        const params = { page: page.value, size: size.value };
        if (username.value) params.username = username.value;
        if (status.value) params.status = status.value;
        const { data } = await api.get("/login-logs", { params });
        logs.value = data.items || [];
        total.value = data.total || 0;
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载登录日志失败");
      } finally {
        loading.value = false;
      }
    }
    function onPage(p) {
      page.value = p;
      reload();
    }
    function resetFilters() {
      username.value = "";
      status.value = "";
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
              modelValue: username.value,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => username.value = $event),
              placeholder: "用户名",
              clearable: "",
              style: { "width": "200px" },
              onKeyup: withKeys(reload, ["enter"]),
              onClear: reload
            }, null, 8, ["modelValue"]),
            createVNode(_component_el_select, {
              modelValue: status.value,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => status.value = $event),
              placeholder: "登录结果",
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
                }),
                createVNode(_component_el_option, {
                  label: "退出",
                  value: "logout"
                })
              ]),
              _: 1
            }, 8, ["modelValue"]),
            createVNode(_component_el_button, {
              type: "primary",
              style: { "margin-left": "12px" },
              onClick: reload
            }, {
              default: withCtx(() => [..._cache[2] || (_cache[2] = [
                createTextVNode("查询", -1)
              ])]),
              _: 1
            }),
            createVNode(_component_el_button, { onClick: resetFilters }, {
              default: withCtx(() => [..._cache[3] || (_cache[3] = [
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
              "empty-text": "暂无登录日志"
            }, {
              default: withCtx(() => [
                createVNode(_component_el_table_column, {
                  type: "index",
                  index: idxFn,
                  label: "ID",
                  width: "70"
                }),
                createVNode(_component_el_table_column, {
                  prop: "username",
                  label: "用户名",
                  "min-width": "140",
                  "show-overflow-tooltip": ""
                }),
                createVNode(_component_el_table_column, {
                  label: "登录时间",
                  "min-width": "180"
                }, {
                  default: withCtx(({ row }) => [
                    createTextVNode(toDisplayString(fmt(row.login_at)), 1)
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
                  label: "登录结果",
                  width: "120",
                  align: "center"
                }, {
                  default: withCtx(({ row }) => [
                    createVNode(_component_el_tag, {
                      type: statusTag(row.status),
                      size: "small"
                    }, {
                      default: withCtx(() => [
                        createTextVNode(toDisplayString(statusText(row.status)), 1)
                      ]),
                      _: 2
                    }, 1032, ["type"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_table_column, {
                  prop: "failure_reason",
                  label: "失败原因",
                  "min-width": "160",
                  "show-overflow-tooltip": ""
                }),
                createVNode(_component_el_table_column, {
                  prop: "user_agent",
                  label: "用户代理 / 设备",
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

const LoginLogs = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-f39b70e0"]]);

export { LoginLogs as default };
