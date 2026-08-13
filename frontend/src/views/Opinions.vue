<template>
  <div class="opinions" v-loading="loading">
    <div class="opinions-head">
      <div class="view-tabs">
        <template v-if="scope === 'domestic'">
          <button class="view-tab" :class="{ active: activeView === 'opinions' }" @click="activeView = 'opinions'">国内舆情</button>
          <button v-if="canReviewRead" class="view-tab" :class="{ active: activeView === 'reviews' }" @click="openReviewView">AI 人工复核</button>
        </template>
        <template v-else>
          <button class="view-tab" :class="{ active: foreignView === 'list' }" @click="foreignView = 'list'">国外舆情</button>
          <button class="view-tab" :class="{ active: foreignView === 'review' }" @click="foreignView = 'review'">AI 人工复核</button>
        </template>
      </div>
      <div class="top-scope-switch">
        <el-radio-group v-model="scope" @change="onScopeChange">
          <el-radio-button label="domestic">国内</el-radio-button>
          <el-radio-button label="foreign">外网</el-radio-button>
        </el-radio-group>
      </div>
    </div>
    <template v-if="scope === 'domestic' && activeView === 'opinions'">
    <!-- Filter bar -->
    <div class="toolbar">
      <div class="filters">
        <select v-model="filters.source" class="select" @change="handleSearch">
          <option value="">来源（全部）</option>
          <option v-for="s in sourceOptions" :key="s" :value="s">{{ s }}</option>
        </select>
        <select v-model="filters.content_type" class="select" @change="handleSearch">
          <option value="">类型（全部）</option>
          <option v-for="o in contentTypeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
        <select v-model="filters.relevance" class="select" @change="handleSearch">
          <option value="">相关性（全部）</option>
          <option value="high">高相关（≥60）</option>
          <option value="low">低相关（40-59）</option>
        </select>
        <select v-model="filters.risk_level" class="select" @change="handleSearch">
          <option value="">情感（全部）</option>
          <option value="negative">负面</option>
          <option value="neutral">中性</option>
          <option value="positive">正面</option>
        </select>
        <select v-model="filters.level" class="select" @change="handleSearch">
          <option value="">级别（全部）</option>
          <option value="high">高危（≥70）</option>
          <option value="mid">中危（40-69）</option>
          <option value="low">低危（&lt;40）</option>
        </select>
        <div class="date-range">
          <input
            v-model="filters.date_from"
            class="select date-input"
            type="date"
            title="发布开始日期"
            @change="handleSearch"
          />
          <span class="date-sep">至</span>
          <input
            v-model="filters.date_to"
            class="select date-input"
            type="date"
            title="发布结束日期"
            @change="handleSearch"
          />
        </div>
        <div class="search-wrap">
          <input
            v-model="filters.keyword"
            class="search"
            type="text"
            placeholder="关键词 / 标题 / 内容"
            @keyup.enter="handleSearch"
          />
          <button v-if="filters.keyword" class="search-clear" @click="filters.keyword=''; handleSearch()">✕</button>
        </div>
        <button class="btn btn-ghost" @click="handleSearch">搜索</button>
        <button class="btn btn-ghost" @click="handleRefresh">刷新</button>
        <button v-if="canAnalyze" class="btn btn-primary" @click="batchDialog = true">批量 AI 研判</button>
        <button v-if="canBatchRead" class="btn btn-ghost" @click="openBatchHistory">运行记录</button>
        <label v-if="isSuperuser" class="low-value-toggle" title="默认列表隐藏 irrelevant / advertising 等低价值内容；勾选后可查看完整数据（含历史重算标定的低价值条目）">
          <input type="checkbox" v-model="includeLowValue" @change="handleSearch" />
          显示低价值内容
        </label>
      </div>
    </div>

    <!-- 批量操作栏：选中行 > 0 时显示 -->
    <div class="batch-bar" v-if="selectedIds.size > 0">
      <span class="batch-count">已选择 <b>{{ selectedIds.size }}</b> 条</span>
      <el-popover
        trigger="manual"
        :visible="batchPopVisible"
        placement="bottom"
        :width="132"
        popper-class="sent-popper"
      >
        <template #reference>
          <button class="btn btn-primary" :disabled="!canEditOpinion" @click.stop="toggleBatchPop">修改情感</button>
        </template>
        <div class="sent-pop">
          <button
            v-for="opt in sentimentOptions"
            :key="opt.value"
            type="button"
            class="sent-opt"
            :class="sentimentPill(opt.value)"
            @click.stop="batchSetSentiment(opt.value)"
          >{{ opt.label }}</button>
        </div>
      </el-popover>
      <button v-if="canDelete" class="btn btn-danger" @click="batchDelete">删除</button>
      <button class="btn btn-ghost" @click="clearSelection">取消选择</button>
    </div>
    <div v-if="activeRun && !['succeeded', 'partial_failed', 'failed', 'cancelled'].includes(activeRun.status)" class="run-progress">
      <div class="run-progress-head"><b>国内 AI 研判进行中</b><span>{{ activeRun.processed_count }}/{{ activeRun.total_count }}</span><button class="link-btn danger" @click="cancelActiveRun">取消任务</button></div>
      <div class="progress-track"><span :style="{ width: `${Math.min(100, Math.round((activeRun.processed_count / Math.max(1, activeRun.total_count)) * 100))}%` }"></span></div>
      <div class="run-progress-meta"><span>成功 {{ activeRun.success_count }}</span><span>失败 {{ activeRun.failed_count }}</span><span>跳过 {{ activeRun.skipped_count }}</span><span>{{ activeRun.current_step }}</span></div>
    </div>
    <div v-if="activeRun && activeRun.status === 'partial_failed' && activeRun.failed_count" class="run-progress run-failed">
      <div class="run-progress-head"><b>批量研判存在失败记录</b><button class="link-btn" @click="retryActiveRun">重试失败记录</button></div>
      <div class="run-progress-meta"><span>失败 {{ activeRun.failed_count }} 条</span><span>{{ activeRun.current_step }}</span></div>
    </div>

    <!-- Table -->
    <div class="card table-card">
      <div class="tbl-scroll">
      <table class="tbl">
        <thead>
          <tr>
            <th v-if="canEditOpinion || canDelete" style="width:44px" class="col-center leading-check">
              <input type="checkbox" class="row-check" :checked="isAllSelected" :indeterminate="isIndeterminate" @click.stop="toggleSelectAll" />
            </th>
            <th style="width:58px" class="leading-id">ID</th>
            <th style="width:280px" class="leading-title">标题</th>
            <th style="width:150px">来源</th>
            <th style="width:110px" class="col-center">类型</th>
            <th style="width:110px" class="col-center">相关性</th>
            <th style="width:200px">准入原因</th>
            <th style="width:100px" class="col-center">情感</th>
            <th style="width:110px" class="col-center">级别</th>
            <th style="width:110px" class="col-center">风险评分</th>
            <th style="width:110px" class="col-center">分析状态</th>
            <th style="width:170px">发布时间</th>
            <th v-if="canDelete" style="width:90px" class="col-center">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="row.id" @click="openDetail(row.id)" style="cursor:pointer">
            <td v-if="canEditOpinion || canDelete" class="col-center leading-check">
              <input type="checkbox" class="row-check" :checked="selectedIds.has(row.id)" @click.stop="toggleRow(row)" />
            </td>
            <td class="leading-id">{{ (page - 1) * size + idx + 1 }}</td>
            <td class="leading-title"><span class="t-title">{{ row.title }}</span></td>
            <td>{{ row.source }}</td>
            <td class="col-center">
              <span class="pill pill-blue">{{ contentTypeText(row.content_type) }}</span>
            </td>
            <td class="col-center">
              <span class="score-chip" :class="relevanceClass(row.relevance_score)">{{ formatRelevance(row.relevance_score) }}</span>
            </td>
            <td>
              <span class="admission-summary">{{ admissionSummary(row.admission_reason) }}</span>
            </td>
            <td class="col-center">
              <!-- 情感：可人工校正（仅 opinions:write 角色）。点击单元格弹出竖向胶囊选项。 -->
              <el-popover
                v-if="canEditOpinion"
                trigger="manual"
                :visible="popoverRowId === row.id"
                placement="bottom"
                :width="132"
                popper-class="sent-popper"
              >
                <template #reference>
                  <span class="pill editable" :class="sentimentPill(row.sentiment)" @click.stop="toggleSentPop(row)">
                    <span class="dot"></span>{{ sentimentText(row.sentiment) }}
                  </span>
                </template>
                <div class="sent-pop">
                  <button
                    v-for="opt in sentimentOptions"
                    :key="opt.value"
                    type="button"
                    class="sent-opt"
                    :class="[sentimentPill(opt.value), { active: row.sentiment === opt.value }]"
                    @click.stop="chooseSentiment(row, opt.value)"
                  >{{ opt.label }}</button>
                </div>
              </el-popover>
              <span v-else class="pill" :class="sentimentPill(row.sentiment)">
                <span class="dot"></span>{{ sentimentText(row.sentiment) }}
              </span>
            </td>
            <td class="col-center">
              <span class="pill" :class="levelPill(row.risk_score)">{{ levelText(row.risk_score) }}</span>
            </td>
            <td class="col-center">
              <span class="risk-num" :style="{ color: riskColor(row.risk_score) }">{{ row.risk_score }}</span>
            </td>
            <td class="col-center">
              <span class="pill" :class="statusPill(row.analysis_status)">{{ statusText(row.analysis_status) }}</span>
            </td>
            <td>{{ formatTime(row.publish_time) }}</td>
            <td v-if="canDelete" class="col-center">
              <button class="op-del" @click.stop="deleteOne(row)">删除</button>
            </td>
          </tr>
          <tr v-if="rows.length===0 && !loading">
            <td :colspan="colCount" class="empty-row">暂无舆情数据</td>
          </tr>
        </tbody>
      </table>

      </div>

      <!-- Pager -->
      <div class="pager" v-if="total > 0">
        <Pager :total="total" v-model:current-page="page" :page-size="size" @current-change="onPageChange" />
      </div>
    </div>

    </template>

    <section v-else-if="scope === 'domestic'" class="review-view">
      <div class="review-head">
        <h2>AI 人工复核</h2>
        <p>AI 研判只生成候选，确认后才会进入正式事件或预警。</p>
      </div>
      <div class="review-filter">
        <button class="seg" :class="{ active: reviewStatusFilter === 'pending_review' }" @click="reviewStatusFilter = 'pending_review'; loadReviews()">待复核</button>
        <button class="seg" :class="{ active: reviewStatusFilter === 'confirmed' }" @click="reviewStatusFilter = 'confirmed'; loadReviews()">已确认</button>
        <button class="seg" :class="{ active: reviewStatusFilter === 'rejected' }" @click="reviewStatusFilter = 'rejected'; loadReviews()">已驳回</button>
        <button class="seg" :class="{ active: reviewStatusFilter === 'all' }" @click="reviewStatusFilter = 'all'; loadReviews()">全部</button>
        <span class="muted review-filter-tip">操作后不会丢失：已处理的舆情可在「已确认 / 已驳回 / 全部」中回看与追溯</span>
        <div v-if="reviewStatusFilter === 'pending_review'" class="review-batch">
          <el-dropdown trigger="click" :disabled="selectedReviewIds.size === 0" @command="onBatchCommand">
            <button class="btn btn-primary" :disabled="selectedReviewIds.size === 0">批量操作 ▾</button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="use_ai_display" :disabled="selectedReviewIds.size === 0">采用 AI 展示</el-dropdown-item>
                <el-dropdown-item command="confirm_event_change" :disabled="selectedReviewIds.size === 0">确认事件影响</el-dropdown-item>
                <el-dropdown-item command="confirm_alert_change" :disabled="selectedReviewIds.size === 0">确认预警影响</el-dropdown-item>
                <el-dropdown-item command="reject_change" :disabled="selectedReviewIds.size === 0">驳回选中（全部 AI 变更）</el-dropdown-item>
                <el-dropdown-item command="confirm_event_all" divided :disabled="reviews.length === 0">全量确认事件</el-dropdown-item>
                <el-dropdown-item command="reject_all" :disabled="reviews.length === 0">全量驳回</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <span class="muted review-toolbar-hint">先勾选左侧复选框，再从「批量操作」中选择动作</span>
        </div>
      </div>
      <div v-if="reviewsLoading" class="review-empty">加载复核记录中…</div>
      <div v-else class="card table-card review-table-card">
        <div class="tbl-scroll">
          <table class="tbl review-table">
            <thead>
              <tr>
                <th style="width:44px"><input type="checkbox" class="row-check" :checked="allReviewsSelected" @click.stop="toggleAllReviews" /></th>
                <th>舆情标题</th><th>来源</th><th>发布时间</th><th>规则风险</th><th>AI 风险</th>
                <th>展示口径</th><th>事件候选</th><th>预警候选</th><th>状态</th><th class="review-op-th">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="review in reviews" :key="review.review_id">
                <td><input type="checkbox" class="row-check" :checked="selectedReviewIds.has(review.review_id)" @click.stop="toggleReview(review)" /></td>
                <td class="review-title-cell"><button class="link-button" @click="openReviewDetail(review)">{{ review.opinion_title || `舆情 #${review.opinion_id}` }}</button></td>
                <td>{{ review.source || '-' }}</td>
                <td>{{ formatTime(review.publish_time) }}</td>
                <td><span class="risk-num">{{ review.rule_risk_snapshot?.risk_score ?? '-' }}</span></td>
                <td><span class="risk-num" :style="{ color: riskColor(review.ai_risk_snapshot?.risk_score) }">{{ review.ai_risk_snapshot?.risk_score ?? '-' }}</span></td>
                <td>{{ review.display_source === 'ai' ? 'AI 展示' : '规则展示' }}</td>
                <td class="col-center">
                  <span v-if="review.event_review_status === 'confirmed'" class="pill pill-green">已确认</span>
                  <span v-else>{{ review.event_candidate_count }}</span>
                </td>
                <td class="col-center">
                  <span v-if="review.alert_review_status === 'confirmed'" class="pill pill-green">已确认</span>
                  <span v-else>{{ review.alert_candidate_count }}</span>
                </td>
                <td><span class="pill" :class="reviewStatusPill(review.review_status)">{{ reviewStatusText(review.review_status) }}</span></td>
                <td class="review-op-cell">
                  <button class="review-op-btn" @click="decideReview(review, 'confirm_event_change')">确认事件影响</button>
                  <button class="review-op-btn" @click="decideReview(review, 'confirm_alert_change')">确认预警影响</button>
                  <el-dropdown trigger="click" @command="(cmd: string) => decideReview(review, cmd as ReviewDecision)">
                    <button class="review-op-btn" type="button">更多 ▾</button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="use_ai_display">采用 AI 展示</el-dropdown-item>
                        <el-dropdown-item command="keep_rule">保留规则风险</el-dropdown-item>
                        <el-dropdown-item command="complete_review" divided>完成复核</el-dropdown-item>
                        <el-dropdown-item command="reject_change">驳回全部 AI 变更</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </td>
              </tr>
              <tr v-if="!reviews.length"><td colspan="11" class="empty-row">暂无待复核记录</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="pager" v-if="reviewsTotal > 0">
        <Pager :total="reviewsTotal" v-model:current-page="reviewsPage" :page-size="reviewsSize" @current-change="loadReviews" />
      </div>
    </section>

    <template v-if="scope === 'domestic'">
      <BatchAIModal
        :visible="batchDialog"
        kicker="国内 AI 研判"
        title="创建批量研判任务"
        preview-endpoint="/domestic/ai-analysis/batch/preview"
        submit-endpoint="/domestic/ai-analysis/batch"
        :scope-options="domesticBatchScopeOptions"
        full-scope-value="filters"
        :selected-count="selectedIds.size"
        :build-payload="buildDomesticBatchPayload"
        @update:visible="batchDialog = $event"
        @submitted="onDomesticBatchSubmitted"
      />
      <div v-if="batchHistoryDialog" class="modal-mask" @click.self="batchHistoryDialog = false">
        <div class="modal-card compact-modal">
          <div class="modal-header"><div class="modal-title-wrap"><span class="modal-kicker">AI 研判运行记录</span><h3 class="modal-title">历史批次</h3></div><button class="modal-close" @click="batchHistoryDialog = false">✕</button></div>
          <div class="modal-body">
            <div v-for="run in batchRuns" :key="run.run_id" class="run-row"><div><b>{{ run.status }}</b><span>{{ run.processed_count }}/{{ run.total_count }}，成功 {{ run.success_count }}，失败 {{ run.failed_count }}，跳过 {{ run.skipped_count }}</span></div><code>{{ run.run_id }}</code></div>
            <p v-if="!batchRuns.length" class="review-empty">暂无运行记录</p>
          </div>
        </div>
      </div>
    </template>
    <template v-else>
      <ForeignOpinionListView v-if="foreignView === 'list'" />
      <ForeignAIReviewView v-else-if="foreignView === 'review'" />
    </template>

    <OpinionDetailModal v-model="detailVisible" :opinion-id="detailId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import type { Opinion, OpinionListResponse, DomesticAIReview, DomesticAIBatchRun } from '@/types'
