<template>
  <div class="bocha-review">
    <section class="review-panel">
      <div class="section-head">
        <div>
          <h2>AI线索审核</h2>
          <p>确认用户主动保存的 AI 检索线索，确认后才允许显式晋级为舆情。</p>
        </div>
        <el-button text type="primary" :loading="loading" @click="loadLeads">刷新</el-button>
      </div>

      <div class="filters">
        <el-select v-model="filters.status" clearable placeholder="全部状态" @change="handleFilterChange">
          <el-option label="待确认" value="new" />
          <el-option label="已确认" value="confirmed" />
          <el-option label="已驳回" value="rejected" />
          <el-option label="已晋级" value="promoted" />
        </el-select>
        <el-select v-model="filters.provider" clearable placeholder="Provider" @change="handleFilterChange">
          <el-option label="Bocha" value="bocha" />
          <el-option label="Anspire" value="anspire" />
        </el-select>
        <el-input
          v-model="filters.query"
          clearable
          placeholder="按关键词筛选"
          @keyup.enter="handleFilterChange"
          @clear="handleFilterChange"
        />
        <el-button class="query-button" type="primary" plain @click="handleFilterChange">查询</el-button>
      </div>

      <div class="bulk-toolbar">
        <el-checkbox
          :model-value="allCurrentPageSelected"
          :indeterminate="isCurrentPageSelectionIndeterminate"
          :disabled="!leads.length || loading || batchOperating"
          @change="toggleSelectCurrentPage"
        >
          全选当前页
        </el-checkbox>
        <span class="bulk-count">已选择 {{ selectedLeads.length }} 条</span>
        <el-button
          type="primary"
          plain
          :disabled="!batchConfirmable.length"
          :loading="batchOperating"
          @click="batchConfirm"
        >
          批量确认
        </el-button>
        <el-button
          type="danger"
          plain
          :disabled="!batchRejectable.length"
          :loading="batchOperating"
          @click="batchReject"
        >
          批量驳回
        </el-button>
        <el-button
          type="success"
          plain
          :disabled="!batchPromotable.length"
          :loading="batchOperating"
          @click="openBatchPromoteDialog"
        >
          批量晋级
        </el-button>
      </div>

      <el-table
        ref="leadTableRef"
        v-loading="loading"
        :data="leads"
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column label="线索标题" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <button class="title-link" type="button" @click="openDetail(row)">
              {{ row.title || row.url }}
            </button>
          </template>
        </el-table-column>
        <el-table-column prop="query" label="检索词" width="160" show-overflow-tooltip />
        <el-table-column prop="source_name" label="来源" width="150" show-overflow-tooltip />
        <el-table-column label="创建人" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.creator_name || (row.created_by != null ? '用户#' + row.created_by : '-') }}</template>
        </el-table-column>
        <el-table-column label="Provider" width="120"><template #default="{ row }"><el-tag size="small" effect="plain">{{ row.provider === 'anspire' ? 'Anspire' : 'Bocha' }}</el-tag><span v-if="row.provider_score != null"> {{ row.provider_score }}</span></template></el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)" effect="light">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'new'"
              type="primary"
              size="small"
              @click="confirmLead(row)"
            >
              确认
            </el-button>
            <el-button
              v-if="row.status === 'new' || row.status === 'confirmed'"
              type="danger"
              plain
              size="small"
              @click="rejectLead(row)"
            >
              驳回
            </el-button>
            <el-button
              v-if="row.status === 'confirmed'"
              type="success"
              plain
              size="small"
              @click="openPromoteDialog(row)"
            >
              晋级
            </el-button>
            <span v-if="row.status === 'rejected' || row.status === 'promoted'" class="action-muted">无需操作</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无待审核线索" :image-size="80" />
        </template>
      </el-table>

      <div class="pagination-row">
        <Pager
          v-model:current-page="page"
          :page-size="size"
          :total="total"
          @current-change="loadLeads"
        />
      </div>
    </section>

    <el-dialog
      v-model="promoteDialogVisible"
      :title="promoteDialogTitle"
      width="520px"
      align-center
    >
      <div v-loading="regionsLoading" class="promote-form">
        <div class="promote-lead-title">{{ promoteDialogLeadTitle }}</div>
        <el-select
          v-model="promoteRegionId"
          filterable
          clearable
          placeholder="按地区名称选择"
          class="region-select"
        >
          <el-option
            v-for="region in regions"
            :key="region.id"
            :label="regionLabel(region)"
            :value="region.id"
          />
        </el-select>
        <p v-if="isBatchPromote" class="promote-warning">
          所选 {{ promoteTargets.length }} 条线索将全部晋级到同一个地区。跨地区线索建议取消后逐条晋级。
        </p>
        <p class="promote-tip">晋级仅创建正式舆情记录，后续风险分析、事件聚合和预警需按照系统流程人工触发。</p>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="promoteDialogVisible = false">取消</el-button>
          <el-button
            type="success"
            :loading="promoting"
            :disabled="!promoteRegionId"
            @click="submitPromote"
          >
            {{ isBatchPromote ? '确认批量晋级' : '确认晋级' }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <BochaDetailModal v-model="detailVisible" :item="detailItem" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import BochaDetailModal from '@/components/BochaDetailModal.vue'
import type { BochaLead, LeadStatus } from '@/stores/bocha'

interface ListResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

interface RegionOption {
  id: number
  code: string
  name: string
  level: string
}

const loading = ref(false)
const leadTableRef = ref<any>(null)
const leads = ref<BochaLead[]>([])
const selectedLeads = ref<BochaLead[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const detailVisible = ref(false)
const detailItem = ref<BochaLead | null>(null)
const promoteDialogVisible = ref(false)
const promoteTarget = ref<BochaLead | null>(null)
const promoteTargets = ref<BochaLead[]>([])
const promoteRegionId = ref<number | null>(null)
const promoting = ref(false)
const batchOperating = ref(false)
const regionsLoading = ref(false)
const regions = ref<RegionOption[]>([])
const filters = reactive({
  status: '' as LeadStatus | '',
  provider: '' as '' | 'bocha' | 'anspire',
  query: '',
})

const batchConfirmable = computed(() => selectedLeads.value.filter((lead) => lead.status === 'new'))
const batchRejectable = computed(() =>
  selectedLeads.value.filter((lead) => lead.status === 'new' || lead.status === 'confirmed')
)
const batchPromotable = computed(() => selectedLeads.value.filter((lead) => lead.status === 'confirmed'))
const selectedLeadIds = computed(() => new Set(selectedLeads.value.map((lead) => lead.id)))
const allCurrentPageSelected = computed(() =>
  leads.value.length > 0 && leads.value.every((lead) => selectedLeadIds.value.has(lead.id))
)
const isCurrentPageSelectionIndeterminate = computed(() =>
  selectedLeads.value.length > 0 && !allCurrentPageSelected.value
)
const isBatchPromote = computed(() => promoteTargets.value.length > 1)
const promoteDialogTitle = computed(() => (isBatchPromote.value ? '批量晋级为舆情' : '晋级为舆情'))
const promoteDialogLeadTitle = computed(() => {
  if (isBatchPromote.value) return `已选择 ${promoteTargets.value.length} 条已确认线索`
  return promoteTarget.value?.title || promoteTarget.value?.url || ''
})

async function loadLeads() {
  loading.value = true
  try {
    const { data } = await api.get<ListResponse<BochaLead>>('/admin/bocha/leads', {
      params: {
        page: page.value,
        size: size.value,
        status: filters.status || undefined,
        provider: filters.provider || undefined,
        query: filters.query.trim() || undefined,
      },
    })
    leads.value = data.items || []
    selectedLeads.value = []
    total.value = data.total || 0
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'AI线索加载失败')
  } finally {
    loading.value = false
  }
}

async function loadRegions() {
  regionsLoading.value = true
  try {
    const { data } = await api.get<RegionOption[]>('/admin/regions')
    regions.value = data || []
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '地区列表加载失败')
  } finally {
    regionsLoading.value = false
  }
}

