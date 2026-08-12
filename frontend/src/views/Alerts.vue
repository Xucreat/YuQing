<template>
  <div class="alerts" v-loading="loading">
    <div class="top-scope-switch">
      <el-radio-group v-model="scope" @change="loadScope">
        <el-radio-button label="domestic">国内</el-radio-button>
        <el-radio-button label="foreign">外网</el-radio-button>
      </el-radio-group>
    </div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="预警规则" name="rules">
        <div class="scope-bar">
          <el-button @click="loadCurrentScope">刷新</el-button>
          <el-button v-if="scope === 'domestic' && canWriteAlert" type="primary" @click="openDomesticRule(null)">新增规则</el-button>
          <el-button v-if="scope === 'domestic' && canWriteAlert" type="warning" :loading="evaluating" @click="handleEvaluate">执行评估</el-button>
          <el-button v-if="scope === 'foreign' && canForeignRuleWrite" type="primary" @click="openForeignRule(null)">新增外网规则</el-button>
          <span v-if="evalResult && scope === 'domestic'" class="eval-result">检查 {{ evalResult.total_checked }} 条，生成 {{ evalResult.alerts_created }} 条</span>
        </div>

        <el-card v-if="scope === 'domestic'" shadow="never" class="table-card">
          <el-table :data="rules" stripe>
            <el-table-column type="index" :index="(idx: number) => (rulesPage - 1) * rulesSize + idx + 1" label="ID" width="70" />
            <el-table-column prop="name" label="规则名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
            <el-table-column label="风险阈值" width="100"><template #default="{ row }">{{ row.risk_threshold }}</template></el-table-column>
            <el-table-column label="预警等级" width="120"><template #default="{ row }"><el-tag :type="riskTag(row.risk_level)" size="small">{{ riskText(row.risk_level) }}</el-tag></template></el-table-column>
            <el-table-column label="状态" width="100"><template #default="{ row }"><el-switch v-if="canWriteAlert" :model-value="row.enabled" @change="(val: boolean) => toggleDomesticRule(row, val)" /><el-tag v-else size="small">{{ row.enabled ? '已启用' : '已停用' }}</el-tag></template></el-table-column>
            <el-table-column v-if="canWriteAlert" label="操作" width="160"><template #default="{ row }"><el-button link type="primary" @click="openDomesticRule(row)">编辑</el-button><el-button link type="danger" @click="deleteDomesticRule(row)">删除</el-button></template></el-table-column>
          </el-table>
          <div class="pagination"><Pager :total="rulesTotal" :current-page="rulesPage" :page-size="rulesSize" @current-change="(p: number) => { rulesPage = p; loadDomesticRules() }" /></div>
        </el-card>

        <el-card v-else shadow="never" class="table-card">
          <el-table :data="foreignRules" stripe>
            <el-table-column prop="name" label="规则名称" min-width="220" show-overflow-tooltip />
            <el-table-column prop="rule_type" label="类型" width="150" />
            <el-table-column prop="severity" label="严重度" width="100" />
            <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag size="small" :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '已启用' : '已停用' }}</el-tag></template></el-table-column>
            <el-table-column v-if="canForeignRuleWrite" label="操作" width="260"><template #default="{ row }"><el-button link type="primary" @click="openForeignRule(row)">编辑</el-button><el-button link @click="toggleForeignRule(row)">{{ row.is_enabled ? '停用' : '启用' }}</el-button><el-button v-if="!row.is_enabled" link type="danger" @click="deleteForeignRule(row)">删除</el-button></template></el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="预警记录" name="records">
        <div class="scope-bar">
          <el-button @click="loadCurrentScope">刷新</el-button>
          <el-button v-if="scope === 'domestic' && canWriteAlert" type="warning" :loading="evaluating" @click="handleEvaluate">执行评估</el-button>
          <el-button v-if="scope === 'foreign' && canEvaluateForeign" type="warning" :loading="foreignEvaluating" @click="evaluateForeign">执行外网评估</el-button>
        </div>

        <el-card v-if="scope === 'domestic'" shadow="never" class="filter-card">
          <el-select v-model="recFilterRisk" placeholder="预警等级" clearable class="filter-select" @change="loadDomesticRecords"><el-option label="严重" value="critical" /><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select>
          <el-select v-model="recFilterStatus" placeholder="处置状态" clearable class="filter-select" @change="loadDomesticRecords"><el-option label="待处理" value="pending" /><el-option label="处理中" value="processing" /><el-option label="已解决" value="resolved" /><el-option label="已忽略" value="ignored" /><el-option label="误报" value="false_positive" /></el-select>
          <span class="inline-switch"><el-switch v-model="hideFalsePositive" @change="loadDomesticRecords" />隐藏误报</span>
          <el-date-picker v-model="recDateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" @change="loadDomesticRecords" />
        </el-card>
        <el-card v-else shadow="never" class="filter-card">
          <el-select v-model="foreignFilters.status" placeholder="状态" clearable class="filter-select" @change="loadForeignRecords"><el-option label="待确认" value="triggered" /><el-option label="已确认" value="acknowledged" /><el-option label="已解决" value="resolved" /><el-option label="已抑制" value="suppressed" /><el-option label="失败" value="failed" /></el-select>
          <el-select v-model="foreignFilters.severity" placeholder="严重度" clearable class="filter-select" @change="loadForeignRecords"><el-option label="低" value="low" /><el-option label="中" value="medium" /><el-option label="高" value="high" /><el-option label="紧急" value="critical" /></el-select>
          <el-input v-model="foreignFilters.source" placeholder="来源" clearable class="filter-select" @keyup.enter="loadForeignRecords" />
          <el-date-picker v-model="foreignDateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" @change="loadForeignRecords" />
        </el-card>

        <el-card v-if="scope === 'domestic'" shadow="never" class="table-card"><el-table :data="records" stripe>
          <el-table-column type="index" label="ID" width="70" /><el-table-column prop="rule_name" label="触发规则" width="200" show-overflow-tooltip /><el-table-column label="预警等级" width="110"><template #default="{ row }"><el-tag :type="riskTag(row.risk_level)" size="small">{{ riskText(row.risk_level) }}</el-tag></template></el-table-column><el-table-column label="关联舆情" min-width="220"><template #default="{ row }"><span v-if="row.opinion_id" class="nav-link" @click="openOpinion(row.opinion_id)">{{ row.opinion_title }}</span><span v-else>{{ row.opinion_title || '-' }}</span></template></el-table-column><el-table-column prop="trigger_reason" label="触发原因" min-width="220" show-overflow-tooltip /><el-table-column label="处置状态" width="110"><template #default="{ row }"><el-tag :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag></template></el-table-column><el-table-column label="触发时间" width="180"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column><el-table-column v-if="canWriteAlert" label="操作" width="100"><template #default="{ row }"><el-button link type="primary" @click="openHandleDialog(row)">处置</el-button></template></el-table-column>
        </el-table><div class="pagination"><Pager :total="recordsTotal" :current-page="recordsPage" :page-size="recordsSize" @current-change="(p: number) => { recordsPage = p; loadDomesticRecords() }" /></div></el-card>

        <el-card v-else shadow="never" class="table-card"><el-table :data="foreignAlerts" stripe>
          <el-table-column prop="id" label="ID" width="70" /><el-table-column label="触发规则" width="200" show-overflow-tooltip><template #default="{ row }">{{ row.rule_snapshot?.name || '外网预警规则' }}</template></el-table-column><el-table-column label="预警等级" width="110"><template #default="{ row }"><el-tag :type="riskTag(row.severity)" size="small">{{ riskText(row.severity) }}</el-tag></template></el-table-column><el-table-column label="关联舆情" min-width="240"><template #default="{ row }"><span v-if="row.foreign_opinion_id" class="nav-link" @click="openForeignOpinion(row.foreign_opinion_id)">{{ row.opinion_title_snapshot || row.title || '-' }}</span><span v-else>{{ row.opinion_title_snapshot || row.title || '-' }}</span></template></el-table-column><el-table-column label="触发原因" min-width="260" show-overflow-tooltip><template #default="{ row }">{{ row.message || row.matched_conditions?.reason || row.title || '-' }}</template></el-table-column><el-table-column label="处置状态" width="110"><template #default="{ row }"><el-tag :type="statusTag(row.status)" size="small">{{ foreignText(row.status) }}</el-tag></template></el-table-column><el-table-column label="触发时间" width="180"><template #default="{ row }">{{ formatTime(row.triggered_at) }}</template></el-table-column><el-table-column label="操作" min-width="280"><template #default="{ row }"><el-button link @click="openForeignDetail(row)">详情</el-button><el-button link @click="openForeignHistory(row)">处置历史</el-button><el-button v-if="row.status === 'triggered'" link type="primary" :disabled="!canAcknowledgeForeign" @click="handleForeign(row, 'acknowledge')">确认</el-button><el-button v-if="row.status === 'triggered' || row.status === 'acknowledged'" link type="success" :disabled="!canResolveForeign" @click="handleForeign(row, 'resolve')">解决</el-button><el-button v-if="row.status === 'triggered' || row.status === 'acknowledged'" link type="warning" :disabled="!canSuppressForeign" @click="handleForeign(row, 'suppress')">抑制</el-button></template></el-table-column>
        </el-table></el-card>
      </el-tab-pane>
      <el-tab-pane v-if="scope === 'foreign'" label="外网入口" name="foreign-entry">
        <el-card shadow="never" class="table-card">
          <div class="scope-bar">
            <span class="muted">外网人工复核已在统一的「外网舆情工作台」中处理，AI 结果仅在人工确认后进入正式业务流程。</span>
            <el-button type="primary" @click="goForeignReview">前往外网人工复核中心</el-button>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="domesticRuleDialog" :title="domesticEditing ? '编辑规则' : '新增规则'" width="min(600px, calc(100vw - 24px))"><el-form :model="domesticForm" label-width="100px"><el-form-item label="规则名称"><el-input v-model="domesticForm.name" /></el-form-item><el-form-item label="描述"><el-input v-model="domesticForm.description" type="textarea" /></el-form-item><el-form-item label="风险阈值"><el-input-number v-model="domesticForm.risk_threshold" :min="0" :max="100" /></el-form-item><el-form-item label="关键词匹配"><el-input v-model="domesticForm.keywords" /></el-form-item><el-form-item label="来源过滤"><el-input v-model="domesticForm.sources" /></el-form-item><el-form-item label="建议等级"><el-select v-model="domesticForm.risk_level"><el-option label="严重" value="critical" /><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item><el-form-item label="启用"><el-switch v-model="domesticForm.enabled" /></el-form-item></el-form><template #footer><el-button @click="domesticRuleDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveDomesticRule">保存</el-button></template></el-dialog>
    <el-dialog v-model="foreignRuleDialog" :title="foreignEditing ? '编辑外网告警规则' : '新增外网告警规则'" width="min(620px, calc(100vw - 24px))"><el-form :model="foreignForm" label-width="110px"><el-form-item label="规则名称"><el-input v-model="foreignForm.name" /></el-form-item><el-form-item label="规则类型"><el-select v-model="foreignForm.rule_type"><el-option value="risk_score" label="风险分" /><el-option value="risk_level" label="风险等级" /><el-option value="risk_category" label="风险类别" /><el-option value="confirmed_event" label="确认事件" /><el-option value="keyword_combo" label="关键词组合" /><el-option value="ai_risk_score" label="AI 风险分" /></el-select></el-form-item>
          <p v-if="foreignForm.rule_type === 'ai_risk_score'" class="scope-hint">AI 风险分规则：当某条外网舆情的 AI 研判风险分 ≥ 条件中的 threshold 时，会在「外网人工复核」中生成待确认预警候选，需人工确认后才会进入正式外网预警。</p><el-form-item label="条件 JSON"><el-input v-model="foreignForm.conditionsText" type="textarea" :rows="3" /></el-form-item><el-form-item label="严重度"><el-select v-model="foreignForm.severity"><el-option value="low" label="低" /><el-option value="medium" label="中" /><el-option value="high" label="高" /><el-option value="critical" label="紧急" /></el-select></el-form-item><el-form-item label="冷却时间"><el-input-number v-model="foreignForm.cooldown_seconds" :min="0" /></el-form-item><el-form-item label="说明"><el-input v-model="foreignForm.description" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="foreignRuleDialog = false">取消</el-button><el-button type="primary" :loading="foreignRuleSaving" @click="saveForeignRule">保存</el-button></template></el-dialog>
    <el-dialog v-model="foreignDetailDialog" title="外网预警详情" width="min(760px, calc(100vw - 24px))"><pre class="detail-pre">{{ JSON.stringify(foreignDetail, null, 2) }}</pre></el-dialog>
    <el-dialog v-model="foreignHistoryDialog" title="外网预警处置历史" width="min(680px, calc(100vw - 24px))"><el-empty v-if="!foreignHistory.length" description="暂无处置历史" /><el-timeline v-else><el-timeline-item v-for="item in foreignHistory" :key="item.id" :timestamp="formatTime(item.created_at)">{{ foreignText(item.previous_status) }} → {{ foreignText(item.new_status) }}：{{ item.note || '-' }}</el-timeline-item></el-timeline></el-dialog>
    <el-dialog v-model="handleDialogVisible" title="预警处置" width="min(480px, calc(100vw - 24px))"><el-form label-width="88px"><el-form-item label="处置状态"><el-select v-model="handleForm.status"><el-option label="待处理" value="pending" /><el-option label="处理中" value="processing" /><el-option label="已解决" value="resolved" /><el-option label="已忽略" value="ignored" /><el-option label="误报" value="false_positive" /></el-select></el-form-item><el-form-item label="处置备注"><el-input v-model="handleForm.note" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="handleDialogVisible = false">取消</el-button><el-button type="primary" :loading="handling" @click="submitHandle">确认处置</el-button></template></el-dialog>
    <OpinionDetailModal v-model="detailVisible" :opinion-id="detailId" />
    <ForeignOpinionDetailModal v-model="foreignOpinionDetailVisible" :opinion-id="foreignOpinionDetailId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { isPermissionDenied } from '@/api'
