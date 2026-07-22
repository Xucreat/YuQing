import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, F as Fragment, i as renderList, A as createCommentVNode, I as withModifiers, t as toDisplayString, v as vModelText, G as vModelSelect, r as ref, g as api, E as ElMessage, D as resolveDirective, o as openBlock, n as normalizeClass, K as ElMessageBox, _ as _export_sfc } from './index-DfUB6--C.js';

const _hoisted_1 = { class: "users-page" };
const _hoisted_2 = { class: "card" };
const _hoisted_3 = { class: "tbl" };
const _hoisted_4 = ["onClick"];
const _hoisted_5 = ["onClick", "disabled"];
const _hoisted_6 = { key: 0 };
const _hoisted_7 = { class: "modal" };
const _hoisted_8 = { class: "form-group" };
const _hoisted_9 = ["disabled"];
const _hoisted_10 = { class: "form-group" };
const _hoisted_11 = { class: "form-group" };
const _hoisted_12 = { class: "form-actions" };
const _hoisted_13 = ["disabled"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Users",
  setup(__props) {
    const loading = ref(false);
    const saving = ref(false);
    const users = ref([]);
    const showForm = ref(false);
    const editingId = ref(null);
    const form = ref({ username: "", password: "", role: "analyst" });
    function rolePill(r) {
      return { admin: "pill-blue", analyst: "pill-green", viewer: "pill-gray" }[r] || "pill-gray";
    }
    function roleText(r) {
      return { admin: "管理员", analyst: "分析员", viewer: "观察员" }[r] || r;
    }
    async function loadUsers() {
      loading.value = true;
      try {
        const { data } = await api.get("/users");
        users.value = data.items;
      } catch (e) {
        ElMessage.error("加载失败");
      } finally {
        loading.value = false;
      }
    }
    function openAdd() {
      editingId.value = null;
      form.value = { username: "", password: "", role: "analyst" };
      showForm.value = true;
    }
    function openEdit(u) {
      editingId.value = u.id;
      form.value = { username: u.username, password: "", role: u.role };
      showForm.value = true;
    }
    async function handleSave() {
      if (!form.value.username) return ElMessage.warning("请输入用户名");
      if (!editingId.value && !form.value.password) return ElMessage.warning("请输入密码");
      saving.value = true;
      try {
        if (editingId.value) {
          await api.put("/users/" + editingId.value, { role: form.value.role, password: form.value.password || void 0 });
          ElMessage.success("更新成功");
        } else {
          await api.post("/users", form.value);
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
    async function handleDelete(u) {
      try {
        await ElMessageBox.confirm("确认删除用户 " + u.username + "？", "警告", { type: "warning" });
        await api.delete("/users/" + u.id);
        ElMessage.success("已删除");
        await loadUsers();
      } catch {
      }
    }
    onMounted(loadUsers);
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", { class: "toolbar" }, [
          _cache[5] || (_cache[5] = createBaseVNode("h3", { class: "section-title" }, "用户管理", -1)),
          createBaseVNode("button", {
            class: "btn btn-primary",
            onClick: openAdd
          }, "+ 新增用户")
        ]),
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("table", _hoisted_3, [
            _cache[7] || (_cache[7] = createBaseVNode("thead", null, [
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
              (openBlock(true), createElementBlock(Fragment, null, renderList(users.value, (u) => {
                return openBlock(), createElementBlock("tr", {
                  key: u.id
                }, [
                  createBaseVNode("td", null, toDisplayString(u.username), 1),
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
                  createBaseVNode("td", null, toDisplayString(u.last_login ? new Date(u.last_login).toLocaleString("zh-CN") : "-"), 1),
                  createBaseVNode("td", null, toDisplayString(new Date(u.created_at).toLocaleDateString("zh-CN")), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("button", {
                      class: "btn btn-mini",
                      onClick: ($event) => openEdit(u)
                    }, "编辑", 8, _hoisted_4),
                    createBaseVNode("button", {
                      class: "btn btn-mini btn-danger",
                      onClick: ($event) => handleDelete(u),
                      disabled: u.username === "admin"
                    }, "删除", 8, _hoisted_5)
                  ])
                ]);
              }), 128)),
              !users.value.length ? (openBlock(), createElementBlock("tr", _hoisted_6, [..._cache[6] || (_cache[6] = [
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
          onClick: _cache[4] || (_cache[4] = withModifiers(($event) => showForm.value = false, ["self"]))
        }, [
          createBaseVNode("div", _hoisted_7, [
            createBaseVNode("h3", null, toDisplayString(editingId.value ? "编辑用户" : "新增用户"), 1),
            createBaseVNode("div", _hoisted_8, [
              _cache[8] || (_cache[8] = createBaseVNode("label", null, "用户名", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => form.value.username = $event),
                class: "input",
                disabled: !!editingId.value
              }, null, 8, _hoisted_9), [
                [vModelText, form.value.username]
              ])
            ]),
            createBaseVNode("div", _hoisted_10, [
              createBaseVNode("label", null, "密码" + toDisplayString(editingId.value ? "（留空不修改）" : ""), 1),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => form.value.password = $event),
                type: "password",
                class: "input"
              }, null, 512), [
                [vModelText, form.value.password]
              ])
            ]),
            createBaseVNode("div", _hoisted_11, [
              _cache[10] || (_cache[10] = createBaseVNode("label", null, "角色", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => form.value.role = $event),
                class: "input"
              }, [..._cache[9] || (_cache[9] = [
                createBaseVNode("option", { value: "admin" }, "管理员", -1),
                createBaseVNode("option", { value: "analyst" }, "分析员", -1),
                createBaseVNode("option", { value: "viewer" }, "观察员", -1)
              ])], 512), [
                [vModelSelect, form.value.role]
              ])
            ]),
            createBaseVNode("div", _hoisted_12, [
              createBaseVNode("button", {
                class: "btn",
                onClick: _cache[3] || (_cache[3] = ($event) => showForm.value = false)
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-primary",
                onClick: handleSave,
                disabled: saving.value
              }, toDisplayString(saving.value ? "保存中..." : "保存"), 9, _hoisted_13)
            ])
          ])
        ])) : createCommentVNode("", true)
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Users = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-bc18596d"]]);

export { Users as default };