function handleFilterChange() {
  page.value = 1
  loadLeads()
}

function handleSelectionChange(rows: BochaLead[]) {
  selectedLeads.value = rows
}

function toggleSelectCurrentPage(checked: boolean) {
  const table = leadTableRef.value
  if (!table) return
  for (const lead of leads.value) {
    table.toggleRowSelection(lead, checked)
  }
}

async function confirmLead(lead: BochaLead) {
  try {
    await api.post(`/admin/bocha/leads/${lead.id}/confirm`)
    ElMessage.success('线索已确认')
    window.dispatchEvent(new CustomEvent('bocha-leads-refresh'))
    await loadLeads()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '确认线索失败')
  }
}

async function rejectLead(lead: BochaLead) {
  let reason = ''
  try {
    const prompt = await ElMessageBox.prompt('可选填驳回原因', '驳回线索', {
      confirmButtonText: '驳回',
      cancelButtonText: '取消',
      inputPlaceholder: '请输入原因',
      inputValidator: (value: string) => value.length <= 1000 || '原因不能超过 1000 个字符',
    })
    reason = prompt.value || ''
  } catch {
    return
  }

  try {
    await api.post(`/admin/bocha/leads/${lead.id}/reject`, { reason })
    ElMessage.success('线索已驳回')
    window.dispatchEvent(new CustomEvent('bocha-leads-refresh'))
    await loadLeads()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '驳回线索失败')
  }
}