import OpinionDetailModal from '@/components/OpinionDetailModal.vue'
import BatchAIModal from '@/components/BatchAIModal.vue'
import ForeignOpinionListView from '@/views/foreign/ForeignOpinionListView.vue'
import ForeignAIReviewView from '@/views/foreign/ForeignAIReviewView.vue'
import { usePermission } from '@/composables/usePermission'
import { riskColor, levelPill, levelText, sentimentPill, sentimentText, statusPill, statusText, formatTime } from '@/utils/opinion'
import { formatAdmissionHits } from '@/utils/admission'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const rows = ref<Opinion[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const sourceOptions = ref<string[]>([])
// 展示治理：管理员可勾选查看低价值内容（irrelevant / advertising），默认隐藏。
const includeLowValue = ref(false)

const contentTypeOptions = [
  { value: 'complaint', label: '投诉举报' },
  { value: 'consultation', label: '咨询求助' },
  { value: 'risk_event', label: '风险事件' },
  { value: 'public_affairs', label: '公共事务' },
  { value: 'news', label: '新闻' },
  { value: 'policy', label: '政策政务' },
]

const CONTENT_TYPE_TEXT: Record<string, string> = {
  complaint: '投诉举报',
  consultation: '咨询求助',
  risk_event: '风险事件',
  public_affairs: '公共事务',
  news: '新闻',
  policy: '政策政务',
  advertising: '广告',
  entertainment: '娱乐',
  irrelevant: '无关',
}

const filters = reactive({
  source: '',
  risk_level: '',
  level: '',
  content_type: '',
  relevance: '',
  date_from: '',
  date_to: '',
  keyword: '',
})

const detailVisible = ref(false)
const detailId = ref<number | null>(null)

type ReviewDecision = 'keep_rule' | 'use_ai_display' | 'confirm_event_change' | 'confirm_alert_change' | 'reject_change' | 'complete_review'
const activeView = ref<'opinions' | 'reviews'>('opinions')
const scope = ref<'domestic' | 'foreign'>('domestic')
const foreignView = ref<'list' | 'review'>('list')
const reviewStatusFilter = ref<string>('pending_review')
function onScopeChange() {
  if (scope.value === 'domestic') activeView.value = 'opinions'
  else foreignView.value = 'list'
}
// 支持从左侧菜单 deep-link（/opinions?scope=foreign）直接进入国外舆情视图
watch(() => route.query.scope, (val) => {
  if (val === 'foreign') scope.value = 'foreign'
  else if (val === 'domestic') scope.value = 'domestic'
}, { immediate: true })
const canAnalyze = computed(() => hasPermission('ai:analyze') || hasPermission('domestic:ai:analyze'))
const canBatchRead = computed(() => hasPermission('domestic:ai:batch:read') || isSuperuser.value)
const canCompleteReview = computed(() => hasPermission('domestic:ai:review:complete') || isSuperuser.value)
const canReviewRead = computed(() =>
  hasPermission('domestic:ai:review:read') ||
  hasPermission('domestic:events:review:read') ||
  hasPermission('domestic:alerts:review:read') ||
  isSuperuser.value,
)

const batchDialog = ref(false)
const batchHistoryDialog = ref(false)
const batchRuns = ref<DomesticAIBatchRun[]>([])
const activeRunId = ref(localStorage.getItem('domestic-ai-active-run') || '')
const activeRun = ref<DomesticAIBatchRun | null>(null)
let runPollTimer: number | null = null

const reviews = ref<DomesticAIReview[]>([])
const reviewsTotal = ref(0)
const reviewsPage = ref(1)
const reviewsSize = 10
const reviewsLoading = ref(false)
const selectedReviewIds = ref<Set<number>>(new Set())
const allReviewsSelected = computed(() => reviews.value.length > 0 && selectedReviewIds.value.size === reviews.value.length)

// ===== 情感人工校正（仅 opinions:write 角色可见编辑入口）=====
const { hasPermission, isSuperuser } = usePermission()
const canEditOpinion = computed(() => hasPermission('opinions:write'))
const sentimentOptions = [
  { value: 'positive', label: '正面' },
  { value: 'neutral', label: '中性' },
  { value: 'negative', label: '负面' },
] as const
// 当前打开的情感编辑气泡对应的舆情行 id（保证同一时刻仅一个）。
const popoverRowId = ref<number | null>(null)

function toggleSentPop(row: Opinion) {
  popoverRowId.value = popoverRowId.value === row.id ? null : row.id
}
function closeSentPop() {
  popoverRowId.value = null
}

async function chooseSentiment(row: Opinion, value: string) {
  if (!canEditOpinion.value) return
  closeSentPop()
  if (row.sentiment === value) return // 未变化，无需请求
  const oldVal = row.sentiment
  row.sentiment = value as Opinion['sentiment'] // 乐观更新
  try {
    await api.patch(`/opinions/${row.id}`, { sentiment: value })
    ElMessage.success('情感已更新')
  } catch (err: any) {
    row.sentiment = oldVal // 失败回滚
    ElMessage.error(err?.response?.data?.detail || '情感更新失败')
  }
}

// 点击气泡外部关闭（参考元素与气泡内按钮均已 @click.stop，不会冒泡到此处；
// 气泡内容区本身点击也应忽略，故放行 .sent-pop）。同时关闭批量情感气泡。
function onDocClick(e: MouseEvent) {
  if (popoverRowId.value == null && !batchPopVisible.value) return
  const t = e.target as HTMLElement | null
  if (t && t.closest('.sent-pop')) return
  closeSentPop()
  batchPopVisible.value = false
}

// ===== 批量操作（Phase 8-E）：选择 + 批量改情感 + 删除 =====
// 删除权限收紧为 admin（isSuperuser 等价于 role=='admin' 或 is_superuser）。
const canDelete = computed(() => isSuperuser.value)

const selectedIds = ref<Set<number>>(new Set())
const batchPopVisible = ref(false)
const isAllSelected = computed(
  () => rows.value.length > 0 && selectedIds.value.size === rows.value.length,
)
const isIndeterminate = computed(
  () => selectedIds.value.size > 0 && selectedIds.value.size < rows.value.length,
)
// 当前可见列数（选择列 + 操作列按权限显隐），用于空行 colspan。
const colCount = computed(
  () => 11 + (canEditOpinion.value || canDelete.value ? 1 : 0) + (canDelete.value ? 1 : 0),
)

function toggleRow(row: Opinion) {
  const next = new Set(selectedIds.value)
  if (next.has(row.id)) next.delete(row.id)
  else next.add(row.id)
  selectedIds.value = next
}
function toggleSelectAll() {
  if (isAllSelected.value) selectedIds.value = new Set()
  else selectedIds.value = new Set(rows.value.map((r) => r.id))
}
function clearSelection() {
  selectedIds.value = new Set()
}
function toggleBatchPop() {
  batchPopVisible.value = !batchPopVisible.value
}

async function batchSetSentiment(value: string) {
  if (!canEditOpinion.value || selectedIds.value.size === 0) return
  batchPopVisible.value = false
  const ids = [...selectedIds.value]
  // 乐观更新：先把选中且值不同的行本地改值，提升反馈速度
  const oldMap: Record<number, string> = {}
  rows.value.forEach((r) => {
    if (ids.includes(r.id) && r.sentiment !== value) {
      oldMap[r.id] = r.sentiment
      r.sentiment = value as Opinion['sentiment']
    }
  })
  try {
    const { data } = await api.patch('/opinions/batch', { ids, sentiment: value })
    ElMessage.success(
      `已更新 ${data.updated} 条，跳过 ${data.skipped} 条` +
        (data.failed ? `，失败 ${data.failed} 条` : ''),
    )
  } catch (err: any) {
    rows.value.forEach((r) => {
      if (oldMap[r.id] !== undefined) r.sentiment = oldMap[r.id] as Opinion['sentiment']
    })
    ElMessage.error(err?.response?.data?.detail || '批量修改情感失败')
  } finally {
    clearSelection()
    loadData() // 保持当前分页刷新
  }
}

async function batchDelete() {
  if (!canDelete.value || selectedIds.value.size === 0) return
  const ids = [...selectedIds.value]
  try {
    await ElMessageBox.confirm(
      `即将删除 ${ids.length} 条舆情\n该操作不可恢复`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    const { data } = await api.delete('/opinions/batch', { data: { ids } })
    ElMessage.success(
      `已删除 ${data.deleted} 条` + (data.not_found ? `，${data.not_found} 条不存在` : ''),
    )
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '批量删除失败')
  } finally {
    clearSelection()
    loadData()
  }
}

async function deleteOne(row: Opinion) {
  if (!canDelete.value) return
  try {
    await ElMessageBox.confirm(
      '即将删除该条舆情\n该操作不可恢复',
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await api.delete(`/opinions/${row.id}`)
    ElMessage.success('已删除')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    const next = new Set(selectedIds.value)
    next.delete(row.id)
    selectedIds.value = next
    loadData()
  }
}

function levelRange(level: string): [number | null, number | null] {
  if (level === 'high') return [70, null]
  if (level === 'mid') return [40, 69]
  if (level === 'low') return [null, 39]
  return [null, null]
}

function relevanceRange(level: string): [number | null, number | null] {
  if (level === 'high') return [60, null]
  if (level === 'low') return [40, 59]
  return [null, null]
}

function contentTypeText(type?: string | null): string {
  return type ? (CONTENT_TYPE_TEXT[type] || type) : '未标注'
}

function formatRelevance(score?: number | null): string {
  return score == null ? '-' : `${score} 分`
}

function relevanceClass(score?: number | null): string {
  if (score == null) return 'score-empty'
  if (score >= 60) return 'score-high'
  if (score >= 40) return 'score-low'
  return 'score-filtered'
}

function admissionSummary(reason?: Record<string, any> | null): string {
  if (!reason || typeof reason !== 'object') return '系统默认准入'
  const policy = String(reason.policy || '')
  if (policy === 'default_allow_non_weibo') {
    const source = String(reason.source || '')
    return source.includes('政府') || source.includes('政务') ? '政府来源默认准入' : '新闻来源默认准入'
  }
  const parts: string[] = []
  const add = (label: string, value: any) => {
    const text = formatAdmissionHits(value, 3)
    if (text) parts.push(`${label}：${text}`)
  }
  add('地域', reason.region_hits)
  add('公共事务', reason.public_hits)
  add('诉求', reason.demand_hits)
  add('风险', reason.risk_hits)
  return parts.length ? parts.join('；') : '系统默认准入'
}

async function loadSources() {
  try {
    const { data } = await api.get<string[]>('/opinions/sources')
    sourceOptions.value = Array.isArray(data) ? data : []
  } catch {
    sourceOptions.value = []
  }
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: size.value }
    if (filters.source) params.source = filters.source
    if (filters.risk_level) params.risk_level = filters.risk_level
    if (filters.content_type) params.content_type = filters.content_type
    if (filters.keyword) params.keyword = filters.keyword
    const [rmin, rmax] = levelRange(filters.level)
    if (rmin != null) params.risk_min = rmin
    if (rmax != null) params.risk_max = rmax
    const [relMin, relMax] = relevanceRange(filters.relevance)
    if (relMin != null) params.relevance_min = relMin
    if (relMax != null) params.relevance_max = relMax
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to
    if (includeLowValue.value) params.include_low_value = true
    const { data } = await api.get<OpinionListResponse>('/opinions', { params })
    rows.value = data.items
    total.value = data.total
    // 删除后当前页可能清空：若本页无数据且非首页，回退一页重载
    if (rows.value.length === 0 && page.value > 1) {
      page.value -= 1
      syncUrl()
      return loadData()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载舆情列表失败')
  } finally { loading.value = false }
}

function buildQuery(): Record<string, string> {
  const q: Record<string, string> = {}
  if (filters.source) q.source = filters.source
  if (filters.risk_level) q.risk_level = filters.risk_level
  if (filters.level) q.level = filters.level
  if (filters.content_type) q.content_type = filters.content_type
  if (filters.relevance) q.relevance = filters.relevance
  if (filters.date_from) q.date_from = filters.date_from
  if (filters.date_to) q.date_to = filters.date_to
  if (filters.keyword) q.keyword = filters.keyword
  if (page.value > 1) q.page = String(page.value)
  return q
}
let syncingUrl = false
function syncUrl() {
  syncingUrl = true
  router.replace({ query: buildQuery() }).finally(() => { syncingUrl = false })
}
function restoreFromQuery() {
  const q = route.query
  page.value = (typeof q.page === 'string' && Number(q.page) > 0) ? Number(q.page) : 1
  filters.source = typeof q.source === 'string' ? q.source : ''
  filters.risk_level = typeof q.risk_level === 'string' ? q.risk_level : ''
  filters.level = typeof q.level === 'string' ? q.level : ''
  filters.content_type = typeof q.content_type === 'string' ? q.content_type : ''
  filters.relevance = typeof q.relevance === 'string' ? q.relevance : ''
  filters.date_from = typeof q.date_from === 'string' ? q.date_from : ''
  filters.date_to = typeof q.date_to === 'string' ? q.date_to : ''
  filters.keyword = typeof q.keyword === 'string' ? q.keyword : ''
}
function handleSearch() { page.value = 1; loadData(); syncUrl() }
function handleRefresh() {
  filters.source = ''; filters.risk_level = ''; filters.level = ''
  filters.content_type = ''; filters.relevance = ''
  filters.date_from = ''; filters.date_to = ''; filters.keyword = ''
  page.value = 1; loadData(); syncUrl()
}
function onPageChange(p: number) { page.value = p; loadData(); syncUrl() }
// 支持浏览器前进/后退恢复筛选与页码（syncUrl 写回时不重复触发）
watch(() => route.query, () => {
  if (syncingUrl) return
  restoreFromQuery()
  loadData()
})

function openDetail(id: number) {
  detailId.value = id
  detailVisible.value = true
}

function domesticFiltersSnapshot() {
  const [riskMin, riskMax] = levelRange(filters.level)
  const [relevanceMin, relevanceMax] = relevanceRange(filters.relevance)
  return {
    source: filters.source || undefined,
    risk_level: filters.risk_level || undefined,
    level: filters.level || undefined,
    risk_min: riskMin ?? undefined,
    risk_max: riskMax ?? undefined,
    content_type: filters.content_type || undefined,
    relevance: filters.relevance || undefined,
    relevance_min: relevanceMin ?? undefined,
    relevance_max: relevanceMax ?? undefined,
    keyword: filters.keyword || undefined,
    q: filters.keyword || undefined,
    date_from: filters.date_from || undefined,
    date_to: filters.date_to || undefined,
    include_low_value: includeLowValue.value,
  }
}

const domesticBatchScopeOptions = [
  { value: 'recent', label: '最近采集（最近 N 条）' },
  { value: 'filters', label: '当前筛选（国内列表筛选条件）' },
  { value: 'time', label: '时间范围' },
  { value: 'selected', label: '已选中舆情' },
]

// 由 BatchAIModal 在点击「预览 / 提交」时调用，差异仅在国内承载的 filters / opinion_ids
function buildDomesticBatchPayload(form: any, fullConfirmation: boolean) {
  return {
    scope: form.scope,
    recent_n: form.recent_n,
    date_from: form.date_from || undefined,
    date_to: form.date_to || undefined,
    filters: domesticFiltersSnapshot(),
    opinion_ids: form.scope === 'selected' ? [...selectedIds.value] : undefined,
    only_unanalyzed: form.only_unanalyzed,
    force: form.force,
    full_confirmation: fullConfirmation,
  }
}

function onDomesticBatchSubmitted(data: any) {
  activeRunId.value = data.run_id
  localStorage.setItem('domestic-ai-active-run', data.run_id)
  batchDialog.value = false
  ElMessage.success(data.message || '国内 AI 研判任务已提交')
  startRunPolling()
}

function clearRunPolling() {
  if (runPollTimer != null) {
    window.clearTimeout(runPollTimer)
    runPollTimer = null
  }
}

async function pollRun() {
  if (!activeRunId.value) return
  try {
    const { data } = await api.get<DomesticAIBatchRun>(`/domestic/ai-analysis/batch/${activeRunId.value}`)
    activeRun.value = data
    if (['succeeded', 'partial_failed', 'failed', 'cancelled'].includes(data.status)) {
      clearRunPolling()
      localStorage.removeItem('domestic-ai-active-run')
      if (data.status === 'succeeded') ElMessage.success('国内 AI 批量研判已完成')
      else if (data.status === 'partial_failed') ElMessage.warning(`批量研判完成，失败 ${data.failed_count} 条`)
      return
    }
    runPollTimer = window.setTimeout(pollRun, 1500)
  } catch {
    runPollTimer = window.setTimeout(pollRun, 3000)
  }
}

function startRunPolling() {
  clearRunPolling()
  void pollRun()
}

async function openBatchHistory() {
  batchHistoryDialog.value = true
  try {
    const { data } = await api.get('/domestic/ai-analysis/batches', { params: { page: 1, size: 20 } })
    batchRuns.value = data.items || []
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载批量运行记录失败')
  }
}

async function cancelActiveRun() {
  if (!activeRunId.value) return
  try {
    await ElMessageBox.confirm('取消后尚未处理的记录将被跳过，是否继续？', '二次确认取消任务', { type: 'warning' })
    await api.post(`/domestic/ai-analysis/batch/${activeRunId.value}/cancel`)
    ElMessage.info('取消请求已提交')
    void pollRun()
  } catch (err: any) {
    if (err?.response) ElMessage.error(err?.response?.data?.detail || '取消任务失败')
  }
}

async function retryActiveRun() {
  if (!activeRunId.value) return
  try {
    const { data } = await api.post(`/domestic/ai-analysis/batch/${activeRunId.value}/retry-failed`)
    activeRunId.value = data.run_id
    localStorage.setItem('domestic-ai-active-run', data.run_id)
    ElMessage.success(data.message || '失败记录已重新提交')
    startRunPolling()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '重试失败记录失败')
  }
}

