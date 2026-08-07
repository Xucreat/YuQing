<template>
  <div class="foreign-page" v-loading="loading">
    <div class="workspace-head">
      <div>
        <h2>外网舆情</h2>
        <p>独立采集、去重和展示链路；不会进入国内舆情、风险、事件或告警。</p>
      </div>
      <button class="btn btn-primary" :disabled="collecting" @click="collectNow">
        {{ collecting ? '采集中...' : '采集外网 RSS' }}
      </button>
    </div>

    <div class="tabs" role="tablist">
      <button v-for="tab in tabs" :key="tab.value" class="tab" :class="{ active: activeTab === tab.value }" @click="switchTab(tab.value)">
        {{ tab.label }}
      </button>
    </div>

    <section v-if="activeTab === 'opinions'" class="panel">
      <div class="toolbar">
        <input v-model="opinionFilters.q" class="input" placeholder="搜索标题、摘要、正文" @keyup.enter="loadOpinions" />
        <select v-model="opinionFilters.source" class="input" @change="loadOpinions">
          <option value="">全部来源</option>
          <option v-for="source in opinionSources" :key="source" :value="source">{{ source }}</option>
        </select>
        <input v-model="opinionFilters.keyword" class="input" placeholder="命中关键词" @keyup.enter="loadOpinions" />
        <button class="btn btn-secondary" @click="loadOpinions">搜索</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>标题</th><th>来源快照</th><th>命中关键词</th><th>发布时间</th><th>采集时间</th></tr></thead>
          <tbody>
            <tr v-for="row in opinions" :key="row.id" @click="selectedOpinion = row">
              <td class="title-cell">{{ row.title || '无标题' }}</td>
              <td>{{ row.source_name_snapshot }}</td>
              <td><span v-for="word in row.matched_keywords" :key="word" class="tag">{{ word }}</span></td>
              <td>{{ formatTime(row.published_at) }}</td>
              <td>{{ formatTime(row.collected_at) }}</td>
            </tr>
            <tr v-if="!opinions.length"><td colspan="5" class="empty">暂无外网舆情</td></tr>
          </tbody>
        </table>
      </div>
      <div class="pager" v-if="opinionTotal > opinionSize">
        <button class="btn btn-secondary" :disabled="opinionPage <= 1" @click="opinionPage--; loadOpinions()">上一页</button>
        <span>第 {{ opinionPage }} 页 / 共 {{ opinionTotal }} 条</span>
        <button class="btn btn-secondary" :disabled="opinionPage * opinionSize >= opinionTotal" @click="opinionPage++; loadOpinions()">下一页</button>
      </div>
    </section>

    <section v-else-if="activeTab === 'keywords'" class="panel">
      <div class="toolbar">
        <input v-model="keywordDraft.word" class="input" placeholder="新增外网关键词" @keyup.enter="createKeyword" />
        <button class="btn btn-primary" @click="createKeyword">新增关键词</button>
        <button class="btn btn-secondary" @click="loadKeywords">刷新</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>关键词</th><th>分类</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in keywords" :key="row.id">
              <td>{{ row.word }}</td><td>{{ row.category }}</td>
              <td><span class="status" :class="{ on: row.is_enabled }">{{ row.is_enabled ? '启用' : '停用' }}</span></td>
              <td class="actions">
                <button class="link-btn" @click="toggleKeyword(row)">{{ row.is_enabled ? '停用' : '启用' }}</button>
                <button class="link-btn danger" @click="removeKeyword(row.id)">删除</button>
              </td>
            </tr>
            <tr v-if="!keywords.length"><td colspan="4" class="empty">暂无外网关键词</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-else-if="activeTab === 'sources'" class="panel">
      <div class="source-note">首批来源默认停用，代理只读取环境变量名，不在前端展示地址、账号或密钥。</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>来源</th><th>RSS</th><th>状态</th><th>调度</th><th>代理</th></tr></thead>
          <tbody>
            <tr v-for="row in sources" :key="row.id">
              <td><strong>{{ row.name }}</strong><div class="muted">{{ row.key }}</div></td>
              <td><div v-for="feed in row.feeds" :key="feed" class="feed">{{ feed }}</div></td>
              <td><button class="status-toggle" :class="{ on: row.enabled }" @click="toggleSource(row)">{{ row.enabled ? '已启用' : '已停用' }}</button></td>
              <td>{{ row.schedule_enabled ? '自动' : '手动' }}</td>
              <td>{{ row.proxy_env || '直连' }}<span v-if="row.proxy_configured" class="proxy-mark">已配置</span></td>
            </tr>
            <tr v-if="!sources.length"><td colspan="5" class="empty">暂无外网数据源</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-else class="panel">
      <div class="toolbar">
        <button class="btn btn-secondary" @click="loadRuns">刷新日志</button>
        <span class="muted">仅显示 scope=foreign 的采集记录</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>来源</th><th>开始</th><th>状态</th><th>抓取</th><th>命中</th><th>新增</th><th>去重</th><th>代理</th><th>失败原因</th></tr></thead>
          <tbody>
            <tr v-for="row in runs" :key="row.id">
              <td>{{ row.collector_name }}</td><td>{{ formatTime(row.start_time) }}</td>
              <td><span class="status" :class="{ on: row.status === 'success' }">{{ row.status }}</span></td>
              <td>{{ row.fetched_raw }}</td><td>{{ row.matched }}</td><td>{{ row.created }}</td><td>{{ row.duplicate }}</td>
              <td>{{ row.proxy_used ? '是' : '否' }}</td><td class="error-cell">{{ row.error_msg || '-' }}</td>
            </tr>
            <tr v-if="!runs.length"><td colspan="9" class="empty">暂无外网采集日志</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="selectedOpinion" class="detail-mask" @click.self="selectedOpinion = null">
      <article class="detail">
        <button class="close" title="关闭详情" @click="selectedOpinion = null">×</button>
        <h3>{{ selectedOpinion.title }}</h3>
        <div class="detail-meta">{{ selectedOpinion.source_name_snapshot }} · 命中 {{ selectedOpinion.matched_keywords.join('、') }}</div>
        <p class="detail-text">{{ selectedOpinion.content || selectedOpinion.summary || '暂无正文' }}</p>
        <a v-if="selectedOpinion.url" :href="selectedOpinion.url" target="_blank" rel="noreferrer" class="original">打开原文</a>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { pollTask } from '@/api'

