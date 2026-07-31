<template>
  <div class="ai-search-page">
    <section class="search-panel">
      <el-form class="search-form" :model="form" label-position="top" @submit.prevent="handleSearch">
        <el-form-item label="检索关键词" class="keyword-field">
          <el-input
            v-model="form.query"
            size="large"
            clearable
            maxlength="512"
            placeholder="输入企业、事件、地点或风险关键词"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-select v-model="form.freshness" size="large">
            <el-option label="不限时间" value="" />
            <el-option label="最近一天" value="oneDay" />
            <el-option label="最近一周" value="oneWeek" />
            <el-option label="最近一月" value="oneMonth" />
            <el-option label="最近一年" value="oneYear" />
          </el-select>
        </el-form-item>
        <el-form-item label="返回数量">
          <el-input-number v-model="form.count" size="large" :min="1" :max="100" controls-position="right" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-switch v-model="form.summary" active-text="开启" inactive-text="关闭" />
        </el-form-item>
        <el-button class="search-button" type="primary" size="large" :loading="searching" @click="handleSearch">
          检索
        </el-button>
      </el-form>
    </section>

    <section class="content-grid">
      <div class="results-column">
        <div class="section-head">
          <div>
            <h2>搜索结果</h2>
            <p v-if="activeSession">本次检索返回 {{ results.length }} 条结果</p>
            <p v-else>输入关键词后开始一次主动检索</p>
          </div>
          <el-tag v-if="activeSession" effect="plain" type="info">Session #{{ activeSession.id }}</el-tag>
        </div>

        <div v-if="results.length" class="bulk-toolbar">
          <el-checkbox
            :model-value="allSelectableSelected"
            :indeterminate="isSelectionIndeterminate"
            :disabled="!selectableResults.length || bulkSaving"
            @change="toggleSelectAll"
          >
            全选可保存结果
          </el-checkbox>
          <span class="bulk-count">已选择 {{ selectedCount }} 条</span>
          <el-button
            class="save-lead-button"
            type="primary"
            plain
            :loading="bulkSaving"
            :disabled="!selectedCount"
            @click="saveSelectedLeads"
          >
            一键保存为线索
          </el-button>
        </div>

        <div v-loading="searching" class="result-list">
          <article v-for="item in pagedResults" :key="item.result_index" class="result-item">
            <el-checkbox
              class="result-check"
              :model-value="selectedIndexes.has(item.result_index)"
              :disabled="savedIndexes.has(item.result_index) || bulkSaving"
              @change="(checked: boolean) => toggleSelect(item, Boolean(checked))"
            />
            <div class="result-main">
              <div class="result-title-row">
                <button class="result-title result-title-button" type="button" @click="openResultDetail(item)">
                  {{ item.title || item.url }}
                </button>
                <el-tag v-if="savedIndexes.has(item.result_index)" type="success" effect="light">已保存</el-tag>
              </div>
              <div class="result-meta">
                <span>{{ item.source_name || '未知来源' }}</span>
                <span v-if="item.publish_time">{{ formatTime(item.publish_time) }}</span>
              </div>
              <p class="result-text">{{ item.summary || item.snippet || '暂无摘要' }}</p>
              <a class="source-link" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.url }}</a>
            </div>
            <el-button
              class="save-lead-button"
              type="primary"
              plain
              :disabled="!activeSession || savedIndexes.has(item.result_index)"
              :loading="savingIndex === item.result_index"
              @click="saveLead(item)"
            >
              保存为线索
            </el-button>
          </article>
          <el-empty v-if="!results.length && !searching" description="暂无搜索结果" />
        </div>
        <div v-if="results.length > resultPageSize" class="result-pagination">
          <Pager v-model:current-page="resultPage" :page-size="resultPageSize" :total="results.length" />
        </div>
      </div>

      <aside class="side-column">
        <section class="side-panel">
          <div class="section-head compact">
            <div>
              <h2>搜索历史</h2>
              <p>仅展示三天内的主动检索记录</p>
            </div>
            <el-button text type="primary" :loading="sessionsLoading" @click="loadSessions">刷新</el-button>
          </div>
          <div v-loading="sessionsLoading" class="mini-list history-list">
            <div v-for="session in sessions" :key="session.id" class="mini-item">
              <div class="mini-title">{{ session.query }}</div>
              <div class="mini-meta">
                <span>{{ formatTime(session.created_at) }}</span>
                <span>{{ session.result_count }} 条</span>
              </div>
            </div>
            <el-empty v-if="!sessions.length && !sessionsLoading" description="暂无历史" :image-size="72" />
          </div>
        </section>

        <section class="side-panel">
          <div class="section-head compact">
            <div>
              <h2>我的线索</h2>
              <p>已保存，等待管理员确认</p>
            </div>
            <el-button text type="primary" :loading="leadsLoading" @click="loadLeads">刷新</el-button>
          </div>
          <div v-loading="leadsLoading" class="mini-list history-list">
            <div v-for="lead in leads" :key="lead.id" class="mini-item">
              <div class="mini-title">{{ lead.title || lead.url }}</div>
              <div class="mini-meta">
                <el-tag size="small" :type="statusType(lead.status)" effect="light">{{ statusText(lead.status) }}</el-tag>
                <span>{{ formatTime(lead.created_at) }}</span>
              </div>
            </div>
            <el-empty v-if="!leads.length && !leadsLoading" description="暂无线索" :image-size="72" />
          </div>
        </section>
      </aside>
    </section>

    <BochaDetailModal
      v-model="detailVisible"
      :item="detailItem"
      :query="activeSession?.query || form.query"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import api from '@/api'
