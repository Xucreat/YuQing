import { d as defineComponent, z as usePermission, C as onMounted, E as ElMessage, w as withDirectives, c as createElementBlock, a as createBaseVNode, H as unref, s as createCommentVNode, F as Fragment, i as renderList, L as withModifiers, t as toDisplayString, e as createTextVNode, v as vModelText, r as ref, j as computed, g as api, B as resolveDirective, o as openBlock, n as normalizeClass, q as createBlock, p as withCtx, M as ElMessageBox, y as resolveComponent, _ as _export_sfc } from './index-CmcgaaTj.js';

const _hoisted_1 = { class: "roles-page" };
const _hoisted_2 = { class: "toolbar" };
const _hoisted_3 = { class: "card" };
const _hoisted_4 = { class: "tbl" };
const _hoisted_5 = { class: "role-name" };
const _hoisted_6 = {
  key: 0,
  class: "role-code"
};
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
const _hoisted_11 = ["disabled", "title", "onClick"];
const _hoisted_12 = ["onClick"];
const _hoisted_13 = {
  key: 2,
  class: "muted"
};
const _hoisted_14 = { key: 0 };
const _hoisted_15 = { class: "modal modal-wide" };
const _hoisted_16 = {
  key: 0,
  class: "banner"
};
const _hoisted_17 = { class: "permission-mode-bar" };
const _hoisted_18 = ["aria-expanded"];
const _hoisted_19 = { class: "perm-groups" };
const _hoisted_20 = { class: "perm-group-title" };
const _hoisted_21 = {
  key: 0,
  class: "perm-group-note"
};
const _hoisted_22 = { class: "perm-grid" };
const _hoisted_23 = ["checked", "disabled", "onChange"];
const _hoisted_24 = { class: "perm-copy" };
const _hoisted_25 = { class: "perm-line" };
const _hoisted_26 = { class: "perm-code" };
const _hoisted_27 = { class: "perm-name" };
const _hoisted_28 = {
  key: 0,
  class: "perm-desc"
};
const _hoisted_29 = ["aria-label"];
const _hoisted_30 = { class: "form-actions" };
const _hoisted_31 = ["disabled"];
const _hoisted_32 = { class: "modal modal-wide" };
const _hoisted_33 = { class: "form-group" };
const _hoisted_34 = { class: "form-group" };
const _hoisted_35 = { class: "form-group" };
const _hoisted_36 = { class: "form-group" };
const _hoisted_37 = { class: "form-group" };
const _hoisted_38 = { class: "permission-mode-bar compact-mode-bar" };
const _hoisted_39 = ["aria-expanded"];
const _hoisted_40 = { class: "perm-groups compact" };
const _hoisted_41 = { class: "perm-group-title" };
const _hoisted_42 = {
  key: 0,
  class: "perm-group-note"
};
const _hoisted_43 = { class: "perm-grid" };
const _hoisted_44 = ["checked", "onChange"];
const _hoisted_45 = { class: "perm-copy" };
const _hoisted_46 = { class: "perm-line" };
const _hoisted_47 = { class: "perm-code" };
const _hoisted_48 = { class: "perm-name" };
const _hoisted_49 = {
  key: 0,
  class: "perm-desc"
};
const _hoisted_50 = ["aria-label"];
const _hoisted_51 = { class: "form-actions" };
const _hoisted_52 = ["disabled"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Roles",
  setup(__props) {
    const { hasPermission } = usePermission();
    const canWrite = hasPermission("roles:write");
    const canDelete = hasPermission("roles:delete");
    const loading = ref(false);
    const saving = ref(false);
    const roleToggleId = ref(null);
    const roles = ref([]);
    const catalog = ref([]);
    const GROUP_LABEL = {
      舆情管理: "舆情",
      事件管理: "事件",
      关键词管理: "关键词",
      用户管理: "用户",
      角色管理: "角色",
      权限管理: "权限",
      预警管理: "预警",
      报告: "报告",
      AI能力: "AI 能力",
      数据源: "数据源",
      采集管理: "采集器",
      传播溯源: "传播",
      驾驶舱: "驾驶舱",
      审计: "审计/登录日志",
      外网风险: "外网风险",
      "Foreign alerts": "外网告警",
      "Foreign events": "外网事件",
      "Foreign sources": "外网数据源",
      "Foreign combined": "外网组合权限"
    };
    const GROUP_ORDER = {
      舆情管理: 1,
      事件管理: 2,
      关键词管理: 3,
      用户管理: 4,
      角色管理: 5,
      权限管理: 6,
      预警管理: 7,
      报告: 8,
      AI能力: 9,
      数据源: 10,
      采集管理: 11,
      传播溯源: 12,
      驾驶舱: 13,
      审计: 14,
      "Foreign combined": 0,
      外网风险: 15,
      "Foreign sources": 16,
      "Foreign alerts": 17,
      "Foreign events": 18
    };
    const PERM_NAME_LABEL = {
      "foreign:read": "外网查看（组合）",
      "foreign:data:manage": "外网数据管理（组合）",
      "foreign:analysis": "外网分析（组合）",
      "foreign:alerts:manage": "外网预警管理（组合）",
      "foreign:alerts:acknowledge": "确认外网告警",
      "foreign:alerts:enable": "启用外网告警规则",
      "foreign:alerts:evaluate": "评估外网告警",
      "foreign:alerts:read": "查看外网告警",
      "foreign:alerts:resolve": "处理外网告警",
      "foreign:alerts:rules:read": "查看外网告警规则",
      "foreign:alerts:rules:write": "编辑外网告警规则",
      "foreign:alerts:suppress": "屏蔽外网告警",
      "foreign:events:candidates:read": "查看外网事件候选",
      "foreign:events:confirm": "确认外网事件候选",
      "foreign:events:merge": "合并外网事件",
      "foreign:events:read": "查看外网事件",
      "foreign:events:rebuild": "重建外网事件候选",
      "foreign:events:split": "拆分外网事件",
      "foreign:events:status": "变更外网事件状态",
      "foreign:ai:analyze": "用 AI 分析外网",
      "foreign:alerts:ai-admit": "准入外网 AI 告警",
      "foreign:events:auto-aggregate": "外网事件自动聚合",
      "foreign:events:write": "外网事件写入",
      "foreign:keywords:read": "查看外网关键词",
      "foreign:keywords:write": "编辑外网关键词",
      "foreign:opinions:read": "查看外网舆情",
      "foreign:sources:read": "查看外网数据源",
      "foreign:sources:test": "测试外网数据源",
      "foreign:sources:write": "编辑外网数据源"
    };
    function permNameLabel(p) {
      return PERM_NAME_LABEL[p.code] || p.name;
    }
    const groupedPermissions = computed(() => {
      const map = /* @__PURE__ */ new Map();
      for (const p of catalog.value) {
        if (!map.has(p.group)) map.set(p.group, []);
        map.get(p.group).push(p);
      }
      return [...map.entries()].sort((a, b) => (GROUP_ORDER[a[0]] ?? 99) - (GROUP_ORDER[b[0]] ?? 99)).map(([group, perms]) => ({ group, label: GROUP_LABEL[group] || group, perms: perms.sort((a, b) => a.code.localeCompare(b.code)) }));
    });
    const editorOpen = ref(false);
    const editingRole = ref(null);
    const selected = ref(/* @__PURE__ */ new Set());
    const isAdminRole = computed(() => editingRole.value?.code === "admin");
    const showLegacyPermissions = ref(false);
    const showLegacyCreate = ref(false);
    const FOREIGN_LEGACY_GROUPS = /* @__PURE__ */ new Set(["外网风险", "Foreign sources", "Foreign alerts", "Foreign events"]);
    function isForeignLegacyGroup(group) {
      return FOREIGN_LEGACY_GROUPS.has(group);
    }
    const legacyPermissionGroups = computed(() => groupedPermissions.value.filter((group) => isForeignLegacyGroup(group.group)));
    const visiblePermissionGroups = computed(() => groupedPermissions.value.filter((group) => !isForeignLegacyGroup(group.group) || showLegacyPermissions.value));
    const visibleCreatePermissionGroups = computed(() => groupedPermissions.value.filter((group) => !isForeignLegacyGroup(group.group) || showLegacyCreate.value));
    const legacyPermissionCount = computed(() => legacyPermissionGroups.value.reduce((total, group) => total + group.perms.length, 0));
    function toggle(code, checked) {
      const s = new Set(selected.value);
      if (checked) s.add(code);
      else s.delete(code);
      selected.value = s;
    }
    async function openEditor(r) {
      editingRole.value = r;
      showLegacyPermissions.value = false;
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
      showLegacyCreate.value = false;
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
    async function toggleRole(role) {
      if (role.is_system) return ElMessage.warning("系统角色不可停用");
      roleToggleId.value = role.id;
      try {
        await api.put("/roles/" + role.id, { is_enabled: !role.is_enabled });
        ElMessage.success(role.is_enabled ? "角色已停用" : "角色已启用");
        await loadRoles();
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || "角色状态更新失败");
      } finally {
        roleToggleId.value = null;
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
      const _component_el_tooltip = resolveComponent("el-tooltip");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          _cache[10] || (_cache[10] = createBaseVNode("h3", { class: "section-title" }, "角色权限", -1)),
          unref(canWrite) ? (openBlock(), createElementBlock("button", {
            key: 0,
            class: "btn btn-primary",
            onClick: openCreate
          }, "+ 新建角色")) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_3, [
          createBaseVNode("table", _hoisted_4, [
            _cache[12] || (_cache[12] = createBaseVNode("thead", null, [
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
                    r.code && r.code !== r.name ? (openBlock(), createElementBlock("span", _hoisted_6, toDisplayString(r.code), 1)) : createCommentVNode("", true)
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
                    unref(canWrite) ? (openBlock(), createElementBlock("button", {
                      key: 0,
                      class: normalizeClass(["btn btn-mini", { "is-disabled-action": r.is_system }]),
                      disabled: r.is_system || roleToggleId.value === r.id,
                      title: r.is_system ? "系统角色不可停用" : void 0,
                      onClick: ($event) => toggleRole(r)
                    }, toDisplayString(roleToggleId.value === r.id ? "处理中…" : r.is_enabled ? "停用" : "启用"), 11, _hoisted_11)) : createCommentVNode("", true),
                    unref(canDelete) && !r.is_system ? (openBlock(), createElementBlock("button", {
                      key: 1,
                      class: "btn btn-mini btn-danger",
                      onClick: ($event) => handleDelete(r)
                    }, "删除", 8, _hoisted_12)) : r.is_system ? (openBlock(), createElementBlock("span", _hoisted_13, "—")) : createCommentVNode("", true)
                  ])
                ]);
              }), 128)),
              !roles.value.length ? (openBlock(), createElementBlock("tr", _hoisted_14, [..._cache[11] || (_cache[11] = [
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
          createBaseVNode("div", _hoisted_15, [
            createBaseVNode("h3", null, toDisplayString(editingRole.value?.display_name || "") + " · 权限配置", 1),
            isAdminRole.value ? (openBlock(), createElementBlock("p", _hoisted_16, [..._cache[13] || (_cache[13] = [
              createTextVNode(" 该角色为", -1),
              createBaseVNode("strong", null, "超管角色", -1),
              createTextVNode("，拥有全部权限（后端按 ", -1),
              createBaseVNode("code", null, "role='admin'", -1),
              createTextVNode(" 或 ", -1),
              createBaseVNode("code", null, "is_superuser", -1),
              createTextVNode(" 放行），无需单独勾选。 ", -1)
            ])])) : createCommentVNode("", true),
            createBaseVNode("div", _hoisted_17, [
              _cache[14] || (_cache[14] = createBaseVNode("div", null, [
                createBaseVNode("strong", null, "权限配置"),
                createBaseVNode("span", null, "默认展示四类外网组合权限；外网旧细粒度权限保留在兼容区，其他权限保持原样。")
              ], -1)),
              createBaseVNode("button", {
                type: "button",
                class: "compatibility-toggle",
                "aria-expanded": showLegacyPermissions.value,
                onClick: _cache[0] || (_cache[0] = ($event) => showLegacyPermissions.value = !showLegacyPermissions.value)
              }, toDisplayString(showLegacyPermissions.value ? "收起兼容权限" : `展开兼容权限（${legacyPermissionCount.value}项）`), 9, _hoisted_18)
            ]),
            createBaseVNode("div", _hoisted_19, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(visiblePermissionGroups.value, (g) => {
                return openBlock(), createElementBlock("div", {
                  key: g.group,
                  class: normalizeClass(["perm-group", { "foreign-combined-group": g.group === "Foreign combined", "legacy-permission-group": isForeignLegacyGroup(g.group) }])
                }, [
                  createBaseVNode("div", _hoisted_20, toDisplayString(g.label), 1),
                  g.group === "Foreign combined" ? (openBlock(), createElementBlock("div", _hoisted_21, " 四类组合权限按业务场景归类；保存后由后端自动展开为兼容的细粒度权限。 ")) : createCommentVNode("", true),
                  createBaseVNode("div", _hoisted_22, [
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
                        }, null, 40, _hoisted_23),
                        createBaseVNode("span", _hoisted_24, [
                          createBaseVNode("span", _hoisted_25, [
                            createBaseVNode("span", _hoisted_26, toDisplayString(p.code), 1),
                            createBaseVNode("span", _hoisted_27, toDisplayString(permNameLabel(p)), 1)
                          ]),
                          g.group !== "Foreign combined" ? (openBlock(), createElementBlock("span", _hoisted_28, toDisplayString(p.description), 1)) : createCommentVNode("", true)
                        ]),
                        g.group === "Foreign combined" || p.description && p.description.length > 42 ? (openBlock(), createBlock(_component_el_tooltip, {
                          key: 0,
                          content: p.description || permNameLabel(p),
                          placement: "top",
                          "show-after": 200
                        }, {
                          default: withCtx(() => [
                            createBaseVNode("button", {
                              type: "button",
                              class: "perm-help",
                              "aria-label": `${permNameLabel(p)}说明`,
                              onClick: _cache[1] || (_cache[1] = withModifiers(() => {
                              }, ["prevent", "stop"]))
                            }, "?", 8, _hoisted_29)
                          ]),
                          _: 2
                        }, 1032, ["content"])) : createCommentVNode("", true)
                      ], 2);
                    }), 128))
                  ])
                ], 2);
              }), 128))
            ]),
            createBaseVNode("div", _hoisted_30, [
              createBaseVNode("button", {
                class: "btn",
                onClick: closeEditor
              }, "关闭"),
              unref(canWrite) && !isAdminRole.value ? (openBlock(), createElementBlock("button", {
                key: 0,
                class: "btn btn-primary",
                onClick: savePermissions,
                disabled: saving.value
              }, toDisplayString(saving.value ? "保存中..." : "保存权限"), 9, _hoisted_31)) : createCommentVNode("", true)
            ])
          ])
        ])) : createCommentVNode("", true),
        createOpen.value ? (openBlock(), createElementBlock("div", {
          key: 1,
          class: "modal-overlay",
          onClick: _cache[9] || (_cache[9] = withModifiers(($event) => createOpen.value = false, ["self"]))
        }, [
          createBaseVNode("div", _hoisted_32, [
            _cache[21] || (_cache[21] = createBaseVNode("h3", null, "新建角色", -1)),
            createBaseVNode("div", _hoisted_33, [
              _cache[15] || (_cache[15] = createBaseVNode("label", null, "角色代码（code，英文唯一）", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => createForm.value.code = $event),
                class: "input",
                placeholder: "如 custom_analyst"
              }, null, 512), [
                [vModelText, createForm.value.code]
              ])
            ]),
            createBaseVNode("div", _hoisted_34, [
              _cache[16] || (_cache[16] = createBaseVNode("label", null, "角色名（name，唯一）", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => createForm.value.name = $event),
                class: "input",
                placeholder: "如 custom_analyst"
              }, null, 512), [
                [vModelText, createForm.value.name]
              ])
            ]),
            createBaseVNode("div", _hoisted_35, [
              _cache[17] || (_cache[17] = createBaseVNode("label", null, "显示名", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => createForm.value.display_name = $event),
                class: "input",
                placeholder: "如 自定义分析员"
              }, null, 512), [
                [vModelText, createForm.value.display_name]
              ])
            ]),
            createBaseVNode("div", _hoisted_36, [
              _cache[18] || (_cache[18] = createBaseVNode("label", null, "描述", -1)),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => createForm.value.description = $event),
                class: "input",
                placeholder: "可选"
              }, null, 512), [
                [vModelText, createForm.value.description]
              ])
            ]),
            createBaseVNode("div", _hoisted_37, [
              _cache[20] || (_cache[20] = createBaseVNode("label", null, "初始权限", -1)),
              createBaseVNode("div", _hoisted_38, [
                _cache[19] || (_cache[19] = createBaseVNode("span", null, "默认显示四类外网组合权限；外网旧细粒度权限保留在兼容区。", -1)),
                createBaseVNode("button", {
                  type: "button",
                  class: "compatibility-toggle",
                  "aria-expanded": showLegacyCreate.value,
                  onClick: _cache[6] || (_cache[6] = ($event) => showLegacyCreate.value = !showLegacyCreate.value)
                }, toDisplayString(showLegacyCreate.value ? "收起兼容权限" : `展开兼容权限（${legacyPermissionCount.value}项）`), 9, _hoisted_39)
              ]),
              createBaseVNode("div", _hoisted_40, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(visibleCreatePermissionGroups.value, (g) => {
                  return openBlock(), createElementBlock("div", {
                    key: g.group,
                    class: normalizeClass(["perm-group", { "foreign-combined-group": g.group === "Foreign combined", "legacy-permission-group": isForeignLegacyGroup(g.group) }])
                  }, [
                    createBaseVNode("div", _hoisted_41, toDisplayString(g.label), 1),
                    g.group === "Foreign combined" ? (openBlock(), createElementBlock("div", _hoisted_42, "四类组合权限保存后由后端自动展开为兼容的细粒度权限。")) : createCommentVNode("", true),
                    createBaseVNode("div", _hoisted_43, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(g.perms, (p) => {
                        return openBlock(), createElementBlock("label", {
                          key: p.code,
                          class: "perm-item"
                        }, [
                          createBaseVNode("input", {
                            type: "checkbox",
                            checked: createSelected.value.has(p.code),
                            onChange: ($event) => toggleCreate(p.code, $event.target.checked)
                          }, null, 40, _hoisted_44),
                          createBaseVNode("span", _hoisted_45, [
                            createBaseVNode("span", _hoisted_46, [
                              createBaseVNode("span", _hoisted_47, toDisplayString(p.code), 1),
                              createBaseVNode("span", _hoisted_48, toDisplayString(permNameLabel(p)), 1)
                            ]),
                            g.group !== "Foreign combined" ? (openBlock(), createElementBlock("span", _hoisted_49, toDisplayString(p.description), 1)) : createCommentVNode("", true)
                          ]),
                          g.group === "Foreign combined" || p.description && p.description.length > 42 ? (openBlock(), createBlock(_component_el_tooltip, {
                            key: 0,
                            content: p.description || permNameLabel(p),
                            placement: "top",
                            "show-after": 200
                          }, {
                            default: withCtx(() => [
                              createBaseVNode("button", {
                                type: "button",
                                class: "perm-help",
                                "aria-label": `${permNameLabel(p)}说明`,
                                onClick: _cache[7] || (_cache[7] = withModifiers(() => {
                                }, ["prevent", "stop"]))
                              }, "?", 8, _hoisted_50)
                            ]),
                            _: 2
                          }, 1032, ["content"])) : createCommentVNode("", true)
                        ]);
                      }), 128))
                    ])
                  ], 2);
                }), 128))
              ])
            ]),
            createBaseVNode("div", _hoisted_51, [
              createBaseVNode("button", {
                class: "btn",
                onClick: _cache[8] || (_cache[8] = ($event) => createOpen.value = false)
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-primary",
                onClick: createRole,
                disabled: saving.value
              }, toDisplayString(saving.value ? "创建中..." : "创建"), 9, _hoisted_52)
            ])
          ])
        ])) : createCommentVNode("", true)
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Roles = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-94f7fb69"]]);

export { Roles as default };