async function batchConfirm() {
  if (!batchConfirmable.value.length || batchOperating.value) return
  batchOperating.value = true
  let success = 0
  let failed = 0
  try {
    for (const lead of batchConfirmable.value) {
      try {
        await api.post(`/admin/bocha/leads/${lead.id}/confirm`)
        success += 1
      } catch {
        failed += 1
      }
    }
    if (success > 0) {
      ElMessage.success(`已确认 ${success} 条线索${failed ? `，${failed} 条失败` : ''}`)
      window.dispatchEvent(new CustomEvent('bocha-leads-refresh'))
      await loadLeads()
    } else {
      ElMessage.error('批量确认失败')
    }
  } finally {
    batchOperating.value = false
  }
}

async function batchReject() {
  if (!batchRejectable.value.length || batchOperating.value) return
  let reason = ''
  try {
    const prompt = await ElMessageBox.prompt('可选填批量驳回原因', '批量驳回线索', {
      confirmButtonText: '批量驳回',
      cancelButtonText: '取消',
      inputPlaceholder: '请输入原因',
      inputValidator: (value: string) => value.length <= 1000 || '原因不能超过 1000 个字符',
    })
    reason = prompt.value || ''
  } catch {
    return
  }

  batchOperating.value = true
  let success = 0
  let failed = 0
  try {
    for (const lead of batchRejectable.value) {
      try {
        await api.post(`/admin/bocha/leads/${lead.id}/reject`, { reason })
        success += 1
      } catch {
        failed += 1
      }
    }
    if (success > 0) {
      ElMessage.success(`已驳回 ${success} 条线索${failed ? `，${failed} 条失败` : ''}`)
      window.dispatchEvent(new CustomEvent('bocha-leads-refresh'))
      await loadLeads()
    } else {
      ElMessage.error('批量驳回失败')
    }
  } finally {
    batchOperating.value = false
  }
}

function openPromoteDialog(lead: BochaLead) {
  promoteTarget.value = lead
  promoteTargets.value = [lead]
  promoteRegionId.value = null
  promoteDialogVisible.value = true
  if (!regions.value.length) loadRegions()
}

