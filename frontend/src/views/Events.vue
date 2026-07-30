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

      <input
        v-model="regionFilter"
        class="compact-input"
        type="number"
        min="1"
        placeholder="地区 ID"
        title="按地区 ID 筛选"
        @change="applyFilters"
      />
      <select v-model="topicFilter" class="compact-select" title="按主题筛选" @change="applyFilters">
        <option value="">全部主题</option>
        <option v-for="option in topicOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <select v-model="statusFilter" class="compact-select" title="按处置状态筛选" @change="applyFilters">
        <option value="">全部处置状态</option>
        <option v-for="option in EVENT_STATUS_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <select v-model="trendFilter" class="compact-select" title="按趋势筛选" @change="applyFilters">
        <option value="">全部趋势</option>
        <option value="rising">↑ 升温</option>
        <option value="stable">→ 平稳</option>
        <option value="falling">↓ 下降</option>
        <option value="unknown">未知</option>
      </select>
      <input
        v-model="heatMin"
        class="compact-input heat-input"
        type="number"
        min="0"
        max="100"
        placeholder="热度 ≥"
        title="最低热度"
        @change="applyFilters"
      />
      <input
        v-model="heatMax"
        class="compact-input heat-input"
        type="number"
        min="0"
        max="100"
        placeholder="热度 ≤"
        title="最高热度"
        @change="applyFilters"
      />

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
            <th style="width:280px">事件标题</th>
            <th style="width:110px">主题</th>
            <th style="width:110px" class="col-center">风险等级</th>
            <th style="width:80px" class="col-center">风险分</th>
            <th style="width:80px" class="col-center">热度</th>
            <th style="width:90px" class="col-center">趋势</th>
            <th style="width:100px" class="col-center">关联舆情</th>
            <th style="width:100px" class="col-center">处置状态</th>
            <th style="width:190px">首次发现</th>
            <th style="width:190px">最后更新</th>
            <th class="col-center operation-col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="row.id" @click="$router.push('/event/' + row.id)" style="cursor:pointer">
            <td>{{ (page - 1) * size + idx + 1 }}</td>
            <td><span class="t-title">{{ row.title }}</span></td>
            <td class="nowrap">{{ topicText(row.topic_category) }}</td>
            <td class="col-center">
              <span class="pill" :class="riskPill(row.risk_level)"><span class="dot"></span>{{ riskText(row.risk_level) }}</span>
              <span v-if="isKeyEvent(row)" class="focus-mark">重点关注</span>
            </td>
            <td class="col-center risk-num" :style="{ color: riskColor(row.risk_score) }">{{ row.risk_score }}</td>
            <td class="col-center risk-num">{{ row.heat_score }}</td>
            <td class="col-center">
              <span class="pill" :class="trendPill(row.trend)">{{ trendText(row.trend) }}</span>
            </td>
            <td class="col-center risk-num">{{ row.opinion_count }}</td>
            <td class="col-center"><span class="pill" :class="eventStatusPill(row.status)"><span class="dot"></span>{{ eventStatusLabel(row.status) }}</span></td>
            <td class="nowrap">{{ formatTime(row.first_time) }}</td>
            <td class="nowrap">{{ formatTime(row.last_time) }}</td>
            <td class="col-center operation-col" @click.stop>
              <div class="row-actions">
                <button class="btn-operate" title="打开事件处置弹窗" @click.stop="openHandle(row)">处置</button>
                <button class="btn-icon btn-delete" title="删除事件" @click="handleDelete(row)">🗑</button>
              </div>
            </td>
          </tr>
          <tr v-if="rows.length===0 && !loading">
            <td colspan="12" class="empty-row">暂无事件数据</td>
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

    <el-dialog
      v-model="handleDialogVisible"
      title="事件处置"
      width="820px"
      top="6vh"
      :close-on-click-modal="true"
      class="op-dialog"
    >
      <div v-if="handleEvent" class="op-modal-body">
        <div class="op-left">
          <div class="operation-header">
            <div>
              <h3 class="section-title">事件处置</h3>
              <div class="operation-current">
                当前处置状态
                <span class="pill" :class="eventStatusPill(handleEvent.status)">{{ eventStatusLabel(handleEvent.status) }}</span>
              </div>
            </div>
          </div>

          <div v-if="canUpdateEvent" class="status-actions" aria-label="变更事件处置状态">
            <button
              v-for="option in EVENT_STATUS_OPTIONS"
              :key="option.value"
              class="status-button"
              :class="{ current: handleEvent.status === option.value }"
              :disabled="savingStatus || !canChangeStatus(option.value)"
              @click="changeStatus(option.value)"
            >
              {{ option.label }}
            </button>
          </div>

          <div v-if="canUpdateEvent" class="note-editor">
            <textarea
              v-model="noteContent"
              maxlength="5000"
              rows="3"
              placeholder="填写核查、联络或处置进展"
              :disabled="savingNote"
            ></textarea>
            <div class="note-submit-row">
              <span>{{ noteContent.length }}/5000</span>
              <button class="btn btn-primary" :disabled="savingNote || !noteContent.trim()" @click="addNote">
                {{ savingNote ? '提交中' : '添加备注' }}
              </button>
            </div>
          </div>
        </div>

        <div class="op-right">
          <div class="op-right-title">
            处置记录<span class="op-count">{{ handleEvent.actions.length }}</span>
          </div>
          <div class="op-right-scroll">
            <div class="action-timeline">
              <div v-for="action in handleEvent.actions" :key="action.id" class="timeline-item">
                <span class="timeline-dot"></span>
                <div class="timeline-body">
                  <div class="timeline-meta">
                    <time>{{ formatTime(action.created_at) }}</time>
                    <strong>{{ action.username || (action.user_id ? `用户 ${action.user_id}` : '系统') }}</strong>
                    <span>{{ actionTypeText(action.action_type) }}</span>
                  </div>
                  <div class="timeline-content">
                    <template v-if="action.action_type === 'status_change' && action.old_status && action.new_status">
                      {{ eventStatusLabel(action.old_status) }} → {{ eventStatusLabel(action.new_status) }}
                    </template>
                    <template v-else>{{ action.content }}</template>
                  </div>
                </div>
              </div>
              <div v-if="handleEvent.actions.length === 0" class="timeline-empty">暂无处置记录</div>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="op-loading">加载中…</div>
      <template #footer>
        <button class="btn btn-ghost" @click="handleDialogVisible = false">关闭</button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { pollTask } from '@/api'
