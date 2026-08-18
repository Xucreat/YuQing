import { d as defineComponent, r as ref, A as watch, z as usePermission, C as onMounted, M as onUnmounted, w as withDirectives, c as createElementBlock, a as createBaseVNode, F as Fragment, n as normalizeClass, s as createCommentVNode, m as createVNode, i as renderList, N as vModelSelect, v as vModelText, b as withKeys, H as unref, O as vModelCheckbox, e as createTextVNode, t as toDisplayString, p as withCtx, k as normalizeStyle, P as withModifiers, q as createBlock, f as reactive, j as computed, Q as ElMessageBox, g as api, E as ElMessage, y as resolveComponent, B as resolveDirective, L as useRoute, h as useRouter, o as openBlock, R as CollectMenu, _ as _export_sfc } from './index-DEChr7so.js';
import { O as OpinionDetailModal } from './OpinionDetailModal-uaDd-Ds4.js';
import { B as BatchAIModal, F as ForeignOpinionListView, a as ForeignAIReviewView } from './ForeignOpinionListView-BPi1eoT-.js';
import { s as sentimentPill, a as sentimentText, l as levelPill, b as levelText, r as riskColor, c as statusPill, d as statusText, f as formatTime } from './opinion-Cag9WtuS.js';
import { f as formatAdmissionHits } from './admission-DpEuIHXC.js';
import './ForeignOpinionDetailModal-cL7pHRGV.js';

