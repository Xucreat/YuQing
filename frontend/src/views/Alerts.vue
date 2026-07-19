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
            <el-table-column prop="id" label="ID" width="70" />
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
            <el-option label="严重 critical" value="critical" />
            <el-option label="高 high" value="high" />
            <el-option label="中 medium" value="medium" />
            <el-option label="低 low" value="low" />
          </el-select>
          <el-select v-model="recFilterHandled" placeholder="处理状态" clearable style="width: 160px; margin-left: 12px" @change="loadRecords">
            <el-option label="未处理" :value="false" />
            <el-option label="已处理" :value="true" />
          </el-select>
          <el-button @click="loadRecords" style="margin-left: 12px">刷新</el-button>
        </el-card>

        <el-card shadow="never" class="table-card">
          <el-table :data="records" stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="rule_name" label="触发规则" width="200" show-overflow-tooltip />
            <el-table-column label="预警等级" width="120" align="center">
              <template #default="{ row }"><el-tag :type="riskTag(row.risk_level)" size="small">{{ riskText(row.risk_level) }}</el-tag></template>
            </el-table-column>
                        <el-table-column label="关联舆情" min-width="220">
              <template #default="{ row }">
                <router-link v-if="row.opinion_id" :to="'/opinion/' + row.opinion_id" class="nav-link">{{ row.opinion_title }}</router-link>
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
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }"><el-tag :type="row.handled ? 'success' : 'danger'" size="small">{{ row.handled ? '已处理' : '未处理' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="触发时间" width="180">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button v-if="!row.handled" type="success" size="small" link @click="handleRecord(row)">标记处理</el-button>
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
        <el-form-item label="预警等级">
          <el-select v-model="ruleForm.risk_level">
            <el-option label="严重 critical" value="critical" />
            <el-option label="高 high" value="high" />
            <el-option label="中 medium" value="medium" />
            <el-option label="低 low" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="ruleForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import type { AlertRule, AlertRuleListResponse, AlertRecord, AlertRecordListResponse, AlertEvaluateResponse } from '@/types'

const activeTab = ref('rules')
const loading = ref(false)
const saving = ref(false)
const evaluating = ref(false)

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
const recFilterHandled = ref<boolean | null>(null)

// Rule dialog
const ruleDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const ruleForm = reactive({ name: '', description: '', risk_threshold: 70, keywords: '', sources: '', risk_level: 'high', enabled: true })
const evalResult = ref<AlertEvaluateResponse | null>(null)

function riskTag(level: string): 'danger' | 'warning' | 'success' | 'info' {
  return ({ critical: 'danger', high: 'danger', medium: 'warning', low: 'info' } as const)[level] || 'info'
}
function riskText(level: string): string { return ({ critical: '严重', high: '高', medium: '中', low: '低' } as const)[level] || level }
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
    if (recFilterHandled.value !== null) params.handled = recFilterHandled.value
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

async function handleRecord(rec: AlertRecord) {
  try {
    await api.put(`/alerts/records/${rec.id}/handle`)
    rec.handled = true
    ElMessage.success('已标记为已处理')
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
}

function handleRulesPage(p: number) { rulesPage.value = p; loadRules() }
function handleRecordsPage(p: number) { recordsPage.value = p; loadRecords() }

onMounted(() => { loadRules() })

watch(activeTab, (tab) => {
  if (tab === 'records') loadRecords()
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
</style>
