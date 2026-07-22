<template>
  <div class="events" v-loading="loading">
    <div class="toolbar">
      <!-- 搜索框（苹果风：内嵌图标 + 毛玻璃 + 蓝色聚焦环） -->
      <div class="search-box" :class="{ 'is-focused': searchFocused }">
        <svg class="search-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="7"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input
          class="search-input"
          v-model="title"
          type="text"
          placeholder="搜索事件标题"
          @focus="searchFocused = true"
          @blur="searchFocused = false"
          @input="onSearchInput"
          @keydown.enter="onSearchEnter"
        />
        <transition name="fade">
          <button v-if="title" class="search-clear" title="清除" @click="clearSearch" @mousedown.prevent>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </transition>
      </div>

      <!-- 风险等级筛选（自定义苹果风下拉：毛玻璃浮层 + 平滑展开 + 选中勾选） -->
      <div class="risk-filter">
        <button class="risk-trigger" :class="{ open: riskOpen, active: !!riskFilter }" @click="riskOpen = !riskOpen" @keydown.esc="riskOpen = false">
          <span class="risk-trigger-label">
            <span v-if="riskFilter" class="risk-trigger-dot" :class="'dot-' + riskFilter"></span>
            {{ riskLabel }}
          </span>
          <svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>
        <div v-if="riskOpen" class="risk-backdrop" @click="riskOpen = false"></div>
        <transition name="pop">
          <div v-if="riskOpen" class="risk-menu" role="listbox">
            <button
              v-for="opt in riskOptions"
              :key="opt.value"
              class="risk-opt"
              :class="{ active: riskFilter === opt.value }"
              @click="selectRisk(opt.value)"
            >
              <span v-if="opt.value" class="risk-opt-dot" :class="'dot-' + opt.value"></span>
              <span class="risk-opt-text">{{ opt.label }}</span>
              <svg v-if="riskFilter === opt.value" class="check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </button>
          </div>
        </transition>
      </div>

      <button class="btn btn-ghost" :disabled="aggregating" @click="handleAggregate">{{ aggregating ? '聚合中...' : '手动聚合' }}</button>
      <button class="btn btn-ghost" @click="loadData">刷新</button>
      <span v-if="lastResult" class="agg-result">
        聚合成功：新建 {{ lastResult.created }} · 更新 {{ lastResult.updated }} · 关联 {{ lastResult.linked }}
      </span>
    </div>

    <div class="card table-card">
      <table class="tbl">
        <thead>
          <tr>
            <th style="width:70px">ID</th>
            <th style="min-width:280px">事件标题</th>
            <th style="width:120px" class="col-center">风险等级</th>
            <th style="width:120px" class="col-center">关联舆情</th>
            <th style="width:100px" class="col-center">状态</th>
            <th style="width:170px">首次发现</th>
            <th style="width:170px">最后更新</th>
            <th style="width:80px" class="col-center">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="row.id" @click="$router.push('/event/' + row.id)" style="cursor:pointer">
            <td>{{ (page - 1) * size + idx + 1 }}</td>
            <td><span class="t-title">{{ row.title }}</span></td>
            <td class="col-center">
              <span class="pill" :class="riskPill(row.risk_level)"><span class="dot"></span>{{ riskText(row.risk_level) }}</span>
            </td>
            <td class="col-center risk-num">{{ row.opinion_count }}</td>
            <td class="col-center"><span class="pill" :class="statusPill(row.status)"><span class="dot"></span>{{ statusText(row.status) }}</span></td>
            <td>{{ formatTime(row.first_time) }}</td>
            <td>{{ formatTime(row.last_time) }}</td>
            <td class="col-center" @click.stop>
              <button class="btn-icon btn-delete" title="删除事件" @click="handleDelete(row)">🗑</button>
            </td>
          </tr>
          <tr v-if="rows.length===0 && !loading">
            <td colspan="8" class="empty-row">暂无事件数据</td>
          </tr>
        </tbody>
      </table>

      <div class="pager" v-if="total > 0">
        <span class="p-info">共 {{ total }} 条</span>
        <button :disabled="page<=1" @click="page--; loadData()">‹</button>
        <button v-for="p in pages" :key="p" :class="{ active: p === page }" @click="page=p; loadData()">{{ p }}</button>
        <button :disabled="page>=maxPage" @click="page++; loadData()">›</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { pollTask } from '@/api'
