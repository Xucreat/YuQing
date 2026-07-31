<template>
  <div class="anspire-page">
    <section class="search-panel">
      <el-form class="search-form" :model="form" label-position="top" @submit.prevent="handleSearch">
        <el-form-item label="搜索关键词" class="keyword-field">
          <el-input v-model="form.query" size="large" clearable maxlength="64" show-word-limit placeholder="输入企业、事件、地点或风险关键词" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="返回数量">
          <el-select v-model="form.top_k" size="large">
            <el-option v-for="value in [10, 20, 30, 40, 50]" :key="value" :label="String(value)" :value="value" />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索区域">
          <el-select v-model="form.region_mode" size="large">
            <el-option label="国内" :value="0" />
            <el-option label="海外" :value="1" />
            <el-option label="国内外混合" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="限定站点">
          <el-input v-model="form.insite" size="large" placeholder="例如 gov.cn,news.cn" />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker v-model="form.from_time" class="date-field" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" placeholder="不限" />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker v-model="form.to_time" class="date-field" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" placeholder="不限" />
        </el-form-item>
        <el-button class="search-button" type="primary" size="large" :loading="searching" @click="handleSearch">搜索</el-button>
      </el-form>
      <el-alert v-if="errorMessage" class="error-alert" type="error" :closable="false" :title="errorMessage" />
    </section>

    <section class="content-grid">
      <div class="results-column">
        <div class="section-head">
          <div>
            <h2>搜索结果</h2>
            <p v-if="activeSession">本次搜索返回 {{ results.length }} 条结果</p>
            <p v-else>输入关键词后开始一次 Anspire 网页搜索</p>
          </div>
          <div class="session-actions">
            <el-tag v-if="activeSession" effect="plain" type="info">会话 #{{ activeSession.id }}</el-tag>
            <el-button v-if="activeSession" text type="primary" @click="showRaw = !showRaw">{{ showRaw ? '隐藏原始 JSON' : '查看原始 JSON' }}</el-button>
          </div>
        </div>

        <pre v-if="showRaw" class="raw-json">{{ JSON.stringify(results, null, 2) }}</pre>

        <div v-if="results.length" class="bulk-toolbar">
          <el-checkbox :model-value="allSelectableSelected" :indeterminate="isSelectionIndeterminate" :disabled="!selectableResults.length || bulkSaving" @change="toggleSelectAll">
            全选可保存结果
          </el-checkbox>
          <span class="bulk-count">已选择 {{ selectedCount }} 条</span>
          <el-button class="save-lead-button" type="primary" plain :loading="bulkSaving" :disabled="!selectedCount" @click="saveSelectedLeads">一键保存为线索</el-button>
        </div>

        <div v-loading="searching" class="result-list">
          <article v-for="item in pagedResults" :key="item.result_index" class="result-item">
            <el-checkbox class="result-check" :model-value="selectedIndexes.has(item.result_index)" :disabled="savedIndexes.has(item.result_index) || bulkSaving" @change="(checked: boolean) => toggleSelect(item, Boolean(checked))" />
            <div class="result-main">
              <div class="result-title-row">
                <button class="result-title result-title-button" type="button" @click="openResultDetail(item)">{{ item.title || item.url }}</button>
                <el-tag v-if="savedIndexes.has(item.result_index)" type="success" effect="light">已保存</el-tag>
              </div>
              <div class="result-meta">
                <span>{{ item.source_name || '未知来源' }}</span>
                <span v-if="item.publish_time">{{ formatTime(item.publish_time) }}</span>
                <span v-if="item.provider_score != null">相关度 {{ item.provider_score }}</span>
              </div>
              <p class="result-text">
                {{ visibleResultText(item) }}
                <el-button v-if="isLongResult(item)" class="expand-result-button" text type="primary" size="small" @click="toggleExpanded(item.result_index)">
                  {{ isExpanded(item.result_index) ? '收起' : '展开全文' }}
                </el-button>
              </p>
              <a class="source-link" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.url }}</a>
            </div>
            <el-button class="save-lead-button" type="primary" plain :disabled="!activeSession || savedIndexes.has(item.result_index)" :loading="savingIndex === item.result_index" @click="saveLead(item)">{{ savedIndexes.has(item.result_index) ? '已保存' : '保存为线索' }}</el-button>
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
            <div><h2>搜索历史</h2><p>仅显示最近三天的 Anspire 搜索</p></div>
            <el-button text type="primary" :loading="sessionsLoading" @click="loadSessions">刷新</el-button>
          </div>
          <div v-loading="sessionsLoading" class="mini-list history-list">
            <div v-for="item in sessions" :key="item.id" class="mini-item">
              <div class="mini-title">{{ item.query }}</div>
              <div class="mini-meta"><span>{{ formatTime(item.created_at) }}</span><span>{{ item.result_count }} 条结果</span></div>
            </div>
            <el-empty v-if="!sessions.length && !sessionsLoading" description="暂无搜索历史" :image-size="72" />
          </div>
        </section>

        <section class="side-panel">
          <div class="section-head compact">
            <div><h2>我的线索</h2><p>已保存，等待管理员确认</p></div>
            <el-button text type="primary" :loading="leadsLoading" @click="loadLeads">刷新</el-button>
          </div>
          <div v-loading="leadsLoading" class="mini-list">
            <div v-for="lead in leads" :key="lead.id" class="mini-item">
              <div class="mini-title">{{ lead.title || lead.url }}</div>
              <div class="mini-meta"><el-tag size="small" :type="statusType(lead.status)" effect="light">{{ statusText(lead.status) }}</el-tag><span>{{ formatTime(lead.created_at) }}</span></div>
            </div>
            <el-empty v-if="!leads.length && !leadsLoading" description="暂无线索" :image-size="72" />
          </div>
        </section>
      </aside>
    </section>

    <BochaDetailModal v-model="detailVisible" :item="detailItem" :query="activeSession?.query || form.query" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import api from '@/api'