import Pager from '@/components/Pager.vue'
import OpinionDetailModal from '@/components/OpinionDetailModal.vue'
import ForeignOpinionDetailModal from '@/views/foreign/ForeignOpinionDetailModal.vue'
import { usePermission } from '@/composables/usePermission'
import { useAlertNotifier } from '@/composables/useAlertNotifier'
import { riskText, riskTag } from '@/utils/alert'
import type { AlertRule, AlertRuleListResponse, AlertRecord, AlertRecordListResponse, AlertEvaluateResponse } from '@/types'

const route = useRoute(); const router = useRouter(); const notifier = useAlertNotifier(); const { hasPermission } = usePermission()
const activeTab = ref<'rules' | 'records' | 'foreign-entry'>('rules'); const scope = ref<'domestic' | 'foreign'>('domestic')
const loading = ref(false); const saving = ref(false); const evaluating = ref(false); const evalResult = ref<AlertEvaluateResponse | null>(null)
const canWriteAlert = computed(() => hasPermission('alerts:write')); const canEvaluateForeign = computed(() => hasPermission('foreign:alerts:evaluate')); const canForeignRuleWrite = computed(() => hasPermission('foreign:alerts:rules:write')); const canForeignRuleEnable = computed(() => hasPermission('foreign:alerts:enable')); const canAcknowledgeForeign = computed(() => hasPermission('foreign:alerts:acknowledge')); const canResolveForeign = computed(() => hasPermission('foreign:alerts:resolve')); const canSuppressForeign = computed(() => hasPermission('foreign:alerts:suppress')); const canForeignReviewConfirm = computed(() => hasPermission('foreign:alerts:review:confirm')); const canForeignReviewReject = computed(() => hasPermission('foreign:ai:review:reject')); const foreignEvaluating = ref(false)
const rules = ref<AlertRule[]>([]); const rulesTotal = ref(0); const rulesPage = ref(1); const rulesSize = 20; const foreignRules = ref<any[]>([])
const records = ref<AlertRecord[]>([]); const recordsTotal = ref(0); const recordsPage = ref(1); const recordsSize = 20; const recFilterRisk = ref<string | null>(null); const recFilterStatus = ref(''); const hideFalsePositive = ref(true); const recDateRange = ref<[string, string] | null>(null)
const foreignAlerts = ref<any[]>([]); const foreignFilters = reactive({ status: '', severity: '', source: '' }); const foreignDateRange = ref<[string, string] | null>(null)
const domesticRuleDialog = ref(false); const domesticEditing = ref(false); const domesticId = ref<number | null>(null); const domesticForm = reactive({ name: '', description: '', risk_threshold: 70, keywords: '', sources: '', risk_level: 'high', enabled: true })
const foreignRuleDialog = ref(false); const foreignEditing = ref(false); const foreignRuleId = ref<number | null>(null); const foreignRuleSaving = ref(false); const foreignForm = reactive({ name: '', description: '', rule_type: 'risk_score', conditionsText: '{"threshold":80}', severity: 'medium', cooldown_seconds: 3600 })
const handleDialogVisible = ref(false); const handling = ref(false); const handlingId = ref<number | null>(null); const handleForm = reactive({ status: 'resolved', note: '' }); const detailVisible = ref(false); const detailId = ref<number | null>(null)
const foreignDetailDialog = ref(false); const foreignDetail = ref<any>(null); const foreignHistoryDialog = ref(false); const foreignHistory = ref<any[]>([]); const foreignOpinionDetailVisible = ref(false); const foreignOpinionDetailId = ref<number | null>(null)
const STATUS_TEXT: Record<string, string> = { pending: '待处理', processing: '处理中', resolved: '已解决', ignored: '已忽略', false_positive: '误报' }; const STATUS_TAG: Record<string, string> = { pending: 'danger', processing: 'warning', resolved: 'success', ignored: 'info', false_positive: 'info' }; const FOREIGN_TEXT: Record<string, string> = { triggered: '待确认', acknowledged: '已确认', resolved: '已解决', suppressed: '已抑制', failed: '失败', critical: '紧急', high: '高', medium: '中', low: '低', pending_review: '待人工复核', confirmed: '已确认', rejected: '已驳回', superseded: '已替代', use_ai_display: '采用 AI 展示', keep_rule: '保留规则', confirm_event_change: '确认事件影响', confirm_alert_change: '确认预警影响', reject_change: '驳回' }
const statusText = (v: string) => STATUS_TEXT[v] || v || '待处理'; const statusTag = (v: string) => STATUS_TAG[v] || 'info'; const foreignText = (v?: string | null) => v ? (FOREIGN_TEXT[v] || v) : '-'; const formatTime = (v?: string | null) => v ? v.replace('T', ' ').slice(0, 19) : '-'
// 选 AI 风险分类型时自动给出 threshold 条件，避免提交时因缺少 threshold 被后端 422。
watch(() => foreignForm.rule_type, (type) => {
  if (type === 'ai_risk_score' && !/threshold/.test(foreignForm.conditionsText)) {
    foreignForm.conditionsText = '{"threshold":70}'
  }
})
function openOpinion(id: number) { detailId.value = id; detailVisible.value = true }
function openForeignOpinion(id: number) { foreignOpinionDetailId.value = id; foreignOpinionDetailVisible.value = true }

