<template>
  <div class="fw-block">
    <div class="toolbar">
      <button class="btn btn-secondary" @click="loadSourcesView">刷新数据源</button>
      <input v-model="sourceFilters.q" class="input" placeholder="搜索来源" @keyup.enter="sourcePage = 1; loadSourcesView()" />
      <span class="scope-badge">来源与语言分布 · 无地图</span>
      <span v-if="visualizationStale" class="stale-badge">数据较旧</span>
    </div>
    <div v-if="visualizationError" class="error-state">{{ visualizationError }} <button class="btn btn-secondary" @click="loadSourcesView">重试</button></div>
    <div v-else-if="sourceDistribution" class="visualization-content">
      <div class="fw-viz-cards">
        <article class="card fw-viz-card">
          <h3>语言分布</h3>
          <div v-for="item in languageDistribution?.items || []" :key="item.language" class="distribution-row">
            <span>{{ item.language }}</span><strong>{{ item.count }}</strong>
          </div>
          <p v-if="!(languageDistribution?.items || []).length" class="empty">暂无语言分布数据</p>
        </article>
        <article class="card fw-viz-card">
          <h3>外网来源</h3>
          <div v-for="item in sourceDistribution.items" :key="item.source_key" class="distribution-row">
            <span>{{ item.source }}<small>{{ item.source_key }}</small></span><strong>{{ item.opinion_count }}</strong>
          </div>
          <p v-if="!sourceDistribution.items.length" class="empty">暂无外网来源数据</p>
        </article>
      </div>

      <div class="visualization-meta">数据范围：{{ formatTime(sourceDistribution.window_start) }} - {{ formatTime(sourceDistribution.window_end) }} · 更新于：{{ formatTime(sourceDistribution.data_as_of) }}</div>
    </div>
    <div v-else class="state">加载外网来源分布中...</div>
    <div class="source-management-note">下方为来源管理；可视化数据不会修改来源状态。</div>
    <div class="source-note">第一方外网来源默认停用，代理配置不展示。</div>
    <div class="toolbar source-editor-toolbar">
      <button class="btn btn-primary" @click="beginNewSource">新增外网源</button>
    </div>
    <el-dialog class="apple-dialog" modal-class="apple-modal" align-center v-model="sourceEditorVisible" :title="editingSourceId ? '编辑外网数据源' : '新增外网数据源'" width="680px">
      <div class="source-editor-form">
        <el-form :model="sourceDraft" label-width="92px">
          <el-form-item label="数据源">
            <input v-model="sourceDraft.name" class="input" placeholder="输入数据源名称" />
          </el-form-item>
          <el-form-item label="来源 Key">
            <input v-model="sourceDraft.key" class="input" :disabled="!!editingSourceId" placeholder="唯一标识，创建后不可修改" />
          </el-form-item>
          <el-form-item label="语言">
            <select v-model="sourceDraft.language" class="input">
              <option value="unknown">未知</option>
              <option value="en">英文</option>
              <option value="zh">中文</option>
              <option value="mixed">中英混合</option>
            </select>
          </el-form-item>
          <el-form-item label="RSS 地址">
            <input v-model="sourceDraft.feedsText" class="input source-feed-input" placeholder="多个地址用换行分隔" />
          </el-form-item>
          <el-form-item label="代理环境变量">
            <input v-model="sourceDraft.proxyEnv" class="input" placeholder="如 FOREIGN_HTTP_PROXY" />
          </el-form-item>
          <el-form-item label="超时(秒)">
            <input v-model.number="sourceDraft.timeout" class="input number-input" type="number" min="1" max="120" />
          </el-form-item>
          <el-form-item label="重试次数">
            <input v-model.number="sourceDraft.maxRetries" class="input number-input" type="number" min="0" max="5" />
          </el-form-item>
          <el-form-item label="最大条数">
            <input v-model.number="sourceDraft.maxItems" class="input number-input" type="number" min="1" max="500" />
          </el-form-item>
          <el-form-item label="请求间隔(秒)">
            <input v-model.number="sourceDraft.requestInterval" class="input number-input" type="number" min="0" max="60" step="0.1" />
          </el-form-item>
          <el-form-item label="采集间隔(分钟)">
            <input v-model.number="sourceDraft.scheduleInterval" class="input number-input" type="number" min="5" max="10080" />
          </el-form-item>
          <el-form-item label="正文上限">
            <input v-model.number="sourceDraft.maxContentLength" class="input number-input" type="number" min="100" max="1000000" />
          </el-form-item>
          <el-form-item label="robots 检查">
            <label class="checkbox-inline"><input v-model="sourceDraft.respectRobots" type="checkbox" /> 启用 robots.txt 检查</label>
          </el-form-item>
          <el-form-item label="正文抓取">
            <span class="muted">本阶段关闭</span>
          </el-form-item>
        </el-form>
        <button class="btn btn-secondary" :disabled="sourceTesting" @click="testSourceDraft">{{ sourceTesting ? '测试中...' : '连通性测试' }}</button>
        <span v-if="!sourceDraftTested" class="muted">保存前必须完成当前配置的 RSS 测试</span>
      </div>
      <div v-if="sourceTestResult" class="source-test-result">
        <strong>{{ sourceTestResult.success ? 'RSS 测试通过' : 'RSS 测试存在失败项' }}</strong>
        <span v-for="feed in sourceTestResult.feeds || []" :key="feed.feed || feed.label">{{ feed.feed || feed.label }}: HTTP {{ feed.http_status ?? '-' }} · XML {{ feed.xml_parsed ? '是' : '否' }} · 原始 {{ feed.raw_count }} · 命中 {{ feed.matched_count }} · 失败 {{ feed.failure_count ?? 0 }}</span>
      </div>
      <template #footer>
        <button class="btn btn-secondary" @click="sourceEditorVisible = false">取消</button>
        <button class="btn btn-primary" :disabled="sourceSaving || !sourceDraftTested" @click="saveSource">{{ sourceSaving ? '保存中...' : '保存' }}</button>
      </template>
    </el-dialog>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>来源</th><th>语言</th><th>文章数</th><th>风险完成</th><th>告警</th><th>失败次数</th><th>最近运行</th><th>RSS</th><th>采集器</th><th>状态</th><th>调度</th><th>间隔</th><th>代理</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in mergedSources" :key="row.id">
            <td><strong>{{ row.name }}</strong><div class="muted">{{ row.key }}</div></td>
            <td>{{ langLabel(row.language) }}</td>
            <td>{{ row.stats?.opinion_count ?? '-' }}</td>
            <td>{{ row.stats?.risk_completed_count ?? '-' }}</td>
            <td>{{ row.stats?.alert_count ?? '-' }}</td>
            <td>{{ row.stats?.failed_count ?? '-' }}</td>
            <td>{{ row.stats?.latest_run?.status || '-' }}</td>
            <td><div v-for="feed in row.feeds" :key="feed" class="feed">{{ feed }}</div></td>
            <td><div class="muted">{{ row.class_path || 'foreign_rss' }}</div></td>
            <td><button class="status-toggle" :class="{ on: row.enabled }" :disabled="sourceBusyId === row.id" @click="toggleSource(row)">{{ row.enabled ? '已启用' : '已停用' }}</button></td>
            <td>{{ row.schedule_enabled ? '自动' : '手动' }}</td>
            <td>{{ row.schedule_interval_minutes || '-' }} 分钟</td>
            <td>{{ row.proxy_env || '直连' }}<span v-if="row.proxy_configured" class="proxy-mark">已配置</span></td>
            <td class="actions">
              <button class="link-btn" @click="editSource(row)">编辑</button>
              <button class="link-btn" @click="testSource(row)">测试</button>
              <button class="link-btn" @click="loadSourceRuns(row)">历史</button>
            </td>
          </tr>
          <tr v-if="!mergedSources.length"><td colspan="14" class="empty">暂无外网来源</td></tr>
        </tbody>
      </table>
    </div>
    <div class="pager" v-if="sourceTotal > 0">
      <Pager :total="sourceTotal" v-model:current-page="sourcePage" :page-size="sourceSize" @current-change="loadSourcesView" />
    </div>
    <el-dialog class="apple-dialog" modal-class="apple-modal" align-center v-model="sourceRunsVisible" :title="(selectedSourceRuns?.name || '来源') + ' · 采集历史'" width="760px">
      <div v-loading="sourceRunsLoading">
        <div class="run-summary" v-if="(selectedSourceRuns?.items || []).length">
          <div class="run-stat"><span>抓取总数</span><b>{{ runsSummary.fetched }}</b></div>
          <div class="run-stat"><span>命中</span><b>{{ runsSummary.matched }}</b></div>
          <div class="run-stat"><span>新增</span><b>{{ runsSummary.created }}</b></div>
          <div class="run-stat"><span>去重</span><b>{{ runsSummary.duplicate }}</b></div>
        </div>
        <div class="card table-card">
          <table class="tbl hist-tbl">
            <thead>
              <tr>
                <th style="width:170px">时间</th>
                <th>采集器</th>
                <th style="width:70px">抓取</th>
                <th style="width:70px">命中</th>
                <th style="width:70px">新增</th>
                <th style="width:70px">去重</th>
                <th style="width:80px">状态</th>
                <th>失败原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="run in (selectedSourceRuns?.items || [])" :key="run.id">
                <td>{{ formatTime(run.start_time) }}</td>
                <td>{{ run.collector_name }}</td>
                <td>{{ run.fetched_raw }}</td>
                <td>{{ run.matched }}</td>
                <td>{{ run.created }}</td>
                <td>{{ run.duplicate }}</td>
                <td><span class="pill" :class="runPill(run.status)">{{ runText(run.status) }}</span></td>
                <td class="error-cell">{{ run.error_msg || '-' }}</td>
              </tr>
              <tr v-if="!(selectedSourceRuns?.items || []).length"><td colspan="8" class="empty-row">暂无采集记录</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <template #footer>
        <span class="dlg-foot"><button class="btn btn-ghost" @click="sourceRunsVisible = false">关闭</button></span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import Pager from '@/components/Pager.vue'
