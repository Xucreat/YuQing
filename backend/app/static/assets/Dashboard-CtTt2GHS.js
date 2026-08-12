import { i as init, L as LinearGradient } from './index-F2TANFn2.js';
import './wordCloud-DTX2zCb6.js';
import { g as api, d as defineComponent, c as createElementBlock, F as Fragment, i as renderList, o as openBlock, n as normalizeClass, t as toDisplayString, _ as _export_sfc, a as createBaseVNode, j as computed, k as normalizeStyle, l as useModel, m as createVNode, p as withCtx, e as createTextVNode, q as createBlock, s as createCommentVNode, x as mergeModels, r as ref, y as resolveComponent, z as usePermission, A as watch, w as withDirectives, E as ElMessage, B as resolveDirective, C as onMounted, D as nextTick, G as onBeforeUnmount, H as unref, f as reactive, h as useRouter } from './index-DeFgZMxo.js';
import { t as topicValueFromLabel, e as eventStatusPill, a as eventStatusLabel } from './event-DY3DZBkH.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-BGFQV1li.js';
import './admission-DpEuIHXC.js';
import './opinion-Cag9WtuS.js';

async function getEventsByHotTopic(keyword) {
  const { data } = await api.get(`/events/hot-topic/${encodeURI(keyword)}`);
  return data;
}

const _hoisted_1$4 = { class: "seg-group" };
const _hoisted_2$4 = ["onClick"];
const _sfc_main$4 = /* @__PURE__ */ defineComponent({
  __name: "SegmentedControl",
  props: {
    modelValue: {},
    options: {}
  },
  emits: ["update:modelValue"],
  setup(__props) {
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$4, [
        (openBlock(true), createElementBlock(Fragment, null, renderList(__props.options, (opt) => {
          return openBlock(), createElementBlock("button", {
            key: opt.value,
            class: normalizeClass(["seg-btn", { active: __props.modelValue === opt.value }]),
            onClick: ($event) => _ctx.$emit("update:modelValue", opt.value)
          }, toDisplayString(opt.label), 11, _hoisted_2$4);
        }), 128))
      ]);
    };
  }
});

const SegmentedControl = /* @__PURE__ */ _export_sfc(_sfc_main$4, [["__scopeId", "data-v-ae024c45"]]);

const _hoisted_1$3 = { class: "donut-wrap" };
const _hoisted_2$3 = {
  class: "donut-svg",
  viewBox: "0 0 140 140"
};
const _hoisted_3$3 = ["stroke", "stroke-dasharray", "stroke-dashoffset"];
const _hoisted_4$3 = {
  x: "70",
  y: "66",
  "text-anchor": "middle",
  "font-size": "28",
  "font-weight": "600",
  fill: "#1d1d1f"
};
const _hoisted_5$3 = { class: "donut-legends" };
const _sfc_main$3 = /* @__PURE__ */ defineComponent({
  __name: "SentimentDonut",
  props: {
    data: {}
  },
  setup(__props) {
    const props = __props;
    const total = computed(() => props.data.reduce((s, d) => s + d.count, 0));
    const circumference = 2 * Math.PI * 58;
    const segments = computed(() => {
      let offset = 0;
      return props.data.map((d) => {
        const pct = total.value > 0 ? d.count / total.value : 0;
        const dash = pct * circumference;
        const seg = {
          ...d,
          pct: Math.round(pct * 100),
          dashArray: dash || 0,
          dashOffset: -offset
        };
        offset += dash;
        return seg;
      });
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$3, [
        (openBlock(), createElementBlock("svg", _hoisted_2$3, [
          _cache[0] || (_cache[0] = createBaseVNode("circle", {
            cx: "70",
            cy: "70",
            r: "58",
            fill: "none",
            stroke: "#e8e8ed",
            "stroke-width": "16"
          }, null, -1)),
          (openBlock(true), createElementBlock(Fragment, null, renderList(segments.value, (seg, i) => {
            return openBlock(), createElementBlock("circle", {
              key: i,
              cx: "70",
              cy: "70",
              r: "58",
              fill: "none",
              stroke: seg.color,
              "stroke-width": "16",
              "stroke-dasharray": seg.dashArray + " " + (364.4 - seg.dashArray),
              "stroke-dashoffset": seg.dashOffset,
              "stroke-linecap": "round",
              transform: "rotate(-90 70 70)"
            }, null, 8, _hoisted_3$3);
          }), 128)),
          createBaseVNode("text", _hoisted_4$3, toDisplayString(total.value), 1),
          _cache[1] || (_cache[1] = createBaseVNode("text", {
            x: "70",
            y: "85",
            "text-anchor": "middle",
            "font-size": "10",
            fill: "#86868b"
          }, " 总计 ", -1))
        ])),
        createBaseVNode("div", _hoisted_5$3, [
          (openBlock(true), createElementBlock(Fragment, null, renderList(segments.value, (seg) => {
            return openBlock(), createElementBlock("div", {
              key: seg.label,
              class: "donut-legend"
            }, [
              createBaseVNode("span", {
                class: "dl-dot",
                style: normalizeStyle({ background: seg.color })
              }, null, 4),
              createBaseVNode("span", null, toDisplayString(seg.label), 1),
              createBaseVNode("i", null, toDisplayString(seg.pct) + "%", 1),
              createBaseVNode("b", null, toDisplayString(seg.count), 1)
            ]);
          }), 128))
        ])
      ]);
    };
  }
});

const SentimentDonut = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-1e1d467a"]]);

function getReportModules() {
  return api.get("/reports/modules");
}
function generateReport(payload) {
  return api.post("/reports/export", payload, { responseType: "blob" });
}
function getTemplates() {
  return api.get("/reports/templates");
}
function createTemplate(payload) {
  return api.post("/reports/templates", payload);
}
function deleteTemplate(id) {
  return api.delete(`/reports/templates/${id}`);
}

