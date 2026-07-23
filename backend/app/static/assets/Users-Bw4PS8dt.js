import { d as defineComponent, u as useAuthStore, l as usePermission, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, b as withKeys, v as vModelText, G as vModelSelect, x as unref, A as createCommentVNode, F as Fragment, i as renderList, J as withModifiers, t as toDisplayString, r as ref, g as api, E as ElMessage, D as resolveDirective, o as openBlock, n as normalizeClass, O as ElMessageBox, _ as _export_sfc } from './index-DlEJu5JL.js';

const _hoisted_1 = { class: "users-page" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = { class: "tools" };
const _hoisted_4 = { class: "card" };
const _hoisted_5 = { class: "tbl" };
const _hoisted_6 = {
  key: 0,
  class: "pill pill-purple"
};
const _hoisted_7 = {
  key: 1,
  class: "muted"
};
const _hoisted_8 = { class: "ops" };
const _hoisted_9 = ["onClick", "disabled"];
const _hoisted_10 = ["onClick", "disabled"];
const _hoisted_11 = ["onClick", "disabled"];
const _hoisted_12 = { key: 0 };
const _hoisted_13 = { class: "modal" };
const _hoisted_14 = { class: "form-group" };
const _hoisted_15 = ["disabled"];
const _hoisted_16 = { class: "form-group" };
const _hoisted_17 = { class: "form-group" };
const _hoisted_18 = { class: "form-group" };
const _hoisted_19 = { class: "form-actions" };
const _hoisted_20 = ["disabled"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Users",
  setup(__props) {
    const authStore = useAuthStore();
    const { hasPermission } = usePermission();
    const canWrite = hasPermission("users:write");
    const canActivate = hasPermission("users:activate");
    const loading = ref(false);
    const saving = ref(false);
    const users = ref([]);
    const searchKey = ref("");
    const roleFilter = ref("");
    const showForm = ref(false);
    const editingId = ref(null);
    const form = ref({ username: "", display_name: "", password: "", role: "analyst" });
    function rolePill(r) {
      return { admin: "pill-blue", analyst: "pill-green", viewer: "pill-gray" }[r] || "pill-gray";
    }
    function roleText(r) {
      return { admin: "管理员", analyst: "分析员", viewer: "观察员" }[r] || r;
    }
    function isSelf(u) {
      return u.username === authStore.username;
    }
    async function loadUsers() {
      loading.value = true;
      try {
        const { data } = await api.get("/users", {
          params: { search: searchKey.value || void 0, role: roleFilter.value || void 0, size: 200 }
        });
        users.value = data.items || [];
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载失败");
      } finally {
        loading.value = false;
      }
    }
    function onSearch() {
      loadUsers();
    }
    function openAdd() {
      editingId.value = null;
      form.value = { username: "", display_name: "", password: "", role: "analyst" };
      showForm.value = true;
    }
    function openEdit(u) {
      editingId.value = u.id;
      form.value = { username: u.username, display_name: u.display_name || "", password: "", role: u.role };
      showForm.value = true;
    }
    async function handleSave() {
      if (!form.value.username) return ElMessage.warning("请输入用户名");
      if (!editingId.value && !form.value.password) return ElMessage.warning("请输入密码");
      saving.value = true;
      try {
        const payload = { role: form.value.role };
        if (form.value.display_name) payload.display_name = form.value.display_name;
        if (form.value.password) payload.password = form.value.password;
        if (editingId.value) {
          await api.put("/users/" + editingId.value, payload);
          ElMessage.success("更新成功");
        } else {
          await api.post("/users", { username: form.value.username, password: form.value.password, role: form.value.role, display_name: form.value.display_name || void 0 });
          ElMessage.success("创建成功");
        }
        showForm.value = false;
        await loadUsers();
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "操作失败");
      } finally {
        saving.value = false;
      }
    }
    async function toggleActive(u) {
      if (isSelf(u)) return ElMessage.warning("不能操作当前登录账号");
      const action = u.is_active ? "停用" : "启用";
      try {
        await ElMessageBox.confirm(`确认${action}用户 ${u.username}？`, "提示", { type: "warning" });
        const url = u.is_active ? `/users/${u.id}/deactivate` : `/users/${u.id}/activate`;
        const { data } = await api.post(url);
        ElMessage.success(`${action}成功`);
        const idx = users.value.findIndex((x) => x.id === u.id);
        if (idx >= 0) users.value[idx] = { ...users.value[idx], ...data };
      } catch (e) {
        if (e !== "cancel" && e?.response) ElMessage.error(e?.response?.data?.detail || `${action}失败`);
      }
    }
    async function handleDelete(u) {
      if (u.username === "admin") return ElMessage.warning("内置管理员不可删除");
      if (isSelf(u)) return ElMessage.warning("不能删除当前登录账号");
      try {
        await ElMessageBox.confirm("确认删除用户 " + u.username + "？此操作不可恢复", "警告", { type: "warning" });
        await api.delete("/users/" + u.id);
        ElMessage.success("已删除");
        await loadUsers();
      } catch (e) {
        if (e !== "cancel" && e?.response) ElMessage.error(e?.response?.data?.detail || "删除失败");
      }
    }
    onMounted(loadUsers);
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          _cache[9] || (_cache[9] = createBaseVNode("h3", { class: "section-title" }, "用户管理", -1)),
          createBaseVNode("div", _hoisted_3, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => searchKey.value = $event),
              class: "input input-search",
              placeholder: "搜索用户名",
              onKeyup: withKeys(onSearch, ["enter"])
            }, null, 544), [
              [vModelText, searchKey.value]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => roleFilter.value = $event),
              class: "input input-select",
              onChange: onSearch
            }, [..._cache[8] || (_cache[8] = [
              createBaseVNode("option", { value: "" }, "全部角色", -1),
              createBaseVNode("option", { value: "admin" }, "管理员", -1),
              createBaseVNode("option", { value: "analyst" }, "分析员", -1),
              createBaseVNode("option", { value: "viewer" }, "观察员", -1)
            ])], 544), [
              [vModelSelect, roleFilter.value]
            ]),
            createBaseVNode("button", {
              class: "btn",
              onClick: onSearch
            }, "查询"),
            unref(canWrite) ? (openBlock(), createElementBlock("button", {
              key: 0,
              class: "btn btn-primary",
              onClick: openAdd
            }, "+ 新增用户")) : createCommentVNode("", true)
          ])
        ]),
        createBaseVNode("div", _hoisted_4, [
          createBaseVNode("table", _hoisted_5, [
            _cache[11] || (_cache[11] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "用户名"),
                createBaseVNode("th", null, "显示名"),
                createBaseVNode("th", null, "角色"),
                createBaseVNode("th", null, "状态"),
                createBaseVNode("th", null, "超管"),
                createBaseVNode("th", null, "最后登录"),
                createBaseVNode("th", null, "创建时间"),
                createBaseVNode("th", null, "操作")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(users.value, (u) => {
                return openBlock(), createElementBlock("tr", {
                  key: u.id
                }, [
                  createBaseVNode("td", null, toDisplayString(u.username), 1),
                  createBaseVNode("td", null, toDisplayString(u.display_name || "-"), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", rolePill(u.role)])
                    }, toDisplayString(roleText(u.role)), 3)
                  ]),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", u.is_active ? "pill-green" : "pill-red"])
                    }, toDisplayString(u.is_active ? "正常" : "禁用"), 3)
                  ]),
                  createBaseVNode("td", null, [
                    u.is_superuser ? (openBlock(), createElementBlock("span", _hoisted_6, "超管")) : (openBlock(), createElementBlock("span", _hoisted_7, "-"))
                  ]),
                  createBaseVNode("td", null, toDisplayString(u.last_login ? new Date(u.last_login).toLocaleString("zh-CN") : "-"), 1),
                  createBaseVNode("td", null, toDisplayString(new Date(u.created_at).toLocaleDateString("zh-CN")), 1),
                  createBaseVNode("td", _hoisted_8, [
                    unref(canActivate) ? (openBlock(), createElementBlock("button", {
                      key: 0,
                      class: "btn btn-mini",
                      onClick: ($event) => toggleActive(u),
                      disabled: isSelf(u)
                    }, toDisplayString(u.is_active ? "停用" : "启用"), 9, _hoisted_9)) : createCommentVNode("", true),
                    unref(canWrite) ? (openBlock(), createElementBlock("button", {
                      key: 1,
                      class: "btn btn-mini",
                      onClick: ($event) => openEdit(u),
                      disabled: isSelf(u) && false
                    }, "编辑", 8, _hoisted_10)) : createCommentVNode("", true),
                    unref(canWrite) ? (openBlock(), createElementBlock("button", {
                      key: 2,
                      class: "btn btn-mini btn-danger",
                      onClick: ($event) => handleDelete(u),
                      disabled: u.username === "admin" || isSelf(u)
                    }, "删除", 8, _hoisted_11)) : createCommentVNode("", true)
                  ])
                ]);
              }), 128)),
              !users.value.length ? (openBlock(), createElementBlock("tr", _hoisted_12, [..._cache[10] || (_cache[10] = [
                createBaseVNode("td", {
                  colspan: "8",
                  class: "empty-row"
                }, "暂无用户", -1)
              ])])) : createCommentVNode("", true)
            ])
          ])
        ]),
        showForm.value ? (openBlock(), createElementBlock("div", {
          key: 0,
          class: "modal-overlay",
          onClick: _cache[7] || (_cache[7] = withModifiers(($event) => showForm.value = false, ["self"]))
        }, [
          createBaseVNode("div", _hoisted_13, [
            createBaseVNode("h3", null, toDisplayString(editingId.value ? "编辑用户" : "新增用户"), 1),
            createBaseVNode("div", _hoisted_14, [
              _cache[12] || (_cache[12] = createBaseVNode("label", null, "用户名", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => form.value.username = $event),
                class: "input",
                disabled: !!editingId.value
              }, null, 8, _hoisted_15), [
                [vModelText, form.value.username]
              ])
            ]),
            createBaseVNode("div", _hoisted_16, [
              _cache[13] || (_cache[13] = createBaseVNode("label", null, "显示名", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => form.value.display_name = $event),
                class: "input",
                placeholder: "可选"
              }, null, 512), [
                [vModelText, form.value.display_name]
              ])
            ]),
            createBaseVNode("div", _hoisted_17, [
              createBaseVNode("label", null, "密码" + toDisplayString(editingId.value ? "（留空不修改）" : ""), 1),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => form.value.password = $event),
                type: "password",
                class: "input"
              }, null, 512), [
                [vModelText, form.value.password]
              ])
            ]),
            createBaseVNode("div", _hoisted_18, [
              _cache[15] || (_cache[15] = createBaseVNode("label", null, "角色", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => form.value.role = $event),
                class: "input"
              }, [..._cache[14] || (_cache[14] = [
                createBaseVNode("option", { value: "admin" }, "管理员", -1),
                createBaseVNode("option", { value: "analyst" }, "分析员", -1),
                createBaseVNode("option", { value: "viewer" }, "观察员", -1)
              ])], 512), [
                [vModelSelect, form.value.role]
              ])
            ]),
            createBaseVNode("div", _hoisted_19, [
              createBaseVNode("button", {
                class: "btn",
                onClick: _cache[6] || (_cache[6] = ($event) => showForm.value = false)
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-primary",
                onClick: handleSave,
                disabled: saving.value
              }, toDisplayString(saving.value ? "保存中..." : "保存"), 9, _hoisted_20)
            ])
          ])
        ])) : createCommentVNode("", true)
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Users = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-faafaccc"]]);

export { Users as default };
