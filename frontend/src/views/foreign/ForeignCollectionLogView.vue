<template>
  <div class="cl-page" v-loading="loading">
      <!-- 当前采集任务（实时进度） -->
      <div class="live-card" v-if="live">
        <div class="live-head">
          <span class="live-title">当前采集任务</span>
          <span class="pill" :class="liveTriggerPill">{{ liveTriggerText }}</span>
          <span class="live-batch">批次 #{{ liveBatchIdShort }}</span>
        </div>
        <div class="live-elapsed">已运行 {{ fmtElapsed }}</div>
        <div class="live-stats">
          <div class="ls"><span class="num">{{ liveTotal }}</span><span class="lab">数据源</span></div>
          <div class="ls"><span class="num">{{ liveCompleted }}</span><span class="lab">已完成</span></div>
          <div class="ls"><span class="num">{{ liveRunning }}</span><span class="lab">运行中</span></div>
        </div>
        <div class="live-stats">
          <div class="ls ok"><span class="num">{{ liveSuccess }}</span><span class="lab">成功</span></div>
          <div class="ls warn"><span class="num">{{ livePartial }}</span><span class="lab">部分成功</span></div>
          <div class="ls bad"><span class="num">{{ liveFailed }}</span><span class="lab">失败</span></div>
        </div>
        <div class="live-sources" v-if="runningSources.length">
          <div class="ls-label">当前正在处理</div>
          <div class="ls-tags">
            <span class="src-tag" v-for="n in runningSources" :key="n">{{ n }}</span>
          </div>
        </div>
        <div class="live-step">{{ liveStep }}</div>
      </div>

    <div class="toolbar">
      <div class="filters">
        <el-select v-model="filterTrigger" placeholder="触发方式" clearable class="f-select" @change="reload">
          <el-option label="手动" value="manual" />
          <el-option label="定时" value="scheduled" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" clearable class="f-select" @change="reload">
          <el-option label="成功" value="success" />
          <el-option label="部分成功" value="partial" />
          <el-option label="失败" value="failed" />
          <el-option label="运行中" value="running" />
        </el-select>
        <button class="btn btn-ghost" @click="reload">刷新</button>
      </div>
      <span class="count-tip">共 {{ total }} 次采集批次</span>
    </div>

    <div class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>采集时间</th>
            <th style="width:104px">触发方式</th>
            <th style="width:84px">数据源数</th>
            <th style="width:64px">成功</th>
            <th style="width:64px">部分</th>
            <th style="width:64px">失败</th>
            <th style="width:64px">抓取</th>
            <th style="width:64px">新增</th>
            <th style="width:64px">分析</th>
            <th style="width:84px">耗时</th>
            <th style="width:84px">状态</th>
            <th style="width:100px">操作</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="b in logs" :key="b.batch_key">
            <tr class="log-row" @click="toggle(b)">
              <td>{{ formatTime(b.started_at) }}</td>
              <td>
                <span v-if="b.trigger_type === 'manual'" class="pill pill-blue">手动</span>
                <span v-else-if="b.trigger_type === 'scheduled'" class="pill pill-gray">定时</span>
                <span v-else class="pill pill-gray" title="该批次产生于采集日志功能上线前，未记录触发方式">历史</span>
              </td>
              <td>{{ b.source_count }}</td>
              <td>{{ b.success_count }}</td>
              <td>{{ b.partial_count }}</td>
              <td>{{ b.failed_count }}</td>
              <td>{{ b.fetched_raw }}</td>
              <td>{{ b.created }}</td>
              <td>{{ b.analyzed }}</td>
              <td>{{ b.duration_seconds != null ? b.duration_seconds.toFixed(1) + 's' : '—' }}</td>
              <td><span class="pill" :class="batchStatusPill(b)" :title="b.status === 'running' && batchStale(b) ? '该批次存在未正常结束的记录，可能因服务中断产生' : ''">{{ batchStatusText(b) }}</span></td>
              <td><button class="btn btn-mini" @click.stop="toggle(b)">{{ expanded === b.batch_key ? '收起' : '查看明细' }}</button></td>
            </tr>
            <tr v-if="expanded === b.batch_key">
              <td colspan="12" class="detail-cell">
                <div v-loading="detailLoading" class="detail-wrap">
                  <table class="tbl hist-tbl">
                    <thead>
                      <tr>
                        <th>数据源</th>
                        <th style="width:170px">开始</th>
                        <th style="width:170px">结束</th>
                        <th style="width:90px">耗时</th>
                        <th style="width:64px">抓取</th>
                        <th style="width:64px">新增</th>
                        <th style="width:64px">分析</th>
                        <th style="width:80px">状态</th>
                        <th>错误</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="r in detail" :key="r.id">
                        <td>{{ r.collector_name }}</td>
                        <td>{{ formatTime(r.start_time) }}</td>
                        <td>{{ formatTime(r.end_time) }}</td>
                        <td>{{ dur(r) }}</td>
                        <td>{{ r.fetched_raw }}</td>
                        <td>{{ r.created }}</td>
                        <td>{{ r.analyzed }}</td>
                        <td><span class="pill" :class="runPill(r.status)">{{ runText(r.status) }}</span></td>
                        <td class="err-cell">{{ r.error_msg || '—' }}</td>
                      </tr>
                      <tr v-if="!detail.length"><td colspan="9" class="empty-row">无明细</td></tr>
                    </tbody>
                  </table>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="!logs.length && !loading"><td colspan="12" class="empty-row">暂无采集日志</td></tr>
        </tbody>
      </table>
    </div>

    <div class="pager" v-if="total > size">
      <Pager :total="total" :page-size="size" v-model:current-page="page" @current-change="onPage" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, onUnmounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { CollectionLogItem, CollectionLogListResponse, CollectorRunItem } from '@/types'
