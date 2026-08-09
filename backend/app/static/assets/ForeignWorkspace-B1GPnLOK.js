import { d as defineComponent, z as usePermission, r as ref, A as watch, w as withDirectives, c as createElementBlock, a as createBaseVNode, t as toDisplayString, F as Fragment, i as renderList, e as createTextVNode, J as vModelSelect, s as createCommentVNode, b as withKeys, v as vModelText, K as vModelCheckbox, N as createStaticVNode, n as normalizeClass, H as unref, L as withModifiers, O as useRoute, f as reactive, g as api, E as ElMessage, M as ElMessageBox, P as pollTask, B as resolveDirective, o as openBlock, h as useRouter, _ as _export_sfc } from './index-DRiKfHAb.js';

const _hoisted_1 = { class: "foreign-page" };
const _hoisted_2 = { class: "workspace-head" };
const _hoisted_3 = ["disabled"];
const _hoisted_4 = {
  class: "tabs",
  role: "tablist"
};
const _hoisted_5 = ["onClick"];
const _hoisted_6 = {
  key: 0,
  class: "panel visualization-panel"
};
const _hoisted_7 = { class: "toolbar" };
const _hoisted_8 = { class: "muted" };
const _hoisted_9 = {
  key: 0,
  class: "stale-badge"
};
const _hoisted_10 = {
  key: 0,
  class: "state error-state"
};
const _hoisted_11 = {
  key: 1,
  class: "visualization-content"
};
const _hoisted_12 = { class: "metric-grid" };
const _hoisted_13 = { class: "metric-card" };
const _hoisted_14 = { class: "metric-card" };
const _hoisted_15 = { class: "metric-card" };
const _hoisted_16 = { class: "metric-card" };
const _hoisted_17 = { class: "metric-card" };
const _hoisted_18 = { class: "visualization-columns" };
const _hoisted_19 = { class: "data-section" };
const _hoisted_20 = {
  key: 0,
  class: "empty"
};
const _hoisted_21 = { class: "data-section" };
const _hoisted_22 = {
  key: 0,
  class: "empty"
};
const _hoisted_23 = { class: "data-section" };
const _hoisted_24 = {
  key: 0,
  class: "distribution-row"
};
const _hoisted_25 = { class: "distribution-row" };
const _hoisted_26 = {
  key: 1,
  class: "empty"
};
const _hoisted_27 = { class: "data-section" };
const _hoisted_28 = { class: "table-wrap" };
const _hoisted_29 = { class: "visualization-meta" };
const _hoisted_30 = {
  key: 2,
  class: "state"
};
const _hoisted_31 = {
  key: 1,
  class: "panel visualization-panel"
};
const _hoisted_32 = { class: "toolbar" };
const _hoisted_33 = { class: "muted" };
const _hoisted_34 = {
  key: 0,
  class: "stale-badge"
};
const _hoisted_35 = {
  key: 0,
  class: "state error-state"
};
const _hoisted_36 = {
  key: 1,
  class: "visualization-content"
};
const _hoisted_37 = { class: "table-wrap" };
const _hoisted_38 = { class: "title-cell" };
const _hoisted_39 = { class: "data-section" };
const _hoisted_40 = { class: "table-wrap" };
const _hoisted_41 = { class: "visualization-meta" };
const _hoisted_42 = {
  key: 2,
  class: "state"
};
const _hoisted_43 = {
  key: 2,
  class: "panel visualization-panel"
};
const _hoisted_44 = { class: "toolbar" };
const _hoisted_45 = {
  key: 0,
  class: "stale-badge"
};
const _hoisted_46 = {
  key: 0,
  class: "state error-state"
};
const _hoisted_47 = {
  key: 1,
  class: "visualization-content"
};
const _hoisted_48 = { class: "visualization-columns" };
const _hoisted_49 = { class: "data-section" };
const _hoisted_50 = { class: "data-section" };
const _hoisted_51 = {
  key: 0,
  class: "empty"
};
const _hoisted_52 = { class: "table-wrap" };
const _hoisted_53 = { class: "muted" };
const _hoisted_54 = { class: "visualization-meta" };
const _hoisted_55 = {
  key: 2,
  class: "state"
};
const _hoisted_56 = { class: "toolbar source-editor-toolbar" };
const _hoisted_57 = {
  key: 3,
  class: "source-editor"
};
const _hoisted_58 = ["disabled"];
const _hoisted_59 = { class: "muted" };
const _hoisted_60 = ["disabled"];
const _hoisted_61 = ["disabled"];
const _hoisted_62 = {
  key: 0,
  class: "muted"
};
const _hoisted_63 = {
  key: 4,
  class: "source-test-result"
};
const _hoisted_64 = { class: "table-wrap" };
const _hoisted_65 = { class: "muted" };
const _hoisted_66 = { class: "muted" };
const _hoisted_67 = ["disabled", "onClick"];
const _hoisted_68 = {
  key: 0,
  class: "proxy-mark"
};
const _hoisted_69 = { class: "actions" };
const _hoisted_70 = ["onClick"];
const _hoisted_71 = ["onClick"];
const _hoisted_72 = ["onClick"];
const _hoisted_73 = { key: 0 };
const _hoisted_74 = {
  key: 5,
  class: "pager"
};
const _hoisted_75 = ["disabled"];
const _hoisted_76 = ["disabled"];
const _hoisted_77 = {
  key: 6,
  class: "source-runs"
};
const _hoisted_78 = { class: "error-cell" };
const _hoisted_79 = {
  key: 0,
  class: "muted"
};
const _hoisted_80 = {
  key: 3,
  class: "panel"
};
const _hoisted_81 = { class: "toolbar" };
const _hoisted_82 = ["value"];
const _hoisted_83 = { class: "table-wrap" };
const _hoisted_84 = ["onClick"];
const _hoisted_85 = { class: "title-cell" };
const _hoisted_86 = { key: 0 };
const _hoisted_87 = {
  key: 0,
  class: "pager"
};
const _hoisted_88 = ["disabled"];
const _hoisted_89 = ["disabled"];
const _hoisted_90 = {
  key: 4,
  class: "panel"
};
const _hoisted_91 = { class: "toolbar" };
const _hoisted_92 = ["value"];
const _hoisted_93 = { class: "table-wrap" };
const _hoisted_94 = ["onClick"];
const _hoisted_95 = { class: "title-cell" };
const _hoisted_96 = {
  key: 0,
  class: "muted"
};
const _hoisted_97 = ["disabled", "onClick"];
const _hoisted_98 = { key: 0 };
const _hoisted_99 = {
  key: 0,
  class: "pager"
};
const _hoisted_100 = ["disabled"];
const _hoisted_101 = ["disabled"];
const _hoisted_102 = {
  key: 5,
  class: "panel"
};
const _hoisted_103 = { class: "toolbar" };
const _hoisted_104 = ["disabled"];
const _hoisted_105 = {
  key: 0,
  class: "state error-state"
};
const _hoisted_106 = {
  key: 1,
  class: "event-failures"
};
const _hoisted_107 = { class: "subtabs" };
const _hoisted_108 = {
  key: 2,
  class: "table-wrap"
};
const _hoisted_109 = { class: "title-cell" };
const _hoisted_110 = { class: "actions" };
const _hoisted_111 = ["disabled", "onClick"];
const _hoisted_112 = ["disabled", "onClick"];
const _hoisted_113 = { key: 0 };
const _hoisted_114 = {
  key: 3,
  class: "table-wrap"
};
const _hoisted_115 = ["onClick"];
const _hoisted_116 = { class: "title-cell" };
const _hoisted_117 = ["disabled", "onClick"];
const _hoisted_118 = ["disabled", "onClick"];
const _hoisted_119 = { key: 0 };
const _hoisted_120 = {
  key: 4,
  class: "event-detail"
};
const _hoisted_121 = { class: "event-detail-head" };
const _hoisted_122 = { class: "actions" };
const _hoisted_123 = ["disabled"];
const _hoisted_124 = ["disabled"];
const _hoisted_125 = ["disabled"];
const _hoisted_126 = { class: "muted" };
const _hoisted_127 = { class: "event-metrics" };
const _hoisted_128 = { class: "muted" };
const _hoisted_129 = ["href"];
const _hoisted_130 = {
  key: 6,
  class: "panel"
};
const _hoisted_131 = { class: "toolbar" };
const _hoisted_132 = ["disabled"];
const _hoisted_133 = {
  key: 0,
  class: "state error-state"
};
const _hoisted_134 = {
  key: 1,
  class: "alert-failures"
};
const _hoisted_135 = { class: "table-wrap" };
const _hoisted_136 = { class: "title-cell" };
const _hoisted_137 = { class: "muted" };
const _hoisted_138 = { class: "actions" };
const _hoisted_139 = ["onClick"];
const _hoisted_140 = ["disabled", "onClick"];
const _hoisted_141 = ["disabled", "onClick"];
const _hoisted_142 = ["disabled", "onClick"];
const _hoisted_143 = { key: 0 };
const _hoisted_144 = {
  key: 2,
  class: "alert-detail"
};
const _hoisted_145 = { class: "event-detail-head" };
const _hoisted_146 = { class: "muted" };
const _hoisted_147 = {
  key: 0,
  class: "muted"
};
const _hoisted_148 = {
  key: 1,
  class: "empty"
};
const _hoisted_149 = {
  key: 2,
  class: "alert-action-history"
};
const _hoisted_150 = { class: "muted" };
const _hoisted_151 = { class: "data-section alert-rules" };
const _hoisted_152 = { class: "toolbar rule-editor" };
const _hoisted_153 = ["disabled"];
const _hoisted_154 = { class: "table-wrap" };
const _hoisted_155 = { class: "actions" };
const _hoisted_156 = ["disabled", "onClick"];
const _hoisted_157 = ["disabled", "onClick"];
const _hoisted_158 = ["disabled", "onClick"];
const _hoisted_159 = { key: 0 };
const _hoisted_160 = {
  key: 7,
  class: "panel"
};
const _hoisted_161 = { class: "toolbar" };
const _hoisted_162 = ["value"];
const _hoisted_163 = { class: "table-wrap" };
const _hoisted_164 = { class: "actions" };
const _hoisted_165 = ["disabled", "onClick"];
const _hoisted_166 = ["onClick"];
const _hoisted_167 = ["onClick"];
const _hoisted_168 = { key: 0 };
const _hoisted_169 = { class: "toolbar" };
const _hoisted_170 = ["disabled"];
const _hoisted_171 = ["disabled"];
const _hoisted_172 = {
  key: 0,
  class: "pager"
};
const _hoisted_173 = ["disabled"];
const _hoisted_174 = ["disabled"];
const _hoisted_175 = {
  key: 8,
  class: "panel"
};
const _hoisted_176 = { class: "table-wrap" };
const _hoisted_177 = { class: "error-cell" };
const _hoisted_178 = { key: 0 };
const _hoisted_179 = { class: "detail" };
const _hoisted_180 = {
  key: 0,
  class: "state"
};
const _hoisted_181 = { class: "detail-meta" };
const _hoisted_182 = { class: "detail-summary" };
const _hoisted_183 = { class: "detail-text" };
const _hoisted_184 = ["href"];
const _hoisted_185 = { class: "analysis-block" };
const _hoisted_186 = {
  key: 0,
  class: "analysis-grid"
};
const _hoisted_187 = { key: 1 };
const _hoisted_188 = { key: 2 };
const _hoisted_189 = {
  key: 3,
  class: "muted"
};
const _hoisted_190 = { class: "analysis-block" };
const _hoisted_191 = { class: "analysis-heading" };
const _hoisted_192 = ["disabled"];
const _hoisted_193 = {
  key: 0,
  class: "analysis-grid"
};
const _hoisted_194 = { key: 1 };
const _hoisted_195 = { key: 2 };
const _hoisted_196 = {
  key: 3,
  class: "error-cell"
};
const _hoisted_197 = {
  key: 4,
  class: "muted"
};
const _hoisted_198 = { class: "analysis-block" };
const _hoisted_199 = {
  key: 0,
  class: "muted"
};
const sourceSize = 20;
const opinionSize = 20;
const riskSize = 20;
const keywordSize = 50;
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "ForeignWorkspace",
  setup(__props) {
    const tabs = [
      { value: "dashboard", label: "外网 Dashboard" },
      { value: "opinions", label: "国外舆情" },
      { value: "risk", label: "风险与情感" },
      { value: "events", label: "外网事件" },
      { value: "alerts", label: "外网告警" },
      { value: "hotwords", label: "外网热词" },
      { value: "keywords", label: "外网关键词" },
      { value: "sources", label: "外网数据源" },
      { value: "runs", label: "外网采集日志" }
    ];
    const route = useRoute();
    const router = useRouter();
    const { hasPermission } = usePermission();
    function normalizeTab(value) {
      return value === "dashboard" || value === "risk" || value === "events" || value === "alerts" || value === "hotwords" || value === "keywords" || value === "sources" || value === "runs" ? value : "opinions";
    }
    const activeTab = ref(normalizeTab(route.query.tab));
    const loading = ref(false);
    const collecting = ref(false);
    const keywords = ref([]);
    const sources = ref([]);
    const sourceEditorVisible = ref(false);
    const editingSourceId = ref(null);
    const sourceSaving = ref(false);
    const sourceTesting = ref(false);
    const sourceBusyId = ref(null);
    const sourceDraftTested = ref(false);
    const sourceTestResult = ref(null);
    const selectedSourceRuns = ref(null);
    const sourceDraft = reactive({ name: "", key: "", feedsText: "", proxyEnv: "FOREIGN_HTTP_PROXY", timeout: 15, maxRetries: 2, maxItems: 100, requestInterval: 0.5, scheduleInterval: 60, maxContentLength: 2e5, respectRobots: true });
    const sourceFilters = reactive({ q: "" });
    const sourcePage = ref(1);
    const sourceTotal = ref(0);
    const opinions = ref([]);
    const runs = ref([]);
    const risks = ref([]);
    const eventCandidates = ref([]);
    const foreignEvents = ref([]);
    const eventRunFailures = ref([]);
    const eventLoadError = ref(null);
    const selectedForeignEvent = ref(null);
    const eventSection = ref("candidates");
    const rebuildingEvents = ref(false);
    const eventActionKey = ref(null);
    const eventDetailLoadingId = ref(null);
    const foreignAlerts = ref([]);
    const alertRunFailures = ref([]);
    const alertLoadError = ref(null);
    const alertEvaluating = ref(false);
    const alertFilters = reactive({ status: "", severity: "" });
    const selectedForeignAlert = ref(null);
    const alertActions = ref([]);
    const alertActionsLoading = ref(false);
    const alertActionBusyId = ref(null);
    const alertRules = ref([]);
    const alertRuleBusyId = ref(null);
    const alertRuleSaving = ref(false);
    const alertRuleDraft = reactive({ name: "", rule_type: "risk_score", conditionsText: '{"threshold":80}', severity: "medium", cooldown_seconds: 3600 });
    const visualizationDays = ref(7);
    const visualizationError = ref(null);
    const visualizationStale = ref(false);
    const dashboardSummary = ref(null);
    const dashboardRisk = ref(null);
    const dashboardEvents = ref(null);
    const dashboardTrends = ref(null);
    const dashboardAlerts = ref(null);
    const dashboardSources = ref(null);
    const hotwordItems = ref([]);
    const hotwordTrendItems = ref([]);
    const hotwordMeta = ref({});
    const hotwordLanguage = ref("");
    const sourceDistribution = ref(null);
    const languageDistribution = ref(null);
    const opinionSources = ref([]);
    const opinionTotal = ref(0);
    const opinionPage = ref(1);
    const riskTotal = ref(0);
    const riskPage = ref(1);
    const selectedOpinion = ref(null);
    const opinionLoading = ref(false);
    const aiAnalyzing = ref(false);
    const keywordSaving = ref(false);
    const keywordCategories = ref([]);
    const keywordPage = ref(1);
    const keywordTotal = ref(0);
    const keywordFilters = reactive({ q: "", category: "", type: "", enabled: "" });
    const keywordDraft = reactive({ word: "", category: "general", type: "monitoring", weight: 10 });
    const editingKeywordId = ref(null);
    const opinionFilters = reactive({ q: "", source: "", keyword: "", date_from: "", date_to: "" });
    const riskFilters = reactive({ q: "", source: "", language: "", sentiment: "", risk_level: "", analysis_status: "", date_from: "", date_to: "" });
    const canAnalyzeRisk = hasPermission("foreign:risk:analyze");
    const canAnalyzeAI = hasPermission("foreign:ai:analyze");
    const canConfirmEvents = hasPermission("foreign:events:confirm");
    const canChangeEventStatus = hasPermission("foreign:events:status");
    const canMergeEvents = hasPermission("foreign:events:merge");
    const canSplitEvents = hasPermission("foreign:events:split");
    const canEvaluateAlerts = hasPermission("foreign:alerts:evaluate");
    const canAcknowledgeAlerts = hasPermission("foreign:alerts:acknowledge");
    const canResolveAlerts = hasPermission("foreign:alerts:resolve");
    const canSuppressAlerts = hasPermission("foreign:alerts:suppress");
    const canEnableAlertRules = hasPermission("foreign:alerts:enable");
    function switchTab(tab) {
      router.push({ path: "/foreign", query: { ...route.query, tab } });
    }
    function loadTab(tab) {
      if (tab === "dashboard") loadDashboard();
      if (tab === "opinions") loadOpinions();
      if (tab === "risk") loadRisk();
      if (tab === "events") loadEvents();
      if (tab === "alerts") loadAlerts();
      if (tab === "hotwords") loadHotwords();
      if (tab === "keywords") loadKeywords();
      if (tab === "sources") loadSourcesView();
      if (tab === "runs") loadRuns();
    }
    function visualizationFailure(err) {
      const status = err?.response?.status;
      const code = err?.response?.data?.error_code;
      if (code === "FOREIGN_VISUALIZATION_QUERY_FAILED" || status === 503) return "外网可视化数据暂时不可用";
      if (status === 403) return "当前账号没有外网可视化权限";
      if (status === 422) return "外网可视化请求参数无效";
      return "外网可视化数据加载失败，请稍后重试";
    }
    function markVisualizationFresh(data) {
      const asOf = data?.data_as_of ? new Date(data.data_as_of).getTime() : Date.now();
      visualizationStale.value = Date.now() - asOf > 15 * 60 * 1e3;
    }
    async function loadDashboard() {
      loading.value = true;
      visualizationError.value = null;
      try {
        const params = { days: visualizationDays.value };
        const [summary, trends, risk, events, alerts, sourceStats] = await Promise.all([
          api.get("/foreign/dashboard/summary", { params }),
          api.get("/foreign/dashboard/trends", { params }),
          api.get("/foreign/dashboard/risk", { params }),
          api.get("/foreign/dashboard/events", { params }),
          api.get("/foreign/dashboard/alerts", { params }),
          api.get("/foreign/dashboard/sources", { params })
        ]);
        dashboardSummary.value = summary.data;
        dashboardTrends.value = trends.data;
        dashboardRisk.value = risk.data;
        dashboardEvents.value = events.data;
        dashboardAlerts.value = alerts.data;
        dashboardSources.value = sourceStats.data;
        markVisualizationFresh(summary.data);
      } catch (err) {
        visualizationError.value = visualizationFailure(err);
        dashboardSummary.value = null;
      } finally {
        loading.value = false;
      }
    }
    async function loadHotwords() {
      loading.value = true;
      visualizationError.value = null;
      try {
        const params = { days: visualizationDays.value, limit: 30 };
        if (hotwordLanguage.value) params.language = hotwordLanguage.value;
        const [response, trendResponse] = await Promise.all([
          api.get("/foreign/hotwords", { params }),
          api.get("/foreign/hotwords/trends", { params })
        ]);
        hotwordItems.value = response.data.items || [];
        hotwordTrendItems.value = trendResponse.data.items || [];
        hotwordMeta.value = response.data;
        markVisualizationFresh(response.data);
      } catch (err) {
        visualizationError.value = visualizationFailure(err);
        hotwordItems.value = [];
      } finally {
        loading.value = false;
      }
    }
    async function loadSourcesView() {
      loading.value = true;
      visualizationError.value = null;
      try {
        const params = { days: visualizationDays.value };
        const [distribution, languages, management] = await Promise.all([
          api.get("/foreign/source-distribution", { params }),
          api.get("/foreign/language-distribution", { params }),
          api.get("/foreign/sources", { params: { page: sourcePage.value, size: sourceSize, q: sourceFilters.q || void 0 } })
        ]);
        sourceDistribution.value = distribution.data;
        languageDistribution.value = languages.data;
        sources.value = management.data.items || [];
        sourceTotal.value = management.data.total || 0;
        markVisualizationFresh(distribution.data);
      } catch (err) {
        visualizationError.value = visualizationFailure(err);
        sourceDistribution.value = null;
        languageDistribution.value = null;
      } finally {
        loading.value = false;
      }
    }
    function formatTime(value) {
      return value ? new Date(value).toLocaleString() : "-";
    }
    function operationRequestId(prefix) {
      const random = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      return `${prefix}-${random}`.slice(0, 128);
    }
    async function loadKeywords() {
      loading.value = true;
      try {
        const params = { page: keywordPage.value, size: keywordSize };
        if (keywordFilters.q) params.q = keywordFilters.q;
        if (keywordFilters.category) params.category = keywordFilters.category;
        if (keywordFilters.type) params.type = keywordFilters.type;
        if (keywordFilters.enabled) params.is_enabled = keywordFilters.enabled === "true";
        const [list, categories] = await Promise.all([
          api.get("/foreign/keywords", { params }),
          api.get("/foreign/keywords/categories")
        ]);
        keywords.value = list.data.items || [];
        keywordTotal.value = list.data.total || 0;
        keywordCategories.value = categories.data.items || [];
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网关键词加载失败");
      } finally {
        loading.value = false;
      }
    }
    async function loadOpinions() {
      loading.value = true;
      try {
        const params = { page: opinionPage.value, size: opinionSize };
        if (opinionFilters.q) params.q = opinionFilters.q;
        if (opinionFilters.source) params.source = opinionFilters.source;
        if (opinionFilters.keyword) params.keyword = opinionFilters.keyword;
        if (opinionFilters.date_from) params.date_from = opinionFilters.date_from;
        if (opinionFilters.date_to) params.date_to = opinionFilters.date_to;
        const [list, sourceList] = await Promise.all([
          api.get("/foreign/opinions", { params }),
          api.get("/foreign/opinions/sources")
        ]);
        opinions.value = list.data.items;
        opinionTotal.value = list.data.total;
        opinionSources.value = sourceList.data;
      } finally {
        loading.value = false;
      }
    }
    async function loadRisk() {
      loading.value = true;
      try {
        const params = { page: riskPage.value, size: riskSize };
        if (riskFilters.q) params.q = riskFilters.q;
        if (riskFilters.source) params.source = riskFilters.source;
        if (riskFilters.language) params.language = riskFilters.language;
        if (riskFilters.sentiment) params.sentiment = riskFilters.sentiment;
        if (riskFilters.risk_level) params.risk_level = riskFilters.risk_level;
        if (riskFilters.analysis_status) params.analysis_status = riskFilters.analysis_status;
        if (riskFilters.date_from) params.date_from = riskFilters.date_from;
        if (riskFilters.date_to) params.date_to = riskFilters.date_to;
        const [list, sourceList] = await Promise.all([
          api.get("/foreign/risk", { params }),
          api.get("/foreign/opinions/sources")
        ]);
        risks.value = list.data.items;
        riskTotal.value = list.data.total;
        opinionSources.value = sourceList.data;
      } finally {
        loading.value = false;
      }
    }
    async function loadRuns() {
      loading.value = true;
      try {
        runs.value = (await api.get("/foreign/collection-runs", { params: { size: 100 } })).data.items;
      } finally {
        loading.value = false;
      }
    }
    async function loadEvents() {
      loading.value = true;
      eventLoadError.value = null;
      try {
        const [candidateResponse, eventResponse, runResponse] = await Promise.all([
          api.get("/foreign/events/candidates", { params: { size: 100, status: "candidate" } }),
          api.get("/foreign/events", { params: { size: 100 } }),
          api.get("/foreign/event-runs", { params: { size: 20, status: "failed" } })
        ]);
        eventCandidates.value = candidateResponse.data.items;
        foreignEvents.value = eventResponse.data.items;
        eventRunFailures.value = runResponse.data.items;
      } catch (err) {
        eventLoadError.value = err?.response?.data?.detail || "请求失败，请稍后重试";
        eventCandidates.value = [];
        foreignEvents.value = [];
        eventRunFailures.value = [];
      } finally {
        loading.value = false;
      }
    }
    async function loadAlerts() {
      loading.value = true;
      alertLoadError.value = null;
      try {
        const params = { size: 100 };
        if (alertFilters.status) params.status = alertFilters.status;
        if (alertFilters.severity) params.severity = alertFilters.severity;
        const [list, runs2] = await Promise.all([
          api.get("/foreign/alerts", { params }),
          api.get("/foreign/alert-runs", { params: { size: 20, status: "failed" } })
        ]);
        foreignAlerts.value = list.data.items || [];
        alertRunFailures.value = runs2.data.items || [];
      } catch (err) {
        alertLoadError.value = err?.response?.data?.detail || "请求失败，请稍后重试";
        foreignAlerts.value = [];
        alertRunFailures.value = [];
      } finally {
        loading.value = false;
      }
      await loadAlertRules();
    }
    async function loadAlertActions(row) {
      if (alertActionsLoading.value) return;
      selectedForeignAlert.value = row;
      alertActionsLoading.value = true;
      try {
        alertActions.value = (await api.get(`/foreign/alerts/${row.id}/actions`)).data.items || [];
      } catch (err) {
        alertActions.value = [];
        ElMessage.error(err?.response?.data?.detail || "外网告警处置历史加载失败");
      } finally {
        alertActionsLoading.value = false;
      }
    }
    async function loadAlertRules() {
      try {
        alertRules.value = (await api.get("/foreign/alert-rules", { params: { size: 100 } })).data.items || [];
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网告警规则加载失败");
      }
    }
    async function createAlertRule() {
      if (alertRuleSaving.value) return;
      if (!alertRuleDraft.name.trim()) {
        ElMessage.warning("请输入规则名称");
        return;
      }
      let conditions;
      try {
        conditions = JSON.parse(alertRuleDraft.conditionsText);
      } catch {
        ElMessage.error("规则条件必须是合法 JSON");
        return;
      }
      alertRuleSaving.value = true;
      try {
        await api.post("/foreign/alert-rules", { name: alertRuleDraft.name.trim(), rule_type: alertRuleDraft.rule_type, conditions, severity: alertRuleDraft.severity, cooldown_seconds: alertRuleDraft.cooldown_seconds, is_enabled: false });
        ElMessage.success("外网告警规则已创建并保持停用");
        alertRuleDraft.name = "";
        await loadAlertRules();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "创建外网告警规则失败");
      } finally {
        alertRuleSaving.value = false;
      }
    }
    async function enableAlertRule(rule) {
      if (!canEnableAlertRules || alertRuleBusyId.value) return;
      alertRuleBusyId.value = rule.id;
      try {
        await api.post(`/foreign/alert-rules/${rule.id}/enable`);
        ElMessage.success("外网告警规则已启用");
        await loadAlertRules();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "启用外网告警规则失败");
      } finally {
        alertRuleBusyId.value = null;
      }
    }
    async function disableAlertRule(rule) {
      if (alertRuleBusyId.value) return;
      alertRuleBusyId.value = rule.id;
      try {
        await api.post(`/foreign/alert-rules/${rule.id}/disable`);
        ElMessage.success("外网告警规则已停用");
        await loadAlertRules();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "停用外网告警规则失败");
      } finally {
        alertRuleBusyId.value = null;
      }
    }
    async function deleteAlertRule(rule) {
      try {
        await ElMessageBox.confirm(`确认删除外网告警规则“${rule.name}”？`, "删除规则", { type: "warning" });
        alertRuleBusyId.value = rule.id;
        await api.delete(`/foreign/alert-rules/${rule.id}`);
        ElMessage.success("外网告警规则已删除");
        await loadAlertRules();
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "删除外网告警规则失败");
      } finally {
        alertRuleBusyId.value = null;
      }
    }
    function actionLabel(action) {
      return action === "acknowledge" ? "确认" : action === "resolve" ? "解决" : "抑制";
    }
    async function evaluateAlerts() {
      if (alertEvaluating.value || !canEvaluateAlerts) return;
      alertEvaluating.value = true;
      try {
        await api.post("/foreign/alerts/evaluate", { dry_run: true, max_items: 200 });
        ElMessage.success("外网告警 Dry-Run 已完成，未写入告警记录");
        await loadAlerts();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网告警评估失败");
      } finally {
        alertEvaluating.value = false;
      }
    }
    async function handleForeignAlert(row, action) {
      const permission = action === "acknowledge" ? canAcknowledgeAlerts : action === "resolve" ? canResolveAlerts : canSuppressAlerts;
      if (!permission || alertActionBusyId.value) return;
      alertActionBusyId.value = row.id;
      try {
        const prompt = await ElMessageBox.prompt(
          `请输入${actionLabel(action)}备注`,
          "外网告警处置",
          {
            inputType: "textarea",
            inputPlaceholder: "备注不能为空",
            inputValidator: (value) => value.trim() ? true : "备注不能为空"
          }
        );
        await api.post(`/foreign/alerts/${row.id}/${action}`, { note: prompt.value });
        ElMessage.success(`外网告警${actionLabel(action)}成功`);
        await loadAlerts();
        await loadAlertActions(row);
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "外网告警操作失败");
      } finally {
        alertActionBusyId.value = null;
      }
    }
    async function rebuildEvents() {
      if (rebuildingEvents.value) return;
      rebuildingEvents.value = true;
      try {
        await api.post("/foreign/events/rebuild", { dry_run: true });
        ElMessage.success("外网事件候选 Dry-Run 已完成");
        await loadEvents();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网事件候选重建失败");
      } finally {
        rebuildingEvents.value = false;
      }
    }
    async function confirmCandidate(row) {
      const key = `candidate-confirm-${row.id}`;
      if (eventActionKey.value) return;
      eventActionKey.value = key;
      try {
        await api.post(`/foreign/events/candidates/${row.id}/confirm`, { reason: "Foreign workspace manual confirmation", request_id: operationRequestId(`candidate-confirm-${row.id}`) });
        ElMessage.success("外网事件候选已确认");
        await loadEvents();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "确认外网事件候选失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function rejectCandidate(row) {
      const key = `candidate-reject-${row.id}`;
      if (eventActionKey.value) return;
      eventActionKey.value = key;
      try {
        await api.post(`/foreign/events/candidates/${row.id}/reject`, { reason: "Foreign workspace manual rejection", request_id: operationRequestId(`candidate-reject-${row.id}`) });
        ElMessage.success("外网事件候选已拒绝");
        await loadEvents();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "拒绝外网事件候选失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function loadEventDetail(id) {
      if (selectedForeignEvent.value?.id === id && selectedForeignEvent.value.opinions) return;
      if (eventDetailLoadingId.value) return;
      eventDetailLoadingId.value = id;
      try {
        selectedForeignEvent.value = (await api.get(`/foreign/events/${id}`)).data;
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网事件详情加载失败");
      } finally {
        eventDetailLoadingId.value = null;
      }
    }
    async function archiveEvent(row) {
      if (eventActionKey.value) return;
      eventActionKey.value = `event-archive-${row.id}`;
      try {
        await api.post(`/foreign/events/${row.id}/status`, { status: "archived", reason: "Foreign workspace archive", request_id: operationRequestId(`event-archive-${row.id}`) });
        ElMessage.success("外网事件已归档");
        await loadEvents();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网事件归档失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function closeEvent(row) {
      if (!canChangeEventStatus || eventActionKey.value) return;
      eventActionKey.value = `event-close-${row.id}`;
      try {
        const prompt = await ElMessageBox.prompt("请输入关闭原因", "关闭外网事件", { inputType: "textarea", inputValidator: (value) => value.trim() ? true : "原因不能为空" });
        await api.post(`/foreign/events/${row.id}/close`, { reason: prompt.value, request_id: operationRequestId(`event-close-${row.id}`) });
        ElMessage.success("外网事件已关闭");
        await loadEvents();
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "关闭外网事件失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function mergeEvent(row) {
      if (!canMergeEvents || eventActionKey.value) return;
      eventActionKey.value = `event-merge-${row.id}`;
      try {
        const prompt = await ElMessageBox.prompt("请输入目标外网事件 ID", "合并外网事件", { inputType: "number", inputValidator: (value) => /^\d+$/.test(value) && Number(value) !== row.id ? true : "请输入不同的有效事件 ID" });
        await api.post(`/foreign/events/${row.id}/merge`, { target_event_id: Number(prompt.value), reason: "Foreign workspace manual merge", request_id: operationRequestId(`event-merge-${row.id}`) });
        ElMessage.success("外网事件已合并");
        selectedForeignEvent.value = null;
        await loadEvents();
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "外网事件合并失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function splitEvent(row) {
      if (!canSplitEvents || !row.opinions?.length || eventActionKey.value) return;
      eventActionKey.value = `event-split-${row.id}`;
      try {
        const prompt = await ElMessageBox.prompt("请输入要拆出的文章 ID，多个 ID 用逗号分隔", "拆分外网事件", { inputValidator: (value) => value.split(",").every((item) => /^\s*\d+\s*$/.test(item)) ? true : "请输入逗号分隔的文章 ID" });
        const opinion_ids = prompt.value.split(",").map((item) => Number(item.trim())).filter(Boolean);
        await api.post(`/foreign/events/${row.id}/split`, { opinion_ids, reason: "Foreign workspace manual split", request_id: operationRequestId(`event-split-${row.id}`) });
        ElMessage.success("外网事件已拆分");
        selectedForeignEvent.value = null;
        await loadEvents();
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "外网事件拆分失败");
      } finally {
        eventActionKey.value = null;
      }
    }
    async function createKeyword() {
      if (keywordSaving.value) return;
      const word = keywordDraft.word.trim();
      if (!word) {
        ElMessage.warning("请输入关键词");
        return;
      }
      keywordSaving.value = true;
      try {
        const payload = { word, category: keywordDraft.category.trim() || "general", type: keywordDraft.type, weight: keywordDraft.weight, severity_weight: 0, source: editingKeywordId.value ? void 0 : "custom", is_enabled: true };
        if (editingKeywordId.value) {
          await api.patch(`/foreign/keywords/${editingKeywordId.value}`, payload);
          ElMessage.success("外网关键词已更新");
        } else {
          await api.post("/foreign/keywords", payload);
          ElMessage.success("外网关键词已新增");
        }
        editingKeywordId.value = null;
        keywordDraft.word = "";
        await loadKeywords();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网关键词保存失败");
      } finally {
        keywordSaving.value = false;
      }
    }
    async function toggleKeyword(row) {
      if (keywordSaving.value) return;
      keywordSaving.value = true;
      try {
        await api.patch(`/foreign/keywords/${row.id}`, { is_enabled: !row.is_enabled });
        await loadKeywords();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网关键词更新失败");
      } finally {
        keywordSaving.value = false;
      }
    }
    async function removeKeyword(id) {
      try {
        await ElMessageBox.confirm("确认删除这个外网关键词？", "删除关键词", { type: "warning" });
        await api.delete(`/foreign/keywords/${id}`);
        await loadKeywords();
        ElMessage.success("外网关键词已删除");
      } catch (err) {
        if (err === "cancel" || err === "close") return;
        ElMessage.error(err?.response?.data?.detail || "外网关键词删除失败");
      }
    }
    function editKeyword(row) {
      editingKeywordId.value = row.id;
      keywordDraft.word = row.word;
      keywordDraft.category = row.category;
      keywordDraft.type = row.type || "monitoring";
      keywordDraft.weight = row.weight ?? 10;
    }
    async function bulkToggleKeywords(isEnabled) {
      if (keywordSaving.value || !keywords.value.length) return;
      keywordSaving.value = true;
      try {
        await api.post("/foreign/keywords/bulk-status", { keyword_ids: keywords.value.map((row) => row.id), is_enabled: isEnabled });
        await loadKeywords();
        ElMessage.success("外网关键词状态已批量更新");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "批量更新失败");
      } finally {
        keywordSaving.value = false;
      }
    }
    async function openOpinion(id) {
      selectedOpinion.value = { id };
      opinionLoading.value = true;
      try {
        selectedOpinion.value = (await api.get(`/foreign/opinions/${id}/detail`)).data;
      } catch (err) {
        selectedOpinion.value = null;
        ElMessage.error(err?.response?.data?.detail || "外网舆情详情加载失败");
      } finally {
        opinionLoading.value = false;
      }
    }
    async function analyzeAI(id) {
      if (!canAnalyzeAI || aiAnalyzing.value) return;
      aiAnalyzing.value = true;
      try {
        const response = await api.post(`/foreign/opinions/${id}/ai-analyze`, {});
        if (selectedOpinion.value) selectedOpinion.value.ai_result = response.data;
        ElMessage.success(response.data?.status === "completed" ? "外网 AI 研判完成" : "外网 AI 研判失败，详情已记录");
        if (selectedOpinion.value) {
          const detail = await api.get(`/foreign/opinions/${id}/detail`);
          selectedOpinion.value = detail.data;
        }
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网 AI 研判失败");
      } finally {
        aiAnalyzing.value = false;
      }
    }
    function resetSourceDraft() {
      sourceDraft.name = "";
      sourceDraft.key = "";
      sourceDraft.feedsText = "";
      sourceDraft.proxyEnv = "FOREIGN_HTTP_PROXY";
      sourceDraft.timeout = 15;
      sourceDraft.maxRetries = 2;
      sourceDraft.maxItems = 100;
      sourceDraft.requestInterval = 0.5;
      sourceDraft.scheduleInterval = 60;
      sourceDraft.maxContentLength = 2e5;
      sourceDraft.respectRobots = true;
      sourceDraftTested.value = false;
      sourceTestResult.value = null;
    }
    function beginNewSource() {
      resetSourceDraft();
      editingSourceId.value = null;
      sourceEditorVisible.value = true;
    }
    function editSource(row) {
      sourceDraft.name = row.name;
      sourceDraft.key = row.key;
      sourceDraft.feedsText = row.feeds.join("\n");
      sourceDraft.proxyEnv = row.proxy_env || "FOREIGN_HTTP_PROXY";
      sourceDraft.timeout = row.timeout || 15;
      sourceDraft.maxRetries = row.max_retries ?? 2;
      sourceDraft.maxItems = row.max_items || 100;
      sourceDraft.requestInterval = row.request_interval ?? 0.5;
      sourceDraft.scheduleInterval = row.schedule_interval_minutes || 60;
      sourceDraft.maxContentLength = row.max_content_length || 2e5;
      sourceDraft.respectRobots = row.respect_robots !== false;
      editingSourceId.value = row.id;
      sourceDraftTested.value = false;
      sourceTestResult.value = null;
      sourceEditorVisible.value = true;
    }
    function sourcePayload() {
      return {
        name: sourceDraft.name.trim(),
        key: sourceDraft.key.trim(),
        feeds: sourceDraft.feedsText.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean),
        proxy_env: sourceDraft.proxyEnv.trim() || null,
        timeout: sourceDraft.timeout,
        connect_timeout: sourceDraft.timeout,
        read_timeout: sourceDraft.timeout,
        max_items: sourceDraft.maxItems,
        max_retries: sourceDraft.maxRetries,
        request_interval: sourceDraft.requestInterval,
        schedule_interval_minutes: sourceDraft.scheduleInterval,
        max_content_length: sourceDraft.maxContentLength,
        respect_robots: sourceDraft.respectRobots,
        fetch_full_text: false
      };
    }
    function sourceTestPayload() {
      const payload = sourcePayload();
      return {
        name: payload.name,
        feeds: payload.feeds,
        proxy_env: payload.proxy_env,
        timeout: payload.timeout,
        connect_timeout: payload.connect_timeout,
        read_timeout: payload.read_timeout,
        max_items: payload.max_items,
        max_retries: payload.max_retries,
        respect_robots: payload.respect_robots,
        fetch_full_text: false
      };
    }
    async function testSourceDraft() {
      if (sourceTesting.value) return;
      sourceTesting.value = true;
      sourceDraftTested.value = false;
      try {
        const response = await api.post("/foreign/sources/test", sourceTestPayload());
        sourceTestResult.value = response.data;
        sourceDraftTested.value = Boolean(response.data?.success);
        if (!response.data?.success) ElMessage.warning("RSS 测试存在失败项，请检查配置");
        else ElMessage.success("RSS 连通性测试通过");
      } catch (err) {
        sourceTestResult.value = null;
        ElMessage.error(err?.response?.data?.detail || "外网源连通性测试失败");
      } finally {
        sourceTesting.value = false;
      }
    }
    async function saveSource() {
      if (sourceSaving.value || !sourceDraftTested.value) return;
      sourceSaving.value = true;
      try {
        const payload = sourcePayload();
        if (editingSourceId.value) {
          const { key: _key, ...updatePayload } = payload;
          await api.patch(`/foreign/sources/${editingSourceId.value}`, updatePayload);
        } else await api.post("/foreign/sources", payload);
        ElMessage.success("外网数据源已保存");
        sourceEditorVisible.value = false;
        await loadSourcesView();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网数据源保存失败");
      } finally {
        sourceSaving.value = false;
      }
    }
    async function testSource(row) {
      sourceTesting.value = true;
      try {
        const response = await api.post("/foreign/sources/test", { source_id: row.id, fetch_full_text: false });
        sourceTestResult.value = response.data;
        ElMessage[response.data?.success ? "success" : "warning"](response.data?.success ? "RSS 连通性测试通过" : "RSS 测试存在失败项");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网源测试失败");
      } finally {
        sourceTesting.value = false;
      }
    }
    async function loadSourceRuns(row) {
      try {
        selectedSourceRuns.value = { name: row.name, items: (await api.get(`/foreign/sources/${row.id}/runs`, { params: { size: 50 } })).data.items || [] };
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网采集历史加载失败");
      }
    }
    async function toggleSource(row) {
      if (sourceBusyId.value) return;
      sourceBusyId.value = row.id;
      try {
        await api.patch(`/foreign/sources/${row.id}`, { enabled: !row.enabled, schedule_enabled: false, fetch_full_text: false });
        await loadSourcesView();
        ElMessage.success("外网数据源状态已更新");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "数据源状态更新失败");
      } finally {
        sourceBusyId.value = null;
      }
    }
    async function analyzeRisk(row) {
      if (!canAnalyzeRisk) {
        ElMessage.warning("当前账号没有外网规则分析权限");
        return;
      }
      try {
        await api.post(`/foreign/risk/${row.foreign_opinion_id}/analyze`, {});
        ElMessage.success("外网规则分析完成");
        await loadRisk();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "外网规则分析失败");
      }
    }
    async function collectNow() {
      if (collecting.value) return;
      collecting.value = true;
      try {
        const { data } = await api.post("/foreign/collect", { source_ids: null });
        const result = await pollTask(data.task_id);
        if (result.status === "success") {
          ElMessage.success(`外网采集完成：新增 ${result.result?.created || 0} 条`);
          await loadOpinions();
          await loadRuns();
        } else ElMessage.error(result.error || "外网采集失败");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || err?.message || "外网采集失败");
      } finally {
        collecting.value = false;
      }
    }
    watch(
      () => route.query.tab,
      (value) => {
        const tab = normalizeTab(value);
        activeTab.value = tab;
        loadTab(tab);
      },
      { immediate: true }
    );
    return (_ctx, _cache) => {
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          _cache[64] || (_cache[64] = createBaseVNode("div", null, [
            createBaseVNode("h2", null, "外网舆情"),
            createBaseVNode("p", null, "独立采集、去重和展示链路；不会进入国内舆情、风险、事件或告警。")
          ], -1)),
          createBaseVNode("button", {
            class: "btn btn-primary",
            disabled: collecting.value,
            onClick: collectNow
          }, toDisplayString(collecting.value ? "采集中..." : "采集外网 RSS"), 9, _hoisted_3)
        ]),
        createBaseVNode("div", _hoisted_4, [
          (openBlock(), createElementBlock(Fragment, null, renderList(tabs, (tab) => {
            return createBaseVNode("button", {
              key: tab.value,
              class: normalizeClass(["tab", { active: activeTab.value === tab.value }]),
              onClick: ($event) => switchTab(tab.value)
            }, toDisplayString(tab.label), 11, _hoisted_5);
          }), 64))
        ]),
        activeTab.value === "dashboard" ? (openBlock(), createElementBlock("section", _hoisted_6, [
          createBaseVNode("div", _hoisted_7, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadDashboard
            }, "Refresh dashboard"),
            createBaseVNode("label", _hoisted_8, [
              _cache[66] || (_cache[66] = createTextVNode("Window ", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => visualizationDays.value = $event),
                class: "input",
                onChange: loadDashboard
              }, [..._cache[65] || (_cache[65] = [
                createBaseVNode("option", { value: 1 }, "1 day", -1),
                createBaseVNode("option", { value: 7 }, "7 days", -1),
                createBaseVNode("option", { value: 30 }, "30 days", -1),
                createBaseVNode("option", { value: 90 }, "90 days", -1)
              ])], 544), [
                [
                  vModelSelect,
                  visualizationDays.value,
                  void 0,
                  { number: true }
                ]
              ])
            ]),
            _cache[67] || (_cache[67] = createBaseVNode("span", { class: "scope-badge" }, "Foreign data only · UTC", -1)),
            visualizationStale.value ? (openBlock(), createElementBlock("span", _hoisted_9, "Stale data")) : createCommentVNode("", true)
          ]),
          visualizationError.value ? (openBlock(), createElementBlock("div", _hoisted_10, [
            createBaseVNode("span", null, toDisplayString(visualizationError.value), 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadDashboard
            }, "Retry")
          ])) : dashboardSummary.value ? (openBlock(), createElementBlock("div", _hoisted_11, [
            createBaseVNode("div", _hoisted_12, [
              createBaseVNode("div", _hoisted_13, [
                _cache[68] || (_cache[68] = createBaseVNode("span", null, "Articles total", -1)),
                createBaseVNode("strong", null, toDisplayString(dashboardSummary.value.articles.total), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.articles.window_new) + " in window", 1)
              ]),
              createBaseVNode("div", _hoisted_14, [
                _cache[69] || (_cache[69] = createBaseVNode("span", null, "Sources", -1)),
                createBaseVNode("strong", null, toDisplayString(dashboardSummary.value.articles.sources), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.articles.languages?.en || 0) + " EN / " + toDisplayString(dashboardSummary.value.articles.languages?.zh || 0) + " ZH", 1)
              ]),
              createBaseVNode("div", _hoisted_15, [
                _cache[70] || (_cache[70] = createBaseVNode("span", null, "Risk completed", -1)),
                createBaseVNode("strong", null, toDisplayString(dashboardSummary.value.risk.completed), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.risk.failed) + " failed · " + toDisplayString(dashboardSummary.value.risk.pending) + " pending", 1)
              ]),
              createBaseVNode("div", _hoisted_16, [
                _cache[71] || (_cache[71] = createBaseVNode("span", null, "Confirmed events", -1)),
                createBaseVNode("strong", null, toDisplayString(dashboardSummary.value.events.confirmed), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.events.candidate) + " candidates", 1)
              ]),
              createBaseVNode("div", _hoisted_17, [
                _cache[72] || (_cache[72] = createBaseVNode("span", null, "Foreign alerts", -1)),
                createBaseVNode("strong", null, toDisplayString(dashboardSummary.value.alerts.total), 1),
                createBaseVNode("small", null, toDisplayString(dashboardSummary.value.alerts.by_status?.triggered || 0) + " triggered", 1)
              ])
            ]),
            createBaseVNode("div", _hoisted_18, [
              createBaseVNode("article", _hoisted_19, [
                _cache[73] || (_cache[73] = createBaseVNode("h3", null, "Risk distribution", -1)),
                (openBlock(true), createElementBlock(Fragment, null, renderList(dashboardRisk.value?.risk_levels, (count, label) => {
                  return openBlock(), createElementBlock("div", {
                    key: label,
                    class: "distribution-row"
                  }, [
                    createBaseVNode("span", null, toDisplayString(label), 1),
                    createBaseVNode("strong", null, toDisplayString(count), 1)
                  ]);
                }), 128)),
                !dashboardRisk.value || !Object.keys(dashboardRisk.value.risk_levels || {}).length ? (openBlock(), createElementBlock("p", _hoisted_20, "No completed risk results")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_21, [
                _cache[74] || (_cache[74] = createBaseVNode("h3", null, "Event states", -1)),
                (openBlock(true), createElementBlock(Fragment, null, renderList(dashboardEvents.value?.formal_events, (count, label) => {
                  return openBlock(), createElementBlock("div", {
                    key: label,
                    class: "distribution-row"
                  }, [
                    createBaseVNode("span", null, toDisplayString(label), 1),
                    createBaseVNode("strong", null, toDisplayString(count), 1)
                  ]);
                }), 128)),
                !dashboardEvents.value || !Object.keys(dashboardEvents.value.formal_events || {}).length ? (openBlock(), createElementBlock("p", _hoisted_22, "No foreign events")) : createCommentVNode("", true)
              ]),
              createBaseVNode("article", _hoisted_23, [
                _cache[77] || (_cache[77] = createBaseVNode("h3", null, "Collection status", -1)),
                dashboardSummary.value.collection.latest ? (openBlock(), createElementBlock("div", _hoisted_24, [
                  _cache[75] || (_cache[75] = createBaseVNode("span", null, "Latest", -1)),
                  createBaseVNode("strong", null, toDisplayString(dashboardSummary.value.collection.latest.status), 1)
                ])) : createCommentVNode("", true),
                createBaseVNode("div", _hoisted_25, [
                  _cache[76] || (_cache[76] = createBaseVNode("span", null, "Success / failed", -1)),
                  createBaseVNode("strong", null, toDisplayString(dashboardSummary.value.collection.success) + " / " + toDisplayString(dashboardSummary.value.collection.failed), 1)
                ]),
                !dashboardSummary.value.collection.latest ? (openBlock(), createElementBlock("p", _hoisted_26, "No foreign collection runs")) : createCommentVNode("", true)
              ])
            ]),
            createBaseVNode("div", _hoisted_27, [
              _cache[79] || (_cache[79] = createBaseVNode("h3", null, "Daily trend", -1)),
              createBaseVNode("div", _hoisted_28, [
                createBaseVNode("table", null, [
                  _cache[78] || (_cache[78] = createBaseVNode("thead", null, [
                    createBaseVNode("tr", null, [
                      createBaseVNode("th", null, "Date"),
                      createBaseVNode("th", null, "Articles"),
                      createBaseVNode("th", null, "Risk completed"),
                      createBaseVNode("th", null, "Risk failed"),
                      createBaseVNode("th", null, "Events"),
                      createBaseVNode("th", null, "Alerts")
                    ])
                  ], -1)),
                  createBaseVNode("tbody", null, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(dashboardTrends.value?.items || [], (item) => {
                      return openBlock(), createElementBlock("tr", {
                        key: item.date
                      }, [
                        createBaseVNode("td", null, toDisplayString(item.date), 1),
                        createBaseVNode("td", null, toDisplayString(item.articles), 1),
                        createBaseVNode("td", null, toDisplayString(item.risk_completed), 1),
                        createBaseVNode("td", null, toDisplayString(item.risk_failed), 1),
                        createBaseVNode("td", null, toDisplayString(item.events), 1),
                        createBaseVNode("td", null, toDisplayString(item.alerts), 1)
                      ]);
                    }), 128))
                  ])
                ])
              ])
            ]),
            createBaseVNode("div", _hoisted_29, "Data range: " + toDisplayString(formatTime(dashboardSummary.value.window_start)) + " - " + toDisplayString(formatTime(dashboardSummary.value.window_end)) + " · Updated: " + toDisplayString(formatTime(dashboardSummary.value.data_as_of)), 1)
          ])) : (openBlock(), createElementBlock("div", _hoisted_30, "Loading foreign dashboard..."))
        ])) : activeTab.value === "hotwords" ? (openBlock(), createElementBlock("section", _hoisted_31, [
          createBaseVNode("div", _hoisted_32, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadHotwords
            }, "Refresh hotwords"),
            createBaseVNode("label", _hoisted_33, [
              _cache[81] || (_cache[81] = createTextVNode("Window ", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => visualizationDays.value = $event),
                class: "input",
                onChange: loadHotwords
              }, [..._cache[80] || (_cache[80] = [
                createBaseVNode("option", { value: 1 }, "1 day", -1),
                createBaseVNode("option", { value: 7 }, "7 days", -1),
                createBaseVNode("option", { value: 30 }, "30 days", -1),
                createBaseVNode("option", { value: 90 }, "90 days", -1)
              ])], 544), [
                [
                  vModelSelect,
                  visualizationDays.value,
                  void 0,
                  { number: true }
                ]
              ])
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => hotwordLanguage.value = $event),
              class: "input",
              onChange: loadHotwords
            }, [..._cache[82] || (_cache[82] = [
              createBaseVNode("option", { value: "" }, "All languages", -1),
              createBaseVNode("option", { value: "en" }, "English", -1),
              createBaseVNode("option", { value: "zh" }, "Chinese", -1),
              createBaseVNode("option", { value: "mixed" }, "Mixed", -1)
            ])], 544), [
              [vModelSelect, hotwordLanguage.value]
            ]),
            _cache[83] || (_cache[83] = createBaseVNode("span", { class: "scope-badge" }, "Foreign text only · China/Chinese/中国 excluded", -1)),
            visualizationStale.value ? (openBlock(), createElementBlock("span", _hoisted_34, "Stale data")) : createCommentVNode("", true)
          ]),
          visualizationError.value ? (openBlock(), createElementBlock("div", _hoisted_35, [
            createTextVNode(toDisplayString(visualizationError.value) + " ", 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadHotwords
            }, "Retry")
          ])) : hotwordItems.value.length ? (openBlock(), createElementBlock("div", _hoisted_36, [
            createBaseVNode("div", _hoisted_37, [
              createBaseVNode("table", null, [
                _cache[84] || (_cache[84] = createBaseVNode("thead", null, [
                  createBaseVNode("tr", null, [
                    createBaseVNode("th", null, "Word"),
                    createBaseVNode("th", null, "Language"),
                    createBaseVNode("th", null, "Count"),
                    createBaseVNode("th", null, "Trend"),
                    createBaseVNode("th", null, "Sources")
                  ])
                ], -1)),
                createBaseVNode("tbody", null, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(hotwordItems.value, (item) => {
                    return openBlock(), createElementBlock("tr", {
                      key: `${item.language}-${item.word}`
                    }, [
                      createBaseVNode("td", _hoisted_38, toDisplayString(item.word), 1),
                      createBaseVNode("td", null, toDisplayString(item.language), 1),
                      createBaseVNode("td", null, toDisplayString(item.count), 1),
                      createBaseVNode("td", null, [
                        createBaseVNode("span", {
                          class: normalizeClass(["status", { on: item.trend === "up" }])
                        }, toDisplayString(item.trend), 3)
                      ]),
                      createBaseVNode("td", null, toDisplayString(item.sources.join(", ") || "-"), 1)
                    ]);
                  }), 128))
                ])
              ])
            ]),
            createBaseVNode("div", _hoisted_39, [
              _cache[86] || (_cache[86] = createBaseVNode("h3", null, "Hotword trend", -1)),
              createBaseVNode("div", _hoisted_40, [
                createBaseVNode("table", null, [
                  _cache[85] || (_cache[85] = createBaseVNode("thead", null, [
                    createBaseVNode("tr", null, [
                      createBaseVNode("th", null, "Date"),
                      createBaseVNode("th", null, "Words")
                    ])
                  ], -1)),
                  createBaseVNode("tbody", null, [
                    (openBlock(true), createElementBlock(Fragment, null, renderList(hotwordTrendItems.value, (item) => {
                      return openBlock(), createElementBlock("tr", {
                        key: item.date
                      }, [
                        createBaseVNode("td", null, toDisplayString(item.date), 1),
                        createBaseVNode("td", null, toDisplayString(Object.entries(item.words).map(([word, count]) => `${word}: ${count}`).join(" · ") || "-"), 1)
                      ]);
                    }), 128))
                  ])
                ])
              ])
            ]),
            createBaseVNode("div", _hoisted_41, "Data range: " + toDisplayString(formatTime(hotwordMeta.value.window_start)) + " - " + toDisplayString(formatTime(hotwordMeta.value.window_end)) + " · Updated: " + toDisplayString(formatTime(hotwordMeta.value.data_as_of)), 1)
          ])) : (openBlock(), createElementBlock("div", _hoisted_42, "No foreign hotwords in this window."))
        ])) : activeTab.value === "sources" ? (openBlock(), createElementBlock("section", _hoisted_43, [
          createBaseVNode("div", _hoisted_44, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadSourcesView
            }, "Refresh sources"),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => sourceFilters.q = $event),
              class: "input",
              placeholder: "搜索来源",
              onKeyup: _cache[4] || (_cache[4] = withKeys(($event) => {
                sourcePage.value = 1;
                loadSourcesView();
              }, ["enter"]))
            }, null, 544), [
              [vModelText, sourceFilters.q]
            ]),
            _cache[87] || (_cache[87] = createBaseVNode("span", { class: "scope-badge" }, "Source and language distribution · no map", -1)),
            visualizationStale.value ? (openBlock(), createElementBlock("span", _hoisted_45, "Stale data")) : createCommentVNode("", true)
          ]),
          visualizationError.value ? (openBlock(), createElementBlock("div", _hoisted_46, [
            createTextVNode(toDisplayString(visualizationError.value) + " ", 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadSourcesView
            }, "Retry")
          ])) : sourceDistribution.value ? (openBlock(), createElementBlock("div", _hoisted_47, [
            createBaseVNode("div", _hoisted_48, [
              createBaseVNode("article", _hoisted_49, [
                _cache[88] || (_cache[88] = createBaseVNode("h3", null, "Language distribution", -1)),
                (openBlock(true), createElementBlock(Fragment, null, renderList(languageDistribution.value?.items || [], (item) => {
                  return openBlock(), createElementBlock("div", {
                    key: item.language,
                    class: "distribution-row"
                  }, [
                    createBaseVNode("span", null, toDisplayString(item.language), 1),
                    createBaseVNode("strong", null, toDisplayString(item.count), 1)
                  ]);
                }), 128))
              ]),
              createBaseVNode("article", _hoisted_50, [
                _cache[89] || (_cache[89] = createBaseVNode("h3", null, "Foreign sources", -1)),
                (openBlock(true), createElementBlock(Fragment, null, renderList(sourceDistribution.value.items, (item) => {
                  return openBlock(), createElementBlock("div", {
                    key: item.source_key,
                    class: "distribution-row"
                  }, [
                    createBaseVNode("span", null, [
                      createTextVNode(toDisplayString(item.source), 1),
                      createBaseVNode("small", null, toDisplayString(item.source_key), 1)
                    ]),
                    createBaseVNode("strong", null, toDisplayString(item.opinion_count), 1)
                  ]);
                }), 128)),
                !sourceDistribution.value.items.length ? (openBlock(), createElementBlock("p", _hoisted_51, "No foreign source data")) : createCommentVNode("", true)
              ])
            ]),
            createBaseVNode("div", _hoisted_52, [
              createBaseVNode("table", null, [
                _cache[90] || (_cache[90] = createBaseVNode("thead", null, [
                  createBaseVNode("tr", null, [
                    createBaseVNode("th", null, "Source"),
                    createBaseVNode("th", null, "Language"),
                    createBaseVNode("th", null, "Articles"),
                    createBaseVNode("th", null, "Risk complete"),
                    createBaseVNode("th", null, "Confirmed events"),
                    createBaseVNode("th", null, "Alerts"),
                    createBaseVNode("th", null, "Latest run"),
                    createBaseVNode("th", null, "Failed runs"),
                    createBaseVNode("th", null, "Trend")
                  ])
                ], -1)),
                createBaseVNode("tbody", null, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(sourceDistribution.value.items, (item) => {
                    return openBlock(), createElementBlock("tr", {
                      key: `detail-${item.source_key}`
                    }, [
                      createBaseVNode("td", null, [
                        createTextVNode(toDisplayString(item.source), 1),
                        createBaseVNode("div", _hoisted_53, toDisplayString(item.source_key), 1)
                      ]),
                      createBaseVNode("td", null, toDisplayString(Object.entries(item.language).map(([key, value]) => `${key}: ${value}`).join(" · ") || "-"), 1),
                      createBaseVNode("td", null, toDisplayString(item.opinion_count), 1),
                      createBaseVNode("td", null, toDisplayString(item.risk_completed_count), 1),
                      createBaseVNode("td", null, toDisplayString(item.confirmed_event_count), 1),
                      createBaseVNode("td", null, toDisplayString(item.alert_count), 1),
                      createBaseVNode("td", null, toDisplayString(item.latest_run?.status || "-"), 1),
                      createBaseVNode("td", null, toDisplayString(item.failed_count), 1),
                      createBaseVNode("td", null, toDisplayString(Object.entries(item.trend || {}).map(([date, count]) => `${date}: ${count}`).join(" · ") || "-"), 1)
                    ]);
                  }), 128))
                ])
              ])
            ]),
            createBaseVNode("div", _hoisted_54, "Data range: " + toDisplayString(formatTime(sourceDistribution.value.window_start)) + " - " + toDisplayString(formatTime(sourceDistribution.value.window_end)) + " · Updated: " + toDisplayString(formatTime(sourceDistribution.value.data_as_of)), 1)
          ])) : (openBlock(), createElementBlock("div", _hoisted_55, "Loading foreign source distribution...")),
          _cache[95] || (_cache[95] = createBaseVNode("div", { class: "source-management-note" }, "Source management remains below. Visualization data never changes source status.", -1)),
          _cache[96] || (_cache[96] = createBaseVNode("div", { class: "source-note" }, "First-party foreign sources are disabled by default. Proxy configuration is not displayed.", -1)),
          createBaseVNode("div", _hoisted_56, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: beginNewSource
            }, "新增外网源"),
            sourceEditorVisible.value ? (openBlock(), createElementBlock("button", {
              key: 0,
              class: "btn btn-secondary",
              onClick: _cache[5] || (_cache[5] = ($event) => sourceEditorVisible.value = false)
            }, "取消编辑")) : createCommentVNode("", true)
          ]),
          sourceEditorVisible.value ? (openBlock(), createElementBlock("div", _hoisted_57, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => sourceDraft.name = $event),
              class: "input",
              placeholder: "来源名称"
            }, null, 512), [
              [vModelText, sourceDraft.name]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => sourceDraft.key = $event),
              class: "input",
              disabled: !!editingSourceId.value,
              placeholder: "来源 key"
            }, null, 8, _hoisted_58), [
              [vModelText, sourceDraft.key]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => sourceDraft.feedsText = $event),
              class: "input source-feed-input",
              placeholder: "RSS 地址，多个地址用换行分隔"
            }, null, 512), [
              [vModelText, sourceDraft.feedsText]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => sourceDraft.proxyEnv = $event),
              class: "input",
              placeholder: "代理环境变量名"
            }, null, 512), [
              [vModelText, sourceDraft.proxyEnv]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => sourceDraft.timeout = $event),
              class: "input number-input",
              type: "number",
              min: "1",
              max: "120",
              placeholder: "超时"
            }, null, 512), [
              [
                vModelText,
                sourceDraft.timeout,
                void 0,
                { number: true }
              ]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => sourceDraft.maxRetries = $event),
              class: "input number-input",
              type: "number",
              min: "0",
              max: "5",
              placeholder: "重试"
            }, null, 512), [
              [
                vModelText,
                sourceDraft.maxRetries,
                void 0,
                { number: true }
              ]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => sourceDraft.maxItems = $event),
              class: "input number-input",
              type: "number",
              min: "1",
              max: "500",
              placeholder: "最大条数"
            }, null, 512), [
              [
                vModelText,
                sourceDraft.maxItems,
                void 0,
                { number: true }
              ]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => sourceDraft.requestInterval = $event),
              class: "input number-input",
              type: "number",
              min: "0",
              max: "60",
              step: "0.1",
              placeholder: "请求间隔秒"
            }, null, 512), [
              [
                vModelText,
                sourceDraft.requestInterval,
                void 0,
                { number: true }
              ]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => sourceDraft.scheduleInterval = $event),
              class: "input number-input",
              type: "number",
              min: "5",
              max: "10080",
              placeholder: "采集间隔分钟"
            }, null, 512), [
              [
                vModelText,
                sourceDraft.scheduleInterval,
                void 0,
                { number: true }
              ]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => sourceDraft.maxContentLength = $event),
              class: "input number-input",
              type: "number",
              min: "100",
              max: "1000000",
              placeholder: "正文上限"
            }, null, 512), [
              [
                vModelText,
                sourceDraft.maxContentLength,
                void 0,
                { number: true }
              ]
            ]),
            createBaseVNode("label", _hoisted_59, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => sourceDraft.respectRobots = $event),
                type: "checkbox"
              }, null, 512), [
                [vModelCheckbox, sourceDraft.respectRobots]
              ]),
              _cache[91] || (_cache[91] = createTextVNode(" robots 检查", -1))
            ]),
            _cache[92] || (_cache[92] = createBaseVNode("label", { class: "muted" }, [
              createBaseVNode("input", {
                type: "checkbox",
                disabled: ""
              }),
              createTextVNode(" 正文抓取（本阶段关闭）")
            ], -1)),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: sourceTesting.value,
              onClick: testSourceDraft
            }, toDisplayString(sourceTesting.value ? "测试中..." : "连通性测试"), 9, _hoisted_60),
            createBaseVNode("button", {
              class: "btn btn-primary",
              disabled: sourceSaving.value || !sourceDraftTested.value,
              onClick: saveSource
            }, toDisplayString(sourceSaving.value ? "保存中..." : "保存"), 9, _hoisted_61),
            !sourceDraftTested.value ? (openBlock(), createElementBlock("span", _hoisted_62, "保存前必须完成当前配置的 RSS 测试")) : createCommentVNode("", true)
          ])) : createCommentVNode("", true),
          sourceTestResult.value ? (openBlock(), createElementBlock("div", _hoisted_63, [
            createBaseVNode("strong", null, toDisplayString(sourceTestResult.value.success ? "RSS 测试通过" : "RSS 测试存在失败项"), 1),
            (openBlock(true), createElementBlock(Fragment, null, renderList(sourceTestResult.value.feeds || [], (feed) => {
              return openBlock(), createElementBlock("span", {
                key: feed.feed || feed.label
              }, toDisplayString(feed.feed || feed.label) + ": HTTP " + toDisplayString(feed.http_status ?? "-") + " · XML " + toDisplayString(feed.xml_parsed ? "是" : "否") + " · 原始 " + toDisplayString(feed.raw_count) + " · 命中 " + toDisplayString(feed.matched_count) + " · 失败 " + toDisplayString(feed.failure_count ?? 0), 1);
            }), 128))
          ])) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_64, [
            createBaseVNode("table", null, [
              _cache[94] || (_cache[94] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "Source"),
                  createBaseVNode("th", null, "RSS"),
                  createBaseVNode("th", null, "Collector"),
                  createBaseVNode("th", null, "Status"),
                  createBaseVNode("th", null, "Schedule"),
                  createBaseVNode("th", null, "Interval"),
                  createBaseVNode("th", null, "Proxy"),
                  createBaseVNode("th", null, "Actions")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(sources.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", null, [
                      createBaseVNode("strong", null, toDisplayString(row.name), 1),
                      createBaseVNode("div", _hoisted_65, toDisplayString(row.key), 1)
                    ]),
                    createBaseVNode("td", null, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(row.feeds, (feed) => {
                        return openBlock(), createElementBlock("div", {
                          key: feed,
                          class: "feed"
                        }, toDisplayString(feed), 1);
                      }), 128))
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("div", _hoisted_66, toDisplayString(row.class_path || "foreign_rss"), 1)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("button", {
                        class: normalizeClass(["status-toggle", { on: row.enabled }]),
                        disabled: sourceBusyId.value === row.id,
                        onClick: ($event) => toggleSource(row)
                      }, toDisplayString(row.enabled ? "Enabled" : "Disabled"), 11, _hoisted_67)
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.schedule_enabled ? "Automatic" : "Manual"), 1),
                    createBaseVNode("td", null, toDisplayString(row.schedule_interval_minutes || "-") + " min", 1),
                    createBaseVNode("td", null, [
                      createTextVNode(toDisplayString(row.proxy_env || "Direct"), 1),
                      row.proxy_configured ? (openBlock(), createElementBlock("span", _hoisted_68, "configured")) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("td", _hoisted_69, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        onClick: ($event) => editSource(row)
                      }, "编辑", 8, _hoisted_70),
                      createBaseVNode("button", {
                        class: "link-btn",
                        onClick: ($event) => testSource(row)
                      }, "测试", 8, _hoisted_71),
                      createBaseVNode("button", {
                        class: "link-btn",
                        onClick: ($event) => loadSourceRuns(row)
                      }, "历史", 8, _hoisted_72)
                    ])
                  ]);
                }), 128)),
                !sources.value.length ? (openBlock(), createElementBlock("tr", _hoisted_73, [..._cache[93] || (_cache[93] = [
                  createBaseVNode("td", {
                    colspan: "8",
                    class: "empty"
                  }, "No foreign sources", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ]),
          sourceTotal.value > sourceSize ? (openBlock(), createElementBlock("div", _hoisted_74, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: sourcePage.value <= 1,
              onClick: _cache[17] || (_cache[17] = ($event) => {
                sourcePage.value--;
                loadSourcesView();
              })
            }, "上一页", 8, _hoisted_75),
            createBaseVNode("span", null, "第 " + toDisplayString(sourcePage.value) + " 页 / 共 " + toDisplayString(sourceTotal.value) + " 条", 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: sourcePage.value * sourceSize >= sourceTotal.value,
              onClick: _cache[18] || (_cache[18] = ($event) => {
                sourcePage.value++;
                loadSourcesView();
              })
            }, "下一页", 8, _hoisted_76)
          ])) : createCommentVNode("", true),
          selectedSourceRuns.value ? (openBlock(), createElementBlock("div", _hoisted_77, [
            createBaseVNode("h4", null, toDisplayString(selectedSourceRuns.value.name) + " 采集历史", 1),
            (openBlock(true), createElementBlock(Fragment, null, renderList(selectedSourceRuns.value.items, (run) => {
              return openBlock(), createElementBlock("div", {
                key: run.id,
                class: "history-row"
              }, [
                createBaseVNode("span", null, toDisplayString(formatTime(run.start_time)), 1),
                createBaseVNode("span", null, toDisplayString(run.status), 1),
                createBaseVNode("span", null, "抓取 " + toDisplayString(run.fetched_raw) + " · 新增 " + toDisplayString(run.created) + " · 去重 " + toDisplayString(run.duplicate), 1),
                createBaseVNode("span", _hoisted_78, toDisplayString(run.error_msg || ""), 1)
              ]);
            }), 128)),
            !selectedSourceRuns.value.items.length ? (openBlock(), createElementBlock("p", _hoisted_79, "暂无采集历史")) : createCommentVNode("", true)
          ])) : createCommentVNode("", true)
        ])) : createCommentVNode("", true),
        activeTab.value === "opinions" ? (openBlock(), createElementBlock("section", _hoisted_80, [
          createBaseVNode("div", _hoisted_81, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[19] || (_cache[19] = ($event) => opinionFilters.q = $event),
              class: "input",
              placeholder: "搜索标题、摘要、正文",
              onKeyup: withKeys(loadOpinions, ["enter"])
            }, null, 544), [
              [vModelText, opinionFilters.q]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[20] || (_cache[20] = ($event) => opinionFilters.source = $event),
              class: "input",
              onChange: loadOpinions
            }, [
              _cache[97] || (_cache[97] = createBaseVNode("option", { value: "" }, "全部来源", -1)),
              (openBlock(true), createElementBlock(Fragment, null, renderList(opinionSources.value, (source) => {
                return openBlock(), createElementBlock("option", {
                  key: source,
                  value: source
                }, toDisplayString(source), 9, _hoisted_82);
              }), 128))
            ], 544), [
              [vModelSelect, opinionFilters.source]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[21] || (_cache[21] = ($event) => opinionFilters.keyword = $event),
              class: "input",
              placeholder: "命中关键词",
              onKeyup: withKeys(loadOpinions, ["enter"])
            }, null, 544), [
              [vModelText, opinionFilters.keyword]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[22] || (_cache[22] = ($event) => opinionFilters.date_from = $event),
              class: "input date-input",
              type: "date",
              title: "发布时间起始",
              onChange: loadOpinions
            }, null, 544), [
              [vModelText, opinionFilters.date_from]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[23] || (_cache[23] = ($event) => opinionFilters.date_to = $event),
              class: "input date-input",
              type: "date",
              title: "发布时间截止",
              onChange: loadOpinions
            }, null, 544), [
              [vModelText, opinionFilters.date_to]
            ]),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadOpinions
            }, "搜索")
          ]),
          createBaseVNode("div", _hoisted_83, [
            createBaseVNode("table", null, [
              _cache[99] || (_cache[99] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "标题"),
                  createBaseVNode("th", null, "来源快照"),
                  createBaseVNode("th", null, "命中关键词"),
                  createBaseVNode("th", null, "发布时间"),
                  createBaseVNode("th", null, "采集时间")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(opinions.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id,
                    onClick: ($event) => openOpinion(row.id)
                  }, [
                    createBaseVNode("td", _hoisted_85, toDisplayString(row.title || "无标题"), 1),
                    createBaseVNode("td", null, toDisplayString(row.source_name_snapshot), 1),
                    createBaseVNode("td", null, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(row.matched_keywords, (word) => {
                        return openBlock(), createElementBlock("span", {
                          key: word,
                          class: "tag"
                        }, toDisplayString(word), 1);
                      }), 128))
                    ]),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.published_at)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.collected_at)), 1)
                  ], 8, _hoisted_84);
                }), 128)),
                !opinions.value.length ? (openBlock(), createElementBlock("tr", _hoisted_86, [..._cache[98] || (_cache[98] = [
                  createBaseVNode("td", {
                    colspan: "5",
                    class: "empty"
                  }, "暂无外网舆情", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ]),
          opinionTotal.value > opinionSize ? (openBlock(), createElementBlock("div", _hoisted_87, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: opinionPage.value <= 1,
              onClick: _cache[24] || (_cache[24] = ($event) => {
                opinionPage.value--;
                loadOpinions();
              })
            }, "上一页", 8, _hoisted_88),
            createBaseVNode("span", null, "第 " + toDisplayString(opinionPage.value) + " 页 / 共 " + toDisplayString(opinionTotal.value) + " 条", 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: opinionPage.value * opinionSize >= opinionTotal.value,
              onClick: _cache[25] || (_cache[25] = ($event) => {
                opinionPage.value++;
                loadOpinions();
              })
            }, "下一页", 8, _hoisted_89)
          ])) : createCommentVNode("", true)
        ])) : activeTab.value === "risk" ? (openBlock(), createElementBlock("section", _hoisted_90, [
          createBaseVNode("div", _hoisted_91, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[26] || (_cache[26] = ($event) => riskFilters.q = $event),
              class: "input",
              placeholder: "搜索标题、摘要、正文",
              onKeyup: withKeys(loadRisk, ["enter"])
            }, null, 544), [
              [vModelText, riskFilters.q]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[27] || (_cache[27] = ($event) => riskFilters.source = $event),
              class: "input",
              onChange: loadRisk
            }, [
              _cache[100] || (_cache[100] = createBaseVNode("option", { value: "" }, "全部来源", -1)),
              (openBlock(true), createElementBlock(Fragment, null, renderList(opinionSources.value, (source) => {
                return openBlock(), createElementBlock("option", {
                  key: source,
                  value: source
                }, toDisplayString(source), 9, _hoisted_92);
              }), 128))
            ], 544), [
              [vModelSelect, riskFilters.source]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[28] || (_cache[28] = ($event) => riskFilters.language = $event),
              class: "input",
              onChange: loadRisk
            }, [..._cache[101] || (_cache[101] = [
              createStaticVNode('<option value="" data-v-3e574cc8>全部语言</option><option value="zh" data-v-3e574cc8>中文</option><option value="en" data-v-3e574cc8>英文</option><option value="mixed" data-v-3e574cc8>中英混合</option><option value="unknown" data-v-3e574cc8>未知</option>', 5)
            ])], 544), [
              [vModelSelect, riskFilters.language]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[29] || (_cache[29] = ($event) => riskFilters.risk_level = $event),
              class: "input",
              onChange: loadRisk
            }, [..._cache[102] || (_cache[102] = [
              createStaticVNode('<option value="" data-v-3e574cc8>全部风险等级</option><option value="high" data-v-3e574cc8>高</option><option value="medium" data-v-3e574cc8>中</option><option value="low" data-v-3e574cc8>低</option><option value="unknown" data-v-3e574cc8>未知</option>', 5)
            ])], 544), [
              [vModelSelect, riskFilters.risk_level]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[30] || (_cache[30] = ($event) => riskFilters.analysis_status = $event),
              class: "input",
              onChange: loadRisk
            }, [..._cache[103] || (_cache[103] = [
              createBaseVNode("option", { value: "" }, "全部分析状态", -1),
              createBaseVNode("option", { value: "completed" }, "完成", -1),
              createBaseVNode("option", { value: "skipped" }, "跳过", -1),
              createBaseVNode("option", { value: "failed" }, "失败", -1)
            ])], 544), [
              [vModelSelect, riskFilters.analysis_status]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[31] || (_cache[31] = ($event) => riskFilters.date_from = $event),
              class: "input date-input",
              type: "date",
              title: "发布时间起始",
              onChange: loadRisk
            }, null, 544), [
              [vModelText, riskFilters.date_from]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[32] || (_cache[32] = ($event) => riskFilters.date_to = $event),
              class: "input date-input",
              type: "date",
              title: "发布时间截止",
              onChange: loadRisk
            }, null, 544), [
              [vModelText, riskFilters.date_to]
            ]),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadRisk
            }, "搜索"),
            _cache[104] || (_cache[104] = createBaseVNode("span", { class: "muted" }, "规则优先；AI 人工复核当前未启用", -1))
          ]),
          createBaseVNode("div", _hoisted_93, [
            createBaseVNode("table", null, [
              _cache[106] || (_cache[106] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "标题"),
                  createBaseVNode("th", null, "来源"),
                  createBaseVNode("th", null, "发布时间"),
                  createBaseVNode("th", null, "风险分"),
                  createBaseVNode("th", null, "等级"),
                  createBaseVNode("th", null, "情感"),
                  createBaseVNode("th", null, "风险类别"),
                  createBaseVNode("th", null, "命中风险词"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "分析时间"),
                  createBaseVNode("th", null, "版本"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(risks.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id,
                    onClick: ($event) => openOpinion(row.foreign_opinion_id)
                  }, [
                    createBaseVNode("td", _hoisted_95, toDisplayString(row.opinion.title || "无标题"), 1),
                    createBaseVNode("td", null, toDisplayString(row.opinion.source_name_snapshot), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.opinion.published_at)), 1),
                    createBaseVNode("td", null, toDisplayString(row.risk_score === null ? "-" : row.risk_score), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.risk_level === "high" }])
                      }, toDisplayString(row.risk_level), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.sentiment), 1),
                    createBaseVNode("td", null, toDisplayString(row.risk_category), 1),
                    createBaseVNode("td", null, [
                      (openBlock(true), createElementBlock(Fragment, null, renderList(row.matched_terms, (term) => {
                        return openBlock(), createElementBlock("span", {
                          key: `${row.id}-${term.word}`,
                          class: "tag"
                        }, toDisplayString(term.word), 1);
                      }), 128)),
                      !row.matched_terms.length ? (openBlock(), createElementBlock("span", _hoisted_96, "无")) : createCommentVNode("", true)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.analysis_status === "completed" }])
                      }, toDisplayString(row.analysis_status), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.analyzed_at)), 1),
                    createBaseVNode("td", null, toDisplayString(row.model_version), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        disabled: !unref(canAnalyzeRisk),
                        onClick: withModifiers(($event) => analyzeRisk(row), ["stop"])
                      }, "重新分析", 8, _hoisted_97)
                    ])
                  ], 8, _hoisted_94);
                }), 128)),
                !risks.value.length ? (openBlock(), createElementBlock("tr", _hoisted_98, [..._cache[105] || (_cache[105] = [
                  createBaseVNode("td", {
                    colspan: "12",
                    class: "empty"
                  }, "暂无外网风险分析结果，请手动触发规则分析", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ]),
          riskTotal.value > riskSize ? (openBlock(), createElementBlock("div", _hoisted_99, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: riskPage.value <= 1,
              onClick: _cache[33] || (_cache[33] = ($event) => {
                riskPage.value--;
                loadRisk();
              })
            }, "上一页", 8, _hoisted_100),
            createBaseVNode("span", null, "第 " + toDisplayString(riskPage.value) + " 页 / 共 " + toDisplayString(riskTotal.value) + " 条", 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: riskPage.value * riskSize >= riskTotal.value,
              onClick: _cache[34] || (_cache[34] = ($event) => {
                riskPage.value++;
                loadRisk();
              })
            }, "下一页", 8, _hoisted_101)
          ])) : createCommentVNode("", true)
        ])) : activeTab.value === "events" ? (openBlock(), createElementBlock("section", _hoisted_102, [
          createBaseVNode("div", _hoisted_103, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadEvents
            }, "刷新外网事件"),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: rebuildingEvents.value,
              onClick: rebuildEvents
            }, toDisplayString(rebuildingEvents.value ? "重建中..." : "候选 Dry-Run"), 9, _hoisted_104),
            _cache[107] || (_cache[107] = createBaseVNode("span", { class: "muted" }, "候选只进入外网事件表，必须人工确认后才形成正式事件", -1))
          ]),
          eventLoadError.value ? (openBlock(), createElementBlock("div", _hoisted_105, [
            createBaseVNode("span", null, "外网事件加载失败：" + toDisplayString(eventLoadError.value), 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadEvents
            }, "重试")
          ])) : createCommentVNode("", true),
          eventRunFailures.value.length ? (openBlock(), createElementBlock("div", _hoisted_106, [
            _cache[109] || (_cache[109] = createBaseVNode("strong", null, "外网事件运行失败", -1)),
            (openBlock(true), createElementBlock(Fragment, null, renderList(eventRunFailures.value, (run) => {
              return openBlock(), createElementBlock("div", {
                key: run.id,
                class: "event-failure-row"
              }, [
                _cache[108] || (_cache[108] = createBaseVNode("span", { class: "status failed" }, "failed", -1)),
                createBaseVNode("span", null, toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
                createBaseVNode("span", null, toDisplayString(run.error_message || "运行失败，未提供错误摘要"), 1)
              ]);
            }), 128))
          ])) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_107, [
            createBaseVNode("button", {
              class: normalizeClass(["tab", { active: eventSection.value === "candidates" }]),
              onClick: _cache[35] || (_cache[35] = ($event) => eventSection.value = "candidates")
            }, "事件候选", 2),
            createBaseVNode("button", {
              class: normalizeClass(["tab", { active: eventSection.value === "confirmed" }]),
              onClick: _cache[36] || (_cache[36] = ($event) => eventSection.value = "confirmed")
            }, "外网事件", 2)
          ]),
          eventSection.value === "candidates" ? (openBlock(), createElementBlock("div", _hoisted_108, [
            createBaseVNode("table", null, [
              _cache[111] || (_cache[111] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "标题"),
                  createBaseVNode("th", null, "语言"),
                  createBaseVNode("th", null, "置信度"),
                  createBaseVNode("th", null, "文章数"),
                  createBaseVNode("th", null, "来源数"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(eventCandidates.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", _hoisted_109, toDisplayString(row.title || "无标题"), 1),
                    createBaseVNode("td", null, toDisplayString(row.language), 1),
                    createBaseVNode("td", null, toDisplayString(Math.round(row.confidence * 100)) + "%", 1),
                    createBaseVNode("td", null, toDisplayString(row.opinion_count), 1),
                    createBaseVNode("td", null, toDisplayString(row.source_count), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.candidate_status === "converted" }])
                      }, toDisplayString(row.candidate_status), 3)
                    ]),
                    createBaseVNode("td", _hoisted_110, [
                      row.candidate_status === "candidate" ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "link-btn",
                        disabled: !unref(canConfirmEvents) || eventActionKey.value === `candidate-confirm-${row.id}`,
                        onClick: ($event) => confirmCandidate(row)
                      }, "确认", 8, _hoisted_111)) : createCommentVNode("", true),
                      row.candidate_status === "candidate" ? (openBlock(), createElementBlock("button", {
                        key: 1,
                        class: "link-btn danger",
                        disabled: !unref(canConfirmEvents) || eventActionKey.value === `candidate-reject-${row.id}`,
                        onClick: ($event) => rejectCandidate(row)
                      }, "拒绝", 8, _hoisted_112)) : createCommentVNode("", true)
                    ])
                  ]);
                }), 128)),
                !eventCandidates.value.length ? (openBlock(), createElementBlock("tr", _hoisted_113, [..._cache[110] || (_cache[110] = [
                  createBaseVNode("td", {
                    colspan: "7",
                    class: "empty"
                  }, "暂无外网事件候选", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])) : (openBlock(), createElementBlock("div", _hoisted_114, [
            createBaseVNode("table", null, [
              _cache[113] || (_cache[113] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "标题"),
                  createBaseVNode("th", null, "语言"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "风险快照"),
                  createBaseVNode("th", null, "热度"),
                  createBaseVNode("th", null, "文章数"),
                  createBaseVNode("th", null, "来源数"),
                  createBaseVNode("th", null, "置信度"),
                  createBaseVNode("th", null, "首次出现"),
                  createBaseVNode("th", null, "最近出现"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(foreignEvents.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id,
                    onClick: ($event) => loadEventDetail(row.id)
                  }, [
                    createBaseVNode("td", _hoisted_116, toDisplayString(row.title || "无标题"), 1),
                    createBaseVNode("td", null, toDisplayString(row.language), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.event_status === "monitoring", failed: row.event_status === "failed" }])
                      }, toDisplayString(row.event_status), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.risk_level), 1),
                    createBaseVNode("td", null, toDisplayString(row.heat_score ?? "-"), 1),
                    createBaseVNode("td", null, toDisplayString(row.opinion_count), 1),
                    createBaseVNode("td", null, toDisplayString(row.source_count), 1),
                    createBaseVNode("td", null, toDisplayString(Math.round(row.confidence * 100)) + "%", 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.first_seen_at)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.last_seen_at)), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        disabled: !unref(canChangeEventStatus) || eventActionKey.value === `event-close-${row.id}`,
                        onClick: withModifiers(($event) => closeEvent(row), ["stop"])
                      }, "关闭", 8, _hoisted_117),
                      createBaseVNode("button", {
                        class: "link-btn",
                        disabled: !unref(canChangeEventStatus) || eventActionKey.value === `event-archive-${row.id}`,
                        onClick: withModifiers(($event) => archiveEvent(row), ["stop"])
                      }, "归档", 8, _hoisted_118)
                    ])
                  ], 8, _hoisted_115);
                }), 128)),
                !foreignEvents.value.length ? (openBlock(), createElementBlock("tr", _hoisted_119, [..._cache[112] || (_cache[112] = [
                  createBaseVNode("td", {
                    colspan: "11",
                    class: "empty"
                  }, "暂无已确认外网事件", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])),
          selectedForeignEvent.value ? (openBlock(), createElementBlock("article", _hoisted_120, [
            createBaseVNode("div", _hoisted_121, [
              createBaseVNode("h3", null, toDisplayString(selectedForeignEvent.value.title), 1),
              createBaseVNode("div", _hoisted_122, [
                createBaseVNode("button", {
                  class: "link-btn",
                  disabled: !unref(canChangeEventStatus) || eventActionKey.value,
                  onClick: _cache[37] || (_cache[37] = ($event) => closeEvent(selectedForeignEvent.value))
                }, "关闭事件", 8, _hoisted_123),
                createBaseVNode("button", {
                  class: "link-btn",
                  disabled: !unref(canMergeEvents) || eventActionKey.value,
                  onClick: _cache[38] || (_cache[38] = ($event) => mergeEvent(selectedForeignEvent.value))
                }, "合并", 8, _hoisted_124),
                createBaseVNode("button", {
                  class: "link-btn",
                  disabled: !unref(canSplitEvents) || eventActionKey.value,
                  onClick: _cache[39] || (_cache[39] = ($event) => splitEvent(selectedForeignEvent.value))
                }, "拆分", 8, _hoisted_125),
                createBaseVNode("button", {
                  class: "link-btn",
                  onClick: _cache[40] || (_cache[40] = ($event) => selectedForeignEvent.value = null)
                }, "关闭详情")
              ])
            ]),
            createBaseVNode("p", _hoisted_126, toDisplayString(selectedForeignEvent.value.language) + " · " + toDisplayString(selectedForeignEvent.value.event_status) + " · " + toDisplayString(selectedForeignEvent.value.opinion_count) + " 篇文章", 1),
            createBaseVNode("div", _hoisted_127, [
              createBaseVNode("span", null, "热度：" + toDisplayString(selectedForeignEvent.value.heat_score ?? "-"), 1),
              createBaseVNode("span", null, "首次出现：" + toDisplayString(formatTime(selectedForeignEvent.value.first_seen_at)), 1),
              createBaseVNode("span", null, "最近出现：" + toDisplayString(formatTime(selectedForeignEvent.value.last_seen_at)), 1)
            ]),
            createBaseVNode("p", null, toDisplayString(selectedForeignEvent.value.summary || "暂无摘要"), 1),
            (openBlock(true), createElementBlock(Fragment, null, renderList(selectedForeignEvent.value.opinions, (opinion) => {
              return openBlock(), createElementBlock("div", {
                key: opinion.id,
                class: "event-opinion"
              }, [
                createBaseVNode("strong", null, toDisplayString(opinion.title), 1),
                createBaseVNode("span", _hoisted_128, toDisplayString(opinion.source_name_snapshot) + " · " + toDisplayString(formatTime(opinion.published_at)), 1),
                createBaseVNode("a", {
                  href: opinion.url,
                  target: "_blank",
                  rel: "noreferrer",
                  class: "original"
                }, "原文", 8, _hoisted_129)
              ]);
            }), 128))
          ])) : createCommentVNode("", true)
        ])) : activeTab.value === "alerts" ? (openBlock(), createElementBlock("section", _hoisted_130, [
          createBaseVNode("div", _hoisted_131, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadAlerts
            }, "刷新外网告警"),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: alertEvaluating.value || !unref(canEvaluateAlerts),
              onClick: evaluateAlerts
            }, toDisplayString(alertEvaluating.value ? "评估中..." : "手动 Dry-Run"), 9, _hoisted_132),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[41] || (_cache[41] = ($event) => alertFilters.status = $event),
              class: "input",
              onChange: loadAlerts
            }, [..._cache[114] || (_cache[114] = [
              createStaticVNode('<option value="" data-v-3e574cc8>全部状态</option><option value="triggered" data-v-3e574cc8>待处理</option><option value="acknowledged" data-v-3e574cc8>已确认</option><option value="resolved" data-v-3e574cc8>已解决</option><option value="suppressed" data-v-3e574cc8>已抑制</option><option value="failed" data-v-3e574cc8>失败</option>', 6)
            ])], 544), [
              [vModelSelect, alertFilters.status]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[42] || (_cache[42] = ($event) => alertFilters.severity = $event),
              class: "input",
              onChange: loadAlerts
            }, [..._cache[115] || (_cache[115] = [
              createStaticVNode('<option value="" data-v-3e574cc8>全部严重度</option><option value="low" data-v-3e574cc8>低</option><option value="medium" data-v-3e574cc8>中</option><option value="high" data-v-3e574cc8>高</option><option value="critical" data-v-3e574cc8>紧急</option>', 5)
            ])], 544), [
              [vModelSelect, alertFilters.severity]
            ]),
            _cache[116] || (_cache[116] = createBaseVNode("span", { class: "muted" }, "告警评估默认关闭 · 外部通知默认关闭 · 当前仅保存站内记录", -1))
          ]),
          _cache[127] || (_cache[127] = createBaseVNode("div", { class: "alert-scope-note" }, " 外网告警只读取外网风险和 confirmed 外网事件；不会进入国内告警、Dashboard、地图、热词或事件链路。 ", -1)),
          alertLoadError.value ? (openBlock(), createElementBlock("div", _hoisted_133, [
            createBaseVNode("span", null, "外网告警加载失败：" + toDisplayString(alertLoadError.value), 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadAlerts
            }, "重试")
          ])) : createCommentVNode("", true),
          alertRunFailures.value.length ? (openBlock(), createElementBlock("div", _hoisted_134, [
            _cache[118] || (_cache[118] = createBaseVNode("strong", null, "外网告警评估失败", -1)),
            (openBlock(true), createElementBlock(Fragment, null, renderList(alertRunFailures.value, (run) => {
              return openBlock(), createElementBlock("div", {
                key: run.id,
                class: "alert-failure-row"
              }, [
                _cache[117] || (_cache[117] = createBaseVNode("span", { class: "status failed" }, "failed", -1)),
                createBaseVNode("span", null, toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
                createBaseVNode("span", null, toDisplayString(run.error_message || "评估失败，未提供错误摘要"), 1)
              ]);
            }), 128))
          ])) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_135, [
            createBaseVNode("table", null, [
              _cache[120] || (_cache[120] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "告警标题"),
                  createBaseVNode("th", null, "严重度"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "触发规则"),
                  createBaseVNode("th", null, "关联文章"),
                  createBaseVNode("th", null, "关联事件"),
                  createBaseVNode("th", null, "风险分/等级"),
                  createBaseVNode("th", null, "触发时间"),
                  createBaseVNode("th", null, "确认时间"),
                  createBaseVNode("th", null, "解决时间"),
                  createBaseVNode("th", null, "抑制"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(foreignAlerts.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", _hoisted_136, [
                      createTextVNode(toDisplayString(row.title || "无标题告警"), 1),
                      createBaseVNode("div", _hoisted_137, toDisplayString(row.message), 1)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { failed: row.severity === "critical" || row.severity === "high" }])
                      }, toDisplayString(row.severity), 3)
                    ]),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.status === "acknowledged" || row.status === "resolved", failed: row.status === "failed" || row.status === "suppressed" }])
                      }, toDisplayString(row.status), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.rule_snapshot?.name || "规则 #" + row.rule_id), 1),
                    createBaseVNode("td", null, toDisplayString(row.opinion_title_snapshot || (row.foreign_opinion_id ? "#" + row.foreign_opinion_id : "-")), 1),
                    createBaseVNode("td", null, toDisplayString(row.event_title_snapshot || (row.foreign_event_id ? "#" + row.foreign_event_id : "-")), 1),
                    createBaseVNode("td", null, toDisplayString(row.risk_score === null ? "-" : row.risk_score) + " / " + toDisplayString(row.risk_level), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.triggered_at)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.acknowledged_at)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.resolved_at)), 1),
                    createBaseVNode("td", null, toDisplayString(row.suppressed_at ? formatTime(row.suppressed_at) : "-"), 1),
                    createBaseVNode("td", _hoisted_138, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        onClick: withModifiers(($event) => loadAlertActions(row), ["stop"])
                      }, "处置历史", 8, _hoisted_139),
                      row.status === "triggered" ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        class: "link-btn",
                        disabled: !unref(canAcknowledgeAlerts) || alertActionBusyId.value === row.id,
                        onClick: withModifiers(($event) => handleForeignAlert(row, "acknowledge"), ["stop"])
                      }, "确认", 8, _hoisted_140)) : createCommentVNode("", true),
                      row.status === "triggered" || row.status === "acknowledged" ? (openBlock(), createElementBlock("button", {
                        key: 1,
                        class: "link-btn",
                        disabled: !unref(canResolveAlerts) || alertActionBusyId.value === row.id,
                        onClick: withModifiers(($event) => handleForeignAlert(row, "resolve"), ["stop"])
                      }, "解决", 8, _hoisted_141)) : createCommentVNode("", true),
                      row.status === "triggered" || row.status === "acknowledged" ? (openBlock(), createElementBlock("button", {
                        key: 2,
                        class: "link-btn danger",
                        disabled: !unref(canSuppressAlerts) || alertActionBusyId.value === row.id,
                        onClick: withModifiers(($event) => handleForeignAlert(row, "suppress"), ["stop"])
                      }, "抑制", 8, _hoisted_142)) : createCommentVNode("", true)
                    ])
                  ]);
                }), 128)),
                !foreignAlerts.value.length ? (openBlock(), createElementBlock("tr", _hoisted_143, [..._cache[119] || (_cache[119] = [
                  createBaseVNode("td", {
                    colspan: "12",
                    class: "empty"
                  }, "暂无外网告警记录", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ]),
          selectedForeignAlert.value ? (openBlock(), createElementBlock("article", _hoisted_144, [
            createBaseVNode("div", _hoisted_145, [
              createBaseVNode("h3", null, toDisplayString(selectedForeignAlert.value.title || "外网告警详情"), 1),
              createBaseVNode("button", {
                class: "link-btn",
                onClick: _cache[43] || (_cache[43] = ($event) => selectedForeignAlert.value = null)
              }, "关闭")
            ]),
            createBaseVNode("p", _hoisted_146, "当前状态：" + toDisplayString(selectedForeignAlert.value.status) + " · 告警 #" + toDisplayString(selectedForeignAlert.value.id), 1),
            alertActionsLoading.value ? (openBlock(), createElementBlock("div", _hoisted_147, "处置历史加载中...")) : !alertActions.value.length ? (openBlock(), createElementBlock("div", _hoisted_148, "暂无处置历史")) : (openBlock(), createElementBlock("div", _hoisted_149, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(alertActions.value, (action) => {
                return openBlock(), createElementBlock("div", {
                  key: action.id,
                  class: "alert-action-row"
                }, [
                  createBaseVNode("strong", null, toDisplayString(actionLabel(action.action_type)), 1),
                  createBaseVNode("span", null, toDisplayString(action.previous_status) + " → " + toDisplayString(action.new_status), 1),
                  createBaseVNode("span", null, toDisplayString(action.note), 1),
                  createBaseVNode("span", _hoisted_150, "操作人 #" + toDisplayString(action.actor_id ?? "-") + " · " + toDisplayString(formatTime(action.created_at)), 1)
                ]);
              }), 128))
            ]))
          ])) : createCommentVNode("", true),
          createBaseVNode("section", _hoisted_151, [
            createBaseVNode("div", { class: "analysis-heading" }, [
              _cache[121] || (_cache[121] = createBaseVNode("h3", null, "外网告警规则", -1)),
              createBaseVNode("button", {
                class: "btn btn-secondary",
                onClick: loadAlertRules
              }, "刷新规则")
            ]),
            _cache[126] || (_cache[126] = createBaseVNode("p", { class: "muted" }, "新规则默认停用；本页面不创建业务阈值，也不会启用自动评估。", -1)),
            createBaseVNode("div", _hoisted_152, [
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[44] || (_cache[44] = ($event) => alertRuleDraft.name = $event),
                class: "input",
                placeholder: "规则名称"
              }, null, 512), [
                [vModelText, alertRuleDraft.name]
              ]),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[45] || (_cache[45] = ($event) => alertRuleDraft.rule_type = $event),
                class: "input"
              }, [..._cache[122] || (_cache[122] = [
                createStaticVNode('<option value="risk_score" data-v-3e574cc8>风险分</option><option value="risk_level" data-v-3e574cc8>风险等级</option><option value="risk_category" data-v-3e574cc8>风险类别</option><option value="confirmed_event" data-v-3e574cc8>确认事件</option><option value="keyword_combo" data-v-3e574cc8>关键词组合</option>', 5)
              ])], 512), [
                [vModelSelect, alertRuleDraft.rule_type]
              ]),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[46] || (_cache[46] = ($event) => alertRuleDraft.conditionsText = $event),
                class: "input",
                placeholder: '条件 JSON，例如 {"threshold":80}'
              }, null, 512), [
                [vModelText, alertRuleDraft.conditionsText]
              ]),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[47] || (_cache[47] = ($event) => alertRuleDraft.severity = $event),
                class: "input"
              }, [..._cache[123] || (_cache[123] = [
                createBaseVNode("option", { value: "low" }, "低", -1),
                createBaseVNode("option", { value: "medium" }, "中", -1),
                createBaseVNode("option", { value: "high" }, "高", -1),
                createBaseVNode("option", { value: "critical" }, "紧急", -1)
              ])], 512), [
                [vModelSelect, alertRuleDraft.severity]
              ]),
              withDirectives(createBaseVNode("input", {
                "onUpdate:modelValue": _cache[48] || (_cache[48] = ($event) => alertRuleDraft.cooldown_seconds = $event),
                class: "input number-input",
                type: "number",
                min: "0",
                placeholder: "冷却秒数"
              }, null, 512), [
                [
                  vModelText,
                  alertRuleDraft.cooldown_seconds,
                  void 0,
                  { number: true }
                ]
              ]),
              createBaseVNode("button", {
                class: "btn btn-primary",
                disabled: alertRuleSaving.value,
                onClick: createAlertRule
              }, toDisplayString(alertRuleSaving.value ? "保存中..." : "新增停用规则"), 9, _hoisted_153)
            ]),
            createBaseVNode("div", _hoisted_154, [
              createBaseVNode("table", null, [
                _cache[125] || (_cache[125] = createBaseVNode("thead", null, [
                  createBaseVNode("tr", null, [
                    createBaseVNode("th", null, "名称"),
                    createBaseVNode("th", null, "类型"),
                    createBaseVNode("th", null, "条件"),
                    createBaseVNode("th", null, "严重度"),
                    createBaseVNode("th", null, "冷却"),
                    createBaseVNode("th", null, "状态"),
                    createBaseVNode("th", null, "操作")
                  ])
                ], -1)),
                createBaseVNode("tbody", null, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(alertRules.value, (rule) => {
                    return openBlock(), createElementBlock("tr", {
                      key: rule.id
                    }, [
                      createBaseVNode("td", null, toDisplayString(rule.name), 1),
                      createBaseVNode("td", null, toDisplayString(rule.rule_type), 1),
                      createBaseVNode("td", null, toDisplayString(JSON.stringify(rule.conditions)), 1),
                      createBaseVNode("td", null, toDisplayString(rule.severity), 1),
                      createBaseVNode("td", null, toDisplayString(rule.cooldown_seconds) + " 秒", 1),
                      createBaseVNode("td", null, toDisplayString(rule.is_enabled ? "启用" : "停用"), 1),
                      createBaseVNode("td", _hoisted_155, [
                        rule.is_enabled ? (openBlock(), createElementBlock("button", {
                          key: 0,
                          class: "link-btn",
                          disabled: alertRuleBusyId.value === rule.id,
                          onClick: ($event) => disableAlertRule(rule)
                        }, "停用", 8, _hoisted_156)) : (openBlock(), createElementBlock("button", {
                          key: 1,
                          class: "link-btn",
                          disabled: alertRuleBusyId.value === rule.id || !unref(canEnableAlertRules),
                          onClick: ($event) => enableAlertRule(rule)
                        }, "启用", 8, _hoisted_157)),
                        !rule.is_enabled ? (openBlock(), createElementBlock("button", {
                          key: 2,
                          class: "link-btn danger",
                          disabled: alertRuleBusyId.value === rule.id,
                          onClick: ($event) => deleteAlertRule(rule)
                        }, "删除", 8, _hoisted_158)) : createCommentVNode("", true)
                      ])
                    ]);
                  }), 128)),
                  !alertRules.value.length ? (openBlock(), createElementBlock("tr", _hoisted_159, [..._cache[124] || (_cache[124] = [
                    createBaseVNode("td", {
                      colspan: "7",
                      class: "empty"
                    }, "暂无外网告警规则", -1)
                  ])])) : createCommentVNode("", true)
                ])
              ])
            ])
          ])
        ])) : activeTab.value === "keywords" ? (openBlock(), createElementBlock("section", _hoisted_160, [
          createBaseVNode("div", _hoisted_161, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[49] || (_cache[49] = ($event) => keywordFilters.q = $event),
              class: "input",
              placeholder: "Search keywords",
              onKeyup: withKeys(loadKeywords, ["enter"])
            }, null, 544), [
              [vModelText, keywordFilters.q]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[50] || (_cache[50] = ($event) => keywordFilters.category = $event),
              class: "input",
              onChange: loadKeywords
            }, [
              _cache[128] || (_cache[128] = createBaseVNode("option", { value: "" }, "All topics", -1)),
              (openBlock(true), createElementBlock(Fragment, null, renderList(keywordCategories.value, (item) => {
                return openBlock(), createElementBlock("option", {
                  key: item,
                  value: item
                }, toDisplayString(item), 9, _hoisted_162);
              }), 128))
            ], 544), [
              [vModelSelect, keywordFilters.category]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[51] || (_cache[51] = ($event) => keywordFilters.type = $event),
              class: "input",
              onChange: loadKeywords
            }, [..._cache[129] || (_cache[129] = [
              createBaseVNode("option", { value: "" }, "All types", -1),
              createBaseVNode("option", { value: "monitoring" }, "Monitoring", -1),
              createBaseVNode("option", { value: "sensitive" }, "Sensitive", -1)
            ])], 544), [
              [vModelSelect, keywordFilters.type]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[52] || (_cache[52] = ($event) => keywordFilters.enabled = $event),
              class: "input",
              onChange: loadKeywords
            }, [..._cache[130] || (_cache[130] = [
              createBaseVNode("option", { value: "" }, "All states", -1),
              createBaseVNode("option", { value: "true" }, "Enabled", -1),
              createBaseVNode("option", { value: "false" }, "Disabled", -1)
            ])], 544), [
              [vModelSelect, keywordFilters.enabled]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[53] || (_cache[53] = ($event) => keywordDraft.category = $event),
              class: "input",
              placeholder: "Topic"
            }, null, 512), [
              [vModelText, keywordDraft.category]
            ]),
            withDirectives(createBaseVNode("select", {
              "onUpdate:modelValue": _cache[54] || (_cache[54] = ($event) => keywordDraft.type = $event),
              class: "input"
            }, [..._cache[131] || (_cache[131] = [
              createBaseVNode("option", { value: "monitoring" }, "Monitoring", -1),
              createBaseVNode("option", { value: "sensitive" }, "Sensitive", -1)
            ])], 512), [
              [vModelSelect, keywordDraft.type]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[55] || (_cache[55] = ($event) => keywordDraft.weight = $event),
              class: "input number-input",
              type: "number",
              min: "0",
              max: "100",
              placeholder: "Weight"
            }, null, 512), [
              [
                vModelText,
                keywordDraft.weight,
                void 0,
                { number: true }
              ]
            ]),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[56] || (_cache[56] = ($event) => keywordDraft.word = $event),
              class: "input",
              placeholder: "新增外网关键词",
              onKeyup: withKeys(createKeyword, ["enter"])
            }, null, 544), [
              [vModelText, keywordDraft.word]
            ]),
            createBaseVNode("button", {
              class: "btn btn-primary",
              onClick: createKeyword
            }, "新增关键词"),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadKeywords
            }, "刷新")
          ]),
          createBaseVNode("div", _hoisted_163, [
            createBaseVNode("table", null, [
              _cache[133] || (_cache[133] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "关键词"),
                  createBaseVNode("th", null, "主题"),
                  createBaseVNode("th", null, "类型"),
                  createBaseVNode("th", null, "来源"),
                  createBaseVNode("th", null, "权重"),
                  createBaseVNode("th", null, "风险权重"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "操作")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(keywords.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", null, toDisplayString(row.word), 1),
                    createBaseVNode("td", null, toDisplayString(row.category), 1),
                    createBaseVNode("td", null, toDisplayString(row.type || "monitoring"), 1),
                    createBaseVNode("td", null, toDisplayString(row.source || "system"), 1),
                    createBaseVNode("td", null, toDisplayString(row.weight ?? 10), 1),
                    createBaseVNode("td", null, toDisplayString(row.severity_weight ?? 0), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.is_enabled }])
                      }, toDisplayString(row.is_enabled ? "启用" : "停用"), 3)
                    ]),
                    createBaseVNode("td", _hoisted_164, [
                      createBaseVNode("button", {
                        class: "link-btn",
                        disabled: keywordSaving.value,
                        onClick: ($event) => toggleKeyword(row)
                      }, toDisplayString(row.is_enabled ? "停用" : "启用"), 9, _hoisted_165),
                      createBaseVNode("button", {
                        class: "link-btn",
                        onClick: ($event) => editKeyword(row)
                      }, "编辑", 8, _hoisted_166),
                      createBaseVNode("button", {
                        class: "link-btn danger",
                        onClick: ($event) => removeKeyword(row.id)
                      }, "删除", 8, _hoisted_167)
                    ])
                  ]);
                }), 128)),
                !keywords.value.length ? (openBlock(), createElementBlock("tr", _hoisted_168, [..._cache[132] || (_cache[132] = [
                  createBaseVNode("td", {
                    colspan: "8",
                    class: "empty"
                  }, "暂无外网关键词", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ]),
          createBaseVNode("div", _hoisted_169, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: keywordSaving.value,
              onClick: _cache[57] || (_cache[57] = ($event) => bulkToggleKeywords(true))
            }, "批量启用全部当前结果", 8, _hoisted_170),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: keywordSaving.value,
              onClick: _cache[58] || (_cache[58] = ($event) => bulkToggleKeywords(false))
            }, "批量停用全部当前结果", 8, _hoisted_171)
          ]),
          keywordTotal.value > keywordSize ? (openBlock(), createElementBlock("div", _hoisted_172, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: keywordPage.value <= 1,
              onClick: _cache[59] || (_cache[59] = ($event) => {
                keywordPage.value--;
                loadKeywords();
              })
            }, "上一页", 8, _hoisted_173),
            createBaseVNode("span", null, "第 " + toDisplayString(keywordPage.value) + " 页 / 共 " + toDisplayString(keywordTotal.value) + " 条", 1),
            createBaseVNode("button", {
              class: "btn btn-secondary",
              disabled: keywordPage.value * keywordSize >= keywordTotal.value,
              onClick: _cache[60] || (_cache[60] = ($event) => {
                keywordPage.value++;
                loadKeywords();
              })
            }, "下一页", 8, _hoisted_174)
          ])) : createCommentVNode("", true)
        ])) : activeTab.value === "runs" ? (openBlock(), createElementBlock("section", _hoisted_175, [
          createBaseVNode("div", { class: "toolbar" }, [
            createBaseVNode("button", {
              class: "btn btn-secondary",
              onClick: loadRuns
            }, "刷新日志"),
            _cache[134] || (_cache[134] = createBaseVNode("span", { class: "muted" }, "仅显示 scope=foreign 的采集记录", -1))
          ]),
          createBaseVNode("div", _hoisted_176, [
            createBaseVNode("table", null, [
              _cache[136] || (_cache[136] = createBaseVNode("thead", null, [
                createBaseVNode("tr", null, [
                  createBaseVNode("th", null, "来源"),
                  createBaseVNode("th", null, "开始"),
                  createBaseVNode("th", null, "结束"),
                  createBaseVNode("th", null, "状态"),
                  createBaseVNode("th", null, "抓取"),
                  createBaseVNode("th", null, "命中"),
                  createBaseVNode("th", null, "新增"),
                  createBaseVNode("th", null, "去重"),
                  createBaseVNode("th", null, "代理"),
                  createBaseVNode("th", null, "失败原因")
                ])
              ], -1)),
              createBaseVNode("tbody", null, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(runs.value, (row) => {
                  return openBlock(), createElementBlock("tr", {
                    key: row.id
                  }, [
                    createBaseVNode("td", null, toDisplayString(row.collector_name), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.start_time)), 1),
                    createBaseVNode("td", null, toDisplayString(formatTime(row.end_time)), 1),
                    createBaseVNode("td", null, [
                      createBaseVNode("span", {
                        class: normalizeClass(["status", { on: row.status === "success" }])
                      }, toDisplayString(row.status), 3)
                    ]),
                    createBaseVNode("td", null, toDisplayString(row.fetched_raw), 1),
                    createBaseVNode("td", null, toDisplayString(row.matched), 1),
                    createBaseVNode("td", null, toDisplayString(row.created), 1),
                    createBaseVNode("td", null, toDisplayString(row.duplicate), 1),
                    createBaseVNode("td", null, toDisplayString(row.proxy_used ? "是" : "否"), 1),
                    createBaseVNode("td", _hoisted_177, toDisplayString(row.error_msg || "-"), 1)
                  ]);
                }), 128)),
                !runs.value.length ? (openBlock(), createElementBlock("tr", _hoisted_178, [..._cache[135] || (_cache[135] = [
                  createBaseVNode("td", {
                    colspan: "10",
                    class: "empty"
                  }, "暂无外网采集日志", -1)
                ])])) : createCommentVNode("", true)
              ])
            ])
          ])
        ])) : createCommentVNode("", true),
        selectedOpinion.value ? (openBlock(), createElementBlock("div", {
          key: 9,
          class: "detail-mask",
          onClick: _cache[63] || (_cache[63] = withModifiers(($event) => selectedOpinion.value = null, ["self"]))
        }, [
          createBaseVNode("article", _hoisted_179, [
            createBaseVNode("button", {
              class: "close",
              title: "关闭详情",
              onClick: _cache[61] || (_cache[61] = ($event) => selectedOpinion.value = null)
            }, "×"),
            opinionLoading.value ? (openBlock(), createElementBlock("div", _hoisted_180, "正在加载外网详情...")) : createCommentVNode("", true),
            createBaseVNode("h3", null, toDisplayString(selectedOpinion.value.title), 1),
            createBaseVNode("div", _hoisted_181, toDisplayString(selectedOpinion.value.source_name_snapshot) + " · " + toDisplayString(formatTime(selectedOpinion.value.published_at)) + " · 命中 " + toDisplayString(selectedOpinion.value.matched_keywords.join("、") || "-"), 1),
            createBaseVNode("p", _hoisted_182, toDisplayString(selectedOpinion.value.summary || "暂无摘要"), 1),
            createBaseVNode("p", _hoisted_183, toDisplayString(selectedOpinion.value.content || "暂无正文（正文抓取已关闭）"), 1),
            selectedOpinion.value.url ? (openBlock(), createElementBlock("a", {
              key: 1,
              href: selectedOpinion.value.url,
              target: "_blank",
              rel: "noreferrer",
              class: "original"
            }, "打开原文", 8, _hoisted_184)) : createCommentVNode("", true),
            createBaseVNode("section", _hoisted_185, [
              _cache[137] || (_cache[137] = createBaseVNode("h4", null, "系统规则研判", -1)),
              selectedOpinion.value.rule_result ? (openBlock(), createElementBlock("div", _hoisted_186, [
                createBaseVNode("span", null, "分数 " + toDisplayString(selectedOpinion.value.rule_result.risk_score ?? "-"), 1),
                createBaseVNode("span", null, "等级 " + toDisplayString(selectedOpinion.value.rule_result.risk_level), 1),
                createBaseVNode("span", null, "类别 " + toDisplayString(selectedOpinion.value.rule_result.risk_category), 1),
                createBaseVNode("span", null, "状态 " + toDisplayString(selectedOpinion.value.rule_result.analysis_status), 1)
              ])) : createCommentVNode("", true),
              selectedOpinion.value.rule_result?.matched_terms?.length ? (openBlock(), createElementBlock("p", _hoisted_187, "命中风险词：" + toDisplayString(selectedOpinion.value.rule_result.matched_terms.map((item) => item.word).join("、")), 1)) : createCommentVNode("", true),
              selectedOpinion.value.rule_result ? (openBlock(), createElementBlock("p", _hoisted_188, toDisplayString(selectedOpinion.value.rule_result.explanation || "暂无规则解释"), 1)) : (openBlock(), createElementBlock("p", _hoisted_189, "暂无规则研判结果"))
            ]),
            createBaseVNode("section", _hoisted_190, [
              createBaseVNode("div", _hoisted_191, [
                _cache[138] || (_cache[138] = createBaseVNode("h4", null, "AI 研判报告", -1)),
                createBaseVNode("button", {
                  class: "btn btn-secondary",
                  disabled: aiAnalyzing.value || !unref(canAnalyzeAI),
                  onClick: _cache[62] || (_cache[62] = ($event) => analyzeAI(selectedOpinion.value.id))
                }, toDisplayString(aiAnalyzing.value ? "分析中..." : "人工触发 AI"), 9, _hoisted_192)
              ]),
              selectedOpinion.value.ai_result ? (openBlock(), createElementBlock("div", _hoisted_193, [
                createBaseVNode("span", null, "状态 " + toDisplayString(selectedOpinion.value.ai_result.status), 1),
                createBaseVNode("span", null, "模型 " + toDisplayString(selectedOpinion.value.ai_result.model_version), 1),
                createBaseVNode("span", null, "情感 " + toDisplayString(selectedOpinion.value.ai_result.sentiment), 1),
                createBaseVNode("span", null, "风险 " + toDisplayString(selectedOpinion.value.ai_result.risk_score ?? "-"), 1)
              ])) : createCommentVNode("", true),
              selectedOpinion.value.ai_result?.status === "completed" ? (openBlock(), createElementBlock("p", _hoisted_194, toDisplayString(selectedOpinion.value.ai_result.summary || "暂无 AI 摘要"), 1)) : createCommentVNode("", true),
              selectedOpinion.value.ai_result?.status === "completed" ? (openBlock(), createElementBlock("p", _hoisted_195, "建议：" + toDisplayString(selectedOpinion.value.ai_result.suggestion || "暂无建议"), 1)) : createCommentVNode("", true),
              selectedOpinion.value.ai_result?.status === "failed" ? (openBlock(), createElementBlock("p", _hoisted_196, toDisplayString(selectedOpinion.value.ai_result.error_message || "AI 分析失败"), 1)) : createCommentVNode("", true),
              !selectedOpinion.value.ai_result ? (openBlock(), createElementBlock("p", _hoisted_197, "尚未执行 AI 研判")) : createCommentVNode("", true)
            ]),
            createBaseVNode("section", _hoisted_198, [
              _cache[139] || (_cache[139] = createBaseVNode("h4", null, "分析运行历史", -1)),
              (openBlock(true), createElementBlock(Fragment, null, renderList(selectedOpinion.value.analysis_runs || [], (run) => {
                return openBlock(), createElementBlock("div", {
                  key: run.id,
                  class: "history-row"
                }, [
                  createBaseVNode("span", null, "#" + toDisplayString(run.id), 1),
                  createBaseVNode("span", null, toDisplayString(run.analyzer_type), 1),
                  createBaseVNode("span", null, toDisplayString(run.status), 1),
                  createBaseVNode("span", null, toDisplayString(formatTime(run.finished_at || run.started_at)), 1),
                  createBaseVNode("span", null, toDisplayString(run.error_message || ""), 1)
                ]);
              }), 128)),
              !selectedOpinion.value.analysis_runs?.length ? (openBlock(), createElementBlock("p", _hoisted_199, "暂无运行记录")) : createCommentVNode("", true)
            ])
          ])
        ])) : createCommentVNode("", true)
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const ForeignWorkspace = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-3e574cc8"]]);

export { ForeignWorkspace as default };