import type { EventItem, EventListResponse, EventCreateResponse } from '@/types'

const loading = ref(false)
const aggregating = ref(false)
const rows = ref<EventItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const lastResult = ref<EventCreateResponse | null>(null)
const title = ref('')          // 标题搜索关键字
const riskFilter = ref('')     // 风险等级筛选：''=全部 / low / medium / high
const searchFocused = ref(false) // 搜索框聚焦态（驱动苹果蓝聚焦环）
const riskOpen = ref(false)      // 风险下拉浮层开合
const riskOptions = [
  { value: '', label: '全部风险' },
  { value: 'low', label: '低风险' },
  { value: 'medium', label: '中风险' },
  { value: 'high', label: '高风险' },
]
const riskLabel = computed(() => (riskOptions.find((o) => o.value === riskFilter.value) || riskOptions[0]).label)
let searchTimer: number | undefined

const maxPage = computed(() => Math.ceil(total.value / size.value) || 1)
const pages = computed(() => {
  const p: number[] = []
  const mp = maxPage.value
  const start = Math.max(1, page.value - 2)
  const end = Math.min(mp, page.value + 2)
  for (let i = start; i <= end; i++) p.push(i)
  return p
})

function riskPill(level: string): string {
  return ({ high: 'pill-red', medium: 'pill-orange', low: 'pill-green' } as const)[level] || 'pill-gray'
}
function riskText(level: string): string { return { high: '高风险', medium: '中风险', low: '低风险' }[level] || level }
function statusText(s: string): string {
  return ({ active: '进行中', resolved: '已处置', monitoring: '监测中', closed: '已关闭' } as const)[s] || s
}
function statusPill(s: string): string {
  return ({ active: 'pill-green', resolved: 'pill-gray', monitoring: 'pill-orange', closed: 'pill-gray' } as const)[s] || 'pill-gray'
}
function formatTime(t: string | null): string { if (!t) return '-'; return t.replace('T', ' ').slice(0, 19) }

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, size: size.value }
    const kw = title.value.trim()
    if (kw) params.title = kw
    if (riskFilter.value) params.risk_level = riskFilter.value
    const { data } = await api.get<EventListResponse>('/events', { params })
    rows.value = data.items; total.value = data.total
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '加载事件列表失败') } finally { loading.value = false }
}

// 标题搜索：输入防抖 350ms，避免每次按键都打接口；变化时回到第 1 页。
function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => { page.value = 1; loadData() }, 350)
}
function clearSearch() {
  title.value = ''
  page.value = 1
  loadData()
}
// 回车立即搜索（不走防抖），给到即时的苹果式反馈。
function onSearchEnter() {
  if (searchTimer) clearTimeout(searchTimer)
  page.value = 1
  loadData()
}
// 风险等级筛选：选中即关闭浮层、回到第 1 页重新查询。
function selectRisk(v: string) {
  riskFilter.value = v
  riskOpen.value = false
  page.value = 1
  loadData()
}

async function handleAggregate() {
  if (aggregating.value) return
  aggregating.value = true
  try {
    // 聚合改为后台任务：接口立即返回 task_id，前端轮询进度直到完成。
    const { data } = await api.post<{ task_id: string }>('/events/aggregate')
    ElMessage.info('聚合任务已启动，后台运行中…')
    const res = await pollTask(data.task_id)
    if (res.status === 'success') {
      const r = res.result || {}
      lastResult.value = r as EventCreateResponse
      const tag = r.incremental ? '（增量）' : ''
      ElMessage.success('聚合完成' + tag + '：新建 ' + r.created + '，更新 ' + r.updated + '，关联 ' + r.linked)
      page.value = 1; await loadData()
    } else if (res.status === 'failed') {
      ElMessage.error('聚合失败：' + (res.error || res.message || '未知错误'))
    }
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '聚合失败') } finally { aggregating.value = false }
}

