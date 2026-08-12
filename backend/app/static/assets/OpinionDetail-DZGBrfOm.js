import { d as defineComponent, z as usePermission, C as onMounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, t as toDisplayString, s as createCommentVNode, n as normalizeClass, F as Fragment, i as renderList, k as normalizeStyle, e as createTextVNode, q as createBlock, j as computed, r as ref, g as api, E as ElMessage, X as isPermissionDenied, B as resolveDirective, h as useRouter, o as openBlock, N as useRoute, y as resolveComponent, _ as _export_sfc } from './index-Cr-cCcQl.js';
import { f as formatAdmissionHits } from './admission-DpEuIHXC.js';

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
const _hoisted_9 = { class: "detail-right" };
const _hoisted_10 = { class: "card card-pad-lg admission-card" };
const _hoisted_11 = { class: "ai-header" };
const _hoisted_12 = { class: "pill pill-blue" };
const _hoisted_13 = { class: "admission-score" };
const _hoisted_14 = {
  key: 0,
  class: "admission-list"
};
const _hoisted_15 = {
  key: 1,
  class: "ai-text muted-admission"
};
const _hoisted_16 = { class: "card card-pad-lg ai-card" };
const _hoisted_17 = { class: "ai-header" };
const _hoisted_18 = { class: "ai-block" };
const _hoisted_19 = { class: "ai-block" };
const _hoisted_20 = { class: "ai-block" };
const _hoisted_21 = { class: "ai-text" };
const _hoisted_22 = { class: "ai-block" };
const _hoisted_23 = {
  key: 0,
  class: "kw-tags"
};
const _hoisted_24 = {
  key: 1,
  class: "ai-text"
};
const _hoisted_25 = { class: "ai-block" };
const _hoisted_26 = { class: "ai-text" };
const _hoisted_27 = { class: "ai-block" };
const _hoisted_28 = { class: "ai-text" };
const _hoisted_29 = {
  key: 0,
  class: "ai-actions"
};
const _hoisted_30 = ["disabled"];
const _hoisted_31 = {
  key: 1,
  class: "ai-status-line"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "OpinionDetail",
  setup(__props) {
    const route = useRoute();
    const router = useRouter();
    const { hasPermission } = usePermission();
    const canAnalyze = computed(() => hasPermission("ai:analyze"));
    const loading = ref(false);
    const analyzing = ref(false);
    const opinion = ref(null);
    const opinionId = computed(() => Number(route.params.id));
    const keywordList = computed(
      () => (opinion.value?.keywords || "").split(",").map((k) => k.trim()).filter(Boolean)
    );
    const CONTENT_TYPE_TEXT = {
      complaint: "投诉举报",
      consultation: "咨询求助",
      risk_event: "风险事件",
      public_affairs: "公共事务",
      news: "新闻",
      policy: "政策政务",
      advertising: "广告",
      entertainment: "娱乐",
      irrelevant: "无关"
    };
    function contentTypeText(type) {
      return type ? CONTENT_TYPE_TEXT[type] || type : "未标注";
    }
    function formatRelevance(score) {
      return score == null ? "-" : `${score} 分`;
    }
    function relevanceClass(score) {
      if (score == null) return "score-empty";
      if (score >= 60) return "score-high";
      if (score >= 40) return "score-low";
      return "score-filtered";
    }
    const admissionItems = computed(() => {
      const reason = opinion.value?.admission_reason;
      if (!reason || typeof reason !== "object" || reason.policy === "default_allow_non_weibo") return [];
      const items = [];
      const add = (label, value) => {
        const text = formatAdmissionHits(value, 5);
        if (text) items.push({ label, value: text });
      };
      add("地域命中", reason.region_hits);
      add("公共事务", reason.public_hits);
      add("诉求词", reason.demand_hits);
      add("风险词", reason.risk_hits);
      return items;
    });
    const defaultAdmissionText = computed(() => {
      const reason = opinion.value?.admission_reason;
      const source = String(reason?.source || opinion.value?.source || "");
      if (reason?.policy === "default_allow_non_weibo") {
        return source.includes("政府") || source.includes("政务") ? "政府来源默认准入" : "新闻来源默认准入";
      }
      return "系统默认准入";
    });
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
        if (!isPermissionDenied(err)) {
          ElMessage.error(err?.response?.data?.detail || "AI 分析失败，请稍后重试");
        }
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
              createBaseVNode("div", _hoisted_11, [
                _cache[1] || (_cache[1] = createBaseVNode("span", { class: "section-title" }, "准入分析", -1)),
                createBaseVNode("span", _hoisted_12, toDisplayString(contentTypeText(opinion.value.content_type)), 1)
              ]),
              _cache[3] || (_cache[3] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
              createBaseVNode("div", _hoisted_13, [
                _cache[2] || (_cache[2] = createBaseVNode("span", { class: "admission-score-label" }, "相关性", -1)),
                createBaseVNode("b", {
                  class: normalizeClass(relevanceClass(opinion.value.relevance_score))
                }, toDisplayString(formatRelevance(opinion.value.relevance_score)), 3)
              ]),
              admissionItems.value.length ? (openBlock(), createElementBlock("div", _hoisted_14, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(admissionItems.value, (item) => {
                  return openBlock(), createElementBlock("div", {
                    key: item.label,
                    class: "admission-row"
                  }, [
                    createBaseVNode("span", null, toDisplayString(item.label), 1),
                    createBaseVNode("b", null, toDisplayString(item.value), 1)
                  ]);
                }), 128))
              ])) : (openBlock(), createElementBlock("div", _hoisted_15, toDisplayString(defaultAdmissionText.value), 1))
            ]),
            createBaseVNode("div", _hoisted_16, [
              createBaseVNode("div", _hoisted_17, [
                _cache[4] || (_cache[4] = createBaseVNode("span", { class: "section-title" }, "AI 分析", -1)),
                createBaseVNode("span", {
                  class: normalizeClass(["pill", statusPill(opinion.value.analysis_status)])
                }, toDisplayString(statusText(opinion.value.analysis_status)), 3)
              ]),
              _cache[13] || (_cache[13] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
              createBaseVNode("div", _hoisted_18, [
                _cache[5] || (_cache[5] = createBaseVNode("div", { class: "ai-label" }, "风险评分", -1)),
                createBaseVNode("div", {
                  class: "risk-big",
                  style: normalizeStyle({ color: riskColor(opinion.value.risk_score) })
                }, toDisplayString(opinion.value.risk_score), 5)
              ]),
              createBaseVNode("div", _hoisted_19, [
                _cache[7] || (_cache[7] = createBaseVNode("div", { class: "ai-label" }, "情感", -1)),
                createBaseVNode("span", {
                  class: normalizeClass(["pill", sentimentPill(opinion.value.sentiment)])
                }, [
                  _cache[6] || (_cache[6] = createBaseVNode("span", { class: "dot" }, null, -1)),
                  createTextVNode(toDisplayString(sentimentText(opinion.value.sentiment)), 1)
                ], 2)
              ]),
              createBaseVNode("div", _hoisted_20, [
                _cache[8] || (_cache[8] = createBaseVNode("div", { class: "ai-label" }, "AI 摘要", -1)),
                createBaseVNode("div", _hoisted_21, toDisplayString(opinion.value.summary || "暂无"), 1)
              ]),
              createBaseVNode("div", _hoisted_22, [
                _cache[9] || (_cache[9] = createBaseVNode("div", { class: "ai-label" }, "关键词", -1)),
                keywordList.value.length ? (openBlock(), createElementBlock("div", _hoisted_23, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(keywordList.value, (k) => {
                    return openBlock(), createElementBlock("span", {
                      key: k,
                      class: "kw-tag"
                    }, toDisplayString(k), 1);
                  }), 128))
                ])) : (openBlock(), createElementBlock("span", _hoisted_24, "暂无"))
              ]),
              createBaseVNode("div", _hoisted_25, [
                _cache[10] || (_cache[10] = createBaseVNode("div", { class: "ai-label" }, "研判建议", -1)),
                createBaseVNode("div", _hoisted_26, toDisplayString(opinion.value.analysis_suggestion || "暂无"), 1)
              ]),
              createBaseVNode("div", _hoisted_27, [
                _cache[11] || (_cache[11] = createBaseVNode("div", { class: "ai-label" }, "分析时间", -1)),
                createBaseVNode("div", _hoisted_28, toDisplayString(formatTime(opinion.value.analysis_time)), 1)
              ]),
              _cache[14] || (_cache[14] = createBaseVNode("div", { class: "detail-divider" }, null, -1)),
              canAnalyze.value || opinion.value.analysis_status === "processing" ? (openBlock(), createElementBlock("div", _hoisted_29, [
                canAnalyze.value && opinion.value.analysis_status !== "processing" ? (openBlock(), createElementBlock("button", {
                  key: 0,
                  class: "btn btn-primary btn-block",
                  disabled: analyzing.value,
                  onClick: triggerAnalyze
                }, toDisplayString(analyzing.value ? "分析中..." : "触发 AI 分析"), 9, _hoisted_30)) : (openBlock(), createElementBlock("div", _hoisted_31, [..._cache[12] || (_cache[12] = [
                  createBaseVNode("span", { class: "spinner" }, null, -1),
                  createBaseVNode("span", { class: "ai-text" }, "AI 分析进行中...", -1)
                ])]))
              ])) : createCommentVNode("", true)
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

const OpinionDetail = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-7282d653"]]);

export { OpinionDetail as default };