const _hoisted_1$2 = { class: "module-list" };
const _hoisted_2$2 = { class: "module-idx" };
const _hoisted_3$2 = { class: "module-title" };
const _hoisted_4$2 = { class: "module-ops" };
const _hoisted_5$2 = {
  key: 0,
  class: "module-add"
};
const _hoisted_6$2 = {
  key: 1,
  class: "form-hint warn"
};
const _sfc_main$2 = /* @__PURE__ */ defineComponent({
  __name: "ModuleSelector",
  props: /* @__PURE__ */ mergeModels({
    modules: {}
  }, {
    "modelValue": { required: true },
    "modelModifiers": {}
  }),
  emits: ["update:modelValue"],
  setup(__props) {
    const model = useModel(__props, "modelValue");
    const props = __props;
    const toAdd = ref("");
    const available = computed(
      () => props.modules.filter((m) => !model.value.includes(m.key))
    );
    function titleOf(key) {
      return props.modules.find((m) => m.key === key)?.title || key;
    }
    function move(idx, dir) {
      const j = idx + dir;
      if (j < 0 || j >= model.value.length) return;
      const arr = [...model.value];
      [arr[idx], arr[j]] = [arr[j], arr[idx]];
      model.value = arr;
    }
    function remove(idx) {
      const arr = [...model.value];
      arr.splice(idx, 1);
      model.value = arr;
    }
    function add(key) {
      if (key && !model.value.includes(key)) {
        model.value = [...model.value, key];
      }
      toAdd.value = "";
    }
    return (_ctx, _cache) => {
      const _component_el_button = resolveComponent("el-button");
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      return openBlock(), createElementBlock("div", _hoisted_1$2, [
        (openBlock(true), createElementBlock(Fragment, null, renderList(model.value, (key, idx) => {
          return openBlock(), createElementBlock("div", {
            key,
            class: "module-item"
          }, [
            createBaseVNode("span", _hoisted_2$2, toDisplayString(idx + 1), 1),
            createBaseVNode("span", _hoisted_3$2, toDisplayString(titleOf(key)), 1),
            createBaseVNode("span", _hoisted_4$2, [
              createVNode(_component_el_button, {
                link: "",
                disabled: idx === 0,
                onClick: ($event) => move(idx, -1),
                title: "上移"
              }, {
                default: withCtx(() => [..._cache[1] || (_cache[1] = [
                  createTextVNode("↑", -1)
                ])]),
                _: 1
              }, 8, ["disabled", "onClick"]),
              createVNode(_component_el_button, {
                link: "",
                disabled: idx === model.value.length - 1,
                onClick: ($event) => move(idx, 1),
                title: "下移"
              }, {
                default: withCtx(() => [..._cache[2] || (_cache[2] = [
                  createTextVNode("↓", -1)
                ])]),
                _: 1
              }, 8, ["disabled", "onClick"]),
              createVNode(_component_el_button, {
                link: "",
                type: "danger",
                onClick: ($event) => remove(idx),
                title: "移除"
              }, {
                default: withCtx(() => [..._cache[3] || (_cache[3] = [
                  createTextVNode("✕", -1)
                ])]),
                _: 1
              }, 8, ["onClick"])
            ])
          ]);
        }), 128)),
        available.value.length ? (openBlock(), createElementBlock("div", _hoisted_5$2, [
          _cache[4] || (_cache[4] = createBaseVNode("span", { class: "add-label" }, "添加模块：", -1)),
          createVNode(_component_el_select, {
            modelValue: toAdd.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => toAdd.value = $event),
            placeholder: "选择未选模块",
            onChange: add,
            clearable: ""
          }, {
            default: withCtx(() => [
              (openBlock(true), createElementBlock(Fragment, null, renderList(available.value, (m) => {
                return openBlock(), createBlock(_component_el_option, {
                  key: m.key,
                  value: m.key,
                  label: m.title
                }, null, 8, ["value", "label"]);
              }), 128))
            ]),
            _: 1
          }, 8, ["modelValue"])
        ])) : createCommentVNode("", true),
        !model.value.length ? (openBlock(), createElementBlock("div", _hoisted_6$2, "未选择任何模块，生成将失败。")) : createCommentVNode("", true)
      ]);
    };
  }
});

const ModuleSelector = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-8665a50e"]]);