async function handleDelete(row: EventItem) {
  try {
    const { ElMessageBox } = await import('element-plus')
    await ElMessageBox.confirm(
      `确认删除事件「${row.title}」？关联的舆情不会被删除，仅解除关联。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.delete('/events/' + row.id)
    ElMessage.success('事件已删除')
    await loadData()
  } catch { /* cancelled or error */ }
}

onMounted(loadData)
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; position: relative; z-index: 30; }
.agg-result { font-size: 13px; color: #34c759; margin-left: 8px; }
.btn { display: inline-flex; align-items: center; gap: 8px; border: none; border-radius: 980px; padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background-color 0.18s ease; }
.btn-ghost { background: #e8e8ed; color: #1d1d1f; }
.btn-ghost:hover { background: #dededf; }

/* ── 苹果风搜索框：毛玻璃 + 蓝色聚焦环 + 线性图标 ── */
.search-box {
  display: inline-flex; align-items: center; gap: 8px;
  height: 40px; min-width: 264px; padding: 0 14px;
  background: rgba(245,245,247,0.72);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 12px;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}
.search-box.is-focused {
  background: rgba(255,255,255,0.92);
  border-color: #0071e3;
  box-shadow: 0 0 0 4px rgba(0,113,227,0.18);
}
.search-ico { width: 16px; height: 16px; color: #8e8e93; flex: none; }
.search-input {
  flex: 1; min-width: 0; height: 100%;
  border: none; outline: none; background: transparent;
  font-size: 14px; color: #1d1d1f;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.search-input::placeholder { color: #a1a1a6; }
.search-clear {
  display: inline-flex; align-items: center; justify-content: center;
  flex: none; width: 20px; height: 20px; padding: 0;
  border: none; border-radius: 50%; background: rgba(0,0,0,0.16); color: #fff; cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}
.search-clear:hover { background: rgba(0,0,0,0.28); }
.search-clear svg { width: 12px; height: 12px; }

/* ── 苹果风风险筛选下拉：毛玻璃浮层 + 平滑展开 + 选中勾选 ── */
.risk-filter { position: relative; }
.risk-trigger {
  display: inline-flex; align-items: center; gap: 8px;
  height: 40px; padding: 0 14px;
  background: rgba(245,245,247,0.72);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 12px;
  font-size: 14px; font-weight: 500; color: #1d1d1f; cursor: pointer; white-space: nowrap;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease, color 0.2s ease;
}
.risk-trigger:hover { background: rgba(255,255,255,0.92); }
.risk-trigger.open { border-color: #0071e3; box-shadow: 0 0 0 4px rgba(0,113,227,0.18); }
.risk-trigger.active { color: #0071e3; }
.risk-trigger-label { display: inline-flex; align-items: center; gap: 7px; }
.risk-trigger-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.chev { width: 15px; height: 15px; color: #8e8e93; flex: none; transition: transform 0.25s cubic-bezier(0.16,1,0.3,1); }
.risk-trigger.open .chev { transform: rotate(180deg); }

.risk-backdrop { position: fixed; inset: 0; z-index: 40; }
.risk-menu {
  position: absolute; top: calc(100% + 8px); left: 0; z-index: 50;
  min-width: 184px; padding: 6px;
  background: rgba(250,250,252,0.92);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 14px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.14);
  transform-origin: top left;
}
.risk-opt {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 9px 12px; border: none; background: transparent;
  border-radius: 9px; font-size: 14px; color: #1d1d1f; cursor: pointer; text-align: left; font-family: inherit;
  transition: background 0.12s ease;
}
.risk-opt:hover { background: rgba(0,0,0,0.05); }
.risk-opt.active { color: #0071e3; font-weight: 600; }
.risk-opt-text { flex: 1; }
.risk-opt-dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
.dot-low { background: #34c759; }
.dot-medium { background: #ff9f0a; }
.dot-high { background: #ff3b30; }
.check { width: 16px; height: 16px; color: #0071e3; flex: none; }

/* 过渡动画 */
.fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.pop-enter-active, .pop-leave-active { transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.16,1,0.3,1); }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(-8px) scale(0.97); }

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

.btn-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border: none; border-radius: 8px;
  background: transparent; cursor: pointer; font-size: 16px;
  transition: background 0.15s ease;
}
.btn-delete:hover { background: rgba(255,59,48,0.1); }
</style>