import api from '@/api'

type Source = {
  id: number
  key: string
  name: string
  feeds: string[]
  language?: string
  enabled: boolean
  schedule_enabled: boolean
  schedule_interval_minutes?: number
  class_path?: string
  proxy_env?: string
  proxy_configured?: boolean
  timeout?: number
  max_retries?: number
  max_items?: number
  request_interval?: number
  max_content_length?: number
  respect_robots?: boolean
}
type Run = { id: number; collector_name: string; start_time?: string | null; end_time?: string | null; status: string; fetched_raw: number; matched: number; created: number; duplicate: number; proxy_used: boolean; error_msg?: string | null }

const loading = ref(false)
const visualizationError = ref<string | null>(null)
const visualizationStale = ref(false)
const visualizationDays = ref(7)
const sourceDistribution = ref<Record<string, any> | null>(null)
const languageDistribution = ref<Record<string, any> | null>(null)
const sources = ref<Source[]>([])
const sourceEditorVisible = ref(false)
const editingSourceId = ref<number | null>(null)
const sourceSaving = ref(false)
const sourceTesting = ref(false)
const sourceBusyId = ref<number | null>(null)
const sourceDraftTested = ref(false)
const sourceTestResult = ref<any | null>(null)
const selectedSourceRuns = ref<{ name: string; items: Run[] } | null>(null)
const sourceRunsVisible = ref(false)
const sourceRunsLoading = ref(false)
const sourceDraft = reactive({ name: '', key: '', feedsText: '', language: 'unknown', proxyEnv: 'FOREIGN_HTTP_PROXY', timeout: 15, maxRetries: 2, maxItems: 100, requestInterval: 0.5, scheduleInterval: 60, maxContentLength: 200000, respectRobots: true })
const sourceFilters = reactive({ q: '' })
const sourcePage = ref(1)
const sourceSize = 20
const sourceTotal = ref(0)
const distMap = computed(() => {
  const m: Map<string, any> = new Map()
  for (const it of (sourceDistribution.value?.items || [])) m.set(it.source_key, it)
  return m
})
const mergedSources = computed(() => sources.value.map((s) => ({ ...s, stats: distMap.value.get(s.key) || {} })))
function langLabel(lang?: string) {
  const map: Record<string, string> = { unknown: '未知', en: '英文', zh: '中文', mixed: '中英混合' }
  return (map[lang || 'unknown'] || lang || '-')
}

