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
            <th style="width:110px" class="col-center">风险评分</th>
            <th style="width:110px" class="col-center">分析状态</th>
            <th style="width:170px">发布时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" @click="goDetail(row.id)" style="cursor:pointer">
            <td>{{ row.id }}</td>
            <td><span class="t-title">{{ row.title }}</span></td>
            <td>{{ row.source }}</td>
            <td class="col-center">
              <span class="pill" :class="sentimentPill(row.sentiment)">
                <span class="dot"></span>{{ sentimentText(row.sentiment) }}
              </span>
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
            <td colspan="7" class="empty-row">暂无舆情数据</td>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { Opinion, OpinionListResponse } from '@/types'

const router = useRouter()

const loading = ref(false)
const rows = ref<Opinion[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const sourceOptions = ref<string[]>([])

const filters = reactive({
  source: '',
  risk_level: '',
  keyword: '',
})

const maxPage = computed(() => Math.ceil(total.value / size.value) || 1)
const pages = computed(() => {
  const p: number[] = []
  const mp = maxPage.value
  const start = Math.max(1, page.value - 2)
  const end = Math.min(mp, page.value + 2)
  for (let i = start; i <= end; i++) p.push(i)
  return p
})

function riskColor(score: number): string {
  if (score >= 70) return '#ff3b30'
  if (score >= 40) return '#ff9f0a'
  return '#34c759'
}

function sentimentPill(s: string): string {
  return { negative: 'pill-red', positive: 'pill-green', neutral: 'pill-gray' }[s] || 'pill-gray'
}
function sentimentText(s: string): string {
  return { negative: '负面', positive: '正面', neutral: '中性' }[s] || s
}

function statusPill(s: string): string {
  return ({ completed: 'pill-green', failed: 'pill-red', processing: 'pill-orange', pending: 'pill-gray' } as const)[s] || 'pill-gray'
}
function statusText(s: string): string {
  return ({ completed: '已完成', failed: '失败', processing: '分析中', pending: '待分析' } as const)[s] || s
}

function formatTime(t: string | null): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: size.value }
    if (filters.source) params.source = filters.source
    if (filters.risk_level) params.risk_level = filters.risk_level
    if (filters.keyword) params.keyword = filters.keyword
    const { data } = await api.get<OpinionListResponse>('/opinions', { params })
    rows.value = data.items
    total.value = data.total
    const set = new Set(sourceOptions.value)
    data.items.forEach(o => o.source && set.add(o.source))
    sourceOptions.value = Array.from(set)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载舆情列表失败')
  } finally { loading.value = false }
}

function handleSearch() { page.value = 1; loadData() }
function handleRefresh() {
  filters.source = ''; filters.risk_level = ''; filters.keyword = ''
  page.value = 1; loadData()
}
function goDetail(id: number) { router.push('/opinion/' + id) }

onMounted(() => {
  loadData()
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

.card { background: #ffffff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05); }
.table-card { padding: 6px 6px 14px; overflow: hidden; }

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
</style>
