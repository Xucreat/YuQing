<template>
  <div class="alerts" v-loading="loading">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="预警规则" name="rules">
        <el-card shadow="never" class="filter-card">
          <el-button type="primary" @click="openRuleDialog(null)">新增规则</el-button>
          <el-button @click="loadRules">刷新</el-button>
          <el-button type="warning" :loading="evaluating" @click="handleEvaluate">执行评估</el-button>
          <span v-if="evalResult" class="eval-result">评估完成：检查 {{ evalResult.total_checked }} 条，生成 {{ evalResult.alerts_created }} 条预警</span>
        </el-card>

        <el-card shadow="never" class="table-card">
          <el-table :data="rules" stripe>
            <el-table-column type="index" :index="(idx: number) => (rulesPage - 1) * rulesSize + idx + 1" label="ID" width="70" />
            <el-table-column prop="name" label="规则名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
            <el-table-column label="风险阈值" width="100" align="center">
              <template #default="{ row }">{{ row.risk_threshold }}</template>
            </el-table-column>
            <el-table-column label="预警等级" width="120" align="center">
              <template #default="{ row }"><el-tag :type="riskTag(row.risk_level)" size="small">{{ riskText(row.risk_level) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled" @change="(val: boolean) => toggleRule(row, val)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" align="center">
              <template #default="{ row }">
                <el-button type="primary" size="small" link @click="openRuleDialog(row)">编辑</el-button>
                <el-button type="danger" size="small" link @click="deleteRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination">
            <el-pagination background layout="total, prev, pager, next" :total="rulesTotal" :current-page="rulesPage" :page-size="rulesSize" @current-change="handleRulesPage" />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="预警记录" name="records">
        <el-card shadow="never" class="filter-card">
          <el-select v-model="recFilterRisk" placeholder="预警等级" clearable style="width: 160px" @change="loadRecords">
            <el-option label="严重" value="critical" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
          <el-select v-model="recFilterStatus" placeholder="处置状态" clearable style="width: 160px; margin-left: 12px" @change="loadRecords">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已忽略" value="ignored" />
            <el-option label="误报" value="false_positive" />
          </el-select>
          <span style="margin-left: 12px; display: inline-flex; align-items: center;">
            <el-switch v-model="hideFalsePositive" @change="loadRecords" />
            <span style="margin-left: 6px;">隐藏误报</span>
          </span>
          <el-date-picker
            v-model="recDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="margin-left: 12px"
            @change="onDateRangeChange"
          />
          <el-button @click="loadRecords" style="margin-left: 12px">刷新</el-button>
        </el-card>

        <el-card shadow="never" class="table-card">
          <el-table :data="records" stripe>
            <el-table-column type="index" :index="(idx: number) => (recordsPage - 1) * recordsSize + idx + 1" label="ID" width="70" />
            <el-table-column prop="rule_name" label="触发规则" width="200" show-overflow-tooltip />
            <el-table-column label="预警等级" width="120" align="center">
              <template #default="{ row }"><el-tag :type="riskTag(row.risk_level)" size="small">{{ riskText(row.risk_level) }}</el-tag></template>
            </el-table-column>
                        <el-table-column label="关联舆情" min-width="220">
              <template #default="{ row }">
                <span v-if="row.opinion_id" class="nav-link" style="cursor:pointer" @click="openOpinion(row.opinion_id)">{{ row.opinion_title }}</span>
                <span v-else>{{ row.opinion_title || '-' }}</span>
              </template>
            </el-table-column>
                        <el-table-column label="关联事件" width="180">
              <template #default="{ row }">
                <router-link v-if="row.event_id" :to="'/event/' + row.event_id" class="nav-link">{{ row.event_title }}</router-link>
                <span v-else>{{ row.event_title || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="trigger_reason" label="触发原因" min-width="220" show-overflow-tooltip />
            <el-table-column label="处置状态" width="110" align="center">
              <template #default="{ row }"><el-tag :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="处置人" width="100" align="center">
              <template #default="{ row }">{{ row.handled_by_name ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="触发时间" width="180">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button type="primary" size="small" link @click="openHandleDialog(row)">处置</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination">
            <el-pagination background layout="total, prev, pager, next" :total="recordsTotal" :current-page="recordsPage" :page-size="recordsSize" @current-change="handleRecordsPage" />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Rule Form Dialog -->
    <el-dialog v-model="ruleDialogVisible" :title="isEditing ? '编辑规则' : '新增规则'" width="600px">
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="规则名称"><el-input v-model="ruleForm.name" placeholder="请输入规则名称" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="ruleForm.description" type="textarea" :rows="2" placeholder="描述该规则的用途" /></el-form-item>
        <el-form-item label="风险阈值"><el-input-number v-model="ruleForm.risk_threshold" :min="0" :max="100" /></el-form-item>
        <el-form-item label="关键词匹配"><el-input v-model="ruleForm.keywords" placeholder="多个关键词用逗号分隔" /></el-form-item>
        <el-form-item label="来源过滤"><el-input v-model="ruleForm.sources" placeholder="多个来源用逗号分隔，留空表示不限" /></el-form-item>
        <el-form-item label="建议等级">
          <el-select v-model="ruleForm.risk_level" style="width: 100%">
            <el-option label="严重" value="critical" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
          <div class="form-hint">说明：该等级为规则建议值，不决定实际告警等级（实际等级由舆情风险分派生）。</div>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="ruleForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>

    <!-- Handle (处置) Dialog -->
    <el-dialog v-model="handleDialogVisible" title="预警处置" width="480px">
      <el-form :model="handleForm" label-width="88px">
        <el-form-item label="处置状态">
          <el-select v-model="handleForm.status" style="width: 100%">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已忽略" value="ignored" />
            <el-option label="误报" value="false_positive" />
          </el-select>
        </el-form-item>
        <el-form-item label="处置备注">
          <el-input v-model="handleForm.note" type="textarea" :rows="3" placeholder="可选：填写处置说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="handling" @click="submitHandle">确认处置</el-button>
      </template>
    </el-dialog>

    <OpinionDetailModal v-model="detailVisible" :opinion-id="detailId" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { riskText, riskTag } from '@/utils/alert'
import type { AlertRule, AlertRuleListResponse, AlertRecord, AlertRecordListResponse, AlertEvaluateResponse } from '@/types'
import OpinionDetailModal from '@/components/OpinionDetailModal.vue'
import { useAlertNotifier } from '@/composables/useAlertNotifier'

// 关联舆情跳转：打开舆情详情弹窗（与「舆情列表」一致）
const detailVisible = ref(false)
const detailId = ref<number | null>(null)
function openOpinion(id: number) {
  detailId.value = id
  detailVisible.value = true
}

const activeTab = ref('rules')
const loading = ref(false)
const saving = ref(false)
const evaluating = ref(false)
const route = useRoute()
const notifier = useAlertNotifier()

// Rules
const rules = ref<AlertRule[]>([])
const rulesTotal = ref(0)
const rulesPage = ref(1)
const rulesSize = ref(20)

// Records
const records = ref<AlertRecord[]>([])
const recordsTotal = ref(0)
const recordsPage = ref(1)
const recordsSize = ref(20)
const recFilterRisk = ref<string | null>(null)
const recFilterStatus = ref<string>('')
const hideFalsePositive = ref<boolean>(true)
const recDateRange = ref<[string, string] | null>(null)

// Rule dialog
const ruleDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const ruleForm = reactive({ name: '', description: '', risk_threshold: 70, keywords: '', sources: '', risk_level: 'high', enabled: true })
const evalResult = ref<AlertEvaluateResponse | null>(null)

// 处置弹窗（Phase 2-B.1 告警处置闭环）
const handleDialogVisible = ref(false)
const handling = ref(false)
const handlingId = ref<number | null>(null)
const handleForm = reactive({ status: 'resolved', note: '' })

const STATUS_TEXT: Record<string, string> = {
  pending: '待处理', processing: '处理中', resolved: '已解决', ignored: '已忽略', false_positive: '误报',
}
const STATUS_TAG: Record<string, string> = {
  pending: 'danger', processing: 'warning', resolved: 'success', ignored: 'info', false_positive: 'info',
}
function statusText(s: string): string { return STATUS_TEXT[s] || s || '待处理' }
function statusTag(s: string): string { return STATUS_TAG[s] || 'info' }

function formatTime(t: string): string { if (!t) return '-'; return t.replace('T', ' ').slice(0, 19) }

async function loadRules() {
  loading.value = true
  try {
    const { data } = await api.get<AlertRuleListResponse>('/alerts/rules', { params: { page: rulesPage.value, size: rulesSize.value } })
    rules.value = data.items; rulesTotal.value = data.total
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '加载规则失败') } finally { loading.value = false }
}

async function loadRecords() {
  loading.value = true
  try {
    const params: any = { page: recordsPage.value, size: recordsSize.value }
    if (recFilterRisk.value) params.risk_level = recFilterRisk.value
    if (recFilterStatus.value) params.status = recFilterStatus.value
    if (hideFalsePositive.value) params.exclude_status = 'false_positive'
    if (recDateRange.value && recDateRange.value[0]) params.date_from = recDateRange.value[0]
    if (recDateRange.value && recDateRange.value[1]) params.date_to = recDateRange.value[1]
    const { data } = await api.get<AlertRecordListResponse>('/alerts/records', { params })
    records.value = data.items; recordsTotal.value = data.total
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '加载记录失败') } finally { loading.value = false }
}