function runPill(st: string): string {
  const m: Record<string, string> = { running: 'pill-blue', success: 'pill-green', partial: 'pill-orange', failed: 'pill-red', error: 'pill-red', unknown: 'pill-gray' }
  return m[st] || 'pill-gray'
}
function runText(st: string): string {
  const m: Record<string, string> = { running: '运行中', success: '成功', partial: '部分成功', failed: '失败', error: '异常', unknown: '未知' }
  return m[st] || st
}
const runsSummary = computed(() => {
  const items = selectedSourceRuns.value?.items || []
  return {
    fetched: items.reduce((a, r) => a + (r.fetched_raw || 0), 0),
    matched: items.reduce((a, r) => a + (r.matched || 0), 0),
    created: items.reduce((a, r) => a + (r.created || 0), 0),
    duplicate: items.reduce((a, r) => a + (r.duplicate || 0), 0),
  }
})

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}
function visualizationFailure(err: any) {
  const status = err?.response?.status
  const code = err?.response?.data?.error_code
  if (code === 'FOREIGN_VISUALIZATION_QUERY_FAILED' || status === 503) return '外网可视化数据暂时不可用'
  if (status === 403) return '当前账号没有外网可视化权限'
  if (status === 422) return '外网可视化请求参数无效'
  return '外网可视化数据加载失败，请稍后重试'
}
function markVisualizationFresh(data: any) {
  const asOf = data?.data_as_of ? new Date(data.data_as_of).getTime() : Date.now()
  visualizationStale.value = Date.now() - asOf > 15 * 60 * 1000
}

