import { d as defineComponent, z as usePermission, r as ref, A as watch, c as createElementBlock, q as createBlock, a as createBaseVNode, n as normalizeClass, s as createCommentVNode, Y as Teleport, j as computed, h as useRouter, o as openBlock, L as useRoute, y as resolveComponent, _ as _export_sfc } from './index-DEChr7so.js';

const _hoisted_1 = { class: "sys-admin" };
const _hoisted_2 = { class: "page-nav" };
const _hoisted_3 = { class: "head-left" };
const _hoisted_4 = { class: "view-tabs" };
const _hoisted_5 = { class: "sys-body" };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "SystemAdmin",
  setup(__props) {
    const route = useRoute();
    const router = useRouter();
    const { hasModulePermission } = usePermission();
    const TABS = ["users", "roles", "login-logs", "operation-logs"];
    const canUsers = computed(() => hasModulePermission("users"));
    const canRoles = computed(() => hasModulePermission("roles"));
    const canLoginLogs = computed(() => hasModulePermission("login_logs"));
    const canOperationLogs = computed(() => hasModulePermission("audit_logs"));
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
      const _component_router_view = resolveComponent("router-view");
      const _component_el_empty = resolveComponent("el-empty");
      return openBlock(), createElementBlock("div", _hoisted_1, [
        (openBlock(), createBlock(Teleport, { to: "#page-nav-target" }, [
          createBaseVNode("div", _hoisted_2, [
            createBaseVNode("div", _hoisted_3, [
              _cache[4] || (_cache[4] = createBaseVNode("h1", { class: "page-title" }, "系统管理", -1)),
              createBaseVNode("div", _hoisted_4, [
                canUsers.value ? (openBlock(), createElementBlock("button", {
                  key: 0,
                  class: normalizeClass(["view-tab", { active: activeTab.value === "users" }]),
                  onClick: _cache[0] || (_cache[0] = ($event) => onTabChange("users"))
                }, "用户管理", 2)) : createCommentVNode("", true),
                canRoles.value ? (openBlock(), createElementBlock("button", {
                  key: 1,
                  class: normalizeClass(["view-tab", { active: activeTab.value === "roles" }]),
                  onClick: _cache[1] || (_cache[1] = ($event) => onTabChange("roles"))
                }, "角色权限", 2)) : createCommentVNode("", true),
                canLoginLogs.value ? (openBlock(), createElementBlock("button", {
                  key: 2,
                  class: normalizeClass(["view-tab", { active: activeTab.value === "login-logs" }]),
                  onClick: _cache[2] || (_cache[2] = ($event) => onTabChange("login-logs"))
                }, "登录日志", 2)) : createCommentVNode("", true),
                canOperationLogs.value ? (openBlock(), createElementBlock("button", {
                  key: 3,
                  class: normalizeClass(["view-tab", { active: activeTab.value === "operation-logs" }]),
                  onClick: _cache[3] || (_cache[3] = ($event) => onTabChange("operation-logs"))
                }, "操作日志", 2)) : createCommentVNode("", true)
              ])
            ])
          ])
        ])),
        createBaseVNode("div", _hoisted_5, [
          hasAny.value ? (openBlock(), createBlock(_component_router_view, { key: 0 })) : (openBlock(), createBlock(_component_el_empty, {
            key: 1,
            description: "当前账号无系统管理权限"
          }))
        ])
      ]);
    };
  }
});

const SystemAdmin = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-be5fce59"]]);

export { SystemAdmin as default };
