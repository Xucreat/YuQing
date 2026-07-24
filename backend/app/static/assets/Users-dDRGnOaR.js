import { d as defineComponent, u as useAuthStore, l as usePermission, p as onMounted, w as withDirectives, c as createElementBlock, B as createVNode, z as withCtx, r as ref, g as api, E as ElMessage, C as resolveComponent, D as resolveDirective, o as openBlock, b as withKeys, e as createTextVNode, y as createBlock, A as createCommentVNode, t as toDisplayString, a as createBaseVNode, F as Fragment, i as renderList, j as computed, O as ElMessageBox, _ as _export_sfc } from './index-RG8CyrnA.js';

const _hoisted_1 = { class: "users-page" };
const _hoisted_2 = {
  key: 1,
  class: "muted"
};
const _hoisted_3 = { class: "pagination" };
const _hoisted_4 = { class: "drawer-body" };
const _hoisted_5 = { class: "sec" };
const _hoisted_6 = {
  key: 1,
  class: "muted"
};
const _hoisted_7 = { class: "sec" };
const _hoisted_8 = { class: "role-chips" };
const _hoisted_9 = {
  key: 0,
  class: "role-meta"
};
const _hoisted_10 = {
  key: 1,
  class: "role-meta"
};
const _hoisted_11 = {
  key: 0,
  class: "muted"
};
const _hoisted_12 = { class: "sec" };
const _hoisted_13 = { class: "perm-role-head" };
const _hoisted_14 = { class: "muted" };
const _hoisted_15 = { class: "perm-chips" };
const _hoisted_16 = {
  key: 0,
  class: "muted"
};
const _hoisted_17 = { class: "perm-final" };
const _hoisted_18 = { class: "perm-chips" };
const _hoisted_19 = {
  key: 0,
  class: "muted"
};
const _hoisted_20 = { class: "sec" };
const _hoisted_21 = { class: "sec" };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Users",
  setup(__props) {
    const authStore = useAuthStore();
    const { hasPermission } = usePermission();
    const canWrite = computed(() => hasPermission("users:write"));
    const canActivate = computed(() => hasPermission("users:activate"));
    const canLoginLogs = computed(() => hasPermission("login_logs:read"));
    const canOpLogs = computed(() => hasPermission("audit_logs:read"));
    const loading = ref(false);
    const saving = ref(false);
    const users = ref([]);
    const total = ref(0);
    const page = ref(1);
    const size = ref(10);
    const searchKey = ref("");
    const roleFilter = ref("");
    const showForm = ref(false);
    const editingId = ref(null);
    const form = ref({ username: "", display_name: "", password: "", role: "analyst" });
    const drawerVisible = ref(false);
    const drawerLoading = ref(false);
    const currentUser = ref(null);
    const roleMap = ref({});
    const roleMapDenied = ref(false);
    const loginHistory = ref([]);
    const opHistory = ref([]);
    const allRoles = computed(() => {
      if (!currentUser.value) return [];
      const list = [];
      const seen = /* @__PURE__ */ new Set();
      const add = (name) => {
        if (!name || seen.has(name)) return;
        seen.add(name);
        list.push(roleMap.value[name] || { name, code: "", display_name: name, is_system: false, permissions: [] });
      };
      add(currentUser.value.role);
      currentUser.value.roles.forEach((r) => add(r.name));
      return list;
    });
    function isSelf(u) {
      return u.username === authStore.username;
    }
    function fmt(t) {
      return t ? t.replace("T", " ").slice(0, 19) : "-";
    }
    function roleText(r) {
      return { admin: "管理员", analyst: "分析员", viewer: "观察员" }[r] || r;
    }
    function roleType(r) {
      return { admin: "danger", analyst: "success", viewer: "info" }[r] || "info";
    }
    function loginStatusText(s) {
      return { success: "成功", failed: "失败", logout: "退出" }[s] || s;
    }
    function isSuperuserUser(u) {
      return !!u.is_superuser || u.role === "admin";
    }
    function rolePerms(name) {
      return roleMap.value[name]?.permissions || [];
    }
    async function loadUsers() {
      loading.value = true;
      try {
        const params = { page: page.value, size: size.value };
        if (searchKey.value) params.search = searchKey.value;
        if (roleFilter.value) params.role = roleFilter.value;
        const { data } = await api.get("/users", { params });
        users.value = data.items || [];
        total.value = data.total || 0;
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载失败");
      } finally {
        loading.value = false;
      }
    }
    function onSearch() {
      page.value = 1;
      loadUsers();
    }
    function resetFilters() {
      searchKey.value = "";
      roleFilter.value = "";
      page.value = 1;
      loadUsers();
    }
    function onPage(p) {
      page.value = p;
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
    async function ensureRoleMap() {
      if (Object.keys(roleMap.value).length || roleMapDenied.value) return;
      try {
        const { data } = await api.get("/roles");
        const m = {};
        (data || []).forEach((r) => {
          m[r.name] = r;
        });
        roleMap.value = m;
      } catch (e) {
        if (e?.response?.status === 403) roleMapDenied.value = true;
        else ElMessage.error(e?.response?.data?.detail || "加载角色信息失败");
      }
    }
    async function openDetail(u) {
      currentUser.value = u;
      loginHistory.value = [];
      opHistory.value = [];
      drawerVisible.value = true;
      drawerLoading.value = true;
      try {
        await ensureRoleMap();
        if (canLoginLogs.value) {
          const { data } = await api.get("/login-logs", { params: { username: u.username, page: 1, size: 20 } });
          loginHistory.value = data.items || [];
        }
        if (canOpLogs.value) {
          const { data } = await api.get("/operation-logs", { params: { target_user_id: u.id, page: 1, size: 20 } });
          opHistory.value = data.items || [];
        }
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载用户详情失败");
      } finally {
        drawerLoading.value = false;
      }
    }
    function closeDrawer() {
      currentUser.value = null;
      loginHistory.value = [];
      opHistory.value = [];
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
      const _component_el_input = resolveComponent("el-input");
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_button = resolveComponent("el-button");
      const _component_el_card = resolveComponent("el-card");
      const _component_el_table_column = resolveComponent("el-table-column");
      const _component_el_tag = resolveComponent("el-tag");
      const _component_el_table = resolveComponent("el-table");
      const _component_el_pagination = resolveComponent("el-pagination");
      const _component_el_form_item = resolveComponent("el-form-item");
      const _component_el_form = resolveComponent("el-form");
      const _component_el_dialog = resolveComponent("el-dialog");
      const _component_el_descriptions_item = resolveComponent("el-descriptions-item");
      const _component_el_descriptions = resolveComponent("el-descriptions");
      const _component_el_alert = resolveComponent("el-alert");
      const _component_el_drawer = resolveComponent("el-drawer");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createVNode(_component_el_card, {
          shadow: "never",
          class: "filter-card"
        }, {
          default: withCtx(() => [
            createVNode(_component_el_input, {
              modelValue: searchKey.value,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => searchKey.value = $event),
              placeholder: "搜索用户名",
              clearable: "",
              style: { "width": "200px" },
              onKeyup: withKeys(onSearch, ["enter"]),
              onClear: onSearch
            }, null, 8, ["modelValue"]),
            createVNode(_component_el_select, {
              modelValue: roleFilter.value,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => roleFilter.value = $event),
              placeholder: "全部角色",
              clearable: "",
              style: { "width": "140px", "margin-left": "12px" },
              onChange: onSearch
            }, {
              default: withCtx(() => [
                createVNode(_component_el_option, {
                  label: "管理员",
                  value: "admin"
                }),
                createVNode(_component_el_option, {
                  label: "分析员",
                  value: "analyst"
                }),
                createVNode(_component_el_option, {
                  label: "观察员",
                  value: "viewer"
                })
              ]),
              _: 1
            }, 8, ["modelValue"]),
            createVNode(_component_el_button, {
              type: "primary",
              style: { "margin-left": "12px" },
              onClick: onSearch
            }, {
              default: withCtx(() => [..._cache[9] || (_cache[9] = [
                createTextVNode("查询", -1)
              ])]),
              _: 1
            }),
            createVNode(_component_el_button, { onClick: resetFilters }, {
              default: withCtx(() => [..._cache[10] || (_cache[10] = [
                createTextVNode("重置", -1)
              ])]),
              _: 1
            }),
            canWrite.value ? (openBlock(), createBlock(_component_el_button, {
              key: 0,
              type: "primary",
              style: { "margin-left": "12px" },
              onClick: openAdd
            }, {
              default: withCtx(() => [..._cache[11] || (_cache[11] = [
                createTextVNode("+ 新增用户", -1)
              ])]),
              _: 1
            })) : createCommentVNode("", true)
          ]),
          _: 1
        }),
        createVNode(_component_el_card, {
          shadow: "never",
          class: "table-card"
        }, {
          default: withCtx(() => [
            createVNode(_component_el_table, {
              data: users.value,
              stripe: "",
              "empty-text": "暂无用户",
              onRowDblclick: openDetail
            }, {
              default: withCtx(() => [
                createVNode(_component_el_table_column, {
                  prop: "username",
                  label: "用户名",
                  "min-width": "140"
                }),
                createVNode(_component_el_table_column, {
                  prop: "display_name",
                  label: "显示名",
                  "min-width": "120",
                  "show-overflow-tooltip": ""
                }),
                createVNode(_component_el_table_column, {
                  label: "角色",
                  "min-width": "110",
                  align: "center"
                }, {
                  default: withCtx(({ row }) => [
                    createVNode(_component_el_tag, {
                      size: "small",
                      type: roleType(row.role)
                    }, {
                      default: withCtx(() => [
                        createTextVNode(toDisplayString(roleText(row.role)), 1)
                      ]),
                      _: 2
                    }, 1032, ["type"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_table_column, {
                  label: "状态",
                  "min-width": "90",
                  align: "center"
                }, {
                  default: withCtx(({ row }) => [
                    createVNode(_component_el_tag, {
                      size: "small",
                      type: row.is_active ? "success" : "danger"
                    }, {
                      default: withCtx(() => [
                        createTextVNode(toDisplayString(row.is_active ? "正常" : "禁用"), 1)
                      ]),
                      _: 2
                    }, 1032, ["type"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_table_column, {
                  label: "超管",
                  "min-width": "80",
                  align: "center"
                }, {
                  default: withCtx(({ row }) => [
                    row.is_superuser ? (openBlock(), createBlock(_component_el_tag, {
                      key: 0,
                      size: "small",
                      type: "warning"
                    }, {
                      default: withCtx(() => [..._cache[12] || (_cache[12] = [
                        createTextVNode("超管", -1)
                      ])]),
                      _: 1
                    })) : (openBlock(), createElementBlock("span", _hoisted_2, "-"))
                  ]),
                  _: 1
                }),
                createVNode(_component_el_table_column, {
                  label: "最后登录",
                  "min-width": "180"
                }, {
                  default: withCtx(({ row }) => [
                    createTextVNode(toDisplayString(fmt(row.last_login)), 1)
                  ]),
                  _: 1
                }),
                createVNode(_component_el_table_column, {
                  label: "创建时间",
                  "min-width": "130"
                }, {
                  default: withCtx(({ row }) => [
                    createTextVNode(toDisplayString(row.created_at ? row.created_at.slice(0, 10) : "-"), 1)
                  ]),
                  _: 1
                }),
                createVNode(_component_el_table_column, {
                  label: "操作",
                  "min-width": "260",
                  align: "center"
                }, {
                  default: withCtx(({ row }) => [
                    createVNode(_component_el_button, {
                      type: "primary",
                      size: "small",
                      link: "",
                      onClick: ($event) => openDetail(row)
                    }, {
                      default: withCtx(() => [..._cache[13] || (_cache[13] = [
                        createTextVNode("详情", -1)
                      ])]),
                      _: 1
                    }, 8, ["onClick"]),
                    canActivate.value ? (openBlock(), createBlock(_component_el_button, {
                      key: 0,
                      type: "primary",
                      size: "small",
                      link: "",
                      disabled: isSelf(row),
                      onClick: ($event) => toggleActive(row)
                    }, {
                      default: withCtx(() => [
                        createTextVNode(toDisplayString(row.is_active ? "停用" : "启用"), 1)
                      ]),
                      _: 2
                    }, 1032, ["disabled", "onClick"])) : createCommentVNode("", true),
                    canWrite.value ? (openBlock(), createBlock(_component_el_button, {
                      key: 1,
                      type: "primary",
                      size: "small",
                      link: "",
                      disabled: isSelf(row),
                      onClick: ($event) => openEdit(row)
                    }, {
                      default: withCtx(() => [..._cache[14] || (_cache[14] = [
                        createTextVNode("编辑", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled", "onClick"])) : createCommentVNode("", true),
                    canWrite.value ? (openBlock(), createBlock(_component_el_button, {
                      key: 2,
                      type: "danger",
                      size: "small",
                      link: "",
                      disabled: row.username === "admin" || isSelf(row),
                      onClick: ($event) => handleDelete(row)
                    }, {
                      default: withCtx(() => [..._cache[15] || (_cache[15] = [
                        createTextVNode("删除", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled", "onClick"])) : createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }, 8, ["data"]),
            createBaseVNode("div", _hoisted_3, [
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
        }),
        createVNode(_component_el_dialog, {
          modelValue: showForm.value,
          "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => showForm.value = $event),
          title: editingId.value ? "编辑用户" : "新增用户",
          width: "460px",
          "align-center": "",
          class: "apple-dialog",
          "modal-class": "apple-modal"
        }, {
          footer: withCtx(() => [
            createVNode(_component_el_button, {
              onClick: _cache[6] || (_cache[6] = ($event) => showForm.value = false)
            }, {
              default: withCtx(() => [..._cache[16] || (_cache[16] = [
                createTextVNode("取消", -1)
              ])]),
              _: 1
            }),
            createVNode(_component_el_button, {
              type: "primary",
              disabled: saving.value,
              onClick: handleSave
            }, {
              default: withCtx(() => [
                createTextVNode(toDisplayString(saving.value ? "保存中…" : "保存"), 1)
              ]),
              _: 1
            }, 8, ["disabled"])
          ]),
          default: withCtx(() => [
            createVNode(_component_el_form, {
              model: form.value,
              "label-width": "80px"
            }, {
              default: withCtx(() => [
                createVNode(_component_el_form_item, { label: "用户名" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: form.value.username,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => form.value.username = $event),
                      disabled: !!editingId.value,
                      placeholder: "登录名"
                    }, null, 8, ["modelValue", "disabled"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "显示名" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: form.value.display_name,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => form.value.display_name = $event),
                      placeholder: "可选"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "密码" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_input, {
                      modelValue: form.value.password,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => form.value.password = $event),
                      type: "password",
                      placeholder: editingId.value ? "留空不修改" : "请输入密码"
                    }, null, 8, ["modelValue", "placeholder"])
                  ]),
                  _: 1
                }),
                createVNode(_component_el_form_item, { label: "角色" }, {
                  default: withCtx(() => [
                    createVNode(_component_el_select, {
                      modelValue: form.value.role,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => form.value.role = $event),
                      style: { "width": "100%" }
                    }, {
                      default: withCtx(() => [
                        createVNode(_component_el_option, {
                          label: "管理员",
                          value: "admin"
                        }),
                        createVNode(_component_el_option, {
                          label: "分析员",
                          value: "analyst"
                        }),
                        createVNode(_component_el_option, {
                          label: "观察员",
                          value: "viewer"
                        })
                      ]),
                      _: 1
                    }, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }, 8, ["model"])
          ]),
          _: 1
        }, 8, ["modelValue", "title"]),
        createVNode(_component_el_drawer, {
          modelValue: drawerVisible.value,
          "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => drawerVisible.value = $event),
          title: "用户详情 · " + (currentUser.value?.username || ""),
          size: "560px",
          onClosed: closeDrawer
        }, {
          default: withCtx(() => [
            withDirectives((openBlock(), createElementBlock("div", _hoisted_4, [
              currentUser.value ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                createBaseVNode("section", _hoisted_5, [
                  _cache[18] || (_cache[18] = createBaseVNode("h4", { class: "sec-title" }, "基本信息", -1)),
                  createVNode(_component_el_descriptions, {
                    column: 1,
                    border: "",
                    size: "small"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_descriptions_item, { label: "用户名" }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(currentUser.value.username), 1)
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_descriptions_item, { label: "显示名" }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(currentUser.value.display_name || "-"), 1)
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_descriptions_item, { label: "主角色" }, {
                        default: withCtx(() => [
                          createVNode(_component_el_tag, {
                            size: "small",
                            type: roleType(currentUser.value.role)
                          }, {
                            default: withCtx(() => [
                              createTextVNode(toDisplayString(roleText(currentUser.value.role)), 1)
                            ]),
                            _: 1
                          }, 8, ["type"])
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_descriptions_item, { label: "状态" }, {
                        default: withCtx(() => [
                          createVNode(_component_el_tag, {
                            size: "small",
                            type: currentUser.value.is_active ? "success" : "danger"
                          }, {
                            default: withCtx(() => [
                              createTextVNode(toDisplayString(currentUser.value.is_active ? "正常" : "禁用"), 1)
                            ]),
                            _: 1
                          }, 8, ["type"])
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_descriptions_item, { label: "超级管理员" }, {
                        default: withCtx(() => [
                          currentUser.value.is_superuser ? (openBlock(), createBlock(_component_el_tag, {
                            key: 0,
                            size: "small",
                            type: "warning"
                          }, {
                            default: withCtx(() => [..._cache[17] || (_cache[17] = [
                              createTextVNode("是", -1)
                            ])]),
                            _: 1
                          })) : (openBlock(), createElementBlock("span", _hoisted_6, "否"))
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_descriptions_item, { label: "最后登录" }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(fmt(currentUser.value.last_login)), 1)
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_descriptions_item, { label: "最后登录 IP" }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(currentUser.value.last_login_ip || "-"), 1)
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_descriptions_item, { label: "创建时间" }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(currentUser.value.created_at ? currentUser.value.created_at.slice(0, 19).replace("T", " ") : "-"), 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                createBaseVNode("section", _hoisted_7, [
                  _cache[19] || (_cache[19] = createBaseVNode("h4", { class: "sec-title" }, "角色信息", -1)),
                  createBaseVNode("div", _hoisted_8, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(allRoles.value, (r) => {
                      return openBlock(), createBlock(_component_el_tag, {
                        key: r.name,
                        type: r.name === currentUser.value.role ? "primary" : "info",
                        size: "small",
                        class: "role-chip"
                      }, {
                        default: withCtx(() => [
                          createTextVNode(toDisplayString(r.display_name || r.name) + " ", 1),
                          r.code ? (openBlock(), createElementBlock("span", _hoisted_9, " · " + toDisplayString(r.code), 1)) : createCommentVNode("", true),
                          r.is_system ? (openBlock(), createElementBlock("span", _hoisted_10, " · 系统")) : createCommentVNode("", true)
                        ]),
                        _: 2
                      }, 1032, ["type"]);
                    }), 128))
                  ]),
                  !allRoles.value.length ? (openBlock(), createElementBlock("p", _hoisted_11, "无关联角色")) : createCommentVNode("", true)
                ]),
                createBaseVNode("section", _hoisted_12, [
                  _cache[23] || (_cache[23] = createBaseVNode("h4", { class: "sec-title" }, "权限来源", -1)),
                  isSuperuserUser(currentUser.value) ? (openBlock(), createBlock(_component_el_alert, {
                    key: 0,
                    type: "warning",
                    closable: false,
                    "show-icon": "",
                    title: "超级管理员"
                  }, {
                    default: withCtx(() => [..._cache[20] || (_cache[20] = [
                      createTextVNode("该用户为超级管理员（role='admin' 或 is_superuser=true）。无论 role_permissions 是否为空，最终权限均为通配 ", -1),
                      createBaseVNode("code", null, '["*"]', -1),
                      createTextVNode("。", -1)
                    ])]),
                    _: 1
                  })) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
                    _cache[21] || (_cache[21] = createBaseVNode("p", { class: "sec-hint" }, "以下为各角色直接授予的权限，最终生效权限由后端按角色合并计算：", -1)),
                    (openBlock(true), createElementBlock(Fragment, null, renderList(allRoles.value, (r) => {
                      return openBlock(), createElementBlock("div", {
                        key: "p" + r.name,
                        class: "perm-role"
                      }, [
                        createBaseVNode("div", _hoisted_13, [
                          createTextVNode(toDisplayString(r.display_name || r.name) + " ", 1),
                          createBaseVNode("span", _hoisted_14, "(" + toDisplayString(r.name) + ")", 1)
                        ]),
                        createBaseVNode("div", _hoisted_15, [
                          (openBlock(true), createElementBlock(Fragment, null, renderList(rolePerms(r.name) || [], (pc) => {
                            return openBlock(), createBlock(_component_el_tag, {
                              key: pc,
                              size: "small",
                              type: "info",
                              class: "perm-chip"
                            }, {
                              default: withCtx(() => [
                                createTextVNode(toDisplayString(pc), 1)
                              ]),
                              _: 2
                            }, 1024);
                          }), 128)),
                          !(rolePerms(r.name) || []).length ? (openBlock(), createElementBlock("span", _hoisted_16, "无直接权限")) : createCommentVNode("", true)
                        ])
                      ]);
                    }), 128))
                  ], 64)),
                  createBaseVNode("div", _hoisted_17, [
                    _cache[22] || (_cache[22] = createBaseVNode("div", { class: "perm-role-head" }, "当前最终生效权限（后端计算）：", -1)),
                    createBaseVNode("div", _hoisted_18, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(currentUser.value.permissions, (pc) => {
                        return openBlock(), createBlock(_component_el_tag, {
                          key: pc,
                          size: "small",
                          type: "success",
                          class: "perm-chip"
                        }, {
                          default: withCtx(() => [
                            createTextVNode(toDisplayString(pc), 1)
                          ]),
                          _: 2
                        }, 1024);
                      }), 128)),
                      !currentUser.value.permissions.length ? (openBlock(), createElementBlock("span", _hoisted_19, "无")) : createCommentVNode("", true)
                    ])
                  ])
                ]),
                createBaseVNode("section", _hoisted_20, [
                  _cache[24] || (_cache[24] = createBaseVNode("h4", { class: "sec-title" }, "登录历史", -1)),
                  !canLoginLogs.value ? (openBlock(), createBlock(_component_el_alert, {
                    key: 0,
                    type: "info",
                    closable: false,
                    "show-icon": "",
                    title: "无权限查看登录日志"
                  })) : (openBlock(), createBlock(_component_el_table, {
                    key: 1,
                    data: loginHistory.value,
                    stripe: "",
                    size: "small",
                    "empty-text": "暂无登录记录"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_table_column, {
                        label: "时间",
                        "min-width": "160"
                      }, {
                        default: withCtx(({ row }) => [
                          createTextVNode(toDisplayString(fmt(row.login_at)), 1)
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_table_column, {
                        prop: "ip_address",
                        label: "IP",
                        "min-width": "120",
                        "show-overflow-tooltip": ""
                      }),
                      createVNode(_component_el_table_column, {
                        label: "结果",
                        width: "90",
                        align: "center"
                      }, {
                        default: withCtx(({ row }) => [
                          createVNode(_component_el_tag, {
                            size: "small",
                            type: row.status === "success" ? "success" : row.status === "failed" ? "danger" : "info"
                          }, {
                            default: withCtx(() => [
                              createTextVNode(toDisplayString(loginStatusText(row.status)), 1)
                            ]),
                            _: 2
                          }, 1032, ["type"])
                        ]),
                        _: 1
                      }),
                      createVNode(_component_el_table_column, {
                        prop: "failure_reason",
                        label: "失败原因",
                        "min-width": "120",
                        "show-overflow-tooltip": ""
                      })
                    ]),
                    _: 1
                  }, 8, ["data"]))
                ]),
                createBaseVNode("section", _hoisted_21, [
                  _cache[25] || (_cache[25] = createBaseVNode("h4", { class: "sec-title" }, "操作历史", -1)),
                  !canOpLogs.value ? (openBlock(), createBlock(_component_el_alert, {
                    key: 0,
                    type: "info",
                    closable: false,
                    "show-icon": "",
                    title: "无权限查看操作日志"
                  })) : (openBlock(), createBlock(_component_el_table, {
                    key: 1,
                    data: opHistory.value,
                    stripe: "",
                    size: "small",
                    "empty-text": "暂无操作记录"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_table_column, {
                        prop: "operator_username_snapshot",
                        label: "操作人",
                        "min-width": "100",
                        "show-overflow-tooltip": ""
                      }),
                      createVNode(_component_el_table_column, {
                        prop: "action",
                        label: "类型",
                        width: "120"
                      }),
                      createVNode(_component_el_table_column, {
                        prop: "resource_type",
                        label: "资源",
                        "min-width": "100",
                        "show-overflow-tooltip": ""
                      }),
                      createVNode(_component_el_table_column, {
                        prop: "resource_id",
                        label: "资源ID",
                        "min-width": "90",
                        "show-overflow-tooltip": ""
                      }),
                      createVNode(_component_el_table_column, {
                        label: "结果",
                        width: "80",
                        align: "center"
                      }, {
                        default: withCtx(({ row }) => [
                          createVNode(_component_el_tag, {
                            size: "small",
                            type: row.result === "success" ? "success" : "danger"
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
                        label: "时间",
                        "min-width": "160"
                      }, {
                        default: withCtx(({ row }) => [
                          createTextVNode(toDisplayString(fmt(row.created_at)), 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["data"]))
                ])
              ], 64)) : createCommentVNode("", true)
            ])), [
              [_directive_loading, drawerLoading.value]
            ])
          ]),
          _: 1
        }, 8, ["modelValue", "title"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Users = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-42ef1c14"]]);

export { Users as default };