async function loadDomesticRules() { loading.value = true; try { const { data } = await api.get<AlertRuleListResponse>('/alerts/rules', { params: { page: rulesPage.value, size: rulesSize } }); rules.value = data.items; rulesTotal.value = data.total } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '加载规则失败') } finally { loading.value = false } }
async function loadForeignRules() { loading.value = true; try { foreignRules.value = (await api.get('/foreign/alert-rules', { params: { size: 100 } })).data.items || [] } catch (e: any) { foreignRules.value = []; if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '加载外网规则失败') } finally { loading.value = false } }
async function loadDomesticRecords() { loading.value = true; try { const params: any = { page: recordsPage.value, size: recordsSize }; if (recFilterRisk.value) params.risk_level = recFilterRisk.value; if (recFilterStatus.value) params.status = recFilterStatus.value; if (hideFalsePositive.value) params.exclude_status = 'false_positive'; if (recDateRange.value?.[0]) params.date_from = recDateRange.value[0]; if (recDateRange.value?.[1]) params.date_to = recDateRange.value[1]; const { data } = await api.get<AlertRecordListResponse>('/alerts/records', { params }); records.value = data.items; recordsTotal.value = data.total } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '加载记录失败') } finally { loading.value = false } }
async function loadForeignRecords() { loading.value = true; try { const params: any = { page: 1, size: 100 }; if (foreignFilters.status) params.status = foreignFilters.status; if (foreignFilters.severity) params.severity = foreignFilters.severity; if (foreignFilters.source) params.source = foreignFilters.source; if (foreignDateRange.value?.[0]) params.triggered_from = foreignDateRange.value[0]; if (foreignDateRange.value?.[1]) params.triggered_to = foreignDateRange.value[1]; foreignAlerts.value = (await api.get('/foreign/alerts', { params })).data.items || [] } catch (e: any) { foreignAlerts.value = []; if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '加载外网预警失败') } finally { loading.value = false } }
function loadCurrentScope() { activeTab.value === 'rules' ? (scope.value === 'foreign' ? loadForeignRules() : loadDomesticRules()) : (scope.value === 'foreign' ? loadForeignRecords() : loadDomesticRecords()) }
function loadScope() { loadCurrentScope() }
function goForeignReview() { router.push({ path: '/foreign', query: { tab: 'opinions', section: 'ai-review' } }) }
function openDomesticRule(row: AlertRule | null) { domesticEditing.value = !!row; domesticId.value = row?.id || null; Object.assign(domesticForm, row ? { name: row.name, description: row.description, risk_threshold: row.risk_threshold, keywords: row.keywords, sources: row.sources, risk_level: row.risk_level, enabled: row.enabled } : { name: '', description: '', risk_threshold: 70, keywords: '', sources: '', risk_level: 'high', enabled: true }); domesticRuleDialog.value = true }
async function saveDomesticRule() { if (!domesticForm.name.trim()) return ElMessage.warning('请输入规则名称'); saving.value = true; try { if (domesticEditing.value) await api.put(`/alerts/rules/${domesticId.value}`, domesticForm); else await api.post('/alerts/rules', domesticForm); domesticRuleDialog.value = false; ElMessage.success('规则已保存'); await loadDomesticRules() } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '保存失败') } finally { saving.value = false } }
async function toggleDomesticRule(row: AlertRule, enabled: boolean) { try { await api.put(`/alerts/rules/${row.id}`, { enabled }); row.enabled = enabled } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '操作失败') } }
async function deleteDomesticRule(row: AlertRule) { try { await ElMessageBox.confirm(`确认删除规则「${row.name}」？`, '提示', { type: 'warning' }); await api.delete(`/alerts/rules/${row.id}`); await loadDomesticRules() } catch (e: any) { if (e?.response && !isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '删除失败') } }
async function handleEvaluate() { if (evaluating.value) return; evaluating.value = true; try { const { data } = await api.post<AlertEvaluateResponse>('/alerts/evaluate'); evalResult.value = data; ElMessage.success('国内预警评估完成'); if (scope.value === 'domestic') await loadDomesticRecords() } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '评估失败') } finally { evaluating.value = false } }
function openForeignRule(row: any | null) { foreignEditing.value = !!row; foreignRuleId.value = row?.id || null; Object.assign(foreignForm, row ? { name: row.name, description: row.description || '', rule_type: row.rule_type, conditionsText: JSON.stringify(row.conditions || {}), severity: row.severity, cooldown_seconds: row.cooldown_seconds || 0 } : { name: '', description: '', rule_type: 'risk_score', conditionsText: '{"threshold":80}', severity: 'medium', cooldown_seconds: 3600 }); foreignRuleDialog.value = true }
async function saveForeignRule() { if (!foreignForm.name.trim()) return ElMessage.warning('请输入规则名称'); let conditions: any; try { conditions = JSON.parse(foreignForm.conditionsText || '{}') } catch { return ElMessage.warning('条件必须是有效 JSON') }; foreignRuleSaving.value = true; try { const payload = { name: foreignForm.name, description: foreignForm.description, rule_type: foreignForm.rule_type, conditions, severity: foreignForm.severity, cooldown_seconds: foreignForm.cooldown_seconds }; if (foreignEditing.value) await api.patch(`/foreign/alert-rules/${foreignRuleId.value}`, payload); else await api.post('/foreign/alert-rules', payload); foreignRuleDialog.value = false; await loadForeignRules(); ElMessage.success('外网规则已保存') } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '外网规则保存失败') } finally { foreignRuleSaving.value = false } }
async function toggleForeignRule(row: any) { const action = row.is_enabled ? 'disable' : 'enable'; if (!row.is_enabled && !canForeignRuleEnable.value) return; try { await api.post(`/foreign/alert-rules/${row.id}/${action}`); await loadForeignRules() } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '外网规则更新失败') } }
async function deleteForeignRule(row: any) { try { await ElMessageBox.confirm(`确认删除外网规则「${row.name}」？`, '提示', { type: 'warning' }); await api.delete(`/foreign/alert-rules/${row.id}`); await loadForeignRules() } catch (e: any) { if (e?.response && !isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '外网规则删除失败') } }
async function evaluateForeign() { foreignEvaluating.value = true; try { await api.post('/foreign/alerts/evaluate', { dry_run: false, max_items: 200 }); ElMessage.success('外网预警评估完成'); await loadForeignRecords() } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '外网评估失败') } finally { foreignEvaluating.value = false } }
async function handleForeign(row: any, action: 'acknowledge' | 'resolve' | 'suppress') { try { await api.post(`/foreign/alerts/${row.id}/${action}`, { note: '预警中心处理' }); await loadForeignRecords() } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '外网预警处理失败') } }
async function openForeignDetail(row: any) { try { foreignDetail.value = (await api.get(`/foreign/alerts/${row.id}`)).data; foreignDetailDialog.value = true } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '详情加载失败') } }
async function openForeignHistory(row: any) { try { foreignHistory.value = (await api.get(`/foreign/alerts/${row.id}/actions`)).data.items || []; foreignHistoryDialog.value = true } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '历史加载失败') } }
function openHandleDialog(row: AlertRecord) { handlingId.value = row.id; handleForm.status = row.status || 'resolved'; handleForm.note = row.handle_note || ''; handleDialogVisible.value = true }
async function submitHandle() { if (handlingId.value == null) return; handling.value = true; try { const { data } = await api.put(`/alerts/records/${handlingId.value}/handle`, { status: handleForm.status, note: handleForm.note }); const idx = records.value.findIndex(item => item.id === handlingId.value); if (idx >= 0) records.value[idx] = data; handleDialogVisible.value = false } catch (e: any) { if (!isPermissionDenied(e)) ElMessage.error(e?.response?.data?.detail || '处置失败') } finally { handling.value = false } }
function normalizeRoute() { const tab = String(route.query.tab || 'rules'); const queryScope = String(route.query.scope || ''); activeTab.value = tab === 'records' ? 'records' : 'rules'; scope.value = queryScope === 'foreign' || tab === 'foreign' || tab === 'foreign-rules' || tab === 'foreign-review' ? 'foreign' : 'domestic' }
onMounted(() => { normalizeRoute(); loadCurrentScope(); if (activeTab.value === 'records') notifier.markVisited() }); watch(() => [route.query.tab, route.query.scope], () => { normalizeRoute(); loadCurrentScope() }); watch(activeTab, (tab) => { if (tab === 'records') notifier.markVisited(); loadCurrentScope() })
</script>