const _hoisted_1 = { class: "opinions" };
const _hoisted_2 = { class: "page-nav" };
const _hoisted_3 = { class: "head-left" };
const _hoisted_4 = { class: "view-tabs" };
const _hoisted_5 = { class: "scope-switch" };
const _hoisted_6 = { class: "toolbar" };
const _hoisted_7 = { class: "filters" };
const _hoisted_8 = ["value"];
const _hoisted_9 = ["value"];
const _hoisted_10 = { class: "risk-view-switch" };
const _hoisted_11 = { class: "date-range" };
const _hoisted_12 = { class: "search-wrap" };
const _hoisted_13 = {
  key: 2,
  class: "low-value-toggle",
  title: "默认列表隐藏 irrelevant / advertising 等低价值内容；勾选后可查看完整数据（含历史重算标定的低价值条目）"
};
const _hoisted_14 = {
  key: 0,
  class: "batch-bar"
};
const _hoisted_15 = { class: "batch-count" };
const _hoisted_16 = ["disabled"];
const _hoisted_17 = { class: "sent-pop" };
const _hoisted_18 = ["onClick"];
const _hoisted_19 = {
  key: 1,
  class: "run-progress"
};
const _hoisted_20 = { class: "run-progress-head" };
const _hoisted_21 = { class: "progress-track" };
const _hoisted_22 = { class: "run-progress-meta" };
const _hoisted_23 = {
  key: 2,
  class: "run-progress run-failed"
};
const _hoisted_24 = { class: "run-progress-meta" };
const _hoisted_25 = { class: "card table-card" };
const _hoisted_26 = { class: "tbl-scroll" };
const _hoisted_27 = { class: "tbl" };
const _hoisted_28 = {
  key: 0,
  style: { "width": "44px" },
  class: "col-center leading-check"
};
const _hoisted_29 = ["checked", "indeterminate"];
const _hoisted_30 = {
  style: { "width": "110px" },
  class: "col-center"
};
const _hoisted_31 = {
  key: 1,
  style: { "width": "90px" },
  class: "col-center"
};
const _hoisted_32 = ["onClick"];
const _hoisted_33 = {
  key: 0,
  class: "col-center leading-check"
};
const _hoisted_34 = ["checked", "onClick"];
const _hoisted_35 = { class: "leading-id" };
const _hoisted_36 = { class: "leading-title" };
const _hoisted_37 = { class: "t-title" };
const _hoisted_38 = { class: "col-center" };
const _hoisted_39 = { class: "pill pill-blue" };
const _hoisted_40 = { class: "col-center" };
const _hoisted_41 = { class: "admission-summary" };
const _hoisted_42 = { class: "col-center" };
const _hoisted_43 = ["onClick"];
const _hoisted_44 = { class: "sent-pop" };
const _hoisted_45 = ["onClick"];
const _hoisted_46 = { class: "col-center" };
const _hoisted_47 = { class: "col-center" };
const _hoisted_48 = {
  key: 0,
  class: "risk-src-tag"
};
const _hoisted_49 = { class: "col-center" };
const _hoisted_50 = {
  key: 1,
  class: "col-center"
};
const _hoisted_51 = ["onClick"];
const _hoisted_52 = { key: 0 };
const _hoisted_53 = ["colspan"];
const _hoisted_54 = {
  key: 0,
  class: "pager"
};
const _hoisted_55 = {
  key: 1,
  class: "review-view"
};
const _hoisted_56 = { class: "review-filter" };
const _hoisted_57 = {
  key: 0,
  class: "review-batch"
};
const _hoisted_58 = ["disabled"];
const _hoisted_59 = {
  key: 0,
  class: "review-empty"
};
const _hoisted_60 = {
  key: 1,
  class: "card table-card review-table-card"
};
const _hoisted_61 = { class: "tbl-scroll" };
const _hoisted_62 = { class: "tbl review-table" };
const _hoisted_63 = { style: { "width": "44px" } };
const _hoisted_64 = ["checked"];
const _hoisted_65 = ["checked", "onClick"];
const _hoisted_66 = { class: "review-title-cell" };
const _hoisted_67 = ["onClick"];
const _hoisted_68 = { class: "risk-num" };
const _hoisted_69 = { class: "col-center" };
const _hoisted_70 = {
  key: 0,
  class: "pill pill-green"
};
const _hoisted_71 = { key: 1 };
const _hoisted_72 = { class: "col-center" };
const _hoisted_73 = {
  key: 0,
  class: "pill pill-green"
};
const _hoisted_74 = { key: 1 };
const _hoisted_75 = { class: "review-op-cell" };
const _hoisted_76 = ["onClick"];
const _hoisted_77 = ["onClick"];
const _hoisted_78 = { key: 0 };
const _hoisted_79 = {
  key: 2,
  class: "pager"
};
const _hoisted_80 = { class: "modal-card compact-modal" };
const _hoisted_81 = { class: "modal-header" };
const _hoisted_82 = { class: "modal-body" };
const _hoisted_83 = {
  key: 0,
  class: "review-empty"
};
const RISK_VIEW_KEY = "domestic-risk-source";
const reviewsSize = 10;
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Opinions",
  setup(__props) {
    const route = useRoute();
    const router = useRouter();
    const loading = ref(false);
    const rows = ref([]);
    const total = ref(0);
    const page = ref(1);
    const size = ref(20);
    const sourceOptions = ref([]);
    const includeLowValue = ref(false);
    const contentTypeOptions = [
      { value: "complaint", label: "投诉举报" },
      { value: "consultation", label: "咨询求助" },
      { value: "risk_event", label: "风险事件" },
      { value: "public_affairs", label: "公共事务" },
      { value: "news", label: "新闻" },
      { value: "policy", label: "政策政务" }
    ];
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
    const filters = reactive({
      source: "",
      risk_level: "",
      level: "",
      content_type: "",
      relevance: "",
      date_from: "",
      date_to: "",
      keyword: ""
    });
    const ACCEPTED_RISK_VIEWS = ["current", "rule", "ai"];
    function resolveRiskView() {
      const raw = localStorage.getItem(RISK_VIEW_KEY);
      return ACCEPTED_RISK_VIEWS.includes(raw) ? raw : "current";
    }
    const riskView = ref(resolveRiskView());
    function rowUsesAiDisplay(row) {
      return row.current_risk_source === "ai" && row.current_risk_score != null;
    }
    function displayRiskScore(row) {
      if (riskView.value === "rule") return row.risk_score;
      if (riskView.value === "ai") {
        return rowUsesAiDisplay(row) ? row.current_risk_score : row.risk_score;
      }
      return rowUsesAiDisplay(row) ? row.current_risk_score : row.risk_score;
    }
    function showAIBadge(row) {
      return riskView.value === "ai" && rowUsesAiDisplay(row);
    }
    const detailVisible = ref(false);
    const detailId = ref(null);
    const activeView = ref("opinions");
    const scope = ref("domestic");
    const foreignView = ref("list");
    const reviewStatusFilter = ref("pending_review");
    function onScopeChange() {
      if (scope.value === "domestic") activeView.value = "opinions";
      else foreignView.value = "list";
    }
    watch(() => route.query.scope, (val) => {
      if (val === "foreign") scope.value = "foreign";
      else if (val === "domestic") scope.value = "domestic";
    }, { immediate: true });
    const canAnalyze = computed(() => hasPermission("ai:analyze") || hasPermission("domestic:ai:analyze"));
    const canBatchRead = computed(() => hasPermission("domestic:ai:batch:read") || isSuperuser.value);
    const canReviewRead = computed(
      () => hasPermission("ai:review:read") || hasPermission("domestic:events:review:read") || hasPermission("domestic:alerts:review:read") || isSuperuser.value
    );
    const batchDialog = ref(false);
    const batchHistoryDialog = ref(false);
    const batchRuns = ref([]);
    const activeRunId = ref(localStorage.getItem("domestic-ai-active-run") || "");
    const activeRun = ref(null);
    let runPollTimer = null;
    const reviews = ref([]);
    const reviewsTotal = ref(0);
    const reviewsPage = ref(1);
    const reviewsLoading = ref(false);
    const selectedReviewIds = ref(/* @__PURE__ */ new Set());
    const allReviewsSelected = computed(() => reviews.value.length > 0 && selectedReviewIds.value.size === reviews.value.length);
    const { hasPermission, isSuperuser } = usePermission();
    const canEditOpinion = computed(() => hasPermission("opinions:write"));
    const sentimentOptions = [
      { value: "positive", label: "正面" },
      { value: "neutral", label: "中性" },
      { value: "negative", label: "负面" }
    ];
    const popoverRowId = ref(null);
    function toggleSentPop(row) {
      popoverRowId.value = popoverRowId.value === row.id ? null : row.id;
    }
    function closeSentPop() {
      popoverRowId.value = null;
    }
    async function chooseSentiment(row, value) {
      if (!canEditOpinion.value) return;
      closeSentPop();
      if (row.sentiment === value) return;
      const oldVal = row.sentiment;
      row.sentiment = value;
      try {
        await api.patch(`/opinions/${row.id}`, { sentiment: value });
        ElMessage.success("情感已更新");
      } catch (err) {
        row.sentiment = oldVal;
        ElMessage.error(err?.response?.data?.detail || "情感更新失败");
      }
    }
    function onDocClick(e) {
      if (popoverRowId.value == null && !batchPopVisible.value) return;
      const t = e.target;
      if (t && t.closest(".sent-pop")) return;
      closeSentPop();
      batchPopVisible.value = false;
    }
    const canDelete = computed(() => isSuperuser.value);
    const selectedIds = ref(/* @__PURE__ */ new Set());
    const batchPopVisible = ref(false);
    const isAllSelected = computed(
      () => rows.value.length > 0 && selectedIds.value.size === rows.value.length
    );
    const isIndeterminate = computed(
      () => selectedIds.value.size > 0 && selectedIds.value.size < rows.value.length
    );
    const colCount = computed(
      () => 11 + (canEditOpinion.value || canDelete.value ? 1 : 0) + (canDelete.value ? 1 : 0)
    );
    function toggleRow(row) {
      const next = new Set(selectedIds.value);
      if (next.has(row.id)) next.delete(row.id);
      else next.add(row.id);
      selectedIds.value = next;
    }
    function toggleSelectAll() {
      if (isAllSelected.value) selectedIds.value = /* @__PURE__ */ new Set();
      else selectedIds.value = new Set(rows.value.map((r) => r.id));
    }
    function clearSelection() {
      selectedIds.value = /* @__PURE__ */ new Set();
    }
    function toggleBatchPop() {
      batchPopVisible.value = !batchPopVisible.value;
    }
    async function batchSetSentiment(value) {
      if (!canEditOpinion.value || selectedIds.value.size === 0) return;
      batchPopVisible.value = false;
      const ids = [...selectedIds.value];
      const oldMap = {};
      rows.value.forEach((r) => {
        if (ids.includes(r.id) && r.sentiment !== value) {
          oldMap[r.id] = r.sentiment;
          r.sentiment = value;
        }
      });
      try {
        const { data } = await api.patch("/opinions/batch", { ids, sentiment: value });
        ElMessage.success(
          `已更新 ${data.updated} 条，跳过 ${data.skipped} 条` + (data.failed ? `，失败 ${data.failed} 条` : "")
        );
      } catch (err) {
        rows.value.forEach((r) => {
          if (oldMap[r.id] !== void 0) r.sentiment = oldMap[r.id];
        });
        ElMessage.error(err?.response?.data?.detail || "批量修改情感失败");
      } finally {
        clearSelection();
        loadData();
      }
    }
    async function batchDelete() {
      if (!canDelete.value || selectedIds.value.size === 0) return;
      const ids = [...selectedIds.value];
      try {
        await ElMessageBox.confirm(
          `即将删除 ${ids.length} 条舆情
该操作不可恢复`,
          "删除确认",
          { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" }
        );
      } catch {
        return;
      }
      try {
        const { data } = await api.delete("/opinions/batch", { data: { ids } });
        ElMessage.success(
          `已删除 ${data.deleted} 条` + (data.not_found ? `，${data.not_found} 条不存在` : "")
        );
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "批量删除失败");
      } finally {
        clearSelection();
        loadData();
      }
    }
    async function deleteOne(row) {
      if (!canDelete.value) return;
      try {
        await ElMessageBox.confirm(
          "即将删除该条舆情\n该操作不可恢复",
          "删除确认",
          { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" }
        );
      } catch {
        return;
      }
      try {
        await api.delete(`/opinions/${row.id}`);
        ElMessage.success("已删除");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "删除失败");
      } finally {
        const next = new Set(selectedIds.value);
        next.delete(row.id);
        selectedIds.value = next;
        loadData();
      }
    }
    function levelRange(level) {
      if (level === "high") return [70, null];
      if (level === "mid") return [40, 69];
      if (level === "low") return [null, 39];
      return [null, null];
    }
    function relevanceRange(level) {
      if (level === "high") return [60, null];
      if (level === "low") return [40, 59];
      return [null, null];
    }
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
    function admissionSummary(reason) {
      if (!reason || typeof reason !== "object") return "系统默认准入";
      const policy = String(reason.policy || "");
      if (policy === "default_allow_non_weibo") {
        const source = String(reason.source || "");
        return source.includes("政府") || source.includes("政务") ? "政府来源默认准入" : "新闻来源默认准入";
      }
      const parts = [];
      const add = (label, value) => {
        const text = formatAdmissionHits(value, 3);
        if (text) parts.push(`${label}：${text}`);
      };
      add("地域", reason.region_hits);
      add("公共事务", reason.public_hits);
      add("诉求", reason.demand_hits);
      add("风险", reason.risk_hits);
      return parts.length ? parts.join("；") : "系统默认准入";
    }
    async function loadSources() {
      try {
        const { data } = await api.get("/opinions/sources");
        sourceOptions.value = Array.isArray(data) ? data : [];
      } catch {
        sourceOptions.value = [];
      }
    }
    async function loadData() {
      loading.value = true;
      try {
        const params = { page: page.value, size: size.value };
        if (filters.source) params.source = filters.source;
        if (filters.risk_level) params.risk_level = filters.risk_level;
        if (filters.content_type) params.content_type = filters.content_type;
        if (filters.keyword) params.keyword = filters.keyword;
        const [rmin, rmax] = levelRange(filters.level);
        if (rmin != null) params.risk_min = rmin;
        if (rmax != null) params.risk_max = rmax;
        const [relMin, relMax] = relevanceRange(filters.relevance);
        if (relMin != null) params.relevance_min = relMin;
        if (relMax != null) params.relevance_max = relMax;
        if (filters.date_from) params.date_from = filters.date_from;
        if (filters.date_to) params.date_to = filters.date_to;
        if (includeLowValue.value) params.include_low_value = true;
        const { data } = await api.get("/opinions", { params });
        rows.value = data.items;
        total.value = data.total;
        if (rows.value.length === 0 && page.value > 1) {
          page.value -= 1;
          syncUrl();
          return loadData();
        }
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载舆情列表失败");
      } finally {
        loading.value = false;
      }
    }
    function buildQuery() {
      const q = {};
      if (filters.source) q.source = filters.source;
      if (filters.risk_level) q.risk_level = filters.risk_level;
      if (filters.level) q.level = filters.level;
      if (filters.content_type) q.content_type = filters.content_type;
      if (filters.relevance) q.relevance = filters.relevance;
      if (filters.date_from) q.date_from = filters.date_from;
      if (filters.date_to) q.date_to = filters.date_to;
      if (filters.keyword) q.keyword = filters.keyword;
      if (page.value > 1) q.page = String(page.value);
      return q;
    }
    let syncingUrl = false;
    function syncUrl() {
      syncingUrl = true;
      router.replace({ query: buildQuery() }).finally(() => {
        syncingUrl = false;
      });
    }
    function restoreFromQuery() {
      const q = route.query;
      page.value = typeof q.page === "string" && Number(q.page) > 0 ? Number(q.page) : 1;
      filters.source = typeof q.source === "string" ? q.source : "";
      filters.risk_level = typeof q.risk_level === "string" ? q.risk_level : "";
      filters.level = typeof q.level === "string" ? q.level : "";
      filters.content_type = typeof q.content_type === "string" ? q.content_type : "";
      filters.relevance = typeof q.relevance === "string" ? q.relevance : "";
      filters.date_from = typeof q.date_from === "string" ? q.date_from : "";
      filters.date_to = typeof q.date_to === "string" ? q.date_to : "";
      filters.keyword = typeof q.keyword === "string" ? q.keyword : "";
    }
    function handleSearch() {
      page.value = 1;
      loadData();
      syncUrl();
    }
    function handleRefresh() {
      filters.source = "";
      filters.risk_level = "";
      filters.level = "";
      filters.content_type = "";
      filters.relevance = "";
      filters.date_from = "";
      filters.date_to = "";
      filters.keyword = "";
      page.value = 1;
      loadData();
      syncUrl();
    }
    function onPageChange(p) {
      page.value = p;
      loadData();
      syncUrl();
    }
    watch(() => route.query, () => {
      if (syncingUrl) return;
      restoreFromQuery();
      loadData();
    });
    function openDetail(id) {
      detailId.value = id;
      detailVisible.value = true;
    }
    function domesticFiltersSnapshot() {
      const [riskMin, riskMax] = levelRange(filters.level);
      const [relevanceMin, relevanceMax] = relevanceRange(filters.relevance);
      return {
        source: filters.source || void 0,
        risk_level: filters.risk_level || void 0,
        level: filters.level || void 0,
        risk_min: riskMin ?? void 0,
        risk_max: riskMax ?? void 0,
        content_type: filters.content_type || void 0,
        relevance: filters.relevance || void 0,
        relevance_min: relevanceMin ?? void 0,
        relevance_max: relevanceMax ?? void 0,
        keyword: filters.keyword || void 0,
        q: filters.keyword || void 0,
        date_from: filters.date_from || void 0,
        date_to: filters.date_to || void 0,
        include_low_value: includeLowValue.value
      };
    }
    const domesticBatchScopeOptions = [
      { value: "recent", label: "最近采集（最近 N 条）" },
      { value: "filters", label: "当前筛选（国内列表筛选条件）" },
      { value: "time", label: "时间范围" },
      { value: "selected", label: "已选中舆情" }
    ];
    function buildDomesticBatchPayload(form, fullConfirmation) {
      return {
        scope: form.scope,
        recent_n: form.recent_n,
        date_from: form.date_from || void 0,
        date_to: form.date_to || void 0,
        filters: domesticFiltersSnapshot(),
        opinion_ids: form.scope === "selected" ? [...selectedIds.value] : void 0,
        only_unanalyzed: form.only_unanalyzed,
        force: form.force,
        full_confirmation: fullConfirmation
      };
    }
    function onDomesticBatchSubmitted(data) {
      activeRunId.value = data.run_id;
      localStorage.setItem("domestic-ai-active-run", data.run_id);
      batchDialog.value = false;
      ElMessage.success(data.message || "国内 AI 研判任务已提交");
      startRunPolling();
    }
    function clearRunPolling() {
      if (runPollTimer != null) {
        window.clearTimeout(runPollTimer);
        runPollTimer = null;
      }
    }
    async function pollRun() {
      if (!activeRunId.value) return;
      try {
        const { data } = await api.get(`/domestic/ai-analysis/batch/${activeRunId.value}`);
        activeRun.value = data;
        if (["succeeded", "partial_failed", "failed", "cancelled"].includes(data.status)) {
          clearRunPolling();
          localStorage.removeItem("domestic-ai-active-run");
          if (data.status === "succeeded") ElMessage.success("国内 AI 批量研判已完成");
          else if (data.status === "partial_failed") ElMessage.warning(`批量研判完成，失败 ${data.failed_count} 条`);
          return;
        }
        runPollTimer = window.setTimeout(pollRun, 1500);
      } catch {
        runPollTimer = window.setTimeout(pollRun, 3e3);
      }
    }
    function startRunPolling() {
      clearRunPolling();
      void pollRun();
    }
    async function openBatchHistory() {
      batchHistoryDialog.value = true;
      try {
        const { data } = await api.get("/domestic/ai-analysis/batches", { params: { page: 1, size: 20 } });
        batchRuns.value = data.items || [];
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载批量运行记录失败");
      }
    }
    async function cancelActiveRun() {
      if (!activeRunId.value) return;
      try {
        await ElMessageBox.confirm("取消后尚未处理的记录将被跳过，是否继续？", "二次确认取消任务", { type: "warning" });
        await api.post(`/domestic/ai-analysis/batch/${activeRunId.value}/cancel`);
        ElMessage.info("取消请求已提交");
        void pollRun();
      } catch (err) {
        if (err?.response) ElMessage.error(err?.response?.data?.detail || "取消任务失败");
      }
    }
    async function retryActiveRun() {
      if (!activeRunId.value) return;
      try {
        const { data } = await api.post(`/domestic/ai-analysis/batch/${activeRunId.value}/retry-failed`);
        activeRunId.value = data.run_id;
        localStorage.setItem("domestic-ai-active-run", data.run_id);
        ElMessage.success(data.message || "失败记录已重新提交");
        startRunPolling();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "重试失败记录失败");
      }
    }
    function openReviewView() {
      activeView.value = "reviews";
      void loadReviews();
    }
    async function loadReviews() {
      reviewsLoading.value = true;
      try {
        const { data } = await api.get("/domestic/ai-analysis/reviews", {
          params: { page: reviewsPage.value, size: reviewsSize, status: reviewStatusFilter.value === "all" ? void 0 : reviewStatusFilter.value }
        });
        reviews.value = data.items || [];
        reviewsTotal.value = data.total || 0;
        selectedReviewIds.value = /* @__PURE__ */ new Set();
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "加载人工复核列表失败");
      } finally {
        reviewsLoading.value = false;
      }
    }
    function toggleReview(review) {
      const next = new Set(selectedReviewIds.value);
      if (next.has(review.review_id)) next.delete(review.review_id);
      else next.add(review.review_id);
      selectedReviewIds.value = next;
    }
    function toggleAllReviews() {
      selectedReviewIds.value = allReviewsSelected.value ? /* @__PURE__ */ new Set() : new Set(reviews.value.map((review) => review.review_id));
    }
    const REVIEW_DECISION_HINT = {
      use_ai_display: "将把该舆情展示用的风险分切换为 AI 风险分（不改变正式规则风险，仅影响展示）。此操作可重复，仍在待复核。",
      keep_rule: "将保留系统规则风险分作为展示用风险。此操作可重复，仍在待复核。",
      confirm_event_change: "将为该舆情簇创建正式事件并生成正式记录。此操作可重复，仍在待复核。",
      confirm_alert_change: "将依据 AI 预警候选生成正式预警。此操作可重复，仍在待复核。",
      reject_change: "将驳回该条复核的全部 AI 变更（状态置为已驳回）。此操作不可撤销。",
      complete_review: "完成复核后该条舆情将进入「已确认」。仅关闭复核，不会自动创建事件或预警。"
    };
    async function decideReview(review, decision) {
      if (review.review_status !== "pending_review") return;
      const hint = REVIEW_DECISION_HINT[decision];
      let reason = "";
      if (decision === "complete_review") {
        try {
          const p = await ElMessageBox.prompt("可填写完成复核的说明（选填）：", "完成复核", {
            inputType: "textarea",
            confirmButtonText: "确认完成",
            cancelButtonText: "取消"
          });
          reason = (p.value || "").trim() || "";
        } catch {
          return;
        }
      } else if (hint) {
        try {
          await ElMessageBox.confirm(hint, "确认复核操作", { type: "warning" });
        } catch {
          return;
        }
      }
      try {
        const { data } = await api.post(`/domestic/ai-analysis/reviews/${review.review_id}/decision`, { decision, reason });
        const updated = data?.review;
        if (updated && updated.review_status !== "pending_review") {
          reviews.value = reviews.value.filter((r) => r.review_id !== review.review_id);
        } else if (updated) {
          const idx = reviews.value.findIndex((r) => r.review_id === review.review_id);
          if (idx >= 0) reviews.value[idx] = { ...reviews.value[idx], ...updated };
        } else {
          await loadReviews();
        }
        ElMessage.success(data.message || "复核已完成");
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "复核操作失败");
      }
    }
    async function batchReview(decision, confirmAll = false) {
      if (!confirmAll && selectedReviewIds.value.size === 0) return;
      if (reviews.value.length === 0) return;
      const ids = [...selectedReviewIds.value];
      const scope2 = confirmAll ? "全部待复核结果" : `选中的 ${ids.length} 条复核记录`;
      try {
        await ElMessageBox.confirm(`将处理${scope2}。`, "确认批量复核", { type: "warning" });
      } catch {
        return;
      }
      try {
        const { data } = await api.post("/domestic/ai-analysis/reviews/batch", { review_ids: confirmAll ? void 0 : ids, decision, confirm_all: confirmAll });
        const succ = data.total || (confirmAll ? reviews.value.length : ids.length);
        const failedItems = data.failed || [];
        const failCount = failedItems.length;
        ElMessage.success(`批量复核完成：成功 ${succ} 条${failCount ? `，失败 ${failCount} 条` : ""}`);
        if (failCount) {
          const msgs = failedItems.slice(0, 3).map((f) => `复核#${f.review_id}: ${f.message || f.reason || "失败"}`).join("；");
          ElMessage.warning(`部分失败：${msgs}${failCount > 3 ? " 等" : ""}`);
        }
        await loadReviews();
        window.dispatchEvent(new Event("data-refresh"));
      } catch (err) {
        ElMessage.error(err?.response?.data?.detail || "批量复核失败");
      }
    }
    function onBatchCommand(cmd) {
      if (cmd === "confirm_event_all") return batchReview("confirm_event_change", true);
      if (cmd === "reject_all") return batchReview("reject_change", true);
      return batchReview(cmd);
    }
    function displaySourceLabel(source) {
      return source === "ai" ? "AI 展示" : "保留规则风险";
    }
    function openReviewDetail(review) {
      openDetail(review.opinion_id);
    }
    function reviewStatusText(status) {
      return { pending_review: "待复核", confirmed: "已确认", rejected: "已驳回", superseded: "已替代" }[status] || status;
    }
    function reviewStatusPill(status) {
      return { pending_review: "pill-orange", confirmed: "pill-green", rejected: "pill-red", superseded: "pill-gray" }[status] || "pill-gray";
    }
    onMounted(() => {
      restoreFromQuery();
      loadData();
      loadSources();
      if (activeRunId.value) startRunPolling();
      window.addEventListener("data-refresh", loadData);
      document.addEventListener("click", onDocClick);
    });
    onUnmounted(() => {
      clearRunPolling();
      window.removeEventListener("data-refresh", loadData);
      document.removeEventListener("click", onDocClick);
    });
    return (_ctx, _cache) => {
      const _component_el_popover = resolveComponent("el-popover");
      const _component_Pager = resolveComponent("Pager");
      const _component_el_dropdown_item = resolveComponent("el-dropdown-item");
      const _component_el_dropdown_menu = resolveComponent("el-dropdown-menu");
      const _component_el_dropdown = resolveComponent("el-dropdown");
      const _directive_loading = resolveDirective("loading");
      return withDirectives((openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            _cache[27] || (_cache[27] = createBaseVNode("h1", { class: "page-title" }, "舆情列表", -1)),
            createBaseVNode("div", _hoisted_4, [
              scope.value === "domestic" ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
                createBaseVNode("button", {
                  class: normalizeClass(["view-tab", { active: activeView.value === "opinions" }]),
                  onClick: _cache[0] || (_cache[0] = ($event) => activeView.value = "opinions")
                }, "国内舆情", 2),
                canReviewRead.value ? (openBlock(), createElementBlock("button", {
                  key: 0,
                  class: normalizeClass(["view-tab", { active: activeView.value === "reviews" }]),
                  onClick: openReviewView
                }, "AI 人工复核", 2)) : createCommentVNode("", true)
              ], 64)) : (openBlock(), createElementBlock(Fragment, { key: 1 }, [
                createBaseVNode("button", {
                  class: normalizeClass(["view-tab", { active: foreignView.value === "list" }]),
                  onClick: _cache[1] || (_cache[1] = ($event) => foreignView.value = "list")
                }, "国外舆情", 2),
                createBaseVNode("button", {
                  class: normalizeClass(["view-tab", { active: foreignView.value === "review" }]),
                  onClick: _cache[2] || (_cache[2] = ($event) => foreignView.value = "review")
                }, "AI 人工复核", 2)
              ], 64))
            ])
          ]),
          _cache[28] || (_cache[28] = createBaseVNode("div", { class: "head-divider" }, null, -1)),
          createBaseVNode("div", _hoisted_5, [
            createBaseVNode("button", {
              class: normalizeClass(["scope-btn", { active: scope.value === "domestic" }]),
              onClick: _cache[3] || (_cache[3] = ($event) => {
                scope.value = "domestic";
                onScopeChange();
              })
            }, "国内", 2),
            createBaseVNode("button", {
              class: normalizeClass(["scope-btn", { active: scope.value === "foreign" }]),
              onClick: _cache[4] || (_cache[4] = ($event) => {
                scope.value = "foreign";
                onScopeChange();
              })
            }, "外网", 2)
          ]),
          createVNode(CollectMenu, { class: "head-collect" })
        ]),
        scope.value === "domestic" && activeView.value === "opinions" ? (openBlock(), createElementBlock(Fragment, { key: 0 }, [
          createBaseVNode("div", _hoisted_6, [
            createBaseVNode("div", _hoisted_7, [
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => filters.source = $event),
                class: "select",
                onChange: handleSearch
              }, [
                _cache[29] || (_cache[29] = createBaseVNode("option", { value: "" }, "来源（全部）", -1)),
                (openBlock(true), createElementBlock(Fragment, null, renderList(sourceOptions.value, (s) => {
                  return openBlock(), createElementBlock("option", {
                    key: s,
                    value: s
                  }, toDisplayString(s), 9, _hoisted_8);
                }), 128))
              ], 544), [
                [vModelSelect, filters.source]
              ]),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => filters.content_type = $event),
                class: "select",
                onChange: handleSearch
              }, [
                _cache[30] || (_cache[30] = createBaseVNode("option", { value: "" }, "类型（全部）", -1)),
                (openBlock(), createElementBlock(Fragment, null, renderList(contentTypeOptions, (o) => {
                  return createBaseVNode("option", {
                    key: o.value,
                    value: o.value
                  }, toDisplayString(o.label), 9, _hoisted_9);
                }), 64))
              ], 544), [
                [vModelSelect, filters.content_type]
              ]),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => filters.relevance = $event),
                class: "select",
                onChange: handleSearch
              }, [..._cache[31] || (_cache[31] = [
                createBaseVNode("option", { value: "" }, "相关性（全部）", -1),
                createBaseVNode("option", { value: "high" }, "高相关（≥60）", -1),
                createBaseVNode("option", { value: "low" }, "低相关（40-59）", -1)
              ])], 544), [
                [vModelSelect, filters.relevance]
              ]),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => filters.risk_level = $event),
                class: "select",
                onChange: handleSearch
              }, [..._cache[32] || (_cache[32] = [
                createBaseVNode("option", { value: "" }, "情感（全部）", -1),
                createBaseVNode("option", { value: "negative" }, "负面", -1),
                createBaseVNode("option", { value: "neutral" }, "中性", -1),
                createBaseVNode("option", { value: "positive" }, "正面", -1)
              ])], 544), [
                [vModelSelect, filters.risk_level]
              ]),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => filters.level = $event),
                class: "select",
                onChange: handleSearch
              }, [..._cache[33] || (_cache[33] = [
                createBaseVNode("option", { value: "" }, "级别（全部）", -1),
                createBaseVNode("option", { value: "high" }, "高危（≥70）", -1),
                createBaseVNode("option", { value: "mid" }, "中危（40-69）", -1),
                createBaseVNode("option", { value: "low" }, "低危（<40）", -1)
              ])], 544), [
                [vModelSelect, filters.level]
              ]),
              createBaseVNode("div", _hoisted_10, [
                _cache[35] || (_cache[35] = createBaseVNode("span", { class: "risk-view-label" }, "展示口径", -1)),
                withDirectives(createBaseVNode("select", {
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => riskView.value = $event),
                  class: "select",
                  onChange: handleSearch
                }, [..._cache[34] || (_cache[34] = [
                  createBaseVNode("option", { value: "current" }, "当前风险", -1),
                  createBaseVNode("option", { value: "rule" }, "系统规则", -1),
                  createBaseVNode("option", { value: "ai" }, "AI 研判", -1)
                ])], 544), [
                  [vModelSelect, riskView.value]
                ])
              ]),
              createBaseVNode("div", _hoisted_11, [
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => filters.date_from = $event),
                  class: "select date-input",
                  type: "date",
                  title: "发布开始日期",
                  onChange: handleSearch
                }, null, 544), [
                  [vModelText, filters.date_from]
                ]),
                _cache[36] || (_cache[36] = createBaseVNode("span", { class: "date-sep" }, "至", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => filters.date_to = $event),
                  class: "select date-input",
                  type: "date",
                  title: "发布结束日期",
                  onChange: handleSearch
                }, null, 544), [
                  [vModelText, filters.date_to]
                ])
              ]),
              createBaseVNode("div", _hoisted_12, [
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => filters.keyword = $event),
                  class: "search",
                  type: "text",
                  placeholder: "关键词 / 标题 / 内容",
                  onKeyup: withKeys(handleSearch, ["enter"])
                }, null, 544), [
                  [vModelText, filters.keyword]
                ]),
                filters.keyword ? (openBlock(), createElementBlock("button", {
                  key: 0,
                  class: "search-clear",
                  onClick: _cache[14] || (_cache[14] = ($event) => {
                    filters.keyword = "";
                    handleSearch();
                  })
                }, "✕")) : createCommentVNode("", true)
              ]),
              createBaseVNode("button", {
                class: "btn btn-ghost",
                onClick: handleSearch
              }, "搜索"),
              createBaseVNode("button", {
                class: "btn btn-ghost",
                onClick: handleRefresh
              }, "刷新"),
              canAnalyze.value ? (openBlock(), createElementBlock("button", {
                key: 0,
                class: "btn btn-primary",
                onClick: _cache[15] || (_cache[15] = ($event) => batchDialog.value = true)
              }, "批量 AI 研判")) : createCommentVNode("", true),
              canBatchRead.value ? (openBlock(), createElementBlock("button", {
                key: 1,
                class: "btn btn-ghost",
                onClick: openBatchHistory
              }, "运行记录")) : createCommentVNode("", true),
              unref(isSuperuser) ? (openBlock(), createElementBlock("label", _hoisted_13, [
                withDirectives(createBaseVNode("input", {
                  type: "checkbox",
                  "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => includeLowValue.value = $event),
                  onChange: handleSearch
                }, null, 544), [
                  [vModelCheckbox, includeLowValue.value]
                ]),
                _cache[37] || (_cache[37] = createTextVNode(" 显示低价值内容 ", -1))
              ])) : createCommentVNode("", true)
            ])
          ]),
          selectedIds.value.size > 0 ? (openBlock(), createElementBlock("div", _hoisted_14, [
            createBaseVNode("span", _hoisted_15, [
              _cache[38] || (_cache[38] = createTextVNode("已选择 ", -1)),
              createBaseVNode("b", null, toDisplayString(selectedIds.value.size), 1),
              _cache[39] || (_cache[39] = createTextVNode(" 条", -1))
            ]),
            createVNode(_component_el_popover, {
              trigger: "manual",
              visible: batchPopVisible.value,
              placement: "bottom",
              width: 132,
              "popper-class": "sent-popper"
            }, {
              reference: withCtx(() => [
                createBaseVNode("button", {
                  class: "btn btn-primary",
                  disabled: !canEditOpinion.value,
                  onClick: withModifiers(toggleBatchPop, ["stop"])
                }, "修改情感", 8, _hoisted_16)
              ]),
              default: withCtx(() => [
                createBaseVNode("div", _hoisted_17, [
                  (openBlock(), createElementBlock(Fragment, null, renderList(sentimentOptions, (opt) => {
                    return createBaseVNode("button", {
                      key: opt.value,
                      type: "button",
                      class: normalizeClass(["sent-opt", unref(sentimentPill)(opt.value)]),
                      onClick: withModifiers(($event) => batchSetSentiment(opt.value), ["stop"])
                    }, toDisplayString(opt.label), 11, _hoisted_18);
                  }), 64))
                ])
              ]),
              _: 1
            }, 8, ["visible"]),
            canDelete.value ? (openBlock(), createElementBlock("button", {
              key: 0,
              class: "btn btn-danger",
              onClick: batchDelete
            }, "删除")) : createCommentVNode("", true),
            createBaseVNode("button", {
              class: "btn btn-ghost",
              onClick: clearSelection
            }, "取消选择")
          ])) : createCommentVNode("", true),
          activeRun.value && !["succeeded", "partial_failed", "failed", "cancelled"].includes(activeRun.value.status) ? (openBlock(), createElementBlock("div", _hoisted_19, [
            createBaseVNode("div", _hoisted_20, [
              _cache[40] || (_cache[40] = createBaseVNode("b", null, "国内 AI 研判进行中", -1)),
              createBaseVNode("span", null, toDisplayString(activeRun.value.processed_count) + "/" + toDisplayString(activeRun.value.total_count), 1),
              createBaseVNode("button", {
                class: "link-btn danger",
                onClick: cancelActiveRun
              }, "取消任务")
            ]),
            createBaseVNode("div", _hoisted_21, [
              createBaseVNode("span", {
                style: normalizeStyle({ width: `${Math.min(100, Math.round(activeRun.value.processed_count / Math.max(1, activeRun.value.total_count) * 100))}%` })
              }, null, 4)
            ]),
            createBaseVNode("div", _hoisted_22, [
              createBaseVNode("span", null, "成功 " + toDisplayString(activeRun.value.success_count), 1),
              createBaseVNode("span", null, "失败 " + toDisplayString(activeRun.value.failed_count), 1),
              createBaseVNode("span", null, "跳过 " + toDisplayString(activeRun.value.skipped_count), 1),
              createBaseVNode("span", null, toDisplayString(activeRun.value.current_step), 1)
            ])
          ])) : createCommentVNode("", true),
          activeRun.value && activeRun.value.status === "partial_failed" && activeRun.value.failed_count ? (openBlock(), createElementBlock("div", _hoisted_23, [
            createBaseVNode("div", { class: "run-progress-head" }, [
              _cache[41] || (_cache[41] = createBaseVNode("b", null, "批量研判存在失败记录", -1)),
              createBaseVNode("button", {
                class: "link-btn",
                onClick: retryActiveRun
              }, "重试失败记录")
            ]),
            createBaseVNode("div", _hoisted_24, [
              createBaseVNode("span", null, "失败 " + toDisplayString(activeRun.value.failed_count) + " 条", 1),
              createBaseVNode("span", null, toDisplayString(activeRun.value.current_step), 1)
            ])
          ])) : createCommentVNode("", true),
          createBaseVNode("div", _hoisted_25, [
            createBaseVNode("div", _hoisted_26, [
              createBaseVNode("table", _hoisted_27, [
                createBaseVNode("thead", null, [
                  createBaseVNode("tr", null, [
                    canEditOpinion.value || canDelete.value ? (openBlock(), createElementBlock("th", _hoisted_28, [
                      createBaseVNode("input", {
                        type: "checkbox",
                        class: "row-check",
                        checked: isAllSelected.value,
                        indeterminate: isIndeterminate.value,
                        onClick: withModifiers(toggleSelectAll, ["stop"])
                      }, null, 8, _hoisted_29)
                    ])) : createCommentVNode("", true),
                    _cache[42] || (_cache[42] = createBaseVNode("th", {
                      style: { "width": "58px" },
                      class: "leading-id"
                    }, "ID", -1)),
                    _cache[43] || (_cache[43] = createBaseVNode("th", {
                      style: { "width": "280px" },
                      class: "leading-title"
                    }, "标题", -1)),
                    _cache[44] || (_cache[44] = createBaseVNode("th", { style: { "width": "150px" } }, "来源", -1)),
                    _cache[45] || (_cache[45] = createBaseVNode("th", {
                      style: { "width": "110px" },
                      class: "col-center"
                    }, "类型", -1)),
                    _cache[46] || (_cache[46] = createBaseVNode("th", {
                      style: { "width": "110px" },
                      class: "col-center"
                    }, "相关性", -1)),
                    _cache[47] || (_cache[47] = createBaseVNode("th", { style: { "width": "200px" } }, "准入原因", -1)),
                    _cache[48] || (_cache[48] = createBaseVNode("th", {
                      style: { "width": "100px" },
                      class: "col-center"
                    }, "情感", -1)),
                    _cache[49] || (_cache[49] = createBaseVNode("th", {
                      style: { "width": "110px" },
                      class: "col-center"
                    }, "级别", -1)),
                    createBaseVNode("th", _hoisted_30, "风险评分" + toDisplayString(riskView.value === "ai" ? "(AI)" : ""), 1),
                    _cache[50] || (_cache[50] = createBaseVNode("th", {
                      style: { "width": "110px" },
                      class: "col-center"
                    }, "分析状态", -1)),
                    _cache[51] || (_cache[51] = createBaseVNode("th", { style: { "width": "170px" } }, "发布时间", -1)),
                    canDelete.value ? (openBlock(), createElementBlock("th", _hoisted_31, "操作")) : createCommentVNode("", true)
                  ])
                ]),
                createBaseVNode("tbody", null, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(rows.value, (row, idx) => {
                    return openBlock(), createElementBlock("tr", {
                      key: row.id,
                      onClick: ($event) => openDetail(row.id),
                      style: { "cursor": "pointer" }
                    }, [
                      canEditOpinion.value || canDelete.value ? (openBlock(), createElementBlock("td", _hoisted_33, [
                        createBaseVNode("input", {
                          type: "checkbox",
                          class: "row-check",
                          checked: selectedIds.value.has(row.id),
                          onClick: withModifiers(($event) => toggleRow(row), ["stop"])
                        }, null, 8, _hoisted_34)
                      ])) : createCommentVNode("", true),
                      createBaseVNode("td", _hoisted_35, toDisplayString((page.value - 1) * size.value + idx + 1), 1),
                      createBaseVNode("td", _hoisted_36, [
                        createBaseVNode("span", _hoisted_37, toDisplayString(row.title), 1)
                      ]),
                      createBaseVNode("td", null, toDisplayString(row.source), 1),
                      createBaseVNode("td", _hoisted_38, [
                        createBaseVNode("span", _hoisted_39, toDisplayString(contentTypeText(row.content_type)), 1)
                      ]),
                      createBaseVNode("td", _hoisted_40, [
                        createBaseVNode("span", {
                          class: normalizeClass(["score-chip", relevanceClass(row.relevance_score)])
                        }, toDisplayString(formatRelevance(row.relevance_score)), 3)
                      ]),
                      createBaseVNode("td", null, [
                        createBaseVNode("span", _hoisted_41, toDisplayString(admissionSummary(row.admission_reason)), 1)
                      ]),
                      createBaseVNode("td", _hoisted_42, [
                        canEditOpinion.value ? (openBlock(), createBlock(_component_el_popover, {
                          key: 0,
                          trigger: "manual",
                          visible: popoverRowId.value === row.id,
                          placement: "bottom",
                          width: 132,
                          "popper-class": "sent-popper"
                        }, {
                          reference: withCtx(() => [
                            createBaseVNode("span", {
                              class: normalizeClass(["pill editable", unref(sentimentPill)(row.sentiment)]),
                              onClick: withModifiers(($event) => toggleSentPop(row), ["stop"])
                            }, [
                              _cache[52] || (_cache[52] = createBaseVNode("span", { class: "dot" }, null, -1)),
                              createTextVNode(toDisplayString(unref(sentimentText)(row.sentiment)), 1)
                            ], 10, _hoisted_43)
                          ]),
                          default: withCtx(() => [
                            createBaseVNode("div", _hoisted_44, [
                              (openBlock(), createElementBlock(Fragment, null, renderList(sentimentOptions, (opt) => {
                                return createBaseVNode("button", {
                                  key: opt.value,
                                  type: "button",
                                  class: normalizeClass(["sent-opt", [unref(sentimentPill)(opt.value), { active: row.sentiment === opt.value }]]),
                                  onClick: withModifiers(($event) => chooseSentiment(row, opt.value), ["stop"])
                                }, toDisplayString(opt.label), 11, _hoisted_45);
                              }), 64))
                            ])
                          ]),
                          _: 2
                        }, 1032, ["visible"])) : (openBlock(), createElementBlock("span", {
                          key: 1,
                          class: normalizeClass(["pill", unref(sentimentPill)(row.sentiment)])
                        }, [
                          _cache[53] || (_cache[53] = createBaseVNode("span", { class: "dot" }, null, -1)),
                          createTextVNode(toDisplayString(unref(sentimentText)(row.sentiment)), 1)
                        ], 2))
                      ]),
                      createBaseVNode("td", _hoisted_46, [
                        createBaseVNode("span", {
                          class: normalizeClass(["pill", unref(levelPill)(displayRiskScore(row))])
                        }, toDisplayString(unref(levelText)(displayRiskScore(row))), 3)
                      ]),
                      createBaseVNode("td", _hoisted_47, [
                        createBaseVNode("span", {
                          class: "risk-num",
                          style: normalizeStyle({ color: unref(riskColor)(displayRiskScore(row)) })
                        }, toDisplayString(displayRiskScore(row)), 5),
                        showAIBadge(row) ? (openBlock(), createElementBlock("span", _hoisted_48, "AI")) : createCommentVNode("", true)
                      ]),
                      createBaseVNode("td", _hoisted_49, [
                        createBaseVNode("span", {
                          class: normalizeClass(["pill", unref(statusPill)(row.analysis_status)])
                        }, toDisplayString(unref(statusText)(row.analysis_status)), 3)
                      ]),
                      createBaseVNode("td", null, toDisplayString(unref(formatTime)(row.publish_time)), 1),
                      canDelete.value ? (openBlock(), createElementBlock("td", _hoisted_50, [
                        createBaseVNode("button", {
                          class: "op-del",
                          onClick: withModifiers(($event) => deleteOne(row), ["stop"])
                        }, "删除", 8, _hoisted_51)
                      ])) : createCommentVNode("", true)
                    ], 8, _hoisted_32);
                  }), 128)),
                  rows.value.length === 0 && !loading.value ? (openBlock(), createElementBlock("tr", _hoisted_52, [
                    createBaseVNode("td", {
                      colspan: colCount.value,
                      class: "empty-row"
                    }, "暂无舆情数据", 8, _hoisted_53)
                  ])) : createCommentVNode("", true)
                ])
              ])
            ]),
            total.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_54, [
              createVNode(_component_Pager, {
                total: total.value,
                "current-page": page.value,
                "onUpdate:currentPage": _cache[17] || (_cache[17] = ($event) => page.value = $event),
                "page-size": size.value,
                onCurrentChange: onPageChange
              }, null, 8, ["total", "current-page", "page-size"])
            ])) : createCommentVNode("", true)
          ])
        ], 64)) : scope.value === "domestic" ? (openBlock(), createElementBlock("section", _hoisted_55, [
          _cache[79] || (_cache[79] = createBaseVNode("div", { class: "review-head" }, [
            createBaseVNode("h2", null, "AI 人工复核"),
            createBaseVNode("p", null, "AI 研判只生成候选，确认后才会进入正式事件或预警。")
          ], -1)),
          createBaseVNode("div", _hoisted_56, [
            createBaseVNode("button", {
              class: normalizeClass(["seg", { active: reviewStatusFilter.value === "pending_review" }]),
              onClick: _cache[18] || (_cache[18] = ($event) => {
                reviewStatusFilter.value = "pending_review";
                loadReviews();
              })
            }, "待复核", 2),
            createBaseVNode("button", {
              class: normalizeClass(["seg", { active: reviewStatusFilter.value === "confirmed" }]),
              onClick: _cache[19] || (_cache[19] = ($event) => {
                reviewStatusFilter.value = "confirmed";
                loadReviews();
              })
            }, "已确认", 2),
            createBaseVNode("button", {
              class: normalizeClass(["seg", { active: reviewStatusFilter.value === "rejected" }]),
              onClick: _cache[20] || (_cache[20] = ($event) => {
                reviewStatusFilter.value = "rejected";
                loadReviews();
              })
            }, "已驳回", 2),
            createBaseVNode("button", {
              class: normalizeClass(["seg", { active: reviewStatusFilter.value === "all" }]),
              onClick: _cache[21] || (_cache[21] = ($event) => {
                reviewStatusFilter.value = "all";
                loadReviews();
              })
            }, "全部", 2),
            _cache[62] || (_cache[62] = createBaseVNode("span", { class: "muted review-filter-tip" }, "操作后不会丢失：已处理的舆情可在「已确认 / 已驳回 / 全部」中回看与追溯", -1)),
            reviewStatusFilter.value === "pending_review" ? (openBlock(), createElementBlock("div", _hoisted_57, [
              createVNode(_component_el_dropdown, {
                trigger: "click",
                disabled: selectedReviewIds.value.size === 0,
                onCommand: onBatchCommand
              }, {
                dropdown: withCtx(() => [
                  createVNode(_component_el_dropdown_menu, null, {
                    default: withCtx(() => [
                      createVNode(_component_el_dropdown_item, {
                        command: "use_ai_display",
                        disabled: selectedReviewIds.value.size === 0
                      }, {
                        default: withCtx(() => [..._cache[54] || (_cache[54] = [
                          createTextVNode("采用 AI 展示", -1)
                        ])]),
                        _: 1
                      }, 8, ["disabled"]),
                      createVNode(_component_el_dropdown_item, {
                        command: "keep_rule",
                        disabled: selectedReviewIds.value.size === 0
                      }, {
                        default: withCtx(() => [..._cache[55] || (_cache[55] = [
                          createTextVNode("保留规则风险", -1)
                        ])]),
                        _: 1
                      }, 8, ["disabled"]),
                      createVNode(_component_el_dropdown_item, {
                        command: "confirm_event_change",
                        disabled: selectedReviewIds.value.size === 0
                      }, {
                        default: withCtx(() => [..._cache[56] || (_cache[56] = [
                          createTextVNode("确认事件影响", -1)
                        ])]),
                        _: 1
                      }, 8, ["disabled"]),
                      createVNode(_component_el_dropdown_item, {
                        command: "confirm_alert_change",
                        disabled: selectedReviewIds.value.size === 0
                      }, {
                        default: withCtx(() => [..._cache[57] || (_cache[57] = [
                          createTextVNode("确认预警影响", -1)
                        ])]),
                        _: 1
                      }, 8, ["disabled"]),
                      createVNode(_component_el_dropdown_item, {
                        command: "reject_change",
                        disabled: selectedReviewIds.value.size === 0
                      }, {
                        default: withCtx(() => [..._cache[58] || (_cache[58] = [
                          createTextVNode("驳回选中（全部 AI 变更）", -1)
                        ])]),
                        _: 1
                      }, 8, ["disabled"]),
                      createVNode(_component_el_dropdown_item, {
                        command: "confirm_event_all",
                        divided: "",
                        disabled: reviews.value.length === 0
                      }, {
                        default: withCtx(() => [..._cache[59] || (_cache[59] = [
                          createTextVNode("全量确认事件", -1)
                        ])]),
                        _: 1
                      }, 8, ["disabled"]),
                      createVNode(_component_el_dropdown_item, {
                        command: "reject_all",
                        disabled: reviews.value.length === 0
                      }, {
                        default: withCtx(() => [..._cache[60] || (_cache[60] = [
                          createTextVNode("全量驳回", -1)
                        ])]),
                        _: 1
                      }, 8, ["disabled"])
                    ]),
                    _: 1
                  })
                ]),
                default: withCtx(() => [
                  createBaseVNode("button", {
                    class: "btn btn-primary",
                    disabled: selectedReviewIds.value.size === 0
                  }, "批量操作 ▾", 8, _hoisted_58)
                ]),
                _: 1
              }, 8, ["disabled"]),
              _cache[61] || (_cache[61] = createBaseVNode("span", { class: "muted review-toolbar-hint" }, "先勾选左侧复选框，再从「批量操作」中选择动作", -1))
            ])) : createCommentVNode("", true)
          ]),
          reviewsLoading.value ? (openBlock(), createElementBlock("div", _hoisted_59, "加载复核记录中…")) : (openBlock(), createElementBlock("div", _hoisted_60, [
            createBaseVNode("div", _hoisted_61, [
              createBaseVNode("table", _hoisted_62, [
                createBaseVNode("thead", null, [
                  createBaseVNode("tr", null, [
                    createBaseVNode("th", _hoisted_63, [
                      createBaseVNode("input", {
                        type: "checkbox",
                        class: "row-check",
                        checked: allReviewsSelected.value,
                        onClick: withModifiers(toggleAllReviews, ["stop"])
                      }, null, 8, _hoisted_64)
                    ]),
                    _cache[63] || (_cache[63] = createBaseVNode("th", null, "舆情标题", -1)),
                    _cache[64] || (_cache[64] = createBaseVNode("th", null, "来源", -1)),
                    _cache[65] || (_cache[65] = createBaseVNode("th", null, "发布时间", -1)),
                    _cache[66] || (_cache[66] = createBaseVNode("th", null, "规则风险", -1)),
                    _cache[67] || (_cache[67] = createBaseVNode("th", null, "AI 风险", -1)),
                    _cache[68] || (_cache[68] = createBaseVNode("th", null, "展示口径", -1)),
                    _cache[69] || (_cache[69] = createBaseVNode("th", null, "事件候选", -1)),
                    _cache[70] || (_cache[70] = createBaseVNode("th", null, "预警候选", -1)),
                    _cache[71] || (_cache[71] = createBaseVNode("th", null, "状态", -1)),
                    _cache[72] || (_cache[72] = createBaseVNode("th", { class: "review-op-th" }, "操作", -1))
                  ])
                ]),
                createBaseVNode("tbody", null, [
                  (openBlock(true), createElementBlock(Fragment, null, renderList(reviews.value, (review) => {
                    return openBlock(), createElementBlock("tr", {
                      key: review.review_id
                    }, [
                      createBaseVNode("td", null, [
                        createBaseVNode("input", {
                          type: "checkbox",
                          class: "row-check",
                          checked: selectedReviewIds.value.has(review.review_id),
                          onClick: withModifiers(($event) => toggleReview(review), ["stop"])
                        }, null, 8, _hoisted_65)
                      ]),
                      createBaseVNode("td", _hoisted_66, [
                        createBaseVNode("button", {
                          class: "link-button",
                          onClick: ($event) => openReviewDetail(review)
                        }, toDisplayString(review.opinion_title || `舆情 #${review.opinion_id}`), 9, _hoisted_67)
                      ]),
                      createBaseVNode("td", null, toDisplayString(review.source || "-"), 1),
                      createBaseVNode("td", null, toDisplayString(unref(formatTime)(review.publish_time)), 1),
                      createBaseVNode("td", null, [
                        createBaseVNode("span", _hoisted_68, toDisplayString(review.rule_risk_snapshot?.risk_score ?? "-"), 1)
                      ]),
                      createBaseVNode("td", null, [
                        createBaseVNode("span", {
                          class: "risk-num",
                          style: normalizeStyle({ color: unref(riskColor)(review.ai_risk_snapshot?.risk_score) })
                        }, toDisplayString(review.ai_risk_snapshot?.risk_score ?? "-"), 5)
                      ]),
                      createBaseVNode("td", null, toDisplayString(displaySourceLabel(review.display_source)), 1),
                      createBaseVNode("td", _hoisted_69, [
                        review.event_review_status === "confirmed" ? (openBlock(), createElementBlock("span", _hoisted_70, "已确认")) : (openBlock(), createElementBlock("span", _hoisted_71, toDisplayString(review.event_candidate_count), 1))
                      ]),
                      createBaseVNode("td", _hoisted_72, [
                        review.alert_review_status === "confirmed" ? (openBlock(), createElementBlock("span", _hoisted_73, "已确认")) : (openBlock(), createElementBlock("span", _hoisted_74, toDisplayString(review.alert_candidate_count), 1))
                      ]),
                      createBaseVNode("td", null, [
                        createBaseVNode("span", {
                          class: normalizeClass(["pill", reviewStatusPill(review.review_status)])
                        }, toDisplayString(reviewStatusText(review.review_status)), 3)
                      ]),
                      createBaseVNode("td", _hoisted_75, [
                        createBaseVNode("button", {
                          class: "review-op-btn",
                          onClick: ($event) => decideReview(review, "confirm_event_change")
                        }, "确认事件影响", 8, _hoisted_76),
                        createBaseVNode("button", {
                          class: "review-op-btn",
                          onClick: ($event) => decideReview(review, "confirm_alert_change")
                        }, "确认预警影响", 8, _hoisted_77),
                        createVNode(_component_el_dropdown, {
                          trigger: "click",
                          onCommand: (cmd) => decideReview(review, cmd)
                        }, {
                          dropdown: withCtx(() => [
                            createVNode(_component_el_dropdown_menu, null, {
                              default: withCtx(() => [
                                createVNode(_component_el_dropdown_item, { command: "use_ai_display" }, {
                                  default: withCtx(() => [..._cache[73] || (_cache[73] = [
                                    createTextVNode("采用 AI 展示", -1)
                                  ])]),
                                  _: 1
                                }),
                                createVNode(_component_el_dropdown_item, { command: "keep_rule" }, {
                                  default: withCtx(() => [..._cache[74] || (_cache[74] = [
                                    createTextVNode("保留规则风险", -1)
                                  ])]),
                                  _: 1
                                }),
                                createVNode(_component_el_dropdown_item, {
                                  command: "complete_review",
                                  divided: ""
                                }, {
                                  default: withCtx(() => [..._cache[75] || (_cache[75] = [
                                    createTextVNode("完成复核", -1)
                                  ])]),
                                  _: 1
                                }),
                                createVNode(_component_el_dropdown_item, { command: "reject_change" }, {
                                  default: withCtx(() => [..._cache[76] || (_cache[76] = [
                                    createTextVNode("驳回全部 AI 变更", -1)
                                  ])]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            })
                          ]),
                          default: withCtx(() => [
                            _cache[77] || (_cache[77] = createBaseVNode("button", {
                              class: "review-op-btn",
                              type: "button"
                            }, "更多 ▾", -1))
                          ]),
                          _: 1
                        }, 8, ["onCommand"])
                      ])
                    ]);
                  }), 128)),
                  !reviews.value.length ? (openBlock(), createElementBlock("tr", _hoisted_78, [..._cache[78] || (_cache[78] = [
                    createBaseVNode("td", {
                      colspan: "11",
                      class: "empty-row"
                    }, "暂无待复核记录", -1)
                  ])])) : createCommentVNode("", true)
                ])
              ])
            ])
          ])),
          reviewsTotal.value > 0 ? (openBlock(), createElementBlock("div", _hoisted_79, [
            createVNode(_component_Pager, {
              total: reviewsTotal.value,
              "current-page": reviewsPage.value,
              "onUpdate:currentPage": _cache[22] || (_cache[22] = ($event) => reviewsPage.value = $event),
              "page-size": reviewsSize,
              onCurrentChange: loadReviews
            }, null, 8, ["total", "current-page"])
          ])) : createCommentVNode("", true)
        ])) : createCommentVNode("", true),
        scope.value === "domestic" ? (openBlock(), createElementBlock(Fragment, { key: 2 }, [
          createVNode(BatchAIModal, {
            visible: batchDialog.value,
            kicker: "国内 AI 研判",
            title: "创建批量研判任务",
            "preview-endpoint": "/domestic/ai-analysis/batch/preview",
            "submit-endpoint": "/domestic/ai-analysis/batch",
            "scope-options": domesticBatchScopeOptions,
            "full-scope-value": "filters",
            "selected-count": selectedIds.value.size,
            "build-payload": buildDomesticBatchPayload,
            "onUpdate:visible": _cache[23] || (_cache[23] = ($event) => batchDialog.value = $event),
            onSubmitted: onDomesticBatchSubmitted
          }, null, 8, ["visible", "selected-count"]),
          batchHistoryDialog.value ? (openBlock(), createElementBlock("div", {
            key: 0,
            class: "modal-mask",
            onClick: _cache[25] || (_cache[25] = withModifiers(($event) => batchHistoryDialog.value = false, ["self"]))
          }, [
            createBaseVNode("div", _hoisted_80, [
              createBaseVNode("div", _hoisted_81, [
                _cache[80] || (_cache[80] = createBaseVNode("div", { class: "modal-title-wrap" }, [
                  createBaseVNode("span", { class: "modal-kicker" }, "AI 研判运行记录"),
                  createBaseVNode("h3", { class: "modal-title" }, "历史批次")
                ], -1)),
                createBaseVNode("button", {
                  class: "modal-close",
                  onClick: _cache[24] || (_cache[24] = ($event) => batchHistoryDialog.value = false)
                }, "✕")
              ]),
              createBaseVNode("div", _hoisted_82, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(batchRuns.value, (run) => {
                  return openBlock(), createElementBlock("div", {
                    key: run.run_id,
                    class: "run-row"
                  }, [
                    createBaseVNode("div", null, [
                      createBaseVNode("b", null, toDisplayString(run.status), 1),
                      createBaseVNode("span", null, toDisplayString(run.processed_count) + "/" + toDisplayString(run.total_count) + "，成功 " + toDisplayString(run.success_count) + "，失败 " + toDisplayString(run.failed_count) + "，跳过 " + toDisplayString(run.skipped_count), 1)
                    ]),
                    createBaseVNode("code", null, toDisplayString(run.run_id), 1)
                  ]);
                }), 128)),
                !batchRuns.value.length ? (openBlock(), createElementBlock("p", _hoisted_83, "暂无运行记录")) : createCommentVNode("", true)
              ])
            ])
          ])) : createCommentVNode("", true)
        ], 64)) : (openBlock(), createElementBlock(Fragment, { key: 3 }, [
          foreignView.value === "list" ? (openBlock(), createBlock(ForeignOpinionListView, { key: 0 })) : foreignView.value === "review" ? (openBlock(), createBlock(ForeignAIReviewView, { key: 1 })) : createCommentVNode("", true)
        ], 64)),
        createVNode(OpinionDetailModal, {
          modelValue: detailVisible.value,
          "onUpdate:modelValue": _cache[26] || (_cache[26] = ($event) => detailVisible.value = $event),
          "opinion-id": detailId.value
        }, null, 8, ["modelValue", "opinion-id"])
      ])), [
        [_directive_loading, loading.value]
      ]);
    };
  }
});

const Opinions = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-b3749c19"]]);

export { Opinions as default };