async function loadSourcesView() {
  loading.value = true
  visualizationError.value = null
  try {
    const params = { days: visualizationDays.value }
    const [distribution, languages, management] = await Promise.all([
      api.get('/foreign/source-distribution', { params }),
      api.get('/foreign/language-distribution', { params }),
      api.get('/foreign/sources', { params: { page: sourcePage.value, size: sourceSize, q: sourceFilters.q || undefined } }),
    ])
    sourceDistribution.value = distribution.data
    languageDistribution.value = languages.data
    sources.value = management.data.items || []
    sourceTotal.value = management.data.total || 0
    markVisualizationFresh(distribution.data)
  } catch (err: any) {
    visualizationError.value = visualizationFailure(err)
    sourceDistribution.value = null
    languageDistribution.value = null
  } finally { loading.value = false }
}

function sourcePayload() {
  return {
    name: sourceDraft.name.trim(),
    key: sourceDraft.key.trim(),
    feeds: sourceDraft.feedsText.split(/\r?\n|,/).map(item => item.trim()).filter(Boolean),
    language: sourceDraft.language,
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
    fetch_full_text: false,
  }
}
function sourceTestPayload() {
  const payload = sourcePayload()
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
    fetch_full_text: false,
  }
}
async function testSourceDraft() {
  if (sourceTesting.value) return
  sourceTesting.value = true
  sourceDraftTested.value = false
  try {
    const response = await api.post('/foreign/sources/test', sourceTestPayload())
    sourceTestResult.value = response.data
    sourceDraftTested.value = Boolean(response.data?.success)
    if (!response.data?.success) ElMessage.warning('RSS 测试存在失败项，请检查配置')
    else ElMessage.success('RSS 连通性测试通过')
  } catch (err: any) { sourceTestResult.value = null; ElMessage.error(err?.response?.data?.detail || '外网源连通性测试失败') } finally { sourceTesting.value = false }
}
async function saveSource() {
  if (sourceSaving.value || !sourceDraftTested.value) return
  sourceSaving.value = true
  try {
    const payload = sourcePayload()
    if (editingSourceId.value) {
      const { key: _key, ...updatePayload } = payload
      await api.patch(`/foreign/sources/${editingSourceId.value}`, updatePayload)
    } else await api.post('/foreign/sources', payload)
    ElMessage.success('外网数据源已保存')
    sourceEditorVisible.value = false
    await loadSourcesView()
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '外网数据源保存失败') } finally { sourceSaving.value = false }
}
async function testSource(row: Source) {
  sourceTesting.value = true
  try {
    const response = await api.post('/foreign/sources/test', { source_id: row.id, fetch_full_text: false })
    sourceTestResult.value = response.data
    ElMessage[response.data?.success ? 'success' : 'warning'](response.data?.success ? 'RSS 连通性测试通过' : 'RSS 测试存在失败项')
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '外网源测试失败') } finally { sourceTesting.value = false }
}
async function loadSourceRuns(row: Source) {
  sourceRunsLoading.value = true
  try {
    selectedSourceRuns.value = { name: row.name, items: (await api.get(`/foreign/sources/${row.id}/runs`, { params: { size: 50 } })).data.items || [] }
    sourceRunsVisible.value = true
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '外网采集历史加载失败')
  } finally {
    sourceRunsLoading.value = false
  }
}
async function toggleSource(row: Source) {
  if (sourceBusyId.value) return
  sourceBusyId.value = row.id
  try { await api.patch(`/foreign/sources/${row.id}`, { enabled: !row.enabled, schedule_enabled: false, fetch_full_text: false }); await loadSourcesView(); ElMessage.success('外网数据源状态已更新') } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '数据源状态更新失败') } finally { sourceBusyId.value = null }
}
function resetSourceDraft() {
  sourceDraft.name = ''
  sourceDraft.key = ''
  sourceDraft.feedsText = ''
  sourceDraft.language = 'unknown'
  sourceDraft.proxyEnv = 'FOREIGN_HTTP_PROXY'
  sourceDraft.timeout = 15
  sourceDraft.maxRetries = 2
  sourceDraft.maxItems = 100
  sourceDraft.requestInterval = 0.5
  sourceDraft.scheduleInterval = 60
  sourceDraft.maxContentLength = 200000
  sourceDraft.respectRobots = true
}
function beginNewSource() {
  resetSourceDraft()
  editingSourceId.value = null
  sourceEditorVisible.value = true
}
function editSource(row: Source) {
  sourceDraft.name = row.name
  sourceDraft.key = row.key
  sourceDraft.feedsText = row.feeds.join('\n')
  sourceDraft.language = row.language || 'unknown'
  sourceDraft.proxyEnv = row.proxy_env || 'FOREIGN_HTTP_PROXY'
  sourceDraft.timeout = row.timeout || 15
  sourceDraft.maxRetries = row.max_retries ?? 2
  sourceDraft.maxItems = row.max_items || 100
  sourceDraft.requestInterval = row.request_interval ?? 0.5
  sourceDraft.scheduleInterval = row.schedule_interval_minutes || 60
  sourceDraft.maxContentLength = row.max_content_length || 200000
  sourceDraft.respectRobots = row.respect_robots !== false
  editingSourceId.value = row.id
  sourceEditorVisible.value = true
}

