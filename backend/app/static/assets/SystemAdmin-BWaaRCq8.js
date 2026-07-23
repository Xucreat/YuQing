import { d as defineComponent, l as usePermission, r as ref, m as watch, c as createElementBlock, B as createVNode, z as withCtx, a as createBaseVNode, y as createBlock, j as computed, C as resolveComponent, o as openBlock, A as createCommentVNode, H as useRoute, h as useRouter, _ as _export_sfc } from './index-BLa-krQZ.js';

const _hoisted_1 = { class: "sys-admin" };
const _hoisted_2 = { class: "sys-body" };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "SystemAdmin",
  setup(__props) {
    const route = useRoute();
    const router = useRouter();
    const { hasPermission } = usePermission();
    const TABS = ["users", "roles", "login-logs", "operation-logs"];
    const canUsers = computed(() => hasPermission("users:read"));
    const canRoles = computed(() => hasPermission("roles:read"));
    const canLoginLogs = computed(() => hasPermission("login_logs:read"));
    const canOperationLogs = computed(() => hasPermission("audit_logs:read"));
    const hasAny = computed(
      () => canUsers.value || canRoles.value || canLoginLogs.value || canOperationLogs.value
    );
    const firstPermitted = computed(() => {
      if (canUsers.value) return "users";
      if (canRoles.value) return "roles";
      if (canLoginLogs.value) return "login-logs";
      return "operation-logs";
    });
    const activeTab = ref(firstPermitted.value);
    watch(
      () => route.path,
      (p) => {
        const seg = p.split("/")[2] || "";
        if (TABS.includes(seg)) activeTab.value = seg;
      },
      { immediate: true }
    );
    function onTabChange(name) {
      router.push("/system/" + name);
    }
    return (_ctx, _cache) => {
      const _component_el_tab_pane = resolveComponent("el-tab-pane");
      const _component_el_tabs = resolveComponent("el-tabs");
      const _component_router_view = resolveComponent("router-view");
      const _component_el_empty = resolveComponent("el-empty");
      return openBlock(), createElementBlock("div", _hoisted_1, [
        createVNode(_component_el_tabs, {
          modelValue: activeTab.value,
          "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => activeTab.value = $event),
          class: "sys-tabs",
          onTabChange
        }, {
          default: withCtx(() => [
            canUsers.value ? (openBlock(), createBlock(_component_el_tab_pane, {
              key: 0,
              label: "用户管理",
              name: "users"
            })) : createCommentVNode("", true),
            canRoles.value ? (openBlock(), createBlock(_component_el_tab_pane, {
              key: 1,
              label: "角色权限",
              name: "roles"
            })) : createCommentVNode("", true),
            canLoginLogs.value ? (openBlock(), createBlock(_component_el_tab_pane, {
              key: 2,
              label: "登录日志",
              name: "login-logs"
            })) : createCommentVNode("", true),
            canOperationLogs.value ? (openBlock(), createBlock(_component_el_tab_pane, {
              key: 3,
              label: "操作日志",
              name: "operation-logs"
            })) : createCommentVNode("", true)
          ]),
          _: 1
        }, 8, ["modelValue"]),
        createBaseVNode("div", _hoisted_2, [
          hasAny.value ? (openBlock(), createBlock(_component_router_view, { key: 0 })) : (openBlock(), createBlock(_component_el_empty, {
            key: 1,
            description: "当前账号无系统管理权限"
          }))
        ])
      ]);
    };
  }
});

const SystemAdmin = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-fb77184d"]]);

export { SystemAdmin as default };