function openBatchPromoteDialog() {
  if (!batchPromotable.value.length) return
  promoteTarget.value = batchPromotable.value[0] || null
  promoteTargets.value = [...batchPromotable.value]
  promoteRegionId.value = null
  promoteDialogVisible.value = true
  if (!regions.value.length) loadRegions()
}

async function submitPromote() {
  if (!promoteTargets.value.length || !promoteRegionId.value || promoting.value) return
  promoting.value = true
  const targets = [...promoteTargets.value]
  let success = 0
  let already = 0
  let failed = 0
  try {
    for (const lead of targets) {
      try {
        const { data } = await api.post(`/admin/bocha/leads/${lead.id}/promote`, {
          region_id: promoteRegionId.value,
        })
        if (data.already_promoted) already += 1
        else success += 1
      } catch {
        failed += 1
      }
    }
    if (success || already) {
      if (targets.length === 1) {
        ElMessage.success(already ? '线索已晋级过' : '线索已晋级为舆情')
      } else {
        ElMessage.success(
          `已晋级 ${success} 条线索${already ? `，${already} 条已晋级过` : ''}${failed ? `，${failed} 条失败` : ''}`,
        )
      }
      promoteDialogVisible.value = false
      window.dispatchEvent(new CustomEvent('bocha-leads-refresh'))
      await loadLeads()
    } else {
      ElMessage.error(targets.length === 1 ? '晋级线索失败' : '批量晋级失败')
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '晋级线索失败')
  } finally {
    promoting.value = false
    if (!promoteDialogVisible.value) {
      promoteTarget.value = null
      promoteTargets.value = []
    }
  }
}

function openDetail(lead: BochaLead) {
  detailItem.value = lead
  detailVisible.value = true
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

function regionLabel(region: RegionOption): string {
  const levelText: Record<string, string> = {
    province: '省级',
    city: '市级',
    county: '区县',
    street: '街道',
    unit: '单位',
  }
  return `${region.name}${region.level ? `（${levelText[region.level] || region.level}）` : ''}`
}

onMounted(() => {
  loadLeads()
  loadRegions()
})
</script>

<style scoped>
.bocha-review {
  min-height: 100%;
}

.review-panel {
  background: #fff;
  border-radius: 18px;
  padding: 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04), 0 12px 32px rgba(0, 0, 0, .05);
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

.filters {
  display: grid;
  grid-template-columns: 160px minmax(220px, 320px) 88px;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
}

.query-button {
  color: #0071e3 !important;
  border-color: #b7d7f8 !important;
  background: #f5faff !important;
  opacity: 1 !important;
}

.query-button:hover {
  color: #fff !important;
  border-color: #0071e3 !important;
  background: #0071e3 !important;
}

.bulk-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 12px;
  margin-bottom: 14px;
  border-radius: 12px;
  background: #f5f5f7;
}

.bulk-count {
  color: #86868b;
  font-size: 13px;
  margin-right: auto;
}

.title-link {
  padding: 0;
  border: none;
  background: transparent;
  color: #1d1d1f;
  font: inherit;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-link:hover {
  color: #0071e3;
}

.action-muted {
  color: #a1a1a6;
  font-size: 12px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.promote-form {
  display: grid;
  gap: 12px;
}

.promote-lead-title {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.region-select {
  width: 100%;
}

.promote-tip {
  color: #86868b;
  font-size: 12.5px;
  line-height: 1.6;
  margin: 0;
}

.promote-warning {
  color: #b26a00;
  background: #fff7e6;
  border: 1px solid #ffe0a3;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12.5px;
  line-height: 1.6;
  margin: 0;
}

.dialog-footer {
  display: inline-flex;
  gap: 10px;
}

@media (max-width: 720px) {
  .review-panel {
    border-radius: 14px;
  }

  .section-head {
    flex-direction: column;
  }

  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