function openReviewView() {
  activeView.value = 'reviews'
  void loadReviews()
}

async function loadReviews() {
  reviewsLoading.value = true
  try {
    const { data } = await api.get('/domestic/ai-analysis/reviews', {
      params: { page: reviewsPage.value, size: reviewsSize, status: reviewStatusFilter.value === 'all' ? undefined : reviewStatusFilter.value },
    })
    reviews.value = data.items || []
    reviewsTotal.value = data.total || 0
    selectedReviewIds.value = new Set()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载人工复核列表失败')
  } finally {
    reviewsLoading.value = false
  }
}

function toggleReview(review: DomesticAIReview) {
  const next = new Set(selectedReviewIds.value)
  if (next.has(review.review_id)) next.delete(review.review_id)
  else next.add(review.review_id)
  selectedReviewIds.value = next
}

function toggleAllReviews() {
  selectedReviewIds.value = allReviewsSelected.value
    ? new Set()
    : new Set(reviews.value.map((review) => review.review_id))
}

const REVIEW_DECISION_HINT: Record<string, string> = {
  use_ai_display: '将把该舆情展示用的风险分切换为 AI 风险分（不改变正式规则风险，仅影响展示）。此操作可重复，仍在待复核。',
  keep_rule: '将保留系统规则风险分作为展示用风险。此操作可重复，仍在待复核。',
  confirm_event_change: '将为该舆情簇创建正式事件并生成正式记录。此操作可重复，仍在待复核。',
  confirm_alert_change: '将依据 AI 预警候选生成正式预警。此操作可重复，仍在待复核。',
  reject_change: '将驳回该条复核的全部 AI 变更（状态置为已驳回）。此操作不可撤销。',
  complete_review: '完成复核后该条舆情将进入「已确认」。仅关闭复核，不会自动创建事件或预警。',
}
async function decideReview(review: DomesticAIReview, decision: ReviewDecision) {
  if (review.review_status !== 'pending_review') return
  const hint = REVIEW_DECISION_HINT[decision]
  let reason = ''
  if (decision === 'complete_review') {
    try {
      const p = await ElMessageBox.prompt('可填写完成复核的说明（选填）：', '完成复核', {
        inputType: 'textarea', confirmButtonText: '确认完成', cancelButtonText: '取消',
      })
      reason = (p.value || '').trim() || ''
    } catch { return }
  } else if (hint) {
    try {
      await ElMessageBox.confirm(hint, '确认复核操作', { type: 'warning' })
    } catch { return }
  }
  try {
    const { data } = await api.post(`/domestic/ai-analysis/reviews/${review.review_id}/decision`, { decision, reason })
    const updated = data?.review
    if (updated && updated.review_status !== 'pending_review') {
      // 完成复核 / 驳回：行离开待复核
      reviews.value = reviews.value.filter((r) => r.review_id !== review.review_id)
    } else if (updated) {
      // 四个蓝色操作：仅局部刷新该行子状态与候选计数，保留在待复核
      const idx = reviews.value.findIndex((r) => r.review_id === review.review_id)
      if (idx >= 0) reviews.value[idx] = { ...reviews.value[idx], ...updated }
    } else {
      await loadReviews()
    }
    ElMessage.success(data.message || '复核已完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '复核操作失败')
  }
}

async function batchReview(decision: ReviewDecision, confirmAll = false) {
  if (!confirmAll && selectedReviewIds.value.size === 0) return
  if (reviews.value.length === 0) return
  const ids = [...selectedReviewIds.value]
  const scope = confirmAll ? '全部待复核结果' : `选中的 ${ids.length} 条复核记录`
  try {
    await ElMessageBox.confirm(`将处理${scope}。`, '确认批量复核', { type: 'warning' })
  } catch { return }
  try {
    const { data } = await api.post('/domestic/ai-analysis/reviews/batch', { review_ids: confirmAll ? undefined : ids, decision, confirm_all: confirmAll })
    ElMessage.success(`已处理 ${data.total || (confirmAll ? reviews.value.length : ids.length)} 条复核记录`)
    await loadReviews()
    window.dispatchEvent(new Event('data-refresh'))
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '批量复核失败')
  }
}