function openRuleDialog(rule: AlertRule | null) {
  if (rule) {
    isEditing.value = true; editingId.value = rule.id
    ruleForm.name = rule.name; ruleForm.description = rule.description
    ruleForm.risk_threshold = rule.risk_threshold; ruleForm.keywords = rule.keywords
    ruleForm.sources = rule.sources; ruleForm.risk_level = rule.risk_level; ruleForm.enabled = rule.enabled
  } else {
    isEditing.value = false; editingId.value = null
    ruleForm.name = ''; ruleForm.description = ''; ruleForm.risk_threshold = 70
    ruleForm.keywords = ''; ruleForm.sources = ''; ruleForm.risk_level = 'high'; ruleForm.enabled = true
  }
  ruleDialogVisible.value = true
}

async function saveRule() {
  if (!ruleForm.name.trim()) { ElMessage.warning('请输入规则名称'); return }
  saving.value = true
  try {
    if (isEditing.value && editingId.value) {
      await api.put(`/alerts/rules/${editingId.value}`, ruleForm)
      ElMessage.success('规则已更新')
    } else {
      await api.post('/alerts/rules', ruleForm)
      ElMessage.success('规则已创建')
    }
    ruleDialogVisible.value = false
    await loadRules()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '保存失败') } finally { saving.value = false }
}