const _hoisted_1$1 = { class: "tpl-row" };
const _hoisted_2$1 = {
  key: 0,
  class: "param-zone"
};
const _hoisted_3$1 = { class: "param-block-title" };
const _hoisted_4$1 = {
  key: 0,
  class: "param-rows"
};
const _hoisted_5$1 = { class: "param-label" };
const _hoisted_6$1 = {
  key: 1,
  class: "form-hint"
};
const _hoisted_7$1 = {
  key: 0,
  class: "form-hint warn"
};
const _sfc_main$1 = /* @__PURE__ */ defineComponent({
  __name: "ReportExportDrawer",
  props: {
    "modelValue": { type: Boolean, ...{ required: true } },
    "modelModifiers": {}
  },
  emits: ["update:modelValue"],
  setup(__props) {
    const open = useModel(__props, "modelValue");
    const reporting = ref(false);
    const loadingModules = ref(false);
    const reportName = ref("舆情监测报告");
    const reportTimeField = ref("created_at");
    const reportRangeMode = ref("preset");
    const reportPresetDays = ref(7);
    const reportCustomRange = ref(null);
    const allModules = ref([]);
    const selectedModules = ref([]);
    const moduleParams = ref({});
    const templates = ref([]);
    const selectedTemplateId = ref(null);
    const loadingTemplates = ref(false);
    const saveDialogVisible = ref(false);
    const savingTemplate = ref(false);
    const deleting = ref(false);
    const templateForm = ref({
      name: "",
      description: "",
      is_public: false
    });
    function buildDefaults(def) {
      const o = {};
      for (const p of def.params) o[p.key] = p.default;
      return o;
    }
    const selectedWithParams = computed(
      () => selectedModules.value.map((key) => allModules.value.find((m) => m.key === key)).filter((m) => !!m && !!m.params && m.params.length > 0)
    );
    const { hasPermission } = usePermission();
    const canManageTemplate = computed(() => hasPermission("reports:manage"));
    const currentTemplateCanEdit = computed(() => {
      const t = templates.value.find((t2) => t2.id === selectedTemplateId.value);
      return !!t && t.can_edit && canManageTemplate.value;
    });
    const templateNameConflict = computed(() => {
      const name = templateForm.value.name.trim().toLowerCase();
      if (!name) return false;
      return templates.value.some((t) => t.name.trim().toLowerCase() === name);
    });
    watch(
      selectedModules,
      (keys) => {
        const set = new Set(keys);
        for (const k of Object.keys(moduleParams.value)) {
          if (!set.has(k)) delete moduleParams.value[k];
        }
        for (const k of keys) {
          const def = allModules.value.find((m) => m.key === k);
          if (def && def.params && def.params.length && !moduleParams.value[k]) {
            moduleParams.value[k] = buildDefaults(def);
          }
        }
      },
      { deep: false }
    );
    async function onOpen() {
      if (loadingModules.value) return;
      loadingModules.value = true;
      try {
        const { data } = await getReportModules();
        allModules.value = data.modules || [];
        if (!selectedModules.value.length) {
          selectedModules.value = [...data.default_modules || allModules.value.map((m) => m.key)];
        }
        for (const key of selectedModules.value) {
          const def = allModules.value.find((m) => m.key === key);
          if (def && def.params && def.params.length && !moduleParams.value[key]) {
            moduleParams.value[key] = buildDefaults(def);
          }
        }
      } catch {
        allModules.value = [];
        selectedModules.value = [];
        ElMessage.error("获取报告模块清单失败");
      } finally {
        loadingModules.value = false;
      }
      await loadTemplates();
    }
    async function loadTemplates() {
      if (loadingTemplates.value) return;
      loadingTemplates.value = true;
      try {
        const { data } = await getTemplates();
        templates.value = data || [];
      } catch {
        templates.value = [];
      } finally {
        loadingTemplates.value = false;
      }
    }
    function applyConfigToForm(cfg) {
      reportName.value = cfg.name || "舆情监测报告";
      reportTimeField.value = cfg.time_field || "created_at";
      if (cfg.range_type === "custom") {
        reportRangeMode.value = "custom";
        reportCustomRange.value = cfg.start_date && cfg.end_date ? [cfg.start_date, cfg.end_date] : null;
      } else {
        reportRangeMode.value = "preset";
        reportPresetDays.value = cfg.range_days || 7;
      }
      selectedModules.value = (cfg.modules || []).map(
        (m) => typeof m === "string" ? m : m.key
      );
      const params = {};
      for (const m of cfg.modules || []) {
        if (typeof m === "string") continue;
        const def = allModules.value.find((d) => d.key === m.key);
        if (def && def.params && def.params.length) {
          const stored = m.params || {};
          const out = {};
          for (const p of def.params) {
            out[p.key] = stored[p.key] !== void 0 ? stored[p.key] : p.default;
          }
          params[m.key] = out;
        }
      }
      moduleParams.value = params;
    }
    function onTemplateSelected() {
      const tpl = templates.value.find((t) => t.id === selectedTemplateId.value);
      if (!tpl) return;
      applyConfigToForm(tpl.config_json);
    }
    function buildConfigFromForm() {
      const isCustom = reportRangeMode.value === "custom";
      const modulesPayload = selectedModules.value.map((key) => {
        const def = allModules.value.find((m) => m.key === key);
        if (def && def.params && def.params.length) {
          return { key, params: collectParams(key, def) };
        }
        return key;
      });
      return {
        name: reportName.value.trim() || "舆情监测报告",
        time_field: reportTimeField.value,
        range_type: isCustom ? "custom" : "last_n_days",
        range_days: isCustom ? 7 : reportPresetDays.value,
        start_date: isCustom && reportCustomRange.value ? reportCustomRange.value[0] : null,
        end_date: isCustom && reportCustomRange.value ? reportCustomRange.value[1] : null,
        modules: modulesPayload
      };
    }
    function openSaveDialog() {
      templateForm.value = {
        name: reportName.value || "舆情监测报告",
        description: "",
        is_public: false
      };
      saveDialogVisible.value = true;
    }
    async function saveAsTemplate() {
      const name = templateForm.value.name.trim();
      if (!name) {
        ElMessage.warning("请输入模板名称");
        return;
      }
      if (templates.value.some((t) => t.name.trim().toLowerCase() === name.toLowerCase())) {
        ElMessage.warning(`模板名称已存在：${name}`);
        return;
      }
      savingTemplate.value = true;
      try {
        const config = buildConfigFromForm();
        const { data } = await createTemplate({
          name,
          description: templateForm.value.description || null,
          is_public: templateForm.value.is_public,
          config_json: config
        });
        ElMessage.success("已保存为模板");
        saveDialogVisible.value = false;
        await loadTemplates();
        selectedTemplateId.value = data.id;
      } catch (e) {
        let msg = "保存模板失败";
        try {
          const text = e?.response?.data ? await e.response.data.text() : "";
          const j = text ? JSON.parse(text) : null;
          if (j?.detail) msg = `保存模板失败：${j.detail}`;
        } catch {
        }
        ElMessage.error(msg);
      } finally {
        savingTemplate.value = false;
      }
    }
    async function onDeleteTemplate() {
      if (!selectedTemplateId.value) return;
      deleting.value = true;
      try {
        await deleteTemplate(selectedTemplateId.value);
        ElMessage.success("模板已删除");
        await loadTemplates();
        selectedTemplateId.value = null;
      } catch (e) {
        let msg = "删除模板失败";
        try {
          const text = e?.response?.data ? await e.response.data.text() : "";
          const j = text ? JSON.parse(text) : null;
          if (j?.detail) msg = `删除模板失败：${j.detail}`;
        } catch {
        }
        ElMessage.error(msg);
      } finally {
        deleting.value = false;
      }
    }
    function collectParams(key, def) {
      const stored = moduleParams.value[key] || {};
      const out = {};
      for (const p of def.params) {
        let v = stored[p.key];
        if (v === void 0 || v === null || v === "") v = p.default;
        if (p.type === "int" && v != null) v = Number(v);
        out[p.key] = v;
      }
      return out;
    }
    async function generateAndDownload() {
      if (!selectedModules.value.length) {
        ElMessage.warning("请至少选择一个报告模块");
        return;
      }
      const modulesPayload = selectedModules.value.map((key) => {
        const def = allModules.value.find((m) => m.key === key);
        if (def && def.params && def.params.length) {
          return { key, params: collectParams(key, def) };
        }
        return key;
      });
      const isCustom = reportRangeMode.value === "custom";
      const payload = {
        name: reportName.value.trim() || "舆情监测报告",
        time_field: reportTimeField.value,
        range_type: isCustom ? "custom" : "last_n_days",
        range_days: isCustom ? 7 : reportPresetDays.value,
        start_date: isCustom && reportCustomRange.value ? reportCustomRange.value[0] : null,
        end_date: isCustom && reportCustomRange.value ? reportCustomRange.value[1] : null,
        modules: modulesPayload,
        delivery: "download"
      };
      reporting.value = true;
      try {
        const res = await generateReport(payload);
        const blob = new Blob([res.data], { type: res.data.type || "application/pdf" });
        if (blob.size === 0) {
          ElMessage.error("生成的报告为空，请调整筛选条件后重试");
          return;
        }
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const now = /* @__PURE__ */ new Date();
        const ds = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`;
        a.download = `${payload.name}_${ds}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        ElMessage.success("报告已生成，开始下载");
        open.value = false;
      } catch (e) {
        let msg = "生成报告失败，请稍后重试";
        try {
          const text = e?.response?.data ? await e.response.data.text() : "";
          const j = text ? JSON.parse(text) : null;
          if (j?.detail) msg = `报告生成失败：${j.detail}`;
        } catch {
        }
        ElMessage.error(msg);
      } finally {
        reporting.value = false;
      }
    }
    return (_ctx, _cache) => {
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_button = resolveComponent("el-button");
      const _component_el_form_item = resolveComponent("el-form-item");
      const _component_el_input = resolveComponent("el-input");
      const _component_el_radio = resolveComponent("el-radio");
      const _component_el_radio_group = resolveComponent("el-radio-group");
      const _component_el_date_picker = resolveComponent("el-date-picker");
      const _component_el_input_number = resolveComponent("el-input-number");
      const _component_el_form = resolveComponent("el-form");
      const _component_el_switch = resolveComponent("el-switch");
      const _component_el_dialog = resolveComponent("el-dialog");
      const _component_el_drawer = resolveComponent("el-drawer");
      const _directive_loading = resolveDirective("loading");
      return openBlock(), createBlock(_component_el_drawer, {
        modelValue: open.value,
        "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => open.value = $event),
        title: "导出舆情报告",
        direction: "rtl",
        size: "460px",
        "close-on-click-modal": false,
        onOpen
      }, {
        footer: withCtx(() => [
          createVNode(_component_el_button, {
            onClick: _cache[7] || (_cache[7] = ($event) => open.value = false)
          }, {
            default: withCtx(() => [..._cache[21] || (_cache[21] = [
              createTextVNode("取消", -1)
            ])]),
            _: 1
          }),
          canManageTemplate.value ? (openBlock(), createBlock(_component_el_button, {
            key: 0,
            onClick: openSaveDialog,
            loading: savingTemplate.value
          }, {
            default: withCtx(() => [..._cache[22] || (_cache[22] = [
              createTextVNode("保存为模板", -1)
            ])]),
            _: 1
          }, 8, ["loading"])) : createCommentVNode("", true),
          createVNode(_component_el_button, {
            type: "primary",
            loading: reporting.value,
            onClick: generateAndDownload
          }, {
            default: withCtx(() => [..._cache[23] || (_cache[23] = [
              createTextVNode(" 生成并下载 PDF ", -1)
            ])]),
            _: 1
          }, 8, ["loading"])
        ]),
        default: withCtx(() => [
          withDirectives((openBlock(), createBlock(_component_el_form, {
            "label-position": "top",
            class: "report-form",
            "element-loading-text": "加载模块清单…"
          }, {
            default: withCtx(() => [
              createVNode(_component_el_form_item, { label: "报告模板" }, {
                default: withCtx(() => [
                  createBaseVNode("div", _hoisted_1$1, [
                    createVNode(_component_el_select, {
                      modelValue: selectedTemplateId.value,
                      "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => selectedTemplateId.value = $event),
                      placeholder: "选择模板以载入配置",
                      loading: loadingTemplates.value,
                      onChange: onTemplateSelected,
                      class: "tpl-select"
                    }, {
                      default: withCtx(() => [
                        (openBlock(true), createElementBlock(Fragment, null, renderList(templates.value, (t) => {
                          return openBlock(), createBlock(_component_el_option, {
                            key: t.id,
                            value: t.id,
                            label: (t.is_public ? "🌐 " : "") + t.name
                          }, null, 8, ["value", "label"]);
                        }), 128))
                      ]),
                      _: 1
                    }, 8, ["modelValue", "loading"]),
                    selectedTemplateId.value && currentTemplateCanEdit.value ? (openBlock(), createBlock(_component_el_button, {
                      key: 0,
                      type: "danger",
                      link: "",
                      loading: deleting.value,
                      onClick: onDeleteTemplate
                    }, {
                      default: withCtx(() => [..._cache[14] || (_cache[14] = [
                        createTextVNode("删除", -1)
                      ])]),
                      _: 1
                    }, 8, ["loading"])) : createCommentVNode("", true)
                  ]),
                  _cache[15] || (_cache[15] = createBaseVNode("div", { class: "form-hint" }, "模板 = 当前导出配置快照（不含投递方式）。🌐 为公共模板。", -1))
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "报告名称" }, {
                default: withCtx(() => [
                  createVNode(_component_el_input, {
                    modelValue: reportName.value,
                    "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => reportName.value = $event),
                    maxlength: "40",
                    "show-word-limit": "",
                    placeholder: "舆情监测报告"
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "统计时间字段" }, {
                default: withCtx(() => [
                  createVNode(_component_el_radio_group, {
                    modelValue: reportTimeField.value,
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => reportTimeField.value = $event)
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_radio, { value: "created_at" }, {
                        default: withCtx(() => [..._cache[16] || (_cache[16] = [
                          createTextVNode("采集时间", -1)
                        ])]),
                        _: 1
                      }),
                      createVNode(_component_el_radio, { value: "publish_time" }, {
                        default: withCtx(() => [..._cache[17] || (_cache[17] = [
                          createTextVNode("发布时间（缺失回退采集时间）", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  _cache[18] || (_cache[18] = createBaseVNode("div", { class: "form-hint" }, "发布时间为空的数据将回退使用采集时间（COALESCE），不丢弃。", -1))
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "统计时间范围" }, {
                default: withCtx(() => [
                  createVNode(_component_el_radio_group, {
                    modelValue: reportRangeMode.value,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => reportRangeMode.value = $event),
                    class: "range-mode"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_radio, { value: "preset" }, {
                        default: withCtx(() => [..._cache[19] || (_cache[19] = [
                          createTextVNode("预设周期", -1)
                        ])]),
                        _: 1
                      }),
                      createVNode(_component_el_radio, { value: "custom" }, {
                        default: withCtx(() => [..._cache[20] || (_cache[20] = [
                          createTextVNode("自定义区间", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  reportRangeMode.value === "preset" ? (openBlock(), createBlock(_component_el_select, {
                    key: 0,
                    modelValue: reportPresetDays.value,
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => reportPresetDays.value = $event),
                    class: "range-control"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_option, {
                        value: 7,
                        label: "近 7 天"
                      }),
                      createVNode(_component_el_option, {
                        value: 15,
                        label: "近 15 天"
                      }),
                      createVNode(_component_el_option, {
                        value: 30,
                        label: "近 30 天"
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"])) : (openBlock(), createBlock(_component_el_date_picker, {
                    key: 1,
                    modelValue: reportCustomRange.value,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => reportCustomRange.value = $event),
                    type: "daterange",
                    "value-format": "YYYY-MM-DD",
                    "range-separator": "至",
                    "start-placeholder": "开始日期",
                    "end-placeholder": "结束日期",
                    class: "range-control"
                  }, null, 8, ["modelValue"]))
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "报告模块（可增删与排序）" }, {
                default: withCtx(() => [
                  createVNode(ModuleSelector, {
                    modelValue: selectedModules.value,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => selectedModules.value = $event),
                    modules: allModules.value
                  }, null, 8, ["modelValue", "modules"])
                ]),
                _: 1
              }),
              createVNode(_component_el_form_item, { label: "模块参数" }, {
                default: withCtx(() => [
                  selectedWithParams.value.length ? (openBlock(), createElementBlock("div", _hoisted_2$1, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(selectedWithParams.value, (m) => {
                      return openBlock(), createElementBlock("div", {
                        key: "p-" + m.key,
                        class: "param-block"
                      }, [
                        createBaseVNode("div", _hoisted_3$1, toDisplayString(m.title), 1),
                        moduleParams.value[m.key] ? (openBlock(), createElementBlock("div", _hoisted_4$1, [
                          (openBlock(true), createElementBlock(Fragment, null, renderList(m.params, (p) => {
                            return openBlock(), createElementBlock("div", {
                              class: "param-row",
                              key: p.key
                            }, [
                              createBaseVNode("span", _hoisted_5$1, toDisplayString(p.label), 1),
                              p.type === "int" ? (openBlock(), createBlock(_component_el_input_number, {
                                key: 0,
                                modelValue: moduleParams.value[m.key][p.key],
                                "onUpdate:modelValue": ($event) => moduleParams.value[m.key][p.key] = $event,
                                min: p.min ?? void 0,
                                max: p.max ?? void 0,
                                size: "small",
                                "controls-position": "right"
                              }, null, 8, ["modelValue", "onUpdate:modelValue", "min", "max"])) : (openBlock(), createBlock(_component_el_input, {
                                key: 1,
                                modelValue: moduleParams.value[m.key][p.key],
                                "onUpdate:modelValue": ($event) => moduleParams.value[m.key][p.key] = $event,
                                size: "small"
                              }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                            ]);
                          }), 128))
                        ])) : createCommentVNode("", true)
                      ]);
                    }), 128))
                  ])) : (openBlock(), createElementBlock("div", _hoisted_6$1, "所选模块暂无可配置参数。"))
                ]),
                _: 1
              })
            ]),
            _: 1
          })), [
            [_directive_loading, loadingModules.value]
          ]),
          createVNode(_component_el_dialog, {
            modelValue: saveDialogVisible.value,
            "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => saveDialogVisible.value = $event),
            title: "保存为模板",
            width: "420px",
            "append-to-body": ""
          }, {
            footer: withCtx(() => [
              createVNode(_component_el_button, {
                onClick: _cache[11] || (_cache[11] = ($event) => saveDialogVisible.value = false)
              }, {
                default: withCtx(() => [..._cache[24] || (_cache[24] = [
                  createTextVNode("取消", -1)
                ])]),
                _: 1
              }),
              createVNode(_component_el_button, {
                type: "primary",
                loading: savingTemplate.value,
                disabled: templateNameConflict.value,
                onClick: saveAsTemplate
              }, {
                default: withCtx(() => [..._cache[25] || (_cache[25] = [
                  createTextVNode("保存", -1)
                ])]),
                _: 1
              }, 8, ["loading", "disabled"])
            ]),
            default: withCtx(() => [
              createVNode(_component_el_form, { "label-position": "top" }, {
                default: withCtx(() => [
                  createVNode(_component_el_form_item, { label: "模板名称" }, {
                    default: withCtx(() => [
                      createVNode(_component_el_input, {
                        modelValue: templateForm.value.name,
                        "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => templateForm.value.name = $event),
                        maxlength: "128",
                        "show-word-limit": "",
                        placeholder: "周报模板"
                      }, null, 8, ["modelValue"]),
                      templateNameConflict.value ? (openBlock(), createElementBlock("div", _hoisted_7$1, " 模板名称已存在（本人或公共模板中已有同名），请更换后再保存。 ")) : createCommentVNode("", true)
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, { label: "描述" }, {
                    default: withCtx(() => [
                      createVNode(_component_el_input, {
                        modelValue: templateForm.value.description,
                        "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => templateForm.value.description = $event),
                        type: "textarea",
                        rows: 2,
                        maxlength: "255",
                        placeholder: "可选"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, { label: "公开模板（所有用户可见）" }, {
                    default: withCtx(() => [
                      createVNode(_component_el_switch, {
                        modelValue: templateForm.value.is_public,
                        "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => templateForm.value.is_public = $event)
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        _: 1
      }, 8, ["modelValue"]);
    };
  }
});

const ReportExportDrawer = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-9d94a667"]]);

const _hoisted_1 = { class: "cockpit" };
const _hoisted_2 = {
  class: "kpi-row",
  "aria-label": "核心指标"
};
const _hoisted_3 = { class: "kpi-card kpi-blue" };
const _hoisted_4 = { class: "kpi-body" };
const _hoisted_5 = { class: "kpi-value" };
const _hoisted_6 = { class: "kpi-card kpi-green" };
const _hoisted_7 = { class: "kpi-body" };
const _hoisted_8 = { class: "kpi-value" };
const _hoisted_9 = { class: "kpi-card kpi-red" };
const _hoisted_10 = { class: "kpi-body" };
const _hoisted_11 = { class: "kpi-value danger" };
const _hoisted_12 = { class: "kpi-card kpi-amber" };
const _hoisted_13 = { class: "kpi-body" };
const _hoisted_14 = { class: "kpi-value" };
const _hoisted_15 = { class: "kpi-body" };
const _hoisted_16 = { class: "kpi-value kpi-status-val" };
const _hoisted_17 = { class: "kpi-foot" };
const _hoisted_18 = { class: "sit-left" };
const _hoisted_19 = { class: "sit-level" };
const _hoisted_20 = { class: "sit-text" };
const _hoisted_21 = { class: "sit-kpis" };
const _hoisted_22 = { class: "sit-kpi" };
const _hoisted_23 = { class: "k" };
const _hoisted_24 = { class: "sit-kpi" };
const _hoisted_25 = { class: "k danger" };
const _hoisted_26 = { class: "sit-kpi" };
const _hoisted_27 = { class: "k" };
const _hoisted_28 = { class: "sit-kpi" };
const _hoisted_29 = { class: "k" };
const _hoisted_30 = { class: "sit-kpi" };
const _hoisted_31 = { class: "k" };
const _hoisted_32 = {
  key: 0,
  class: "sit-action"
};
const _hoisted_33 = { class: "widget-grid" };
const _hoisted_34 = { class: "card widget widget-trend" };
const _hoisted_35 = { class: "w-head" };
const _hoisted_36 = { class: "card widget widget-alert" };
const _hoisted_37 = { class: "scroll-wrap" };
const _hoisted_38 = ["title", "onClick"];
const _hoisted_39 = { class: "ai-body" };
const _hoisted_40 = { class: "ai-title" };
const _hoisted_41 = { class: "ai-meta" };
const _hoisted_42 = {
  key: 0,
  class: "feed-empty"
};
const _hoisted_43 = { class: "card widget widget-source" };
const _hoisted_44 = { class: "card widget widget-sentiment" };
const _hoisted_45 = { class: "card widget widget-feed" };
const _hoisted_46 = { class: "scroll-wrap" };
const _hoisted_47 = ["onClick"];
const _hoisted_48 = { class: "fi-body" };
const _hoisted_49 = { class: "fi-title" };
const _hoisted_50 = { class: "fi-meta" };
const _hoisted_51 = {
  key: 0,
  class: "feed-empty"
};
const _hoisted_52 = { class: "card widget widget-word" };
const _hoisted_53 = { class: "w-head" };
const _hoisted_54 = { class: "card widget widget-geo" };
const _hoisted_55 = { class: "ht-body" };
const _hoisted_56 = {
  key: 0,
  class: "ht-error"
};
const _hoisted_57 = ["onClick"];
const _hoisted_58 = { class: "ht-event-head" };
const _hoisted_59 = { class: "ht-event-title" };
const _hoisted_60 = { class: "ht-event-meta" };
const _hoisted_61 = {
  key: 0,
  class: "ht-empty"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Dashboard",
  setup(__props) {
    const { can } = usePermission();
    const router = useRouter();
    const detailVisible = ref(false);
    const detailId = ref(null);
    function goOpinion(id) {
      if (!id) return;
      detailId.value = id;
      detailVisible.value = true;
    }
    const loading = ref(false);
    const trendDays = ref(7);
    const segOptions = [
      { label: "7天", value: 7 },
      { label: "14天", value: 14 },
      { label: "30天", value: 30 }
    ];
    const wordMode = ref("risk");
    const wordModeOptions = [
      { label: "风险关键词", value: "risk" },
      { label: "热点主题", value: "hot" }
    ];
    const stats = reactive({
      total: 0,
      today: 0,
      high_risk: 0,
      event_count: 0,
      trend: [],
      keywords: [],
      sources: [],
      sentiments: [],
      regions: [],
      region_detail: []
    });
    const recentNews = ref([]);
    const alerts = ref([]);
    const doubledNews = computed(() => recentNews.value.length ? [...recentNews.value, ...recentNews.value] : []);
    const doubledAlerts = computed(() => alerts.value.length ? [...alerts.value, ...alerts.value] : []);
    const feedDuration = computed(() => Math.max(12, recentNews.value.length * 3));
    const alertDuration = computed(() => Math.max(12, alerts.value.length * 3));
    const topicKeywords = ref([]);
    const topicLoaded = ref(false);
    const topicLoading = ref(false);
    function loadTopicKeywords(force = false) {
      if (topicLoading.value) return Promise.resolve();
      if (topicLoaded.value && !force) return Promise.resolve();
      topicLoading.value = true;
      return api.get("/dashboard/hot-keywords", {
        params: { days: trendDays.value, limit: 10, category: "主题" }
      }).then((res) => {
        topicKeywords.value = res.data.items || [];
        topicLoaded.value = true;
      }).catch(() => {
        topicKeywords.value = [];
      }).finally(() => {
        topicLoading.value = false;
      });
    }
    const hotTopicDrawer = ref(false);
    const hotTopicLabel = ref("");
    const hotTopicEvents = ref([]);
    const hotTopicLoading = ref(false);
    const hotTopicError = ref("");
    async function openHotTopic(keyword) {
      if (!keyword) return;
      hotTopicLabel.value = keyword;
      hotTopicDrawer.value = true;
      hotTopicLoading.value = true;
      hotTopicError.value = "";
      hotTopicEvents.value = [];
      const kw = topicValueFromLabel(keyword);
      try {
        const data = await getEventsByHotTopic(kw);
        hotTopicEvents.value = data.items || [];
      } catch {
        hotTopicError.value = "加载失败，请稍后重试";
      } finally {
        hotTopicLoading.value = false;
      }
    }
    function goEventDetail(id) {
      if (!id) return;
      hotTopicDrawer.value = false;
      router.push(`/event/${id}`);
    }
    const collectorOnline = ref(false);
    const collectorLastRun = ref("");
    const collectorText = computed(() => collectorOnline.value ? "运行中" : "等待触发");
    const riskRate = computed(() => stats.total ? Math.round((stats.high_risk || 0) / stats.total * 100) : 0);
    const negativeRate = computed(() => {
      const neg = stats.sentiments?.find((s) => s.label === "negative")?.count || 0;
      return stats.total ? Math.round(neg / stats.total * 100) : 0;
    });
    const situationLevel = computed(() => {
      if (!stats.total) return "green";
      if (riskRate.value < 10) return "green";
      if (riskRate.value < 20) return "yellow";
      return "red";
    });
    const levelText = computed(() => ({ green: "态势平稳", yellow: "态势需警惕", red: "态势紧张" })[situationLevel.value]);
    const situationText = computed(() => {
      if (situationLevel.value === "green") return "整体态势平稳，暂无需要紧急处置的高风险舆情。";
      if (situationLevel.value === "yellow") return "态势总体可控，存在少量高风险舆情，建议持续关注。";
      return "态势紧张，高风险舆情占比偏高，建议立即研判处置。";
    });
    const reportDrawer = ref(false);
    function openReportDrawer() {
      reportDrawer.value = true;
    }
    const trendRef = ref();
    let trendChart = null;
    const sourceRef = ref();
    let sourceChart = null;
    const wordcloudRef = ref();
    let wordcloudChart = null;
    const regionRef = ref();
    let regionChart = null;
    const realSentimentData = computed(() => {
      if (stats.sentiments && stats.sentiments.length) {
        const map = {
          negative: { label: "负面", count: 0, color: "#ff3b30" },
          neutral: { label: "中性", count: 0, color: "#86868b" },
          positive: { label: "正面", count: 0, color: "#34c759" }
        };
        for (const s of stats.sentiments) {
          const key = s.label.toLowerCase();
          if (map[key]) map[key].count = s.count;
        }
        return Object.values(map);
      }
      return [
        { label: "负面", count: stats.high_risk || 0, color: "#ff3b30" },
        { label: "中性", count: Math.max(0, (stats.total || 0) - (stats.high_risk || 0) - (stats.today || 0)), color: "#86868b" },
        { label: "正面", count: Math.max(0, (stats.today || 0) - (stats.high_risk || 0)), color: "#34c759" }
      ];
    });
    function renderTrend(trend) {
      if (!trendChart) return;
      trendChart.setOption({
        tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        grid: { left: 40, right: 20, top: 10, bottom: 30 },
        xAxis: { type: "category", data: trend.map((t) => t.date), axisLine: { lineStyle: { color: "#e8e8ed" } }, axisTick: { show: false }, axisLabel: { color: "#86868b", fontSize: 11 } },
        yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        series: [{ name: "舆情数", type: "line", smooth: true, symbol: "circle", symbolSize: 5, data: trend.map((t) => t.count), areaStyle: { color: new LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(0,113,227,0.12)" }, { offset: 1, color: "rgba(0,113,227,0)" }]) }, lineStyle: { width: 2.5, color: "#0071e3" }, itemStyle: { color: "#0071e3" } }]
      });
    }
    const SOURCE_LABEL_MAP = { weibo: "微博", xiaohongshu: "小红书", xhs: "小红书", web: "网页" };
    function sourceLabel(name) {
      return SOURCE_LABEL_MAP[(name || "").toLowerCase()] || name || "未知";
    }
    function renderSourceDistribution() {
      if (!sourceChart || !stats.sources?.length) return;
      const data = [...stats.sources].sort((a, b) => b.count - a.count).slice(0, 10);
      sourceChart.setOption({
        tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        grid: { left: 128, right: 30, top: 10, bottom: 20 },
        xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        // width + overflow:truncate：名称从开头完整显示，过长时末尾用省略号（…）代替，避免开头被裁切
        yAxis: { type: "category", data: data.map((d) => sourceLabel(d.source)).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12, width: 116, overflow: "truncate", align: "right" }, inverse: true },
        series: [{ name: "舆情数", type: "bar", data: data.map((d) => d.count).reverse(), barWidth: 16, itemStyle: { borderRadius: [0, 6, 6, 0], color: new LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#0071e3" }, { offset: 1, color: "#5ac8fa" }]) } }]
      });
    }
    function renderRegionDistribution() {
      const src = stats.region_detail?.length ? stats.region_detail : stats.regions;
      if (!regionChart || !src?.length) return;
      const data = [...src].sort((a, b) => b.count - a.count).slice(0, 10);
      regionChart.setOption({
        tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
        grid: { left: 110, right: 30, top: 10, bottom: 20 },
        xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
        yAxis: { type: "category", data: data.map((d) => d.region_name).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12 }, inverse: true },
        series: [{ name: "舆情数", type: "bar", data: data.map((d) => d.count).reverse(), barWidth: 16, itemStyle: { borderRadius: [0, 6, 6, 0], color: new LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#ff9f0a" }, { offset: 1, color: "#ffd60a" }]) } }]
      });
    }
    function renderWordCloud() {
      if (!wordcloudChart) return;
      let data = [];
      let tooltipFormatter = (p) => `${p.name}: ${p.value}`;
      if (wordMode.value === "hot") {
        if (!topicKeywords.value.length) {
          wordcloudChart.clear();
          return;
        }
        const max = Math.max(...topicKeywords.value.map((k) => k.count), 1);
        data = topicKeywords.value.slice(0, 30).map((k) => ({
          name: k.keyword,
          value: k.count,
          textStyle: { color: `hsl(${k.count / max * 210 + 200}, 70%, ${60 - k.count / max * 30}%)` }
        }));
        tooltipFormatter = (p) => {
          const k = topicKeywords.value.find((x) => x.keyword === p.name);
          if (!k) return `${p.name}: ${p.value}`;
          const arrow = k.trend === "up" ? "↑" : k.trend === "down" ? "↓" : "→";
          const label = k.trend === "up" ? "上升" : k.trend === "down" ? "下降" : "持平";
          return `${k.keyword}<br/>近${trendDays.value}天: ${k.count}<br/>趋势: ${arrow} ${label}`;
        };
      } else {
        if (!stats.keywords?.length) {
          wordcloudChart.clear();
          return;
        }
        const max = stats.keywords[0]?.count || 1;
        data = stats.keywords.slice(0, 30).map((kw) => ({
          name: kw.word,
          value: kw.count,
          textStyle: { color: `hsl(${kw.count / max * 210 + 200}, 70%, ${60 - kw.count / max * 30}%)` }
        }));
      }
      wordcloudChart.setOption({
        tooltip: {
          show: true,
          backgroundColor: "rgba(29,29,31,0.94)",
          borderColor: "transparent",
          textStyle: { color: "#fff", fontSize: 12 },
          formatter: tooltipFormatter
        },
        series: [{ type: "wordCloud", shape: "circle", left: "center", top: "center", width: "90%", height: "90%", sizeRange: [14, 42], rotationRange: [-30, 30], gridSize: 8, layoutAnimation: true, textStyle: { fontFamily: "sans-serif", fontWeight: "bold" }, emphasis: { textStyle: { color: "#0071e3" } }, data }]
      }, { notMerge: true });
    }
    async function loadCollectorStatus() {
      try {
        const res = await api.get("/collector/status");
        const d = res.data;
        collectorOnline.value = d.collector_type === "government";
        collectorLastRun.value = d.last_run ? new Date(d.last_run).toLocaleString("zh-CN") : "暂无记录";
      } catch {
        collectorOnline.value = false;
      }
    }
    async function loadFeeds() {
      try {
        const [r1, r2] = await Promise.all([
          api.get("/dashboard/recent", { params: { limit: 8 } }),
          api.get("/dashboard/alerts", { params: { limit: 8 } })
        ]);
        recentNews.value = r1.data;
        alerts.value = r2.data;
      } catch {
      }
    }
    function handleResize() {
      trendChart?.resize();
      sourceChart?.resize();
      wordcloudChart?.resize();
      regionChart?.resize();
    }
    async function loadData() {
      loading.value = true;
      try {
        const [statsRes] = await Promise.all([
          api.get("/dashboard/stats", { params: { days: trendDays.value } }),
          loadCollectorStatus(),
          loadFeeds()
        ]);
        Object.assign(stats, statsRes.data);
        await nextTick();
        renderTrend(stats.trend);
        renderSourceDistribution();
        renderRegionDistribution();
        renderWordCloud();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载统计数据失败");
      } finally {
        loading.value = false;
      }
    }
    watch(trendDays, () => {
      loadData();
      if (wordMode.value === "hot") {
        loadTopicKeywords(true).then(() => renderWordCloud());
      }
    });
    watch(wordMode, async (m) => {
      if (m === "hot") {
        await loadTopicKeywords();
      }
      renderWordCloud();
    });
    function fmtTime(s) {
      if (!s) return "-";
      return s.replace("T", " ").slice(0, 16);
    }
    function sentClass(s) {
      return { negative: "neg", neutral: "neu", positive: "pos" }[s] || "neu";
    }
    function sentLabel(s) {
      return { negative: "负面", neutral: "中性", positive: "正面" }[s] || "中性";
    }
    function riskClass(l) {
      return { critical: "crit", high: "crit", medium: "med", low: "low" }[l] || "low";
    }
    function riskText(l) {
      return { critical: "严重", high: "高", medium: "中", low: "低" }[l] || l;
    }
    function riskPill(l) {
      return { critical: "pill-red", high: "pill-red", medium: "pill-orange", low: "pill-green" }[l] || "pill-gray";
    }
    let feedTimer;
    onMounted(async () => {
      await nextTick();
      if (trendRef.value) trendChart = init(trendRef.value);
      if (sourceRef.value) sourceChart = init(sourceRef.value);
      if (wordcloudRef.value) wordcloudChart = init(wordcloudRef.value);
      if (regionRef.value) regionChart = init(regionRef.value);
      wordcloudChart?.on("click", (params) => {
        if (wordMode.value !== "hot") return;
        const name = params?.name;
        if (name) openHotTopic(name);
      });
      window.addEventListener("resize", handleResize);
      window.addEventListener("data-refresh", loadData);
      await loadData();
      feedTimer = window.setInterval(loadFeeds, 3e4);
    });
    onBeforeUnmount(() => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("data-refresh", loadData);
      if (feedTimer) clearInterval(feedTimer);
      trendChart?.dispose();
      trendChart = null;
      sourceChart?.dispose();
      sourceChart = null;
      wordcloudChart?.dispose();
      wordcloudChart = null;
      regionChart?.dispose();
      regionChart = null;
    });
    return (_ctx, _cache) => {
      const _component_el_button = resolveComponent("el-button");
      const _component_el_drawer = resolveComponent("el-drawer");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("section", _hoisted_2, [
          createBaseVNode("article", _hoisted_3, [
            _cache[7] || (_cache[7] = createBaseVNode("span", { class: "kpi-ico" }, "▦", -1)),
            createBaseVNode("div", _hoisted_4, [
              _cache[5] || (_cache[5] = createBaseVNode("div", { class: "kpi-label" }, "总舆情数", -1)),
              createBaseVNode("div", _hoisted_5, toDisplayString(stats.total.toLocaleString()), 1),
              _cache[6] || (_cache[6] = createBaseVNode("div", { class: "kpi-foot" }, "累计监测数据", -1))
            ])
          ]),
          createBaseVNode("article", _hoisted_6, [
            _cache[10] || (_cache[10] = createBaseVNode("span", { class: "kpi-ico" }, "↗", -1)),
            createBaseVNode("div", _hoisted_7, [
              _cache[8] || (_cache[8] = createBaseVNode("div", { class: "kpi-label" }, "今日新增", -1)),
              createBaseVNode("div", _hoisted_8, toDisplayString(stats.today.toLocaleString()), 1),
              _cache[9] || (_cache[9] = createBaseVNode("div", { class: "kpi-foot" }, "当日采集", -1))
            ])
          ]),
          createBaseVNode("article", _hoisted_9, [
            _cache[13] || (_cache[13] = createBaseVNode("span", { class: "kpi-ico" }, "!", -1)),
            createBaseVNode("div", _hoisted_10, [
              _cache[11] || (_cache[11] = createBaseVNode("div", { class: "kpi-label" }, "高风险", -1)),
              createBaseVNode("div", _hoisted_11, toDisplayString(stats.high_risk.toLocaleString()), 1),
              _cache[12] || (_cache[12] = createBaseVNode("div", { class: "kpi-foot" }, "需关注处理", -1))
            ])
          ]),
          createBaseVNode("article", _hoisted_12, [
            _cache[16] || (_cache[16] = createBaseVNode("span", { class: "kpi-ico" }, "◎", -1)),
            createBaseVNode("div", _hoisted_13, [
              _cache[14] || (_cache[14] = createBaseVNode("div", { class: "kpi-label" }, "事件数", -1)),
              createBaseVNode("div", _hoisted_14, toDisplayString((stats.event_count || 0).toLocaleString()), 1),
              _cache[15] || (_cache[15] = createBaseVNode("div", { class: "kpi-foot" }, "聚合事件", -1))
            ])
          ]),
          createBaseVNode("article", {
            class: normalizeClass(["kpi-card kpi-status", collectorOnline.value ? "is-on" : "is-off"])
          }, [
            _cache[19] || (_cache[19] = createBaseVNode("span", { class: "kpi-ico" }, "↻", -1)),
            createBaseVNode("div", _hoisted_15, [
              _cache[18] || (_cache[18] = createBaseVNode("div", { class: "kpi-label" }, "采集状态", -1)),
              createBaseVNode("div", _hoisted_16, [
                _cache[17] || (_cache[17] = createBaseVNode("span", { class: "status-dot" }, null, -1)),
                createTextVNode(toDisplayString(collectorText.value), 1)
              ]),
              createBaseVNode("div", _hoisted_17, toDisplayString(collectorLastRun.value), 1)
            ])
          ], 2)
        ]),
        createBaseVNode("section", {
          class: normalizeClass(["situation", "lvl-" + situationLevel.value])
        }, [
          createBaseVNode("div", _hoisted_18, [
            createBaseVNode("div", _hoisted_19, [
              _cache[20] || (_cache[20] = createBaseVNode("span", { class: "lvl-dot" }, null, -1)),
              createTextVNode(toDisplayString(levelText.value), 1)
            ]),
            createBaseVNode("div", _hoisted_20, toDisplayString(situationText.value), 1)
          ]),
          createBaseVNode("div", _hoisted_21, [
            createBaseVNode("div", _hoisted_22, [
              createBaseVNode("span", _hoisted_23, toDisplayString(stats.total.toLocaleString()), 1),
              _cache[21] || (_cache[21] = createBaseVNode("span", { class: "l" }, "总舆情", -1))
            ]),
            createBaseVNode("div", _hoisted_24, [
              createBaseVNode("span", _hoisted_25, toDisplayString(stats.high_risk.toLocaleString()), 1),
              _cache[22] || (_cache[22] = createBaseVNode("span", { class: "l" }, "高风险", -1))
            ]),
            createBaseVNode("div", _hoisted_26, [
              createBaseVNode("span", _hoisted_27, toDisplayString(riskRate.value) + "%", 1),
              _cache[23] || (_cache[23] = createBaseVNode("span", { class: "l" }, "风险率", -1))
            ]),
            createBaseVNode("div", _hoisted_28, [
              createBaseVNode("span", _hoisted_29, toDisplayString(negativeRate.value) + "%", 1),
              _cache[24] || (_cache[24] = createBaseVNode("span", { class: "l" }, "负面率", -1))
            ]),
            createBaseVNode("div", _hoisted_30, [
              createBaseVNode("span", _hoisted_31, toDisplayString((stats.event_count || 0).toLocaleString()), 1),
              _cache[25] || (_cache[25] = createBaseVNode("span", { class: "l" }, "事件", -1))
            ])
          ]),
          unref(can)("reports:read") || unref(can)("reports:export") ? (openBlock(), createElementBlock("div", _hoisted_32, [
            unref(can)("reports:export") ? (openBlock(), createBlock(_component_el_button, {
              key: 0,
              type: "primary",
              onClick: openReportDrawer
            }, {
              default: withCtx(() => [..._cache[26] || (_cache[26] = [
                createBaseVNode("span", { style: { "margin-right": "4px" } }, "⎙", -1),
                createTextVNode("导出舆情报告 ", -1)
              ])]),
              _: 1
            })) : createCommentVNode("", true)
          ])) : createCommentVNode("", true)
        ], 2),
        createBaseVNode("section", _hoisted_33, [
          createBaseVNode("article", _hoisted_34, [
            createBaseVNode("header", _hoisted_35, [
              _cache[27] || (_cache[27] = createBaseVNode("h3", { class: "w-title" }, "舆情趋势", -1)),
              createVNode(SegmentedControl, {
                modelValue: trendDays.value,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => trendDays.value = $event),
                options: segOptions
              }, null, 8, ["modelValue"])
            ]),
            createBaseVNode("div", {
              ref_key: "trendRef",
              ref: trendRef,
              class: "chart-box"
            }, null, 512)
          ]),
          createBaseVNode("article", _hoisted_36, [
            _cache[28] || (_cache[28] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "预警滚动"),
              createBaseVNode("span", { class: "live-dot warn" }, "● ALERT")
            ], -1)),
            createBaseVNode("div", _hoisted_37, [
              createBaseVNode("div", {
                class: "scroll-inner",
                style: normalizeStyle({ animationDuration: alertDuration.value + "s" })
              }, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(doubledAlerts.value, (a, i) => {
                  return openBlock(), createElementBlock("div", {
                    key: "a" + i,
                    class: normalizeClass(["alert-item", { handled: a.handled, clickable: !!a.opinion_id }]),
                    title: a.opinion_id ? "查看舆情详情" : "",
                    onClick: ($event) => a.opinion_id && goOpinion(a.opinion_id)
                  }, [
                    createBaseVNode("span", {
                      class: normalizeClass(["ai-tag", riskClass(a.risk_level)])
                    }, toDisplayString(riskText(a.risk_level)), 3),
                    createBaseVNode("div", _hoisted_39, [
                      createBaseVNode("div", _hoisted_40, toDisplayString(a.opinion_title || a.rule_name), 1),
                      createBaseVNode("div", _hoisted_41, toDisplayString(a.rule_name) + " · " + toDisplayString(fmtTime(a.created_at)) + toDisplayString(a.handled ? " · 已处置" : ""), 1)
                    ])
                  ], 10, _hoisted_38);
                }), 128))
              ], 4),
              !alerts.value.length ? (openBlock(), createElementBlock("div", _hoisted_42, "暂无预警")) : createCommentVNode("", true)
            ])
          ]),
          createBaseVNode("article", _hoisted_43, [
            _cache[29] || (_cache[29] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "来源分布")
            ], -1)),
            createBaseVNode("div", {
              ref_key: "sourceRef",
              ref: sourceRef,
              class: "chart-box"
            }, null, 512)
          ]),
          createBaseVNode("article", _hoisted_44, [
            _cache[30] || (_cache[30] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "情感分布")
            ], -1)),
            createVNode(SentimentDonut, { data: realSentimentData.value }, null, 8, ["data"])
          ]),
          createBaseVNode("article", _hoisted_45, [
            _cache[31] || (_cache[31] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "实时快讯"),
              createBaseVNode("span", { class: "live-dot" }, "● LIVE")
            ], -1)),
            createBaseVNode("div", _hoisted_46, [
              createBaseVNode("div", {
                class: "scroll-inner",
                style: normalizeStyle({ animationDuration: feedDuration.value + "s" })
              }, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(doubledNews.value, (n, i) => {
                  return openBlock(), createElementBlock("div", {
                    key: "n" + i,
                    class: "feed-item clickable",
                    title: "查看舆情详情",
                    onClick: ($event) => goOpinion(n.id)
                  }, [
                    createBaseVNode("span", {
                      class: normalizeClass(["fi-tag", sentClass(n.sentiment)])
                    }, toDisplayString(sentLabel(n.sentiment)), 3),
                    createBaseVNode("div", _hoisted_48, [
                      createBaseVNode("div", _hoisted_49, toDisplayString(n.title), 1),
                      createBaseVNode("div", _hoisted_50, toDisplayString(n.source) + " · " + toDisplayString(n.region_name) + " · " + toDisplayString(fmtTime(n.created_at)) + " · 风险 " + toDisplayString(n.risk_score), 1)
                    ])
                  ], 8, _hoisted_47);
                }), 128))
              ], 4),
              !recentNews.value.length ? (openBlock(), createElementBlock("div", _hoisted_51, "暂无实时快讯")) : createCommentVNode("", true)
            ])
          ]),
          createBaseVNode("article", _hoisted_52, [
            createBaseVNode("header", _hoisted_53, [
              _cache[32] || (_cache[32] = createBaseVNode("h3", { class: "w-title" }, "热点词云", -1)),
              createVNode(SegmentedControl, {
                modelValue: wordMode.value,
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => wordMode.value = $event),
                options: wordModeOptions
              }, null, 8, ["modelValue"])
            ]),
            createBaseVNode("div", {
              ref_key: "wordcloudRef",
              ref: wordcloudRef,
              class: "chart-box"
            }, null, 512)
          ]),
          createBaseVNode("article", _hoisted_54, [
            _cache[33] || (_cache[33] = createBaseVNode("header", { class: "w-head" }, [
              createBaseVNode("h3", { class: "w-title" }, "地理分布（地区舆情细分 TOP）")
            ], -1)),
            createBaseVNode("div", {
              ref_key: "regionRef",
              ref: regionRef,
              class: "chart-box"
            }, null, 512)
          ])
        ]),
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"]),
        createVNode(ReportExportDrawer, {
          modelValue: reportDrawer.value,
          "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => reportDrawer.value = $event)
        }, null, 8, ["modelValue"]),
        createVNode(_component_el_drawer, {
          modelValue: hotTopicDrawer.value,
          "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => hotTopicDrawer.value = $event),
          title: `${hotTopicLabel.value} 相关事件`,
          direction: "rtl",
          size: "480px",
          class: "hot-topic-drawer"
        }, {
          default: withCtx(() => [
            withDirectives((openBlock(), createElementBlock("div", _hoisted_55, [
              hotTopicError.value ? (openBlock(), createElementBlock("div", _hoisted_56, toDisplayString(hotTopicError.value), 1)) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(hotTopicEvents.value, (ev) => {
                  return openBlock(), createElementBlock("div", {
                    key: ev.id,
                    class: "ht-event",
                    onClick: ($event) => goEventDetail(ev.id)
                  }, [
                    createBaseVNode("div", _hoisted_58, [
                      createBaseVNode("span", _hoisted_59, toDisplayString(ev.title), 1),
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", riskPill(ev.risk_level)])
                      }, [
                        _cache[34] || (_cache[34] = createBaseVNode("span", { class: "dot" }, null, -1)),
                        createTextVNode(toDisplayString(riskText(ev.risk_level)), 1)
                      ], 2)
                    ]),
                    createBaseVNode("div", _hoisted_60, [
                      createBaseVNode("span", {
                        class: normalizeClass(["pill", unref(eventStatusPill)(ev.status)])
                      }, toDisplayString(unref(eventStatusLabel)(ev.status)), 3),
                      createBaseVNode("span", null, "热度 " + toDisplayString(ev.heat_score), 1),
                      createBaseVNode("span", null, toDisplayString(ev.source_count ?? "-") + " 个来源", 1),
                      createBaseVNode("span", null, toDisplayString(fmtTime(ev.last_time || "")), 1)
                    ])
                  ], 8, _hoisted_57);
                }), 128)),
                !hotTopicLoading.value && hotTopicEvents.value.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_61, " 暂无相关事件 ")) : createCommentVNode("", true)
              ], 64))
            ])), [
              [_directive_loading, hotTopicLoading.value]
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

const Dashboard = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-505c17aa"]]);

export { Dashboard as default };