onMounted(loadSourcesView)
</script>

<style scoped src="./foreign-ui.css" />


<style>
/* 苹果风弹窗：仅作用于带 apple-dialog 类的 el-dialog（teleport 到 body，需全局样式，避免 Sources.vue 卸载后被移除） */
.apple-dialog {
  border-radius: 22px;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.22), 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  background: #fff;
}
.apple-dialog .el-dialog__header { padding: 22px 26px 10px; margin-right: 0; }
.apple-dialog .el-dialog__title { font-size: 17px; font-weight: 600; color: #1d1d1f; letter-spacing: 0.2px; }
.apple-dialog .el-dialog__headerbtn { top: 20px; right: 20px; width: 28px; height: 28px; border-radius: 50%; transition: background-color 0.18s; }
.apple-dialog .el-dialog__headerbtn:hover { background: #f0f0f3; }
.apple-dialog .el-dialog__headerbtn .el-dialog__close { color: #86868b; font-size: 18px; font-weight: 400; }
.apple-dialog .el-dialog__headerbtn:hover .el-dialog__close { color: #1d1d1f; }
.apple-dialog .el-dialog__body { padding: 4px 26px 10px; color: #1d1d1f; font-size: 14px; }
.apple-dialog .el-dialog__footer { padding: 14px 26px 22px; }
.apple-modal { background: rgba(0, 0, 0, 0.34); backdrop-filter: saturate(160%) blur(8px); -webkit-backdrop-filter: saturate(160%) blur(8px); }

/* 采集历史弹窗（对齐国内数据源管理页查看历史弹窗） */
.run-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
.run-stat { min-height: 58px; padding: 10px 12px; border: 1px solid #e8e8ed; border-radius: 12px; background: #fafafc; box-sizing: border-box; }
.run-stat span { display: block; font-size: 12px; color: #86868b; margin-bottom: 4px; }
.run-stat b { font-size: 18px; font-weight: 600; color: #1d1d1f; }
.table-card { padding: 0 6px 14px; max-height: 56vh; overflow: auto; background: #fff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 12px 32px rgba(0,0,0,.05); }
.table-card::-webkit-scrollbar { width: 8px; height: 8px; }
.table-card::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 8px; }
.table-card::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.32); }
.hist-tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
.hist-tbl thead th { text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b; padding: 14px 18px; border-bottom: 1px solid #e8e8ed; }
.hist-tbl tbody td { padding: 12px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; vertical-align: middle; }
.hist-tbl tbody tr:last-child td { border-bottom: none; }
.hist-tbl td, .hist-tbl th { white-space: nowrap; }
.hist-tbl thead th { position: sticky; top: 0; z-index: 2; background: #fff; border-bottom: 1px solid #e8e8ed; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }
.dlg-foot { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 980px; font-size: 12px; font-weight: 500; }
.pill-blue { background: rgba(0,122,255,0.1); color: #007aff; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.error-cell { color: #ff3b30; font-size: 12.5px; max-width: 320px; }
</style>