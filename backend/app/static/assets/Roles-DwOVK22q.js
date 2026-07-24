import { d as defineComponent, l as usePermission, p as onMounted, E as ElMessage, w as withDirectives, c as createElementBlock, a as createBaseVNode, x as unref, A as createCommentVNode, F as Fragment, i as renderList, J as withModifiers, t as toDisplayString, e as createTextVNode, v as vModelText, r as ref, j as computed, g as api, D as resolveDirective, o as openBlock, n as normalizeClass, O as ElMessageBox, _ as _export_sfc } from './index-iT_24xn-.js';

const _hoisted_1 = { class: "roles-page" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = { class: "card" };
const _hoisted_4 = { class: "tbl" };
const _hoisted_5 = { class: "role-name" };
const _hoisted_6 = { class: "role-code" };
const _hoisted_7 = {
  key: 0,
  class: "pill pill-purple"
};
const _hoisted_8 = {
  key: 1,
  class: "pill pill-gray"
};
const _hoisted_9 = { class: "ops" };
const _hoisted_10 = ["onClick"];
const _hoisted_11 = ["onClick"];
const _hoisted_12 = {
  key: 1,
  class: "muted"
};
const _hoisted_13 = { key: 0 };
const _hoisted_14 = { class: "modal modal-wide" };
const _hoisted_15 = {
  key: 0,
  class: "banner"
};
const _hoisted_16 = { class: "perm-groups" };
const _hoisted_17 = { class: "perm-group-title" };
const _hoisted_18 = { class: "perm-grid" };
const _hoisted_19 = ["checked", "disabled", "onChange"];
const _hoisted_20 = { class: "perm-code" };
const _hoisted_21 = { class: "perm-name" };
const _hoisted_22 = ["title"];
const _hoisted_23 = { class: "form-actions" };
const _hoisted_24 = ["disabled"];
const _hoisted_25 = { class: "modal modal-wide" };
const _hoisted_26 = { class: "form-group" };
const _hoisted_27 = { class: "form-group" };
const _hoisted_28 = { class: "form-group" };
const _hoisted_29 = { class: "form-group" };
const _hoisted_30 = { class: "form-group" };
const _hoisted_31 = { class: "perm-groups compact" };
const _hoisted_32 = { class: "perm-group-title" };
const _hoisted_33 = { class: "perm-grid" };
const _hoisted_34 = ["checked", "onChange"];
const _hoisted_35 = { class: "perm-code" };
const _hoisted_36 = { class: "perm-name" };
const _hoisted_37 = { class: "form-actions" };
const _hoisted_38 = ["disabled"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Roles",
  setup(__props) {
    const { hasPermission } = usePermission();
    const canWrite = hasPermission("roles:write");
    const canDelete = hasPermission("roles:delete");
    const loading = ref(false);
    const saving = ref(false);
    const roles = ref([]);
    const catalog = ref([]);
    const GROUP_LABEL = {
      舆情管理: "舆情",
      事件管理: "事件",
      关键词管理: "关键词",
      用户管理: "用户",
      角色管理: "角色",
      权限管理: "权限",
      告警管理: "预警",
      报告: "报告",
      数据源: "数据源",
      采集管理: "采集器",
      传播溯源: "传播",
      驾驶舱: "驾驶舱",
      审计: "审计/登录日志"
    };
    const GROUP_ORDER = {
      舆情管理: 1,
      事件管理: 2,
      关键词管理: 3,
      用户管理: 4,
      角色管理: 5,
      权限管理: 6,
      告警管理: 7,
      报告: 8,
      数据源: 9,
      采集管理: 10,
      传播溯源: 11,
      驾驶舱: 12,
      审计: 13
    };
    const groupedPermissions = computed(() => {
      const map = /* @__PURE__ */ new Map();
      for (const p of catalog.value) {
        if (!map.has(p.group)) map.set(p.group, []);
        map.get(p.group).push(p);
      }
      return [...map.entries()].sort((a, b) => (GROUP_ORDER[a[0]] ?? 99) - (GROUP_ORDER[b[0]] ?? 99)).map(([group, perms]) => ({ group, label: GROUP_LABEL[group] || group, perms }));
    });
    const editorOpen = ref(false);
    const editingRole = ref(null);
    const selected = ref(/* @__PURE__ */ new Set());
    const isAdminRole = computed(() => editingRole.value?.code === "admin");
    function toggle(code, checked) {
      const s = new Set(selected.value);
      if (checked) s.add(code);
      else s.delete(code);
      selected.value = s;
    }
    async function openEditor(r) {
      editingRole.value = r;
      selected.value = isAdminRole.value ? new Set(catalog.value.map((p) => p.code)) : new Set(r.permissions);
      editorOpen.value = true;
    }
    function closeEditor() {
      editorOpen.value = false;
      editingRole.value = null;
    }
    async function savePermissions() {
      if (!editingRole.value || isAdminRole.value) return;
      saving.value = true;
      try {
        await api.put("/roles/" + editingRole.value.id, { permissions: [...selected.value] });
        ElMessage.success("权限已保存");
        await loadRoles();
        closeEditor();
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "保存失败");
      } finally {
        saving.value = false;
      }
    }
    const createOpen = ref(false);
    const createSelected = ref(/* @__PURE__ */ new Set());
    const createForm = ref({ code: "", name: "", display_name: "", description: "" });
    function toggleCreate(code, checked) {
      const s = new Set(createSelected.value);
      if (checked) s.add(code);
      else s.delete(code);
      createSelected.value = s;
    }
    function openCreate() {
      createForm.value = { code: "", name: "", display_name: "", description: "" };
      createSelected.value = /* @__PURE__ */ new Set();
      createOpen.value = true;
    }
    async function createRole() {
      if (!createForm.value.code || !createForm.value.name) return ElMessage.warning("请填写角色代码与名称");
      saving.value = true;
      try {
        await api.post("/roles", {
          code: createForm.value.code,
          name: createForm.value.name,
          display_name: createForm.value.display_name || createForm.value.name,
          description: createForm.value.description || "",
          is_enabled: true,
          permissions: [...createSelected.value]
        });
        ElMessage.success("角色已创建");
        createOpen.value = false;
        await loadRoles();
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "创建失败");
      } finally {
        saving.value = false;
      }
    }
    async function handleDelete(r) {
      if (r.is_system) return ElMessage.warning("系统角色不可删除");
      try {
        await ElMessageBox.confirm(`确认删除角色 ${r.display_name}（${r.name}）？此操作不可恢复`, "警告", { type: "warning" });
        await api.delete("/roles/" + r.id);
        ElMessage.success("已删除");
        await loadRoles();
      } catch (e) {
        if (e !== "cancel" && e?.response) ElMessage.error(e?.response?.data?.detail || "删除失败");
      }
    }
    async function loadRoles() {
      const { data } = await api.get("/roles");
      roles.value = data;
    }
    async function loadCatalog() {
      const { data } = await api.get("/permissions");
      catalog.value = data;
    }
    onMounted(async () => {
      loading.value = true;
      try {
        await Promise.all([loadCatalog(), loadRoles()]);
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "加载失败");
      } finally {
        loading.value = false;
      }
    });
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          _cache[6] || (_cache[6] = createBaseVNode("h3", { class: "section-title" }, "角色权限", -1)),
          unref(canWrite) ? (openBlock(), createElementBlock("button", {
            key: 0,
            class: "btn btn-primary",
            onClick: openCreate
          }, "+ 新建角色")) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_3, [
          createBaseVNode("table", _hoisted_4, [
            _cache[8] || (_cache[8] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "角色名"),
                createBaseVNode("th", null, "显示名"),
                createBaseVNode("th", null, "类型"),
                createBaseVNode("th", null, "权限数"),
                createBaseVNode("th", null, "用户数"),
                createBaseVNode("th", null, "状态"),
                createBaseVNode("th", null, "操作")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(roles.value, (r) => {
                return openBlock(), createElementBlock("tr", {
                  key: r.id
                }, [
                  createBaseVNode("td", null, [
                    createBaseVNode("span", _hoisted_5, toDisplayString(r.name), 1),
                    createBaseVNode("span", _hoisted_6, toDisplayString(r.code), 1)
                  ]),
                  createBaseVNode("td", null, toDisplayString(r.display_name), 1),
                  createBaseVNode("td", null, [
                    r.is_system ? (openBlock(), createElementBlock("span", _hoisted_7, "系统角色")) : (openBlock(), createElementBlock("span", _hoisted_8, "自定义"))
                  ]),
                  createBaseVNode("td", null, toDisplayString(r.permissions.length), 1),
                  createBaseVNode("td", null, toDisplayString(r.user_count), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", r.is_enabled ? "pill-green" : "pill-red"])
                    }, toDisplayString(r.is_enabled ? "启用" : "禁用"), 3)
                  ]),
                  createBaseVNode("td", _hoisted_9, [
                    createBaseVNode("button", {
                      class: "btn btn-mini",
                      onClick: ($event) => openEditor(r)
                    }, "权限", 8, _hoisted_10),
                    unref(canDelete) && !r.is_system ? (openBlock(), createElementBlock("button", {
                      key: 0,
                      class: "btn btn-mini btn-danger",
                      onClick: ($event) => handleDelete(r)
                    }, "删除", 8, _hoisted_11)) : r.is_system ? (openBlock(), createElementBlock("span", _hoisted_12, "—")) : createCommentVNode("", true)
                  ])
                ]);
              }), 128)),
              !roles.value.length ? (openBlock(), createElementBlock("tr", _hoisted_13, [..._cache[7] || (_cache[7] = [
                createBaseVNode("td", {
                  colspan: "7",
                  class: "empty-row"
                }, "暂无角色", -1)
              ])])) : createCommentVNode("", true)
            ])
          ])
        ]),
        editorOpen.value ? (openBlock(), createElementBlock("div", {
          key: 0,
          class: "modal-overlay",
          onClick: withModifiers(closeEditor, ["self"])
        }, [
          createBaseVNode("div", _hoisted_14, [
            createBaseVNode("h3", null, toDisplayString(editingRole.value?.display_name || "") + " · 权限配置", 1),
            isAdminRole.value ? (openBlock(), createElementBlock("p", _hoisted_15, [..._cache[9] || (_cache[9] = [
              createTextVNode(" 该角色为", -1),
              createBaseVNode("strong", null, "超管角色", -1),
              createTextVNode("，拥有全部权限（后端按 ", -1),
              createBaseVNode("code", null, "role='admin'", -1),
              createTextVNode(" 或 ", -1),
              createBaseVNode("code", null, "is_superuser", -1),
              createTextVNode(" 放行），无需单独勾选。 ", -1)
            ])])) : createCommentVNode("", true),
            createBaseVNode("div", _hoisted_16, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(groupedPermissions.value, (g) => {
                return openBlock(), createElementBlock("div", {
                  key: g.group,
                  class: "perm-group"
                }, [
                  createBaseVNode("div", _hoisted_17, toDisplayString(g.label), 1),
                  createBaseVNode("div", _hoisted_18, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(g.perms, (p) => {
                      return openBlock(), createElementBlock("label", {
                        key: p.code,
                        class: normalizeClass(["perm-item", { disabled: isAdminRole.value }])
                      }, [
                        createBaseVNode("input", {
                          type: "checkbox",
                          checked: selected.value.has(p.code),
                          disabled: isAdminRole.value,
                          onChange: ($event) => toggle(p.code, $event.target.checked)
                        }, null, 40, _hoisted_19),
                        createBaseVNode("span", _hoisted_20, toDisplayString(p.code), 1),
                        createBaseVNode("span", _hoisted_21, toDisplayString(p.name), 1),
                        createBaseVNode("span", {
                          class: "perm-desc",
                          title: p.description
                        }, toDisplayString(p.description), 9, _hoisted_22)
                      ], 2);
                    }), 128))
                  ])
                ]);
              }), 128))
            ]),
            createBaseVNode("div", _hoisted_23, [
              createBaseVNode("button", {
                class: "btn",
                onClick: closeEditor
              }, "关闭"),
              unref(canWrite) && !isAdminRole.value ? (openBlock(), createElementBlock("button", {
                key: 0,
                class: "btn btn-primary",
                onClick: savePermissions,
                disabled: saving.value
              }, toDisplayString(saving.value ? "保存中..." : "保存权限"), 9, _hoisted_24)) : createCommentVNode("", true)
            ])
          ])
        ])) : createCommentVNode("", true),
        createOpen.value ? (openBlock(), createElementBlock("div", {
          key: 1,
          class: "modal-overlay",
          onClick: _cache[5] || (_cache[5] = withModifiers(($event) => createOpen.value = false, ["self"]))
        }, [
          createBaseVNode("div", _hoisted_25, [
            _cache[15] || (_cache[15] = createBaseVNode("h3", null, "新建角色", -1)),
            createBaseVNode("div", _hoisted_26, [
              _cache[10] || (_cache[10] = createBaseVNode("label", null, "角色代码（code，英文唯一）", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => createForm.value.code = $event),
                class: "input",
                placeholder: "如 custom_analyst"
              }, null, 512), [
                [vModelText, createForm.value.code]
              ])
            ]),
            createBaseVNode("div", _hoisted_27, [
              _cache[11] || (_cache[11] = createBaseVNode("label", null, "角色名（name，唯一）", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => createForm.value.name = $event),
                class: "input",
                placeholder: "如 custom_analyst"
              }, null, 512), [
                [vModelText, createForm.value.name]
              ])
            ]),
            createBaseVNode("div", _hoisted_28, [
              _cache[12] || (_cache[12] = createBaseVNode("label", null, "显示名", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => createForm.value.display_name = $event),
                class: "input",
                placeholder: "如 自定义分析员"
              }, null, 512), [
                [vModelText, createForm.value.display_name]
              ])
            ]),
            createBaseVNode("div", _hoisted_29, [
              _cache[13] || (_cache[13] = createBaseVNode("label", null, "描述", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => createForm.value.description = $event),
                class: "input",
                placeholder: "可选"
              }, null, 512), [
                [vModelText, createForm.value.description]
              ])
            ]),
            createBaseVNode("div", _hoisted_30, [
              _cache[14] || (_cache[14] = createBaseVNode("label", null, "初始权限", -1)),
              createBaseVNode("div", _hoisted_31, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(groupedPermissions.value, (g) => {
                  return openBlock(), createElementBlock("div", {
                    key: g.group,
                    class: "perm-group"
                  }, [
                    createBaseVNode("div", _hoisted_32, toDisplayString(g.label), 1),
                    createBaseVNode("div", _hoisted_33, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(g.perms, (p) => {
                        return openBlock(), createElementBlock("label", {
                          key: p.code,
                          class: "perm-item"
                        }, [
                          createBaseVNode("input", {
                            type: "checkbox",
                            checked: createSelected.value.has(p.code),
                            onChange: ($event) => toggleCreate(p.code, $event.target.checked)
                          }, null, 40, _hoisted_34),
                          createBaseVNode("span", _hoisted_35, toDisplayString(p.code), 1),
                          createBaseVNode("span", _hoisted_36, toDisplayString(p.name), 1)
                        ]);
                      }), 128))
                    ])
                  ]);
                }), 128))
              ])
            ]),
            createBaseVNode("div", _hoisted_37, [
              createBaseVNode("button", {
                class: "btn",
                onClick: _cache[4] || (_cache[4] = ($event) => createOpen.value = false)
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-primary",
                onClick: createRole,
                disabled: saving.value
              }, toDisplayString(saving.value ? "创建中..." : "创建"), 9, _hoisted_38)
            ])
          ])
        ])) : createCommentVNode("", true)
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Roles = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-6dfec79a"]]);

export { Roles as default };