async function toggleRule(rule: AlertRule, val: boolean) {
  try {
    await api.put(`/alerts/rules/${rule.id}`, { enabled: val })
    rule.enabled = val
    ElMessage.success(val ? '规则已启用' : '规则已禁用')
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
}

async function deleteRule(rule: AlertRule) {
  try {
    await ElMessageBox.confirm(`确认删除规则「${rule.name}」？`, '提示', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await api.delete(`/alerts/rules/${rule.id}`)
    ElMessage.success('规则已删除')
    await loadRules()
  } catch { /* cancelled */ }
}

async function handleEvaluate() {
  if (evaluating.value) return
  evaluating.value = true
  try {
    const { data } = await api.post<AlertEvaluateResponse>('/alerts/evaluate')
    evalResult.value = data
    ElMessage.success(`评估完成：检查 ${data.total_checked} 条，生成 ${data.alerts_created} 条预警`)
    if (activeTab.value === 'records') await loadRecords()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '评估失败') } finally { evaluating.value = false }
}

function openHandleDialog(rec: AlertRecord) {
  handlingId.value = rec.id
  handleForm.status = rec.status || 'resolved'
  handleForm.note = rec.handle_note || ''
  handleDialogVisible.value = true
}

async function submitHandle() {
  if (handlingId.value == null) return
  handling.value = true
  try {
    const { data } = await api.put<AlertRecord>(`/alerts/records/${handlingId.value}/handle`, {
      status: handleForm.status,
      note: handleForm.note,
    })
    const idx = records.value.findIndex(r => r.id === handlingId.value)
    if (idx >= 0) records.value[idx] = data
    ElMessage.success('处置成功')
    handleDialogVisible.value = false
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '处置失败') } finally { handling.value = false }
}

function handleRulesPage(p: number) { rulesPage.value = p; loadRules() }
function handleRecordsPage(p: number) { recordsPage.value = p; loadRecords() }
function onDateRangeChange() {
  recordsPage.value = 1
  loadRecords()
}

onMounted(() => {
  loadRules()
  // 支持从通知红点/弹窗带 ?tab=records 直接进入预警记录列表，并清除未读红点。
  if (route.query.tab === 'records') {
    activeTab.value = 'records'
    notifier.markVisited()
  }
})

watch(activeTab, (tab) => {
  if (tab === 'records') {
    loadRecords()
    notifier.markVisited()
  }
})

// 外部（红色通知铃铛/弹窗）可能通过路由带 ?tab=records 切入本页，同步切换。
watch(() => route.query.tab, (tab) => {
  if (tab === 'records') {
    activeTab.value = 'records'
    notifier.markVisited()
  }
})
</script>

<style scoped>
.alerts { height: 100%; }
.filter-card { margin-bottom: 16px; }
.table-card { margin-top: 0; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.eval-result { margin-left: 16px; color: #67c23a; font-size: 14px; }

.nav-link { color: #409eff; text-decoration: none; }
.nav-link:hover { text-decoration: underline; }

.form-hint { color: #909399; font-size: 12px; line-height: 1.5; margin-top: 4px; }
</style>