type Tab = 'opinions' | 'keywords' | 'sources' | 'runs'
type Keyword = { id: number; word: string; category: string; is_enabled: boolean }
type Source = { id: number; key: string; name: string; feeds: string[]; enabled: boolean; schedule_enabled: boolean; proxy_env?: string; proxy_configured?: boolean }
type Opinion = { id: number; title: string; summary: string; content: string; url: string; source_name_snapshot: string; matched_keywords: string[]; published_at?: string | null; collected_at?: string | null }
type Run = { id: number; collector_name: string; start_time?: string | null; status: string; fetched_raw: number; matched: number; created: number; duplicate: number; proxy_used: boolean; error_msg?: string | null }

const tabs: { value: Tab; label: string }[] = [
  { value: 'opinions', label: '国外舆情' },
  { value: 'keywords', label: '外网关键词' },
  { value: 'sources', label: '外网数据源' },
  { value: 'runs', label: '外网采集日志' },
]
const activeTab = ref<Tab>('opinions')
const loading = ref(false)
const collecting = ref(false)
const keywords = ref<Keyword[]>([])
const sources = ref<Source[]>([])
const opinions = ref<Opinion[]>([])
const runs = ref<Run[]>([])
const opinionSources = ref<string[]>([])
const opinionTotal = ref(0)
const opinionPage = ref(1)
const opinionSize = 20
const selectedOpinion = ref<Opinion | null>(null)
const keywordDraft = reactive({ word: '' })
const opinionFilters = reactive({ q: '', source: '', keyword: '' })

function switchTab(tab: Tab) {
  activeTab.value = tab
  if (tab === 'opinions') loadOpinions()
  if (tab === 'keywords') loadKeywords()
  if (tab === 'sources') loadSources()
  if (tab === 'runs') loadRuns()
}
function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}
async function loadKeywords() {
  loading.value = true
  try { keywords.value = (await api.get('/foreign/keywords', { params: { size: 100 } })).data.items } finally { loading.value = false }
}
async function loadSources() {
  loading.value = true
  try { sources.value = (await api.get('/foreign/sources')).data.items } finally { loading.value = false }
}
async function loadOpinions() {
  loading.value = true
  try {
    const params: Record<string, string | number> = { page: opinionPage.value, size: opinionSize }
    if (opinionFilters.q) params.q = opinionFilters.q
    if (opinionFilters.source) params.source = opinionFilters.source
    if (opinionFilters.keyword) params.keyword = opinionFilters.keyword
    const [list, sourceList] = await Promise.all([
      api.get('/foreign/opinions', { params }),
      api.get('/foreign/opinions/sources'),
    ])
    opinions.value = list.data.items
    opinionTotal.value = list.data.total
    opinionSources.value = sourceList.data
  } finally { loading.value = false }
}
async function loadRuns() {
  loading.value = true
  try { runs.value = (await api.get('/foreign/collection-runs', { params: { size: 100 } })).data.items } finally { loading.value = false }
}
async function createKeyword() {
  const word = keywordDraft.word.trim()
  if (!word) return
  try { await api.post('/foreign/keywords', { word, category: 'general', is_enabled: true }); keywordDraft.word = ''; await loadKeywords(); ElMessage.success('外网关键词已新增') } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '新增失败') }
}
async function toggleKeyword(row: Keyword) {
  try { await api.patch(`/foreign/keywords/${row.id}`, { word: row.word, category: row.category, is_enabled: !row.is_enabled }); await loadKeywords() } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '更新失败') }
}
async function removeKeyword(id: number) {
  try { await api.delete(`/foreign/keywords/${id}`); await loadKeywords() } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '删除失败') }
}
async function toggleSource(row: Source) {
  try { await api.patch(`/foreign/sources/${row.id}`, { enabled: !row.enabled }); await loadSources() } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '数据源状态更新失败') }
}
async function collectNow() {
  if (collecting.value) return
  collecting.value = true
  try {
    const { data } = await api.post('/foreign/collect', { source_ids: null })
    const result = await pollTask(data.task_id)
    if (result.status === 'success') { ElMessage.success(`外网采集完成：新增 ${result.result?.created || 0} 条`); await loadOpinions(); await loadRuns() }
    else ElMessage.error(result.error || '外网采集失败')
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || err?.message || '外网采集失败') } finally { collecting.value = false }
}
onMounted(loadOpinions)
</script>