import { useCollectStore } from '@/stores/collect'

const loading = ref(false)
const logs = ref<CollectionLogItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const filterTrigger = ref<string>('')
const filterStatus = ref<string>('')

const expanded = ref<string | null>(null)
const detail = ref<CollectorRunItem[]>([])
const detailLoading = ref(false)

function runPill(s: string): string {
  const m: Record<string, string> = {
    running: 'pill-blue', success: 'pill-green', partial: 'pill-orange',
    failed: 'pill-red', error: 'pill-red', unknown: 'pill-gray',
  }
  return m[s] || 'pill-gray'
}
function runText(s: string): string {
  const m: Record<string, string> = {
    running: '运行中', success: '成功', partial: '部分成功',
    failed: '失败', error: '异常', unknown: '未知',
  }
  return m[s] || s
}
const STALE_MS = 2 * 3600 * 1000
function batchStale(b: CollectionLogItem): boolean {
  if (!b.started_at) return false
  const t = new Date(b.started_at).getTime()
  if (isNaN(t)) return false
  return Date.now() - t > STALE_MS
}
function batchStatusPill(b: CollectionLogItem): string {
  if (b.status === 'running' && batchStale(b)) return 'pill-gray'
  return runPill(b.status)
}
function batchStatusText(b: CollectionLogItem): string {
  if (b.status === 'running' && batchStale(b)) return '未完成'
  return runText(b.status)
}
function formatTime(t: string | null): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}
function dur(r: CollectorRunItem): string {
  if (!r.start_time || !r.end_time) return '—'
  const a = new Date(r.start_time).getTime()
  const b = new Date(r.end_time).getTime()
  if (isNaN(a) || isNaN(b)) return '—'
  return ((b - a) / 1000).toFixed(1) + 's'
}

async function reload() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: size.value, scope: 'foreign' }
    if (filterTrigger.value) params.trigger_type = filterTrigger.value
    if (filterStatus.value) params.status = filterStatus.value
    const { data } = await api.get<CollectionLogListResponse>('/admin/data-sources/collection-logs', { params })
    logs.value = data.items || []
    total.value = data.total || 0
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载采集日志失败')
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  reload()
}

async function toggle(b: CollectionLogItem) {
  if (expanded.value === b.batch_key) {
    expanded.value = null
    return
  }
  expanded.value = b.batch_key
  detail.value = []
  detailLoading.value = true
  try {
    const { data } = await api.get<{ items: CollectorRunItem[] }>(
      '/admin/data-sources/collection-logs/' + encodeURIComponent(b.batch_key) + '/runs',
      { params: { page: 1, size: 50, scope: 'foreign' } },
    )
    detail.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载明细失败')
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  if (collectStore.activeTaskId && collectStore.activeTaskScope === 'foreign') startLive(collectStore.activeTaskId)
  reload()
})

const collectStore = useCollectStore()

// —— 实时采集进度（当前采集任务）——
const live = ref(false)
const liveTaskId = ref<string | null>(null)
const liveBatch = ref<CollectionLogItem | null>(null)
const runningSources = ref<string[]>([])
const liveTask = ref<any>(null)
const elapsedSec = ref(0)
const batchOnly = ref(false)

const liveBatchIdShort = computed(() =>
  (collectStore.activeBatchId || liveBatch.value?.batch_id || '').slice(0, 8) || '—')
const liveTriggerText = computed(() => {
  const t = liveBatch.value?.trigger_type
  if (t === 'manual') return '手动采集'
  if (t === 'scheduled') return '定时采集'
  return '采集'
})
const liveTriggerPill = computed(() =>
  liveBatch.value?.trigger_type === 'manual' ? 'pill-blue' : 'pill-gray')