import BochaDetailModal from '@/components/BochaDetailModal.vue'
import {
  useBochaSearchStore,
  type BochaLead,
  type LeadStatus,
  type SearchResult,
  type SearchSession,
} from '@/stores/bocha'

interface ListResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

const bochaStore = useBochaSearchStore()
const form = bochaStore.form

const searching = ref(false)
const sessionsLoading = ref(false)
const leadsLoading = ref(false)
const savingIndex = ref<number | null>(null)
const bulkSaving = ref(false)
const detailVisible = ref(false)
const detailItem = ref<SearchResult | null>(null)
const resultPageSize = 10

const { activeSession, results, savedIndexes, selectedIndexes, resultPage } = storeToRefs(bochaStore)
const sessions = ref<SearchSession[]>([])
const leads = ref<BochaLead[]>([])
const pagedResults = computed(() => {
  const start = (resultPage.value - 1) * resultPageSize
  return results.value.slice(start, start + resultPageSize)
})

const selectableResults = computed(() =>
  results.value.filter((item) => !savedIndexes.value.has(item.result_index))
)
const selectedCount = computed(() =>
  [...selectedIndexes.value].filter((index) =>
    selectableResults.value.some((item) => item.result_index === index)
  ).length
)
const allSelectableSelected = computed(() =>
  selectableResults.value.length > 0 &&
  selectableResults.value.every((item) => selectedIndexes.value.has(item.result_index))
)
const isSelectionIndeterminate = computed(() =>
  selectedCount.value > 0 && !allSelectableSelected.value
)

async function handleSearch() {
  const query = form.query.trim()
  if (!query) {
    ElMessage.warning('请输入检索关键词')
    return
  }
  searching.value = true
  try {
    const payload: Record<string, unknown> = {
      query,
      summary: form.summary,
      count: form.count,
    }
    if (form.freshness) payload.freshness = form.freshness
    const { data } = await api.post<{
      session: SearchSession
      items: SearchResult[]
      total: number
      query: string
    }>('/bocha/search', payload)
    bochaStore.setSearchResult(data.session, data.items || [])
    ElMessage.success(`检索完成，返回 ${data.total} 条结果`)
    await loadSessions()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '检索失败')
  } finally {
    searching.value = false
  }
}

async function persistLead(item: SearchResult, showMessage = true): Promise<boolean> {
  if (!activeSession.value) return false
  savingIndex.value = item.result_index
  try {
    const { data } = await api.post<BochaLead>('/bocha/leads', {
      session_id: activeSession.value.id,
      result_index: item.result_index,
    })
    bochaStore.markSaved(item.result_index)
    if (showMessage) {
      ElMessage.success(data.status === 'new' ? '已保存为线索' : '线索已存在')
    }
    window.dispatchEvent(new CustomEvent('bocha-leads-refresh'))
    return true
  } catch (err: any) {
    if (showMessage) {
      ElMessage.error(err?.response?.data?.detail || '保存线索失败')
    }
    return false
  } finally {
    savingIndex.value = null
  }
}

async function saveLead(item: SearchResult) {
  const ok = await persistLead(item)
  if (ok) await loadLeads()
}

async function saveSelectedLeads() {
  if (!activeSession.value || bulkSaving.value) return
  const items = selectableResults.value.filter((item) => selectedIndexes.value.has(item.result_index))
  if (!items.length) return

  bulkSaving.value = true
  let success = 0
  let failed = 0
  try {
    for (const item of items) {
      const ok = await persistLead(item, false)
      if (ok) success += 1
      else failed += 1
    }
    if (success > 0) {
      ElMessage.success(`已保存 ${success} 条线索${failed ? `，${failed} 条失败` : ''}`)
      await loadLeads()
    } else {
      ElMessage.error('批量保存线索失败')
    }
  } finally {
    bulkSaving.value = false
  }
}

function toggleSelect(item: SearchResult, checked: boolean) {
  if (savedIndexes.value.has(item.result_index)) return
  bochaStore.setSelected(item.result_index, checked)
}

function toggleSelectAll(checked: boolean) {
  if (checked) {
    bochaStore.setSelectedIndexes(selectableResults.value.map((item) => item.result_index))
  } else {
    bochaStore.clearSelected()
  }
}

