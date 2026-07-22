import { d as defineComponent, p as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, t as toDisplayString, A as createCommentVNode, n as normalizeClass, k as normalizeStyle, e as createTextVNode, F as Fragment, i as renderList, y as createBlock, r as ref, j as computed, g as api, E as ElMessage, D as resolveDirective, h as useRouter, o as openBlock, H as useRoute, C as resolveComponent, _ as _export_sfc } from './index-BPeYYIlC.js';

const _hoisted_1 = { class: "detail" };
const _hoisted_2 = {
  key: 0,
  class: "detail-grid"
};
const _hoisted_3 = { class: "card card-pad-lg" };
const _hoisted_4 = { class: "detail-title" };
const _hoisted_5 = { class: "detail-meta" };
const _hoisted_6 = {
  key: 0,
  class: "detail-meta"
};
const _hoisted_7 = ["href"];
const _hoisted_8 = { class: "detail-content" };
const _hoisted_9 = { class: "card card-pad-lg ai-card" };
const _hoisted_10 = { class: "ai-header" };
const _hoisted_11 = { class: "ai-block" };
const _hoisted_12 = { class: "ai-block" };
const _hoisted_13 = { class: "ai-block" };
const _hoisted_14 = { class: "ai-text" };
const _hoisted_15 = { class: "ai-block" };
const _hoisted_16 = {
  key: 0,
  class: "kw-tags"
};
const _hoisted_17 = {
  key: 1,
  class: "ai-text"
};
const _hoisted_18 = { class: "ai-block" };
const _hoisted_19 = { class: "ai-text" };
const _hoisted_20 = { class: "ai-block" };
const _hoisted_21 = { class: "ai-text" };
const _hoisted_22 = { class: "ai-actions" };
const _hoisted_23 = ["disabled"];
const _hoisted_24 = {
  key: 1,
  class: "ai-status-line"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "OpinionDetail",
  setup(__props) {
    const route = useRoute();
    const router = useRouter();
    const loading = ref(false);
    const analyzing = ref(false);
    const opinion = ref(null);
    const opinionId = computed(() => Number(route.params.id));
    const keywordList = computed(
      () => (opinion.value?.keywords || "").split(",").map((k) => k.trim()).filter(Boolean)
    );
    function riskColor(score) {
      if (score >= 70) return "#ff3b30";
      if (score >= 40) return "#ff9f0a";
      return "#34c759";
    }
    function sentimentPill(s) {
      return { negative: "pill-red", positive: "pill-green", neutral: "pill-gray" }[s] || "pill-gray";
    }
    function sentimentText(s) {
      return { negative: "负面", positive: "正面", neutral: "中性" }[s] || s;
    }
    function statusPill(s) {
      return { completed: "pill-green", failed: "pill-red", processing: "pill-orange", pending: "pill-gray" }[s] || "pill-gray";
    }
    function statusText(s) {
      return { completed: "已完成", failed: "失败", processing: "分析中", pending: "待分析" }[s] || s;
    }
    function formatTime(t) {
      if (!t) return "-";
      return t.replace("T", " ").slice(0, 19);
    }
    async function loadData() {
      loading.value = true;
      try {
        const { data } = await api.get("/opinions/" + opinionId.value);
        opinion.value = data;
      } catch (err) {
        if (err?.response?.status === 404) {
          opinion.value = null;
        } else {
          ElMessage.error(err?.response?.data?.detail || "加载详情失败");
        }
      } finally {
        loading.value = false;
      }
    }
    async function triggerAnalyze() {
      if (analyzing.value) return;
      analyzing.value = true;
      try {
        const { data } = await api.post("/analyze/" + opinionId.value);
        opinion.value = data;
        ElMessage.success("AI 分析完成");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "AI 分析失败，请稍后重试");
        loadData();
      } finally {
        analyzing.value = false;
      }
    }
    function goBack() {
      router.back();
    }
    onMounted(loadData);
    return (_ctx, _cache) => {
      const _component_el_empty = resolveComponent("el-empty");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", { class: "detail-back" }, [
          createBaseVNode("button", {
            class: "btn btn-ghost",
            onClick: goBack
          }, "← 返回")
        ]),
        opinion.value ? (openBlock(), createElementBlock("div", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            createBaseVNode("h2", _hoisted_4, toDisplayString(opinion.value.title), 1),
            createBaseVNode("div", _hoisted_5, [
              createBaseVNode("span", null, "来源：" + toDisplayString(opinion.value.source), 1),
              createBaseVNode("span", null, "发布时间：" + toDisplayString(formatTime(opinion.value.publish_time)), 1)
            ]),
            opinion.value.url ? (openBlock(), createElementBlock("div", _hoisted_6, [
              createBaseVNode("a", {
                class: "detail-url",
                href: opinion.value.url,
                target: "_blank",
                rel: "noopener"
              }, toDisplayString(opinion.value.url), 9, _hoisted_7)
            ])) : createCommentVNode("", true),
            _cache[0] || (_cache[0] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
            createBaseVNode("div", _hoisted_8, toDisplayString(opinion.value.content), 1)
          ]),
          createBaseVNode("div", _hoisted_9, [
            createBaseVNode("div", _hoisted_10, [
              _cache[1] || (_cache[1] = createBaseVNode("span", { class: "section-title" }, "AI 分析", -1)),
              createBaseVNode("span", {
                class: normalizeClass(["pill", statusPill(opinion.value.analysis_status)])
              }, toDisplayString(statusText(opinion.value.analysis_status)), 3)
            ]),
            _cache[10] || (_cache[10] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
            createBaseVNode("div", _hoisted_11, [
              _cache[2] || (_cache[2] = createBaseVNode("div", { class: "ai-label" }, "风险评分", -1)),
              createBaseVNode("div", {
                class: "risk-big",
                style: normalizeStyle({ color: riskColor(opinion.value.risk_score) })
              }, toDisplayString(opinion.value.risk_score), 5)
            ]),
            createBaseVNode("div", _hoisted_12, [
              _cache[4] || (_cache[4] = createBaseVNode("div", { class: "ai-label" }, "情感", -1)),
              createBaseVNode("span", {
                class: normalizeClass(["pill", sentimentPill(opinion.value.sentiment)])
              }, [
                _cache[3] || (_cache[3] = createBaseVNode("span", { class: "dot" }, null, -1)),
                createTextVNode(toDisplayString(sentimentText(opinion.value.sentiment)), 1)
              ], 2)
            ]),
            createBaseVNode("div", _hoisted_13, [
              _cache[5] || (_cache[5] = createBaseVNode("div", { class: "ai-label" }, "AI 摘要", -1)),
              createBaseVNode("div", _hoisted_14, toDisplayString(opinion.value.summary || "暂无"), 1)
            ]),
            createBaseVNode("div", _hoisted_15, [
              _cache[6] || (_cache[6] = createBaseVNode("div", { class: "ai-label" }, "关键词", -1)),
              keywordList.value.length ? (openBlock(), createElementBlock("div", _hoisted_16, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(keywordList.value, (k) => {
                  return openBlock(), createElementBlock("span", {
                    key: k,
                    class: "kw-tag"
                  }, toDisplayString(k), 1);
                }), 128))
              ])) : (openBlock(), createElementBlock("span", _hoisted_17, "暂无"))
            ]),
            createBaseVNode("div", _hoisted_18, [
              _cache[7] || (_cache[7] = createBaseVNode("div", { class: "ai-label" }, "研判建议", -1)),
              createBaseVNode("div", _hoisted_19, toDisplayString(opinion.value.analysis_suggestion || "暂无"), 1)
            ]),
            createBaseVNode("div", _hoisted_20, [
              _cache[8] || (_cache[8] = createBaseVNode("div", { class: "ai-label" }, "分析时间", -1)),
              createBaseVNode("div", _hoisted_21, toDisplayString(formatTime(opinion.value.analysis_time)), 1)
            ]),
            _cache[11] || (_cache[11] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
            createBaseVNode("div", _hoisted_22, [
              opinion.value.analysis_status !== "processing" ? (openBlock(), createElementBlock("button", {
                key: 0,
                class: "btn btn-primary btn-block",
                disabled: analyzing.value,
                onClick: triggerAnalyze
              }, toDisplayString(analyzing.value ? "分析中..." : "触发 AI 分析"), 9, _hoisted_23)) : (openBlock(), createElementBlock("div", _hoisted_24, [..._cache[9] || (_cache[9] = [
                createBaseVNode("span", { class: "spinner" }, null, -1),
                createBaseVNode("span", { class: "ai-text" }, "AI 分析进行中...", -1)
              ])]))
            ])
          ])
        ])) : !loading.value ? (openBlock(), createBlock(_component_el_empty, {
          key: 1,
          description: "未找到该舆情"
        })) : createCommentVNode("", true)
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const OpinionDetail = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-5e0e58af"]]);

export { OpinionDetail as default };