const liveTotal = computed(() => liveBatch.value?.source_count || 0)
const liveCompleted = computed(() =>
  (liveBatch.value?.success_count || 0) + (liveBatch.value?.partial_count || 0) + (liveBatch.value?.failed_count || 0))
const liveRunning = computed(() => {
  const b = liveBatch.value
  if (!b) return 0
  if (typeof b.running_count === 'number') return b.running_count
  return Math.max(0, (b.source_count || 0) - (b.success_count || 0) - (b.partial_count || 0) - (b.failed_count || 0))
})
const liveSuccess = computed(() => liveBatch.value?.success_count || 0)
const livePartial = computed(() => liveBatch.value?.partial_count || 0)
const liveFailed = computed(() => liveBatch.value?.failed_count || 0)
const liveStep = computed(() => liveTask.value?.step || '采集中…')
const fmtElapsed = computed(() => {
  const sec = elapsedSec.value
  const m = Math.floor(sec / 60)
  const ss = sec % 60
  return String(m).padStart(2, '0') + ':' + String(ss).padStart(2, '0')
})

let taskTimer: any = null
let batchTimer: any = null
let elapsedTimer: any = null

function clearLiveTimers() {
  if (taskTimer) { clearTimeout(taskTimer); taskTimer = null }
  if (batchTimer) { clearTimeout(batchTimer); batchTimer = null }
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}
function stopLive() {
  live.value = false
  clearLiveTimers()
}
function updateElapsed() {
  if (!liveBatch.value || !liveBatch.value.started_at) return
  const t = new Date(liveBatch.value.started_at).getTime()
  if (isNaN(t)) return
  elapsedSec.value = Math.max(0, Math.floor((Date.now() - t) / 1000))
}
function scheduleElapsed() {
  elapsedTimer = setInterval(() => { if (live.value) updateElapsed() }, 1000)
}
function scheduleTaskPoll() {
  taskTimer = setTimeout(async () => {
    if (!live.value) return
    try {
      const { data } = await api.get('/tasks/' + liveTaskId.value)
      liveTask.value = data
      if (data.batch_id && !collectStore.activeBatchId) collectStore.setBatchId(data.batch_id)
      if (data.status === 'success') { finishLive(); return }
      if (data.status === 'failed') {
        const err = (data.error || data.message || '') + ''
        if (err.includes('frequently') || err.includes('CollectorThrottled')) {
          ElMessage.warning('采集操作过于频繁，请稍后再试。')
        } else {
          ElMessage.error('采集失败：' + (data.error || data.message || '未知错误'))
        }
        finishLive(); return
      }
      if (data.batch_id && !batchTimer) scheduleBatchPoll(data.batch_id)
      scheduleTaskPoll()
    } catch (e: any) {
      const st = e?.response?.status
      if (st === 404) {
        if (collectStore.activeBatchId) {
          batchOnly.value = true
          if (!batchTimer) scheduleBatchPoll(collectStore.activeBatchId)
        } else {
          finishLive()
        }
        return
      }
      if (st === 401) { stopLive(); return }
      scheduleTaskPoll()
    }
  }, 1500)
}
function scheduleBatchPoll(batchId: string) {
  batchTimer = setTimeout(async () => {
    if (!live.value) return
    try {
      const { data: running } = await api.get<CollectionLogListResponse>(
        '/admin/data-sources/collection-logs', { params: { size: 100, scope: 'foreign' } })
      const item = (running.items || []).find((b) => b.batch_id === batchId) || null
      if (item) {
        liveBatch.value = item
        updateElapsed()
        const { data: runs } = await api.get<{ items: CollectorRunItem[] }>(
          '/admin/data-sources/collection-logs/' + encodeURIComponent(batchId) + '/runs',
          { params: { page: 1, size: 50, scope: 'foreign' } })
        runningSources.value = (runs.items || [])
          .filter((r) => r.status === 'running')
          .map((r) => r.collector_name)
        scheduleBatchPoll(batchId)
        return
      }
      if (batchOnly.value) { finishLive(); return }
      if (liveTask.value && liveTask.value.status === 'running') {
        // 采集源已全部完成，正在自动聚合事件：保留上次计数，等待 task 终态
        batchTimer = null
        return
      }
      if (!liveTask.value) { scheduleBatchPoll(batchId); return }
      finishLive()
    } catch (e: any) {
      const st = e?.response?.status
      if (st === 401) { stopLive(); return }
      if (st === 404) { batchTimer = null; return }
      scheduleBatchPoll(batchId)
    }
  }, 2000)
}
function startLive(taskId: string) {
  if (live.value && liveTaskId.value === taskId) return
  stopLive()
  live.value = true
  liveTaskId.value = taskId
  liveBatch.value = null
  runningSources.value = []
  liveTask.value = null
  elapsedSec.value = 0
  batchOnly.value = false
  scheduleTaskPoll()
  scheduleElapsed()
}
function finishLive() {
  stopLive()
  collectStore.clear()
  setTimeout(() => { reload() }, 400)
}