function openResultDetail(item: SearchResult) {
  detailItem.value = item
  detailVisible.value = true
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    const createdFrom = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString()
    const { data } = await api.get<ListResponse<SearchSession>>('/bocha/sessions', {
      params: { page: 1, size: 50, created_from: createdFrom },
    })
    const cutoff = Date.now() - 3 * 24 * 60 * 60 * 1000
    sessions.value = (data.items || []).filter((item) => new Date(item.created_at).getTime() >= cutoff)
  } catch {
    ElMessage.error('搜索历史加载失败')
  } finally {
    sessionsLoading.value = false
  }
}

async function loadLeads() {
  leadsLoading.value = true
  try {
    const { data } = await api.get<ListResponse<BochaLead>>('/bocha/leads', {
      params: { page: 1, size: 8 },
    })
    leads.value = data.items || []
  } catch {
    ElMessage.error('我的线索加载失败')
  } finally {
    leadsLoading.value = false
  }
}

function formatTime(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function statusText(status: LeadStatus): string {
  const map: Record<LeadStatus, string> = {
    new: '待确认',
    confirmed: '已确认',
    rejected: '已驳回',
    promoted: '已晋级',
  }
  return map[status] || status
}

function statusType(status: LeadStatus): 'success' | 'warning' | 'info' | 'danger' {
  if (status === 'confirmed') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'promoted') return 'warning'
  return 'info'
}

onMounted(() => {
  loadSessions()
  loadLeads()
})

watch(
  () => results.value.length,
  (total) => {
    const maxPage = Math.max(1, Math.ceil(total / resultPageSize))
    if (resultPage.value > maxPage) bochaStore.setResultPage(maxPage)
  },
  { immediate: true },
)
</script>

<style scoped>
.ai-search-page {
  min-height: 100%;
}

.search-panel {
  background: #fff;
  border-radius: 18px;
  padding: 18px 20px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04), 0 12px 32px rgba(0, 0, 0, .05);
  margin-bottom: 18px;
}

.search-form {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) 160px 132px 120px 104px;
  gap: 14px;
  align-items: end;
}

.keyword-field {
  min-width: 0;
}

.search-button {
  width: 100%;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 18px;
  align-items: start;
}

.results-column,
.side-panel {
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04), 0 12px 32px rgba(0, 0, 0, .05);
}

.results-column {
  padding: 18px;
  min-height: 560px;
}

.side-column {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.side-panel {
  padding: 16px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.section-head h2 {
  font-size: 18px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.section-head p {
  font-size: 13px;
  color: #86868b;
  margin: 4px 0 0;
}

.section-head.compact {
  align-items: center;
  margin-bottom: 8px;
}

.section-head.compact h2 {
  font-size: 16px;
}

.bulk-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 12px;
  margin-bottom: 6px;
  border-radius: 12px;
  background: #f5f5f7;
}

.bulk-count {
  color: #86868b;
  font-size: 13px;
  margin-right: auto;
}

.result-list {
  min-height: 420px;
}

.result-pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
  border-top: 1px solid #e8e8ed;
}

.result-item {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 0;
  border-top: 1px solid #e8e8ed;
}

.result-check {
  flex: 0 0 auto;
  padding-top: 2px;
}

.result-item:first-child {
  border-top: none;
}

.result-main {
  flex: 1 1 auto;
  min-width: 0;
}

.result-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.result-title {
  color: #1d1d1f;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.45;
  text-decoration: none;
  overflow-wrap: anywhere;
}

.result-title:hover {
  color: #0071e3;
}

.result-title-button {
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
}

.result-meta,
.mini-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: #86868b;
  font-size: 12.5px;
  margin-top: 6px;
}

.result-text {
  color: #424245;
  font-size: 14px;
  line-height: 1.65;
  margin: 10px 0 8px;
  overflow-wrap: anywhere;
}

.source-link {
  display: inline-block;
  max-width: 100%;
  color: #0071e3;
  font-size: 12.5px;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.save-lead-button {
  flex: 0 0 auto;
  min-width: 112px;
  color: #0071e3 !important;
  border-color: #b7d7f8 !important;
  background: #f5faff !important;
  opacity: 1 !important;
}

.save-lead-button:not(.is-disabled):hover {
  color: #fff !important;
  border-color: #0071e3 !important;
  background: #0071e3 !important;
}

.save-lead-button.is-disabled {
  color: #7ca9d4 !important;
  border-color: #d6e6f7 !important;
  background: #f5faff !important;
}

.mini-list {
  min-height: 120px;
}

.history-list {
  max-height: 320px;
  overflow-y: auto;
  padding-right: 4px;
}

.mini-item {
  padding: 12px 0;
  border-top: 1px solid #e8e8ed;
}

.mini-item:first-child {
  border-top: none;
}

.mini-title {
  color: #1d1d1f;
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

@media (max-width: 1120px) {
  .search-form {
    grid-template-columns: 1fr 1fr;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .search-panel,
  .results-column,
  .side-panel {
    border-radius: 14px;
  }

  .search-form {
    grid-template-columns: 1fr;
  }

  .result-item {
    flex-direction: column;
  }
}
</style>
