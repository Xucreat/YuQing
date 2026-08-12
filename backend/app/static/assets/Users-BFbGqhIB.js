import { d as defineComponent, u as useAuthStore, z as usePermission, C as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, F as Fragment, i as renderList, s as createCommentVNode, L as withModifiers, t as toDisplayString, v as vModelText, J as vModelSelect, r as ref, g as api, E as ElMessage, B as resolveDirective, j as computed, o as openBlock, n as normalizeClass, H as unref, M as ElMessageBox, _ as _export_sfc } from './index-Dcs1vdKg.js';

const _hoisted_1 = { class: "users-page" };
const _hoisted_2 = { class: "card" };
const _hoisted_3 = { class: "tbl" };
const _hoisted_4 = { class: "actions" };
const _hoisted_5 = ["onClick"];
const _hoisted_6 = ["disabled", "title", "onClick"];
const _hoisted_7 = ["onClick", "disabled"];
const _hoisted_8 = { key: 0 };
const _hoisted_9 = { class: "modal" };
const _hoisted_10 = { class: "form-group" };
const _hoisted_11 = ["disabled"];
const _hoisted_12 = {
  key: 0,
  class: "form-group"
};
const _hoisted_13 = { class: "form-group" };
const _hoisted_14 = ["disabled", "title"];
const _hoisted_15 = {
  key: 0,
  class: "field-hint"
};
const _hoisted_16 = {
  key: 1,
  class: "password-row"
};
const _hoisted_17 = { class: "form-actions" };
const _hoisted_18 = ["disabled"];
const _hoisted_19 = { class: "modal" };
const _hoisted_20 = {
  key: 0,
  class: "form-group"
};
const _hoisted_21 = { class: "form-group" };
const _hoisted_22 = { class: "form-group" };
const _hoisted_23 = { class: "form-actions" };
const _hoisted_24 = ["disabled"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Users",
  setup(__props) {
    const authStore = useAuthStore();
    const { hasPermission } = usePermission();
    const canActivate = hasPermission("users:activate");
    const loading = ref(false);
    const saving = ref(false);
    const passwordSaving = ref(false);
    const userToggleId = ref(null);
    const users = ref([]);
    const showForm = ref(false);
    const showPassword = ref(false);
    const editingId = ref(null);
    const selectedUser = ref(null);
    const passwordMode = ref("admin");
    const form = ref({ username: "", password: "", role: "analyst" });
    const passwordForm = ref({ old_password: "", new_password: "", confirm_password: "" });
    const currentUsername = computed(() => authStore.username || "");
    const activeAdminCount = computed(() => users.value.filter((user) => user.role === "admin" && user.is_active).length);
    function cannotDeactivate(user) {
      return user.username === currentUsername.value || user.role === "admin" && user.is_active && activeAdminCount.value <= 1;
    }
    function deactivateDisabledReason(user) {
      if (user.username === currentUsername.value) return "当前登录用户不可停用";
      if (user.role === "admin" && user.is_active && activeAdminCount.value <= 1) return "最后一个启用中的超级管理员不可停用";
      return void 0;
    }
    function rolePill(role) {
      return { admin: "pill-blue", analyst: "pill-green", viewer: "pill-gray" }[role] || "pill-gray";
    }
    function roleText(role) {
      return { admin: "管理员", analyst: "分析员", viewer: "观察员" }[role] || role;
    }
    async function loadUsers() {
      loading.value = true;
      try {
        users.value = (await api.get("/users")).data.items || [];
      } catch (error) {
        ElMessage.error(error?.response?.data?.detail || "加载用户失败");
      } finally {
        loading.value = false;
      }
    }
    function openAdd() {
      editingId.value = null;
      selectedUser.value = null;
      form.value = { username: "", password: "", role: "analyst" };
      showForm.value = true;
    }
    function openEdit(user) {
      editingId.value = user.id;
      selectedUser.value = user;
      form.value = { username: user.username, password: "", role: user.role };
      showForm.value = true;
    }
    async function handleSave() {
      if (!form.value.username.trim()) return ElMessage.warning("请输入用户名");
      if (!editingId.value && form.value.password.length < 6) return ElMessage.warning("初始密码至少需要 6 个字符");
      saving.value = true;
      try {
        if (editingId.value) await api.put(`/users/${editingId.value}`, { role: form.value.role });
        else await api.post("/users", form.value);
        ElMessage.success(editingId.value ? "用户已更新" : "用户已创建");
        showForm.value = false;
        await loadUsers();
      } catch (error) {
        ElMessage.error(error?.response?.data?.detail || "操作失败");
      } finally {
        saving.value = false;
      }
    }
    function openPasswordDialog(user) {
      selectedUser.value = user;
      passwordMode.value = user.username === currentUsername.value ? "self" : "admin";
      passwordForm.value = { old_password: "", new_password: "", confirm_password: "" };
      showPassword.value = true;
    }
    function closePasswordDialog() {
      if (!passwordSaving.value) showPassword.value = false;
    }
    async function submitPassword() {
      const values = passwordForm.value;
      if (passwordMode.value === "self" && !values.old_password) return ElMessage.warning("请输入旧密码");
      if (!values.new_password || values.new_password.length < 6) return ElMessage.warning("新密码至少需要 6 个字符");
      if (values.new_password !== values.confirm_password) return ElMessage.warning("两次输入的新密码不一致");
      passwordSaving.value = true;
      try {
        if (passwordMode.value === "self") {
          await api.post("/users/me/password", values);
          ElMessage.success("密码修改成功，请重新登录");
          authStore.logout();
          window.location.assign("/login");
        } else {
          await api.post(`/users/${selectedUser.value.id}/reset-password`, { new_password: values.new_password });
          ElMessage.success("用户密码已重置");
          showPassword.value = false;
        }
      } catch (error) {
        ElMessage.error(error?.response?.data?.detail || "密码操作失败");
      } finally {
        passwordSaving.value = false;
      }
    }
    async function toggleUser(user) {
      if (cannotDeactivate(user)) return ElMessage.warning(deactivateDisabledReason(user) || "该用户不可停用");
      userToggleId.value = user.id;
      try {
        const action = user.is_active ? "deactivate" : "activate";
        await api.post(`/users/${user.id}/${action}`);
        ElMessage.success(user.is_active ? "用户已停用" : "用户已启用");
        await loadUsers();
      } catch (error) {
        ElMessage.error(error?.response?.data?.detail || "用户状态更新失败");
      } finally {
        userToggleId.value = null;
      }
    }
    async function handleDelete(user) {
      try {
        await ElMessageBox.confirm(`确认删除用户 ${user.username}？`, "警告", { type: "warning" });
        await api.delete(`/users/${user.id}`);
        ElMessage.success("用户已删除");
        await loadUsers();
      } catch {
      }
    }
    onMounted(loadUsers);
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", { class: "toolbar" }, [
          _cache[9] || (_cache[9] = createBaseVNode("h3", { class: "section-title" }, "用户管理", -1)),
          createBaseVNode("button", {
            class: "btn btn-primary",
            onClick: openAdd
          }, "+ 新增用户")
        ]),
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("table", _hoisted_3, [
            _cache[11] || (_cache[11] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "用户名"),
                createBaseVNode("th", null, "角色"),
                createBaseVNode("th", null, "状态"),
                createBaseVNode("th", null, "最后登录"),
                createBaseVNode("th", null, "创建时间"),
                createBaseVNode("th", null, "操作")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(users.value, (user) => {
                return openBlock(), createElementBlock("tr", {
                  key: user.id
                }, [
                  createBaseVNode("td", null, toDisplayString(user.username), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", rolePill(user.role)])
                    }, toDisplayString(roleText(user.role)), 3)
                  ]),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", user.is_active ? "pill-green" : "pill-red"])
                    }, toDisplayString(user.is_active ? "正常" : "禁用"), 3)
                  ]),
                  createBaseVNode("td", null, toDisplayString(user.last_login ? new Date(user.last_login).toLocaleString("zh-CN") : "-"), 1),
                  createBaseVNode("td", null, toDisplayString(new Date(user.created_at).toLocaleDateString("zh-CN")), 1),
                  createBaseVNode("td", _hoisted_4, [
                    createBaseVNode("button", {
                      class: "btn btn-mini",
                      onClick: ($event) => openEdit(user)
                    }, "编辑", 8, _hoisted_5),
                    unref(canActivate) ? (openBlock(), createElementBlock("button", {
                      key: 0,
                      class: normalizeClass(["btn btn-mini", { "is-disabled-action": cannotDeactivate(user) }]),
                      disabled: cannotDeactivate(user) || userToggleId.value === user.id,
                      title: deactivateDisabledReason(user),
                      onClick: ($event) => toggleUser(user)
                    }, toDisplayString(userToggleId.value === user.id ? "处理中…" : user.is_active ? "停用" : "启用"), 11, _hoisted_6)) : createCommentVNode("", true),
                    createBaseVNode("button", {
                      class: "btn btn-mini btn-danger",
                      onClick: ($event) => handleDelete(user),
                      disabled: user.username === "admin"
                    }, "删除", 8, _hoisted_7)
                  ])
                ]);
              }), 128)),
              !users.value.length ? (openBlock(), createElementBlock("tr", _hoisted_8, [..._cache[10] || (_cache[10] = [
                createBaseVNode("td", {
                  colspan: "6",
                  class: "empty-row"
                }, "暂无用户", -1)
              ])])) : createCommentVNode("", true)
            ])
          ])
        ]),
        showForm.value ? (openBlock(), createElementBlock("div", {
          key: 0,
          class: "modal-overlay",
          onClick: _cache[5] || (_cache[5] = withModifiers(($event) => showForm.value = false, ["self"]))
        }, [
          createBaseVNode("div", _hoisted_9, [
            createBaseVNode("h3", null, toDisplayString(editingId.value ? "编辑用户" : "新增用户"), 1),
            createBaseVNode("div", _hoisted_10, [
              _cache[12] || (_cache[12] = createBaseVNode("label", null, "用户名", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => form.value.username = $event),
                class: "input",
                disabled: !!editingId.value
              }, null, 8, _hoisted_11), [
                [vModelText, form.value.username]
              ])
            ]),
            !editingId.value ? (openBlock(), createElementBlock("div", _hoisted_12, [
              _cache[13] || (_cache[13] = createBaseVNode("label", null, "初始密码", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => form.value.password = $event),
                type: "password",
                class: "input",
                autocomplete: "new-password"
              }, null, 512), [
                [vModelText, form.value.password]
              ])
            ])) : createCommentVNode("", true),
            createBaseVNode("div", _hoisted_13, [
              _cache[15] || (_cache[15] = createBaseVNode("label", null, "角色", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => form.value.role = $event),
                class: "input",
                disabled: !!editingId.value && selectedUser.value?.role === "admin",
                title: editingId.value && selectedUser.value?.role === "admin" ? "管理员角色不可修改" : void 0
              }, [..._cache[14] || (_cache[14] = [
                createBaseVNode("option", { value: "admin" }, "管理员", -1),
                createBaseVNode("option", { value: "analyst" }, "分析员", -1),
                createBaseVNode("option", { value: "viewer" }, "观察员", -1)
              ])], 8, _hoisted_14), [
                [vModelSelect, form.value.role]
              ]),
              editingId.value && selectedUser.value?.role === "admin" ? (openBlock(), createElementBlock("small", _hoisted_15, "管理员角色固定，仅可修改密码。")) : createCommentVNode("", true)
            ]),
            editingId.value && selectedUser.value ? (openBlock(), createElementBlock("div", _hoisted_16, [
              _cache[16] || (_cache[16] = createBaseVNode("span", null, "密码管理", -1)),
              createBaseVNode("button", {
                class: "btn btn-mini",
                onClick: _cache[3] || (_cache[3] = ($event) => openPasswordDialog(selectedUser.value))
              }, "修改此用户密码")
            ])) : createCommentVNode("", true),
            createBaseVNode("div", _hoisted_17, [
              createBaseVNode("button", {
                class: "btn",
                onClick: _cache[4] || (_cache[4] = ($event) => showForm.value = false)
              }, "关闭"),
              !(editingId.value && selectedUser.value?.role === "admin") ? (openBlock(), createElementBlock("button", {
                key: 0,
                class: "btn btn-primary",
                onClick: handleSave,
                disabled: saving.value
              }, toDisplayString(saving.value ? "保存中..." : "保存"), 9, _hoisted_18)) : createCommentVNode("", true)
            ])
          ])
        ])) : createCommentVNode("", true),
        showPassword.value ? (openBlock(), createElementBlock("div", {
          key: 1,
          class: "modal-overlay",
          onClick: withModifiers(closePasswordDialog, ["self"])
        }, [
          createBaseVNode("div", _hoisted_19, [
            createBaseVNode("h3", null, toDisplayString(passwordMode.value === "self" ? "修改我的密码" : `重置 ${selectedUser.value?.username || ""} 的密码`), 1),
            passwordMode.value === "self" ? (openBlock(), createElementBlock("div", _hoisted_20, [
              _cache[17] || (_cache[17] = createBaseVNode("label", null, "旧密码", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => passwordForm.value.old_password = $event),
                type: "password",
                class: "input",
                autocomplete: "current-password"
              }, null, 512), [
                [vModelText, passwordForm.value.old_password]
              ])
            ])) : createCommentVNode("", true),
            createBaseVNode("div", _hoisted_21, [
              _cache[18] || (_cache[18] = createBaseVNode("label", null, "新密码", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => passwordForm.value.new_password = $event),
                type: "password",
                class: "input",
                autocomplete: "new-password"
              }, null, 512), [
                [vModelText, passwordForm.value.new_password]
              ])
            ]),
            createBaseVNode("div", _hoisted_22, [
              _cache[19] || (_cache[19] = createBaseVNode("label", null, "确认新密码", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => passwordForm.value.confirm_password = $event),
                type: "password",
                class: "input",
                autocomplete: "new-password"
              }, null, 512), [
                [vModelText, passwordForm.value.confirm_password]
              ])
            ]),
            _cache[20] || (_cache[20] = createBaseVNode("p", { class: "password-hint" }, "密码至少 6 个字符；审计日志不会记录明文密码。", -1)),
            createBaseVNode("div", _hoisted_23, [
              createBaseVNode("button", {
                class: "btn",
                onClick: closePasswordDialog
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-primary",
                onClick: submitPassword,
                disabled: passwordSaving.value
              }, toDisplayString(passwordSaving.value ? "提交中..." : "保存密码"), 9, _hoisted_24)
            ])
          ])
        ])) : createCommentVNode("", true)
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Users = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-95396276"]]);

export { Users as default };