watch(() => collectStore.activeTaskId, (id) => {
  if (id && id !== liveTaskId.value && collectStore.activeTaskScope === 'foreign') startLive(id)
})

onUnmounted(stopLive)

</script>

<style scoped>
.cl-page { min-height: 100%; }
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; gap: 12px; flex-wrap: wrap; }
.filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.f-select { width: 150px; }
.count-tip { font-size: 13px; color: #86868b; }

.card {
  background: #fff; border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 12px 32px rgba(0,0,0,.05);
  padding: 6px 6px 14px; overflow-x: auto;
}
table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
table.tbl thead th {
  text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b;
  padding: 14px 18px; border-bottom: 1px solid #e8e8ed;
}
table.tbl tbody td { padding: 13px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; vertical-align: middle; }
table.tbl tbody tr:last-child td { border-bottom: none; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }
.log-row { cursor: pointer; }
.log-row:hover { background: #fafafa; }

.ds-name { font-size: 14px; font-weight: 600; color: #1d1d1f; }
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; border-radius: 980px; font-size: 12px; font-weight: 500;
}
.pill-blue { background: rgba(0,122,255,0.1); color: #007aff; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.err-cell { color: #ff3b30; font-size: 12.5px; max-width: 320px; }
.muted { color: #b0b0b5; }

.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
.btn {
  display: inline-flex; align-items: center; justify-content: center;
  border: none; border-radius: 980px; padding: 8px 16px; font-size: 14px;
  font-weight: 500; cursor: pointer; transition: background-color .18s, opacity .18s;
}
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover { background: #0077ed; }
.btn-primary:disabled { opacity: .55; cursor: default; }
.btn-ghost { background: #f5f5f7; color: #1d1d1f; }
.btn-ghost:hover { background: #e8e8ed; }
.btn-mini { background: transparent; color: #0071e3; padding: 4px 10px; font-size: 13px; }
.btn-mini:hover { background: #e8f1fd; }

.detail-cell { background: #fafafc; padding: 0 !important; }
.detail-wrap { padding: 6px 18px 16px; max-height: 50vh; overflow: auto; }
.hist-tbl td, .hist-tbl th { white-space: nowrap; }
.hist-tbl thead th {
  position: sticky; top: 0; z-index: 2; background: #fafafc; border-bottom: 1px solid #e8e8ed;
}
.hist-tbl td { padding: 11px 18px; }
.detail-wrap::-webkit-scrollbar { width: 8px; height: 8px; }
.detail-wrap::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 8px; }
.detail-wrap::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.32); }
.detail-wrap::-webkit-scrollbar-track { background: transparent; }

.live-card {
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 12px 32px rgba(0,0,0,.05);
  padding: 18px 22px;
  margin-bottom: 18px;
  border: 1px solid #e8f1fd;
}
.live-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.live-title { font-size: 15px; font-weight: 600; color: #1d1d1f; }
.live-batch { font-size: 12.5px; color: #86868b; margin-left: auto; font-variant-numeric: tabular-nums; }
.live-elapsed { font-size: 13px; color: #007aff; font-weight: 500; margin-bottom: 12px; font-variant-numeric: tabular-nums; }
.live-stats { display: flex; gap: 26px; flex-wrap: wrap; margin-bottom: 8px; }
.live-stats .ls { display: flex; flex-direction: column; gap: 2px; }
.live-stats .num { font-size: 20px; font-weight: 600; color: #1d1d1f; font-variant-numeric: tabular-nums; }
.live-stats .lab { font-size: 12px; color: #86868b; }
.live-stats .ok .num { color: #1a8e3c; }
.live-stats .warn .num { color: #c77700; }
.live-stats .bad .num { color: #ff3b30; }
.live-sources { margin-top: 10px; }
.ls-label { font-size: 12px; color: #86868b; margin-bottom: 6px; }
.ls-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.src-tag { background: rgba(0,122,255,0.08); color: #007aff; padding: 3px 10px; border-radius: 980px; font-size: 12.5px; }
.live-step { margin-top: 12px; font-size: 13px; color: #1d1d1f; background: #f5f5f7; border-radius: 10px; padding: 8px 12px; }
</style>