import BochaDetailModal from '@/components/BochaDetailModal.vue'
import { useAnspireSearchStore, type AnspireLead, type AnspireLeadStatus, type AnspireResult, type AnspireSession } from '@/stores/anspire'

interface ListResponse<T> { items: T[]; total: number; page: number; size: number }
const store = useAnspireSearchStore()
const { form, session: activeSession, results, savedIndexes, selectedIndexes, resultPage } = storeToRefs(store)
const searching = ref(false); const sessionsLoading = ref(false); const leadsLoading = ref(false); const savingIndex = ref<number | null>(null); const bulkSaving = ref(false); const errorMessage = ref(''); const showRaw = ref(false)
const detailVisible = ref(false); const detailItem = ref<AnspireResult | null>(null); const sessions = ref<AnspireSession[]>([]); const leads = ref<AnspireLead[]>([]); const resultPageSize = 10
const expandedIndexes = ref<Set<number>>(new Set())
const RESULT_PREVIEW_LENGTH = 280

const pagedResults = computed(() => results.value.slice((resultPage.value - 1) * resultPageSize, resultPage.value * resultPageSize))
const selectableResults = computed(() => results.value.filter(item => !savedIndexes.value.has(item.result_index)))
const selectedCount = computed(() => [...selectedIndexes.value].filter(index => selectableResults.value.some(item => item.result_index === index)).length)
const allSelectableSelected = computed(() => selectableResults.value.length > 0 && selectableResults.value.every(item => selectedIndexes.value.has(item.result_index)))
const isSelectionIndeterminate = computed(() => selectedCount.value > 0 && !allSelectableSelected.value)
function resultText(item: AnspireResult) { return item.summary || item.snippet || '暂无摘要' }
function isLongResult(item: AnspireResult) { return resultText(item).length > RESULT_PREVIEW_LENGTH }
function isExpanded(index: number) { return expandedIndexes.value.has(index) }
function visibleResultText(item: AnspireResult) {
  const text = resultText(item)
  return !isLongResult(item) || isExpanded(item.result_index) ? text : `${text.slice(0, RESULT_PREVIEW_LENGTH)}…`
}
function toggleExpanded(index: number) {
  const next = new Set(expandedIndexes.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  expandedIndexes.value = next
}

async function handleSearch() {
  const query = form.value.query.trim()
  if (!query) { errorMessage.value = '请输入搜索关键词'; return }
  searching.value = true; errorMessage.value = ''
  try {
    const { data } = await api.post('/anspire/search', { query, top_k: form.value.top_k, insite: form.value.insite, from_time: form.value.from_time || undefined, to_time: form.value.to_time || undefined, region_mode: form.value.region_mode })
    store.setResult(data.session, data.items || [])
    ElMessage.success(`搜索完成，返回 ${data.total || 0} 条结果`)
    await loadSessions()
  } catch (err: any) { errorMessage.value = err?.response?.data?.detail || 'Anspire 搜索暂时不可用' } finally { searching.value = false }
}

async function persistLead(item: AnspireResult, showMessage = true): Promise<boolean> {
  if (!activeSession.value) return false
  savingIndex.value = item.result_index
  try { const { data } = await api.post<AnspireLead>('/anspire/leads', { session_id: activeSession.value.id, result_index: item.result_index }); store.markSaved(item.result_index); if (showMessage) ElMessage.success(data.status === 'new' ? '已保存为线索' : '线索已存在'); window.dispatchEvent(new CustomEvent('bocha-leads-refresh')); return true } catch (err: any) { if (showMessage) ElMessage.error(err?.response?.data?.detail || '保存线索失败'); return false } finally { savingIndex.value = null }
}
async function saveLead(item: AnspireResult) { if (await persistLead(item)) await loadLeads() }
async function saveSelectedLeads() { if (!activeSession.value || bulkSaving.value) return; const items = selectableResults.value.filter(item => selectedIndexes.value.has(item.result_index)); if (!items.length) return; bulkSaving.value = true; let success = 0; try { for (const item of items) if (await persistLead(item, false)) success += 1; if (success) { ElMessage.success(`已保存 ${success} 条线索`); await loadLeads() } } finally { bulkSaving.value = false } }
function toggleSelect(item: AnspireResult, checked: boolean) { if (!savedIndexes.value.has(item.result_index)) store.setSelected(item.result_index, checked) }
function toggleSelectAll(checked: boolean) { store.setSelectedIndexes(checked ? selectableResults.value.map(item => item.result_index) : []) }
function openResultDetail(item: AnspireResult) { detailItem.value = item; detailVisible.value = true }

async function loadSessions() { sessionsLoading.value = true; try { const createdFrom = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(); const { data } = await api.get<ListResponse<AnspireSession>>('/anspire/sessions', { params: { page: 1, size: 50, created_from: createdFrom } }); const cutoff = Date.now() - 3 * 24 * 60 * 60 * 1000; sessions.value = (data.items || []).filter(item => new Date(item.created_at).getTime() >= cutoff) } catch { ElMessage.error('搜索历史加载失败') } finally { sessionsLoading.value = false } }
async function loadLeads() { leadsLoading.value = true; try { const { data } = await api.get<ListResponse<AnspireLead>>('/anspire/leads', { params: { page: 1, size: 8 } }); leads.value = data.items || [] } catch { ElMessage.error('我的线索加载失败') } finally { leadsLoading.value = false } }
function formatTime(value?: string | null) { if (!value) return '-'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
function statusText(status: AnspireLeadStatus) { return ({ new: '待确认', confirmed: '已确认', rejected: '已驳回', promoted: '已晋级' } as Record<AnspireLeadStatus, string>)[status] || status }
function statusType(status: AnspireLeadStatus): 'success' | 'warning' | 'info' | 'danger' { if (status === 'confirmed') return 'success'; if (status === 'rejected') return 'danger'; if (status === 'promoted') return 'warning'; return 'info' }
onMounted(() => { loadSessions(); loadLeads() })
watch(() => results.value.length, total => { const maxPage = Math.max(1, Math.ceil(total / resultPageSize)); if (resultPage.value > maxPage) store.setResultPage(maxPage) }, { immediate: true })
</script>

<style scoped>
.anspire-page{min-width:0}.search-panel{background:#fff;border-radius:18px;padding:18px 20px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 12px 32px rgba(0,0,0,.05);margin-bottom:18px}.search-form{display:grid;grid-template-columns:minmax(280px,1fr) 130px 140px 180px 170px 170px 104px;gap:12px;align-items:end}.keyword-field{min-width:0}.date-field{width:100%}.search-button{width:100%}.error-alert{margin-top:12px}.content-grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:18px;align-items:start}.results-column,.side-panel{background:#fff;border-radius:18px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 12px 32px rgba(0,0,0,.05)}.results-column{padding:18px;min-height:560px}.side-column{display:flex;flex-direction:column;gap:18px}.side-panel{padding:16px}.section-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}.section-head h2{font-size:18px;font-weight:600;color:#1d1d1f;margin:0}.section-head p{font-size:13px;color:#86868b;margin:4px 0 0}.section-head.compact{align-items:center;margin-bottom:8px}.section-head.compact h2{font-size:16px}.session-actions{display:flex;align-items:center;gap:8px}.bulk-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 12px;margin-bottom:6px;border-radius:12px;background:#f5f5f7}.bulk-count{color:#86868b;font-size:13px;margin-right:auto}.result-list{min-height:420px}.result-pagination{display:flex;justify-content:flex-end;padding-top:14px;border-top:1px solid #e8e8ed}.result-item{display:flex;justify-content:space-between;gap:18px;padding:16px 0;border-top:1px solid #e8e8ed}.result-item:first-child{border-top:none}.result-check{flex:0 0 auto;padding-top:2px}.result-main{flex:1 1 auto;min-width:0}.result-title-row{display:flex;align-items:center;gap:10px;min-width:0}.result-title{color:#1d1d1f;font-size:16px;font-weight:600;line-height:1.45;text-decoration:none;overflow-wrap:anywhere}.result-title:hover{color:#0071e3}.result-title-button{padding:0;border:none;background:transparent;cursor:pointer;text-align:left;font-family:inherit}.result-meta,.mini-meta{display:flex;align-items:center;flex-wrap:wrap;gap:8px;color:#86868b;font-size:12.5px;margin-top:6px}.result-text{color:#424245;font-size:14px;line-height:1.65;margin:10px 0 4px;overflow-wrap:anywhere}.expand-result-button{padding:0;height:22px}.source-link{display:inline-block;max-width:100%;color:#0071e3;font-size:12.5px;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.save-lead-button{flex:0 0 auto;min-width:112px;color:#0071e3!important;border-color:#b7d7f8!important;background:#f5faff!important;opacity:1!important}.save-lead-button:not(.is-disabled):hover{color:#fff!important;border-color:#0071e3!important;background:#0071e3!important}.mini-list{min-height:120px}.history-list{max-height:320px;overflow-y:auto;padding-right:4px}.mini-item{padding:12px 0;border-top:1px solid #e8e8ed}.mini-item:first-child{border-top:none}.mini-title{color:#1d1d1f;font-size:13.5px;font-weight:600;line-height:1.45;overflow-wrap:anywhere}.raw-json{max-height:300px;overflow:auto;white-space:pre-wrap;font-size:12px;background:#f5f5f7;padding:10px;border-radius:8px;margin:0 0 12px}@media(max-width:1180px){.search-form{grid-template-columns:1fr 1fr 1fr}.keyword-field{grid-column:span 3}.content-grid{grid-template-columns:1fr}.side-column{display:grid;grid-template-columns:1fr 1fr}}@media(max-width:680px){.search-panel,.results-column,.side-panel{border-radius:14px}.search-form{grid-template-columns:1fr}.keyword-field{grid-column:auto}.side-column{display:flex}.result-item{flex-direction:column}.session-actions{align-items:flex-end;flex-direction:column}}
.expand-result-button,.expand-result-button.el-button{display:inline;padding:0;margin-left:4px;min-height:0;height:auto;line-height:inherit;vertical-align:baseline}
</style>
