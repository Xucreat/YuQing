<template>
  <div class="opinions" v-loading="loading">
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
        <Pager :total="total" v-model:current-page="page" :page-size="size" @current-change="loadData" />
      </div>
    </div>

    <!-- Centered floating preview modal (shared component) -->
    <OpinionDetailModal v-model="detailVisible" :opinion-id="detailId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import type { Opinion, OpinionListResponse } from '@/types'
import OpinionDetailModal from '@/components/OpinionDetailModal.vue'
import { usePermission } from '@/composables/usePermission'
import { riskColor, levelPill, levelText, sentimentPill, sentimentText, statusPill, statusText, formatTime } from '@/utils/opinion'
import { formatAdmissionHits } from '@/utils/admission'

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
      return loadData()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载舆情列表失败')
  } finally { loading.value = false }
}

function handleSearch() { page.value = 1; loadData() }
function handleRefresh() {
  filters.source = ''; filters.risk_level = ''; filters.level = ''
  filters.content_type = ''; filters.relevance = ''
  filters.date_from = ''; filters.date_to = ''; filters.keyword = ''
  page.value = 1; loadData()
}

function openDetail(id: number) {
  detailId.value = id
  detailVisible.value = true
}

onMounted(() => {
  loadData()
  loadSources()
  window.addEventListener('data-refresh', loadData)
  document.addEventListener('click', onDocClick)
})

onUnmounted(() => {
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
  .opinions { max-width: 100%; min-width: 0; overflow-x: hidden; }
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
</style>