function onBatchCommand(cmd: string) {
  if (cmd === 'confirm_event_all') return batchReview('confirm_event_change', true)
  if (cmd === 'reject_all') return batchReview('reject_change', true)
  return batchReview(cmd as ReviewDecision)
}

function openReviewDetail(review: DomesticAIReview) {
  openDetail(review.opinion_id)
}

function reviewStatusText(status: string) {
  return ({ pending_review: '待复核', confirmed: '已确认', rejected: '已驳回', superseded: '已替代' } as Record<string, string>)[status] || status
}

function reviewStatusPill(status: string) {
  return ({ pending_review: 'pill-orange', confirmed: 'pill-green', rejected: 'pill-red', superseded: 'pill-gray' } as Record<string, string>)[status] || 'pill-gray'
}

onMounted(() => {
  restoreFromQuery()
  loadData()
  loadSources()
  if (activeRunId.value) startRunPolling()
  window.addEventListener('data-refresh', loadData)
  document.addEventListener('click', onDocClick)
})

onUnmounted(() => {
  clearRunPolling()
  window.removeEventListener('data-refresh', loadData)
  document.removeEventListener('click', onDocClick)
})
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
.filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; flex: 1; }
.select, .search {
  height: 42px;
  padding: 0 14px;
  font-size: 14px;
  color: #1d1d1f;
  background: #ffffff;
  border: 1px solid #d2d2d7;
  border-radius: 12px;
  outline: none;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
  box-sizing: border-box;
}
.select { min-width: 160px; }
.search { min-width: 220px; flex: 1; max-width: 320px; }
.select:focus, .search:focus {
  border-color: #0071e3;
  box-shadow: 0 0 0 4px rgba(0,113,227,0.1);
}
.date-range { display: inline-flex; align-items: center; gap: 8px; }
.date-input { min-width: 150px; padding: 0 12px; }
.date-sep { color: #86868b; font-size: 13px; }
.search-wrap { position: relative; display: inline-flex; align-items: center; flex: 1; max-width: 320px; }
.search-wrap .search { width: 100%; max-width: none; flex: none; padding-right: 34px; }
.search-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  border: none; background: transparent; color: #86868b; cursor: pointer;
  font-size: 12px; width: 22px; height: 22px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
}
.search-clear:hover { background: #e8e8ed; }

.btn { display: inline-flex; align-items: center; gap: 8px; border: none; border-radius: 980px; padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background-color 0.18s ease; }
.btn-ghost { background: #e8e8ed; color: #1d1d1f; }
.btn-ghost:hover { background: #dededf; }
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover { background: #0077ed; }
.btn-primary:disabled { opacity: 0.55; cursor: default; }
.btn-block { width: 100%; justify-content: center; }
.low-value-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 10px;
  font-size: 13px;
  color: #515154;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
}
.low-value-toggle input { width: 15px; height: 15px; accent-color: #0071e3; }

.card { background: #ffffff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05); }
.table-card {
  max-width: 100%;
  min-width: 0;
  padding: 6px 6px 14px;
  overflow: hidden;
  box-sizing: border-box;
}
.card-pad { padding: 24px 26px; }

table.tbl { width: 100%; min-width: 1686px; table-layout: fixed; border-collapse: collapse; font-size: 14px; }
table.tbl thead th {
  text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b;
  padding: 14px 18px; border-bottom: 1px solid #e8e8ed; white-space: nowrap;
}
table.tbl tbody td {
  padding: 15px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; vertical-align: middle;
}
table.tbl tbody tr { transition: background-color 0.12s ease; }
table.tbl tbody tr:hover { background: #fafafc; }
table.tbl tbody tr:last-child td { border-bottom: none; }
.col-center { text-align: center; }
.tbl-scroll {
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-x: contain;
}
.t-title {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  font-weight: 500; color: #1d1d1f;
}
.risk-num { font-weight: 600; font-variant-numeric: tabular-nums; }
.leading-check { width: 44px !important; padding-left: 8px !important; padding-right: 8px !important; }
.leading-id { width: 58px !important; padding-left: 8px !important; padding-right: 10px !important; }
.leading-title { width: 280px !important; padding-left: 10px !important; padding-right: 14px !important; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }

.pill {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px;
  border-radius: 980px; font-size: 13px; font-weight: 500; line-height: 1.4; white-space: nowrap;
}
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.pill-blue { background: #e8f1fd; color: #0071e3; }
.score-chip {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 58px; height: 26px; padding: 0 10px; border-radius: 980px;
  font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums;
}
.score-high { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.score-low { background: rgba(255,159,10,0.12); color: #c77700; }
.score-filtered { background: rgba(255,59,48,0.10); color: #ff3b30; }
.score-empty { background: rgba(110,110,115,0.12); color: #6e6e73; }
.admission-summary {
  display: inline-block; max-width: 260px; color: #515154; font-size: 13px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle;
}

.pager { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 16px 18px 0; }

/* ===== Modal ===== */
.modal-mask {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.42);
  backdrop-filter: saturate(140%) blur(2px);
  display: flex; align-items: center; justify-content: center;
  padding: 32px 20px; animation: maskIn 0.16s ease;
}
@keyframes maskIn { from { opacity: 0; } to { opacity: 1; } }
.modal-card {
  width: min(960px, 100%);
  max-height: calc(100vh - 64px);
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 24px 70px rgba(0,0,0,0.30);
  display: flex; flex-direction: column;
  overflow: hidden;
  animation: cardIn 0.18s ease;
}
@keyframes cardIn { from { transform: translateY(10px) scale(0.99); opacity: 0; } to { transform: none; opacity: 1; } }
.modal-header {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  padding: 18px 22px; border-bottom: 1px solid #e8e8ed;
}
.modal-title-wrap { min-width: 0; }
.modal-kicker { font-size: 12px; font-weight: 600; color: #86868b; letter-spacing: 0.04em; text-transform: uppercase; }
.modal-title { font-size: 18px; font-weight: 600; margin: 4px 0 0; color: #1d1d1f; line-height: 1.35; word-break: break-word; }
.modal-header-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.jump-link {
  display: inline-flex; align-items: center; gap: 6px;
  color: #0071e3; font-size: 13.5px; font-weight: 500; text-decoration: none;
  padding: 7px 14px; border-radius: 980px; background: #eaf2fd; white-space: nowrap;
  transition: background 0.15s ease;
}
.jump-link:hover { background: #dbe9fb; text-decoration: underline; }
.modal-close {
  width: 34px; height: 34px; border-radius: 50%; border: none; background: #e8e8ed;
  color: #1d1d1f; font-size: 15px; cursor: pointer; transition: background 0.15s ease;
}
.modal-close:hover { background: #dededf; }
.modal-body { padding: 18px 22px 22px; overflow-y: auto; }

.detail-grid {
  display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; align-items: start;
}
.detail-meta { display: flex; flex-wrap: wrap; gap: 8px 22px; font-size: 13px; color: #6e6e73; margin-bottom: 6px; }
.detail-divider { height: 1px; background: #e8e8ed; margin: 16px 0; }
.detail-content { font-size: 15px; line-height: 1.85; color: #2b2b2e; white-space: pre-wrap; }
.orig-p { margin: 0 0 14px; text-indent: 2em; }
.orig-p:last-child { margin-bottom: 0; }
.orig-empty { margin: 0; color: #86868b; }
.detail-foot-note { margin-top: 12px; font-size: 12.5px; color: #86868b; text-align: right; }

.ai-header { display: flex; align-items: center; justify-content: space-between; }
.section-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }
.ai-text { font-size: 14.5px; line-height: 1.7; color: #1d1d1f; }

/* Flowing judgment report */
.report-meta {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  font-size: 14px; color: #6e6e73; margin-bottom: 14px;
}
.report-meta .meta-item b { color: #1d1d1f; font-weight: 600; }
.report-meta .meta-sep { color: #d2d2d7; }
.report-body { margin-bottom: 14px; }
.report-p {
  font-size: 15px; line-height: 1.85; color: #2b2b2e;
  margin: 0 0 12px; text-indent: 2em;
}
.report-p:last-child { margin-bottom: 0; }
.report-muted { color: #86868b; text-indent: 0; }
.report-keywords { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px; }
.kw-label { font-size: 13px; color: #86868b; margin-right: 2px; }
.kw-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.kw-tag { background: #e8f1fd; color: #0071e3; padding: 5px 12px; border-radius: 980px; font-size: 13px; font-weight: 500; }
.report-time { font-size: 12.5px; color: #86868b; }
.ai-actions { margin-top: 6px; }
.ai-status-line { display: flex; align-items: center; gap: 10px; }
.spinner {
  width: 15px; height: 15px; border-radius: 50%;
  border: 2px solid #d2d2d7; border-top-color: #0071e3;
  animation: spin 0.7s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 1100px) { .detail-grid { grid-template-columns: 1fr; } }
@media (max-width: 820px) {
  .opinions { max-width: 100%; min-width: 0; overflow-x: hidden; position: relative; }
  .toolbar, .batch-bar { max-width: 100%; }
}

/* ===== 情感人工校正：可编辑胶囊 + 竖向选项气泡 ===== */
.pill.editable {
  cursor: pointer;
  position: relative;
  transition: box-shadow 0.15s ease, transform 0.12s ease;
}
.pill.editable:hover {
  box-shadow: 0 0 0 2px rgba(0,113,227,0.35);
}
.pill.editable::after {
  content: "✎";
  margin-left: 6px;
  font-size: 11px;
  opacity: 0.55;
}
.sent-pop {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px;
}
.sent-opt {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: 980px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  background: transparent;
  color: #1d1d1f;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
.sent-opt:hover { background: #f0f0f3; }
/* 用与展示胶囊一致的语义色（红/灰/绿），当前选中项加描边突出 */
.sent-opt.pill-red { background: rgba(255,59,48,0.10); color: #ff3b30; }
.sent-opt.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.sent-opt.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.sent-opt.active { border-color: rgba(0,0,0,0.25); box-shadow: 0 0 0 2px rgba(0,113,227,0.25); }

/* ===== Phase 8-E：批量操作栏 / 选择框 / 删除按钮 ===== */
.row-check { width: 16px; height: 16px; cursor: pointer; accent-color: #0071e3; vertical-align: middle; }
.batch-bar {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  margin-bottom: 14px; padding: 12px 16px;
  background: #f5f8ff; border: 1px solid #d6e4ff; border-radius: 14px;
}
.view-tabs { display: flex; gap: 4px; }
.view-tab { border: 1px solid #d2d2d7; background: #fff; color: #515154; border-radius: 10px; padding: 9px 15px; cursor: pointer; font-size: 14px; }
.view-tab.active { color: #0071e3; border-color: #9bc5f2; background: #eef6ff; font-weight: 600; }
.opinions-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.top-scope-switch { flex-shrink: 0; }
@media (max-width: 700px) {
  .opinions-head { flex-direction: column; align-items: flex-start; gap: 10px; }
}
.run-progress { margin-bottom: 14px; padding: 12px 16px; border: 1px solid #cfe1fb; background: #f5f9ff; border-radius: 12px; }
.run-failed { border-color: #ffd6d2; background: #fff8f7; }
.run-progress-head, .run-progress-meta { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.run-progress-head { justify-content: space-between; }
.run-progress-meta { margin-top: 8px; color: #6e6e73; font-size: 13px; }
.progress-track { height: 7px; margin-top: 10px; overflow: hidden; background: #dbe9fb; border-radius: 8px; }
.progress-track span { display: block; height: 100%; background: #0071e3; border-radius: inherit; transition: width .25s ease; }
.review-view { min-width: 0; }
.review-head { margin-bottom: 14px; }
.review-head h2 { margin: 0; font-size: 22px; color: #1d1d1f; }
.review-head p { margin: 6px 0 0; color: #6e6e73; font-size: 13px; }
.review-filter { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.seg { border: 1px solid #d8d8de; background: #fff; color: #515154; border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 13px; }
.seg.active { border-color: #0071e3; color: #0071e3; background: #e8f1fd; font-weight: 600; }
.review-filter-tip { color: #86868b; font-size: 12px; margin-left: 4px; }
.review-batch { margin-left: auto; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.review-toolbar-hint { color: #86868b; font-size: 12px; }
.review-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.review-table { min-width: 1280px !important; }
.review-title-cell { max-width: 280px; }
.link-button { border: 0; padding: 0; background: transparent; color: #0071e3; cursor: pointer; text-align: left; font: inherit; }
.review-title-cell .link-button { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; word-break: break-word; white-space: normal; text-align: left; }
.review-op-cell { display: flex; gap: 6px; flex-wrap: nowrap; white-space: nowrap; min-width: 520px; }
.review-op-th { min-width: 400px; text-align: left; }
.link-btn { border: 0; padding: 3px 0; background: transparent; color: #0071e3; cursor: pointer; font-size: 12px; }
.link-btn.danger { color: #ff3b30; }
.review-empty { color: #86868b; padding: 30px 0; text-align: center; }
.compact-modal { width: min(620px, 100%); }
.batch-form { display: grid; gap: 14px; }
.batch-form label { display: grid; gap: 7px; color: #515154; font-size: 13px; }
.batch-form .select { width: 100%; }
.check-line { display: flex !important; grid-template-columns: none !important; align-items: center; gap: 8px !important; }
.form-note { margin: 0; color: #6e6e73; font-size: 13px; }
.preview-box { display: grid; gap: 5px; padding: 12px 14px; border: 1px solid #dbe9fb; background: #f5f9ff; border-radius: 10px; color: #515154; font-size: 13px; }
.warning-text { color: #c77700; font-size: 13px; margin: 0; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding-top: 4px; }
.run-row { display: flex; justify-content: space-between; gap: 12px; padding: 12px 0; border-bottom: 1px solid #e8e8ed; font-size: 13px; }
.run-row span { margin-left: 12px; color: #6e6e73; }
.run-row code { color: #86868b; font-size: 11px; }
.batch-count { font-size: 14px; color: #1d1d1f; }
.batch-count b { color: #0071e3; }
.btn-danger { background: #ff3b30; color: #fff; }
.btn-danger:hover { background: #e6352b; }
.btn-danger:disabled { opacity: 0.5; cursor: default; }
.op-del {
  border: 1px solid #ffd9d6; background: #fff; color: #ff3b30;
  border-radius: 8px; padding: 5px 12px; font-size: 13px; cursor: pointer;
  transition: background 0.15s ease;
}
.op-del:hover { background: #fff0ef; }

.review-op-btn { display: inline-flex; align-items: center; border: 1px solid #d8d8de; background: #fff; color: #1d1d1f; border-radius: 7px; padding: 5px 11px; font-size: 12.5px; line-height: 1.2; cursor: pointer; white-space: nowrap; transition: border-color .15s ease, color .15s ease, background .15s ease; }
.review-op-btn:hover:not(:disabled) { border-color: #0071e3; color: #0071e3; }
.review-op-btn:disabled { opacity: .5; cursor: default; }
.review-op-btn.danger { color: #ff3b30; border-color: #f3c7c2; }
.review-op-btn.danger:hover:not(:disabled) { background: #fff8f7; border-color: #ff3b30; }
</style>