<style scoped>
.foreign-page { min-width: 0; }
.workspace-head { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; margin-bottom: 20px; }
.workspace-head h2 { margin: 0 0 6px; font-size: 24px; color: #1d1d1f; }
.workspace-head p, .source-note, .muted { margin: 0; color: #86868b; font-size: 13px; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid #e8e8ed; }
.tab { border: 0; background: transparent; padding: 10px 16px; color: #6e6e73; cursor: pointer; border-bottom: 2px solid transparent; }
.tab.active { color: #0071e3; border-bottom-color: #0071e3; }
.panel { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 8px 24px rgba(0,0,0,.05); }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; align-items: center; }
.input { height: 38px; border: 1px solid #d2d2d7; border-radius: 8px; padding: 0 11px; min-width: 190px; color: #1d1d1f; background: #fff; }
.btn { border: 0; border-radius: 8px; padding: 9px 15px; cursor: pointer; font-size: 13px; }
.btn-primary { color: #fff; background: #0071e3; }.btn-secondary { color: #1d1d1f; background: #f0f0f3; }
.btn:disabled { opacity: .5; cursor: default; }
.table-wrap { overflow-x: auto; } table { width: 100%; border-collapse: collapse; min-width: 720px; font-size: 13px; }
th, td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #e8e8ed; vertical-align: top; } th { color: #86868b; font-weight: 600; }
tbody tr:hover { background: #fafafc; cursor: pointer; }.title-cell { min-width: 280px; font-weight: 600; }
.tag { display: inline-block; color: #0071e3; background: #e8f1fd; border-radius: 999px; padding: 3px 7px; margin: 0 4px 3px 0; }
.status, .status-toggle { display: inline-block; border: 0; border-radius: 999px; padding: 4px 9px; color: #86868b; background: #f0f0f3; }.status.on, .status-toggle.on { color: #1a8e3c; background: #eafaf0; }
.status-toggle { cursor: pointer; }.link-btn { border: 0; background: transparent; color: #0071e3; cursor: pointer; margin-right: 10px; }.link-btn.danger { color: #ff3b30; }
.feed { max-width: 420px; overflow-wrap: anywhere; color: #515154; }.proxy-mark { color: #1a8e3c; margin-left: 8px; }.error-cell { color: #ff3b30; max-width: 240px; }
.empty { text-align: center; color: #86868b; padding: 30px; }.pager { display: flex; justify-content: flex-end; align-items: center; gap: 10px; margin-top: 14px; color: #6e6e73; font-size: 13px; }
.detail-mask { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: grid; place-items: center; padding: 20px; z-index: 20; }.detail { position: relative; width: min(760px, 100%); max-height: 80vh; overflow: auto; background: #fff; border-radius: 12px; padding: 24px; }.detail h3 { margin: 0 34px 10px 0; color: #1d1d1f; }.detail-meta { color: #86868b; font-size: 13px; }.detail-text { white-space: pre-wrap; line-height: 1.8; color: #2b2b2e; }.close { position: absolute; right: 14px; top: 12px; border: 0; background: #f0f0f3; border-radius: 50%; width: 28px; height: 28px; cursor: pointer; }.original { color: #0071e3; }
@media (max-width: 700px) { .workspace-head { flex-direction: column; }.input { width: 100%; min-width: 0; } }
</style>
