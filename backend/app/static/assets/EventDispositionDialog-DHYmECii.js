import { d as defineComponent, z as usePermission, A as watch, q as createBlock, p as withCtx, j as computed, y as resolveComponent, o as openBlock, c as createElementBlock, a as createBaseVNode, e as createTextVNode, n as normalizeClass, H as unref, t as toDisplayString, F as Fragment, i as renderList, s as createCommentVNode, m as createVNode, w as withDirectives, v as vModelText, r as ref, g as api, E as ElMessage, _ as _export_sfc } from './index-pb2TILNy.js';
import { e as eventStatusPill, a as eventStatusLabel, E as EVENT_STATUS_OPTIONS } from './event-DY3DZBkH.js';

const _hoisted_1 = {
  key: 0,
  class: "op-modal-body"
};
const _hoisted_2 = { class: "op-left" };
const _hoisted_3 = { class: "operation-header" };
const _hoisted_4 = { class: "operation-current" };
const _hoisted_5 = {
  key: 0,
  class: "status-actions",
  "aria-label": "����¼�����״̬"
};
const _hoisted_6 = ["disabled", "onClick"];
const _hoisted_7 = {
  key: 1,
  class: "merge-split-actions"
};
const _hoisted_8 = ["disabled"];
const _hoisted_9 = ["disabled"];
const _hoisted_10 = {
  key: 2,
  class: "sub-panel"
};
const _hoisted_11 = { class: "sub-actions" };
const _hoisted_12 = ["disabled"];
const _hoisted_13 = {
  key: 3,
  class: "sub-panel"
};
const _hoisted_14 = { class: "sub-actions" };
const _hoisted_15 = ["disabled"];
const _hoisted_16 = {
  key: 4,
  class: "note-editor"
};
const _hoisted_17 = ["disabled"];
const _hoisted_18 = { class: "note-submit-row" };
const _hoisted_19 = ["disabled"];
const _hoisted_20 = { class: "op-right" };
const _hoisted_21 = { class: "op-right-title" };
const _hoisted_22 = { class: "op-count" };
const _hoisted_23 = { class: "op-right-scroll" };
const _hoisted_24 = { class: "action-timeline" };
const _hoisted_25 = { class: "timeline-body" };
const _hoisted_26 = { class: "timeline-meta" };
const _hoisted_27 = { class: "timeline-content" };
const _hoisted_28 = {
  key: 0,
  class: "timeline-empty"
};
const _hoisted_29 = {
  key: 1,
  class: "op-loading"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "EventDispositionDialog",
  props: {
    modelValue: { type: Boolean },
    eventId: {},
    scope: { default: "domestic" }
  },
  emits: ["update:modelValue", "updated"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const { hasPermission } = usePermission();
    const base = computed(() => props.scope === "foreign" ? "/foreign/events" : "/events");
    const canUpdate = computed(
      () => hasPermission(props.scope === "foreign" ? "foreign:events:write" : "events:write")
    );
    const visible = computed({
      get: () => props.modelValue,
      set: (v) => emit("update:modelValue", v)
    });
    const event = ref(null);
    const savingStatus = ref(false);
    const savingNote = ref(false);
    const noteContent = ref("");
    const mergePanelOpen = ref(false);
    const splitPanelOpen = ref(false);
    const mergeTargetId = ref(null);
    const mergeReason = ref("");
    const merging = ref(false);
    const mergeCandidates = ref([]);
    const mergeSearching = ref(false);
    const splitOpinionIds = ref([]);
    const splitReason = ref("");
    const splitting = ref(false);
    const busy = computed(() => savingStatus.value || savingNote.value || merging.value || splitting.value);
    const statusButtons = computed(() => [
      ...EVENT_STATUS_OPTIONS,
      { value: "archived", label: "�鵵" }
    ]);
    const nextStatus = {
      active: "verifying",
      verifying: "processing",
      processing: "resolved",
      resolved: "closed"
    };
    const DEPRECATE_ALLOWED_FROM = ["active", "verifying", "processing"];
    function canChangeStatus(target) {
      const current = event.value?.status;
      if (!current || target === current) return false;
      if (target === "active") return true;
      if (target === "archived") return current !== "archived";
      if (target === "deprecated") return DEPRECATE_ALLOWED_FROM.includes(current);
      return nextStatus[current] === target;
    }
    function formatTime(t) {
      if (!t) return "-";
      return t.replace("T", " ").slice(0, 19);
    }
    function actionTypeText(value) {
      return { status_change: "״̬���", note: "��ע", assign: "ָ��", resolve: "���" }[value] || value;
    }
    function errorMessage(err, fallback) {
      const detail = err?.response?.data?.detail;
      return typeof detail === "string" ? detail : fallback;
    }
    async function loadDetail() {
      if (!props.eventId) return;
      try {
        const { data } = await api.get(`${base.value}/${props.eventId}`);
        event.value = {
          id: data.id,
          title: data.title,
          status: data.status,
          actions: data.actions || [],
          opinions: data.opinions || []
        };
      } catch (err) {
        ElMessage.error(errorMessage(err, "�����¼�����ʧ��"));
      }
    }
    function onOpen() {
      mergePanelOpen.value = false;
      splitPanelOpen.value = false;
      mergeTargetId.value = null;
      mergeReason.value = "";
      splitOpinionIds.value = [];
      splitReason.value = "";
      noteContent.value = "";
      loadDetail();
      if (props.scope === "domestic") fetchMergeCandidates("");
    }
    watch(
      () => [props.modelValue, props.eventId],
      ([open]) => {
        if (open) onOpen();
      }
    );
    async function changeStatus(target) {
      if (!canChangeStatus(target) || !event.value) return;
      savingStatus.value = true;
      try {
        await api.patch(`${base.value}/${event.value.id}/status`, { status: target });
        ElMessage.success(`����״̬�Ѹ���Ϊ${eventStatusLabel(target)}`);
        await loadDetail();
        emit("updated", event.value.id);
      } catch (err) {
        ElMessage.error(errorMessage(err, "���´���״̬ʧ��"));
      } finally {
        savingStatus.value = false;
      }
    }
    async function addNote() {
      const content = noteContent.value.trim();
      if (!content || !event.value) return;
      savingNote.value = true;
      try {
        await api.post(`${base.value}/${event.value.id}/actions`, { action_type: "note", content });
        noteContent.value = "";
        ElMessage.success("�¼���ע������");
        await loadDetail();
        emit("updated", event.value.id);
      } catch (err) {
        ElMessage.error(errorMessage(err, "�����¼���עʧ��"));
      } finally {
        savingNote.value = false;
      }
    }
    function toggleMerge() {
      mergePanelOpen.value = !mergePanelOpen.value;
      if (mergePanelOpen.value && mergeCandidates.value.length === 0) fetchMergeCandidates("");
    }
    function toggleSplit() {
      splitPanelOpen.value = !splitPanelOpen.value;
    }
    async function fetchMergeCandidates(keyword) {
      if (!props.eventId) return;
      mergeSearching.value = true;
      try {
        const { data } = await api.get(base.value, {
          params: { title: keyword || void 0, size: 30, page: 1 }
        });
        mergeCandidates.value = (data.items || []).filter((e) => e.id !== props.eventId).map((e) => ({ id: e.id, title: e.title }));
      } catch {
        mergeCandidates.value = [];
      } finally {
        mergeSearching.value = false;
      }
    }
    function onMergeSearch(keyword) {
      fetchMergeCandidates(keyword);
    }
    async function submitMerge() {
      if (!mergeTargetId.value || !event.value) return;
      merging.value = true;
      try {
        await api.post(`${base.value}/${event.value.id}/merge`, {
          target_event_id: mergeTargetId.value,
          reason: mergeReason.value.trim()
        });
        ElMessage.success("�¼��Ѻϲ���Ŀ���¼�");
        mergePanelOpen.value = false;
        mergeTargetId.value = null;
        mergeReason.value = "";
        await loadDetail();
        emit("updated", event.value.id);
      } catch (err) {
        ElMessage.error(errorMessage(err, "�ϲ��¼�ʧ��"));
      } finally {
        merging.value = false;
      }
    }
    async function submitSplit() {
      if (splitOpinionIds.value.length === 0 || !event.value) return;
      splitting.value = true;
      try {
        await api.post(`${base.value}/${event.value.id}/split`, {
          opinion_ids: splitOpinionIds.value,
          reason: splitReason.value.trim()
        });
        ElMessage.success("�Ѳ��ѡ�е�����");
        splitPanelOpen.value = false;
        splitOpinionIds.value = [];
        splitReason.value = "";
        await loadDetail();
        emit("updated", event.value.id);
      } catch (err) {
        ElMessage.error(errorMessage(err, "����¼�ʧ��"));
      } finally {
        splitting.value = false;
      }
    }
    return (_ctx, _cache) => {
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_dialog = resolveComponent("el-dialog");
      return openBlock(), createBlock(_component_el_dialog, {
        modelValue: visible.value,
        "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => visible.value = $event),
        title: "�¼�����",
        width: "840px",
        "align-center": "",
        "close-on-click-modal": true,
        class: "op-dialog",
        onOpen
      }, {
        footer: withCtx(() => [
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: _cache[5] || (_cache[5] = ($event) => visible.value = false)
          }, "�ر�")
        ]),
        default: withCtx(() => [
          event.value ? (openBlock(), createElementBlock("div", _hoisted_1, [
            createBaseVNode("div", _hoisted_2, [
              createBaseVNode("div", _hoisted_3, [
                createBaseVNode("div", null, [
                  createBaseVNode("div", _hoisted_4, [
                    _cache[7] || (_cache[7] = createTextVNode(" ��ǰ����״̬ ", -1)),
                    createBaseVNode("span", {
                      class: normalizeClass(["pill", unref(eventStatusPill)(event.value.status)])
                    }, toDisplayString(unref(eventStatusLabel)(event.value.status)), 3)
                  ])
                ])
              ]),
              canUpdate.value ? (openBlock(), createElementBlock("div", _hoisted_5, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(statusButtons.value, (option) => {
                  return openBlock(), createElementBlock("button", {
                    key: option.value,
                    class: normalizeClass(["status-button", { current: event.value.status === option.value }]),
                    disabled: busy.value || !canChangeStatus(option.value),
                    onClick: ($event) => changeStatus(option.value)
                  }, toDisplayString(option.value === "deprecated" ? "�����¼�" : option.label), 11, _hoisted_6);
                }), 128))
              ])) : createCommentVNode("", true),
              canUpdate.value ? (openBlock(), createElementBlock("div", _hoisted_7, [
                createBaseVNode("button", {
                  class: "btn btn-ghost",
                  disabled: busy.value,
                  onClick: toggleMerge
                }, toDisplayString(mergePanelOpen.value ? "����ϲ�" : "�ϲ��������¼�"), 9, _hoisted_8),
                createBaseVNode("button", {
                  class: "btn btn-ghost",
                  disabled: busy.value,
                  onClick: toggleSplit
                }, toDisplayString(splitPanelOpen.value ? "������" : "�������"), 9, _hoisted_9)
              ])) : createCommentVNode("", true),
              mergePanelOpen.value && canUpdate.value ? (openBlock(), createElementBlock("div", _hoisted_10, [
                _cache[8] || (_cache[8] = createBaseVNode("label", null, "�ϲ���Ŀ���¼�����ǰ�¼����鵵������Ǩ�Ƶ�Ŀ�꣩", -1)),
                createVNode(_component_el_select, {
                  modelValue: mergeTargetId.value,
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => mergeTargetId.value = $event),
                  filterable: "",
                  remote: "",
                  "remote-method": onMergeSearch,
                  loading: mergeSearching.value,
                  placeholder: "����Ŀ���¼��������⣩",
                  clearable: "",
                  style: { "width": "100%" }
                }, {
                  default: withCtx(() => [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(mergeCandidates.value, (c) => {
                      return openBlock(), createBlock(_component_el_option, {
                        key: c.id,
                        label: `#${c.id} ${c.title}`,
                        value: c.id
                      }, null, 8, ["label", "value"]);
                    }), 128))
                  ]),
                  _: 1
                }, 8, ["modelValue", "loading"]),
                _cache[9] || (_cache[9] = createBaseVNode("label", { style: { "margin-top": "12px" } }, "�ϲ�ԭ�򣨿�ѡ��", -1)),
                withDirectives(createBaseVNode("textarea", {
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => mergeReason.value = $event),
                  maxlength: "5000",
                  rows: "2",
                  placeholder: "��д�ϲ�ԭ��",
                  class: "sub-textarea"
                }, null, 512), [
                  [vModelText, mergeReason.value]
                ]),
                createBaseVNode("div", _hoisted_11, [
                  createBaseVNode("button", {
                    class: "btn btn-primary",
                    disabled: merging.value || !mergeTargetId.value,
                    onClick: submitMerge
                  }, toDisplayString(merging.value ? "�ϲ���" : "ȷ�Ϻϲ�"), 9, _hoisted_12)
                ])
              ])) : createCommentVNode("", true),
              splitPanelOpen.value && canUpdate.value ? (openBlock(), createElementBlock("div", _hoisted_13, [
                _cache[10] || (_cache[10] = createBaseVNode("label", null, "������飨ѡ�е����齫Ǩ�����½�һ���¼����أ�", -1)),
                createVNode(_component_el_select, {
                  modelValue: splitOpinionIds.value,
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => splitOpinionIds.value = $event),
                  multiple: "",
                  filterable: "",
                  placeholder: "ѡ��Ҫ���������",
                  style: { "width": "100%" }
                }, {
                  default: withCtx(() => [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(event.value.opinions || [], (o) => {
                      return openBlock(), createBlock(_component_el_option, {
                        key: o.id,
                        label: `#${o.id} ${o.title}`,
                        value: o.id
                      }, null, 8, ["label", "value"]);
                    }), 128))
                  ]),
                  _: 1
                }, 8, ["modelValue"]),
                _cache[11] || (_cache[11] = createBaseVNode("label", { style: { "margin-top": "12px" } }, "���ԭ�򣨿�ѡ��", -1)),
                withDirectives(createBaseVNode("textarea", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => splitReason.value = $event),
                  maxlength: "5000",
                  rows: "2",
                  placeholder: "��д���ԭ��",
                  class: "sub-textarea"
                }, null, 512), [
                  [vModelText, splitReason.value]
                ]),
                createBaseVNode("div", _hoisted_14, [
                  createBaseVNode("button", {
                    class: "btn btn-primary",
                    disabled: splitting.value || splitOpinionIds.value.length === 0,
                    onClick: submitSplit
                  }, toDisplayString(splitting.value ? "�����" : "ȷ�ϲ��"), 9, _hoisted_15)
                ])
              ])) : createCommentVNode("", true),
              canUpdate.value ? (openBlock(), createElementBlock("div", _hoisted_16, [
                withDirectives(createBaseVNode("textarea", {
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => noteContent.value = $event),
                  maxlength: "5000",
                  rows: "3",
                  placeholder: "��д�˲顢������ý�չ",
                  disabled: busy.value
                }, null, 8, _hoisted_17), [
                  [vModelText, noteContent.value]
                ]),
                createBaseVNode("div", _hoisted_18, [
                  createBaseVNode("span", null, toDisplayString(noteContent.value.length) + "/5000", 1),
                  createBaseVNode("button", {
                    class: "btn btn-primary",
                    disabled: busy.value || !noteContent.value.trim(),
                    onClick: addNote
                  }, toDisplayString(savingNote.value ? "�ύ��" : "���ӱ�ע"), 9, _hoisted_19)
                ])
              ])) : createCommentVNode("", true)
            ]),
            createBaseVNode("div", _hoisted_20, [
              createBaseVNode("div", _hoisted_21, [
                _cache[12] || (_cache[12] = createTextVNode(" ���ü�¼", -1)),
                createBaseVNode("span", _hoisted_22, toDisplayString((event.value.actions || []).length), 1)
              ]),
              createBaseVNode("div", _hoisted_23, [
                createBaseVNode("div", _hoisted_24, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(event.value.actions || [], (action) => {
                    return openBlock(), createElementBlock("div", {
                      key: action.id,
                      class: "timeline-item"
                    }, [
                      _cache[13] || (_cache[13] = createBaseVNode("span", { class: "timeline-dot" }, null, -1)),
                      createBaseVNode("div", _hoisted_25, [
                        createBaseVNode("div", _hoisted_26, [
                          createBaseVNode("time", null, toDisplayString(formatTime(action.created_at)), 1),
                          createBaseVNode("strong", null, toDisplayString(action.username || (action.user_id ? `�û� ${action.user_id}` : "ϵͳ")), 1),
                          createBaseVNode("span", null, toDisplayString(actionTypeText(action.action_type)), 1)
                        ]),
                        createBaseVNode("div", _hoisted_27, [
                          action.action_type === "status_change" && action.old_status && action.new_status ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                            createTextVNode(toDisplayString(unref(eventStatusLabel)(action.old_status)) + " �� " + toDisplayString(unref(eventStatusLabel)(action.new_status)), 1)
                          ], 64)) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
                            createTextVNode(toDisplayString(action.content), 1)
                          ], 64))
                        ])
                      ])
                    ]);
                  }), 128)),
                  (event.value.actions || []).length === 0 ? (openBlock(), createElementBlock("div", _hoisted_28, "���޴��ü�¼")) : createCommentVNode("", true)
                ])
              ])
            ])
          ])) : (openBlock(), createElementBlock("div", _hoisted_29, "�����С�"))
        ]),
        _: 1
      }, 8, ["modelValue"]);
    };
  }
});

const EventDispositionDialog = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-2e53a4a7"]]);

export { EventDispositionDialog as E };
