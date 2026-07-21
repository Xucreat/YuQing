<template>
  <div class="opinions" v-loading="loading">
    <!-- Filter bar -->
    <div class="toolbar">
      <div class="filters">
        <select v-model="filters.source" class="select" @change="handleSearch">
          <option value="">来源（全部）</option>
          <option v-for="s in sourceOptions" :key="s" :value="s">{{ s }}</option>
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
      </div>
    </div>

    <!-- Table -->
    <div class="card table-card">
      <table class="tbl">
        <thead>
          <tr>
            <th style="width:70px">ID</th>
            <th style="min-width:260px">标题</th>
            <th style="width:150px">来源</th>
            <th style="width:100px" class="col-center">情感</th>
            <th style="width:110px" class="col-center">级别</th>
            <th style="width:110px" class="col-center">风险评分</th>
            <th style="width:110px" class="col-center">分析状态</th>
            <th style="width:170px">发布时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="row.id" @click="openDetail(row.id)" style="cursor:pointer">
            <td>{{ (page - 1) * size + idx + 1 }}</td>
            <td><span class="t-title">{{ row.title }}</span></td>
            <td>{{ row.source }}</td>
            <td class="col-center">
              <span class="pill" :class="sentimentPill(row.sentiment)">
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
          </tr>
          <tr v-if="rows.length===0 && !loading">
            <td colspan="8" class="empty-row">暂无舆情数据</td>
          </tr>
        </tbody>
      </table>

      <!-- Pager -->
      <div class="pager" v-if="total > 0">
        <span class="p-info">共 {{ total }} 条</span>
        <button :disabled="page<=1" @click="page--; loadData()">‹</button>
        <button
          v-for="p in pages"
          :key="p"
          :class="{ active: p === page }"
          @click="page=p; loadData()"
        >{{ p }}</button>
        <button :disabled="page>=maxPage" @click="page++; loadData()">›</button>
      </div>
    </div>

    <!-- Centered floating preview modal (shared component) -->
    <OpinionDetailModal v-model="detailVisible" :opinion-id="detailId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { Opinion, OpinionListResponse } from '@/types'
import OpinionDetailModal from '@/components/OpinionDetailModal.vue'
import { riskColor, levelPill, levelText, sentimentPill, sentimentText, statusPill, statusText, formatTime } from '@/utils/opinion'

const loading = ref(false)
const rows = ref<Opinion[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const sourceOptions = ref<string[]>([])

const filters = reactive({
  source: '',
  risk_level: '',
  level: '',
  date_from: '',
  date_to: '',
  keyword: '',
})

const detailVisible = ref(false)
const detailId = ref<number | null>(null)

const maxPage = computed(() => Math.ceil(total.value / size.value) || 1)
const pages = computed(() => {
  const p: number[] = []
  const mp = maxPage.value
  const start = Math.max(1, page.value - 2)
  const end = Math.min(mp, page.value + 2)
  for (let i = start; i <= end; i++) p.push(i)
  return p
})

function levelRange(level: string): [number | null, number | null] {
  if (level === 'high') return [70, null]
  if (level === 'mid') return [40, 69]
  if (level === 'low') return [null, 39]
  return [null, null]
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
    if (filters.keyword) params.keyword = filters.keyword
    const [rmin, rmax] = levelRange(filters.level)
    if (rmin != null) params.risk_min = rmin
    if (rmax != null) params.risk_max = rmax
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to
    const { data } = await api.get<OpinionListResponse>('/opinions', { params })
    rows.value = data.items
    total.value = data.total
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载舆情列表失败')
  } finally { loading.value = false }
}

function handleSearch() { page.value = 1; loadData() }
function handleRefresh() {
  filters.source = ''; filters.risk_level = ''; filters.level = ''
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

.card { background: #ffffff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05); }
.table-card { padding: 6px 6px 14px; overflow: hidden; }
.card-pad { padding: 24px 26px; }

table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
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
.t-title { font-weight: 500; color: #1d1d1f; }
.risk-num { font-weight: 600; font-variant-numeric: tabular-nums; }
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

.pager { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 16px 18px 0; }
.pager .p-info { color: #86868b; font-size: 13px; margin-right: auto; }
.pager button {
  min-width: 34px; height: 34px; padding: 0 10px; border: 1px solid #d2d2d7;
  background: #ffffff; border-radius: 9px; color: #1d1d1f; font-size: 13.5px;
  cursor: pointer; transition: background 0.15s ease;
}
.pager button:hover:not(:disabled) { background: #e8e8ed; }
.pager button.active { background: #1d1d1f; color: #fff; border-color: #1d1d1f; }
.pager button:disabled { opacity: 0.4; cursor: default; }

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
</style>