import type { EventItem, EventListResponse, EventCreateResponse, EventActionItem } from '@/types'
import { EVENT_STATUS_OPTIONS, eventStatusLabel, eventStatusPill } from '@/utils/event'
import { usePermission } from '@/composables/usePermission'

const loading = ref(false)
const aggregating = ref(false)
const rows = ref<EventItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const lastResult = ref<EventCreateResponse | null>(null)
const title = ref('')          // 标题搜索关键字
const riskFilter = ref('')     // 风险等级筛选：''=全部 / low / medium / high
const regionFilter = ref('')
const topicFilter = ref('')
const statusFilter = ref('')
const trendFilter = ref('')
const heatMin = ref('')
const heatMax = ref('')
const searchFocused = ref(false) // 搜索框聚焦态（驱动苹果蓝聚焦环）
const riskOpen = ref(false)      // 风险下拉浮层开合

// 事件处置弹窗（点击列表“处置”按钮唤起）
interface HandleEvent { id: number; status: string; actions: EventActionItem[] }
const handleDialogVisible = ref(false)
const handleEventId = ref<number | null>(null)
const handleEvent = ref<HandleEvent | null>(null)
const savingStatus = ref(false)
const savingNote = ref(false)
const noteContent = ref('')
const { hasPermission } = usePermission()
const canUpdateEvent = computed(() => hasPermission('events:write'))
const riskOptions = [
  { value: '', label: '全部风险' },
  { value: 'low', label: '低风险' },
  { value: 'medium', label: '中风险' },
  { value: 'high', label: '高风险' },
]
const topicOptions = [
  { value: 'livelihood', label: '民生' },
  { value: 'traffic', label: '交通' },
  { value: 'education', label: '教育' },
  { value: 'healthcare', label: '医疗卫生' },
  { value: 'environment', label: '环境' },
  { value: 'safety', label: '安全' },
  { value: 'market', label: '市场' },
  { value: 'gov_service', label: '政务服务' },
  { value: 'social_security', label: '社会保障' },
  { value: 'public_emergency', label: '公共突发事件' },
  { value: 'other', label: '其他' },
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
function topicText(value: string | null | undefined): string {
  return topicOptions.find((option) => option.value === value)?.label || '未分类'
}
function isKeyEvent(row: EventItem): boolean {
  return row.risk_score >= 70 && row.heat_score >= 60
}
function riskColor(score: number): string {
  if (score >= 70) return '#ff3b30'
  if (score >= 40) return '#c77700'
  return '#1a8e3c'
}
function trendText(value: string): string {
  return ({ rising: '↑ 升温', stable: '→ 平稳', falling: '↓ 下降', unknown: '未知' } as const)[value] || value
}
function trendPill(value: string): string {
  return ({ rising: 'pill-red', stable: 'pill-gray', falling: 'pill-green', unknown: 'pill-gray' } as const)[value] || 'pill-gray'
}
function formatTime(t: string | null): string { if (!t) return '-'; return t.replace('T', ' ').slice(0, 19) }

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, size: size.value }
    const kw = title.value.trim()
    if (kw) params.title = kw
    if (riskFilter.value) params.risk_level = riskFilter.value
    if (regionFilter.value) params.region_id = Number(regionFilter.value)
    if (topicFilter.value) params.topic_category = topicFilter.value
    if (statusFilter.value) params.status = statusFilter.value
    if (trendFilter.value) params.trend = trendFilter.value
    if (heatMin.value) params.heat_min = Number(heatMin.value)
    if (heatMax.value) params.heat_max = Number(heatMax.value)
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
function applyFilters() {
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

// ── 事件处置弹窗逻辑（与详情页一致） ──
const nextStatus: Partial<Record<string, string>> = {
  active: 'verifying', verifying: 'processing', processing: 'resolved', resolved: 'closed',
}
function actionTypeText(value: string): string {
  return ({ status_change: '状态变更', note: '备注', assign: '指派', resolve: '解决' } as Record<string, string>)[value] || value
}
function canChangeStatus(target: string): boolean {
  const current = handleEvent.value?.status
  if (!current || target === current) return false
  return target === 'active' || nextStatus[current] === target
}
function openHandle(row: EventItem) {
  handleEventId.value = row.id
  handleEvent.value = null
  handleDialogVisible.value = true
  loadHandleEvent()
}
async function loadHandleEvent() {
  if (!handleEventId.value) return
  try {
    const { data } = await api.get('/events/' + handleEventId.value)
    handleEvent.value = data
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '加载事件详情失败') }
}
async function changeStatus(target: string) {
  if (!canChangeStatus(target) || !handleEvent.value) return
  savingStatus.value = true
  try {
    await api.patch(`/events/${handleEvent.value.id}/status`, { status: target })
    ElMessage.success(`处置状态已更新为${eventStatusLabel(target)}`)
    await loadHandleEvent()
    const r = rows.value.find((x) => x.id === handleEvent.value!.id)
    if (r) r.status = target
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '更新处置状态失败') } finally { savingStatus.value = false }
}
async function addNote() {
  const content = noteContent.value.trim()
  if (!content || !handleEvent.value) return
  savingNote.value = true
  try {
    await api.post(`/events/${handleEvent.value.id}/actions`, { action_type: 'note', content })
    noteContent.value = ''
    ElMessage.success('事件备注已添加')
    await loadHandleEvent()
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '添加事件备注失败') } finally { savingNote.value = false }
}
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; position: relative; z-index: 30; }
.compact-select, .compact-input { height: 40px; padding: 0 11px; border: 1px solid rgba(0,0,0,0.08); border-radius: 10px; background: rgba(245,245,247,0.8); color: #1d1d1f; font: inherit; font-size: 13px; }
.compact-select { min-width: 112px; }
.compact-input { width: 92px; }
.heat-input { width: 76px; }
.focus-mark { display: block; width: fit-content; margin: 5px auto 0; color: #c77700; font-size: 11px; font-weight: 600; }
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
.table-card { padding: 6px 0 14px 6px; overflow-x: auto; }

table.tbl { width: 100%; min-width: 1520px; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
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
.nowrap { white-space: nowrap; }
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
.row-actions { display: flex; align-items: center; justify-content: center; gap: 6px; }
.operation-col {
  position: sticky; right: 0; z-index: 2; min-width: 110px; width: 110px;
  background: #fff; box-shadow: -10px 0 14px -14px rgba(0,0,0,0.38);
}
table.tbl thead .operation-col { z-index: 3; }
table.tbl tbody tr:hover .operation-col { background: #fafafc; }
.btn-operate {
  height: 32px; padding: 0 12px; border: 1px solid #b9d5f2; border-radius: 6px;
  background: #f2f7fd; color: #0066cc; cursor: pointer; font-size: 13px; font-weight: 500;
  white-space: nowrap; transition: background 0.15s ease, border-color 0.15s ease;
}
.btn-operate:hover { background: #e8f1fd; border-color: #7eb4e6; }
.btn-delete:hover { background: rgba(255,59,48,0.1); }

/* ── 事件处置弹窗（点击列表“处置”按钮唤起，与详情页一致） ── */
.op-modal-body { display: flex; gap: 24px; align-items: stretch; min-height: 0; height: 520px; }
.op-left { flex: 1 1 0; min-width: 0; }
.op-right {
  flex: 0 0 440px; min-width: 0; position: relative; overflow: hidden;
  border: 1px solid #e8e8ed; border-radius: 12px; background: #fff;
}
.op-right-title {
  position: relative; z-index: 1; background: #fff;
  display: flex; align-items: center; gap: 8px;
  height: 48px; padding: 0 16px; box-sizing: border-box;
  font-size: 14px; font-weight: 600; color: #1d1d1f;
}
.op-right-scroll {
  position: absolute; top: 48px; left: 0; right: 0; bottom: 0;
  overflow-y: auto; padding: 2px 16px 14px;
}
.op-count {
  font-size: 12px; font-weight: 500; color: #86868b;
  background: #f0f0f3; border-radius: 980px; padding: 1px 8px;
}
.op-loading { padding: 48px; text-align: center; color: #86868b; font-size: 14px; }
.operation-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.operation-current { display: flex; align-items: center; gap: 10px; margin-top: 10px; color: #6e6e73; font-size: 13px; }
.status-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.status-button {
  border: 1px solid #d2d2d7; background: #fff; color: #1d1d1f; border-radius: 6px;
  min-width: 84px; height: 36px; padding: 0 14px; cursor: pointer; font-size: 13px;
}
.status-button:hover:not(:disabled) { border-color: #0071e3; color: #0066cc; }
.status-button.current { border-color: #1d1d1f; background: #1d1d1f; color: #fff; }
.status-button:disabled { cursor: not-allowed; opacity: 0.48; }
.note-editor { margin-top: 18px; max-width: 760px; }
.note-editor textarea {
  box-sizing: border-box; width: 100%; resize: vertical; border: 1px solid #d2d2d7; border-radius: 6px;
  padding: 11px 12px; color: #1d1d1f; background: #fff; font: inherit; line-height: 1.6;
}
.note-editor textarea:focus { outline: none; border-color: #0071e3; box-shadow: 0 0 0 2px rgba(0,113,227,0.12); }
.note-submit-row { display: flex; justify-content: flex-end; align-items: center; gap: 12px; margin-top: 8px; color: #86868b; font-size: 12px; }
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #0066cc; }
.btn:disabled { cursor: not-allowed; opacity: 0.5; }
.action-timeline { min-width: 0; }
.timeline-item { position: relative; display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: 10px; padding-bottom: 18px; }
.timeline-item:not(:last-child)::before { content: ''; position: absolute; left: 5px; top: 12px; bottom: 0; width: 1px; background: #d2d2d7; }
.timeline-dot { width: 11px; height: 11px; margin-top: 4px; border-radius: 50%; background: #0071e3; z-index: 1; }
.timeline-meta { display: flex; flex-wrap: wrap; gap: 12px; color: #86868b; font-size: 12px; }
.timeline-meta strong { color: #1d1d1f; font-weight: 600; }
.timeline-content { margin-top: 5px; color: #3a3a3c; font-size: 14px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.timeline-empty { color: #86868b; padding: 10px 0 4px; font-size: 14px; }
.section-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }

@media (max-width: 860px) {
  .op-modal-body { flex-direction: column; height: auto; }
  .op-right { flex: 1 1 auto; width: 100%; max-height: 340px; position: static; display: flex; flex-direction: column; }
  .op-right-scroll { position: static; flex: 1 1 auto; min-height: 0; }
}
</style>