<style scoped>
.alerts { height: 100%; position: relative; }.alerts :deep(.el-tabs__header) { padding-right: 190px; }.top-scope-switch { position: absolute; top: 0; right: 0; z-index: 2; }.scope-bar,.filter-card :deep(.el-card__body) { display:flex; align-items:center; flex-wrap:wrap; gap:12px; }.scope-bar { margin: 0 0 16px; }.filter-card { margin-bottom:16px; }.table-card { margin-top:0; }.filter-select { width:160px; }.inline-switch { display:inline-flex; align-items:center; gap:6px; }.pagination { margin-top:16px; display:flex; justify-content:flex-end; }.eval-result { color:#67c23a; }.nav-link { color:#409eff; cursor:pointer; }.detail-pre { max-height:55vh; overflow:auto; white-space:pre-wrap; word-break:break-word; font-size:12px; }.record-filter-select { width:160px; }.scope-hint { margin: 4px 0 0; color:#909399; font-size:12px; line-height:1.5; }
@media (max-width:600px) { .alerts :deep(.el-tabs__header) { padding-right: 0; padding-top: 48px; }.top-scope-switch { left: 0; right: auto; }.scope-bar,.filter-card :deep(.el-card__body) { align-items:stretch; }.filter-select,.filter-card :deep(.el-date-editor),.scope-bar :deep(.el-button) { width:100%!important; }.scope-bar :deep(.el-radio-group) { width:100%; }.scope-bar :deep(.el-radio-button) { flex:1; }.scope-bar :deep(.el-radio-button__inner) { width:100%; } }
</style>
