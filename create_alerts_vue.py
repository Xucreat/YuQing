import pathlib

alerts_vue = '''\x3ctemplate\x3e
  \x3cdiv class=\x22alerts\x22 v-loading=\x22loading\x22\x3e
    \x3cel-tabs v-model=\x22activeTab\x22\x3e
      \x3cel-tab-pane label=\x22预警规则\x22 name=\x22rules\x22\x3e
        \x3cel-card shadow=\x22never\x22 class=\x22filter-card\x22\x3e
          \x3cel-button type=\x22primary\x22 @click=\x22openRuleDialog(null)\x22\x3e新增规则\x3c/el-button\x3e
          \x3cel-button @click=\x22loadRules\x22\x3e刷新\x3c/el-button\x3e
          \x3cel-button type=\x22warning\x22 :loading=\x22evaluating\x22 @click=\x22handleEvaluate\x22\x3e执行评估\x3c/el-button\x3e
          \x3cspan v-if=\x22evalResult\x22 class=\x22eval-result\x22\x3e评估完成：检查 {{ evalResult.total_checked }} 条，生成 {{ evalResult.alerts_created }} 条预警\x3c/span\x3e
        \x3c/el-card\x3e

        \x3cel-card shadow=\x22never\x22 class=\x22table-card\x22\x3e
          \x3cel-table :data=\x22rules\x22 stripe\x3e
            \x3cel-table-column prop=\x22id\x22 label=\x22ID\x22 width=\x2270\x22 /\x3e
            \x3cel-table-column prop=\x22name\x22 label=\x22规则名称\x22 min-width=\x22200\x22 show-overflow-tooltip /\x3e
            \x3cel-table-column prop=\x22description\x22 label=\x22描述\x22 min-width=\x22200\x22 show-overflow-tooltip /\x3e
            \x3cel-table-column label=\x22风险阈值\x22 width=\x22100\x22 align=\x22center\x22\x3e
              \x3ctemplate #default=\x22{ row }\x22\x3e{{ row.risk_threshold }}\x3c/template\x3e
            \x3c/el-table-column\x3e
            \x3cel-table-column label=\x22预警等级\x22 width=\x22120\x22 align=\x22center\x22\x3e
              \x3ctemplate #default=\x22{ row }\x22\x3e\x3cel-tag :type=\x22riskTag(row.risk_level)\x22 size=\x22small\x22\x3e{{ riskText(row.risk_level) }}\x3c/el-tag\x3e\x3c/template\x3e
            \x3c/el-table-column\x3e
            \x3cel-table-column label=\x22状态\x22 width=\x22100\x22 align=\x22center\x22\x3e
              \x3ctemplate #default=\x22{ row }\x22\x3e
                \x3cel-switch :model-value=\x22row.enabled\x22 @change=\x22(val: boolean) =\x3e toggleRule(row, val)\x22 /\x3e
              \x3c/template\x3e
            \x3c/el-table-column\x3e
            \x3cel-table-column label=\x22操作\x22 width=\x22180\x22 align=\x22center\x22\x3e
              \x3ctemplate #default=\x22{ row }\x22\x3e
                \x3cel-button type=\x22primary\x22 size=\x22small\x22 link @click=\x22openRuleDialog(row)\x22\x3e编辑\x3c/el-button\x3e
                \x3cel-button type=\x22danger\x22 size=\x22small\x22 link @click=\x22deleteRule(row)\x22\x3e删除\x3c/el-button\x3e
              \x3c/template\x3e
            \x3c/el-table-column\x3e
          \x3c/el-table\x3e
          \x3cdiv class=\x22pagination\x22\x3e
            \x3cel-pagination background layout=\x22total, prev, pager, next\x22 :total=\x22rulesTotal\x22 :current-page=\x22rulesPage\x22 :page-size=\x22rulesSize\x22 @current-change=\x22handleRulesPage\x22 /\x3e
          \x3c/div\x3e
        \x3c/el-card\x3e
      \x3c/el-tab-pane\x3e

      \x3cel-tab-pane label=\x22预警记录\x22 name=\x22records\x22\x3e
        \x3cel-card shadow=\x22never\x22 class=\x22filter-card\x22\x3e
          \x3cel-select v-model=\x22recFilterRisk\x22 placeholder=\x22预警等级\x22 clearable style=\x22width: 160px\x22 @change=\x22loadRecords\x22\x3e
            \x3cel-option label=\x22严重 critical\x22 value=\x22critical\x22 /\x3e
            \x3cel-option label=\x22高 high\x22 value=\x22high\x22 /\x3e
            \x3cel-option label=\x22中 medium\x22 value=\x22medium\x22 /\x3e
            \x3cel-option label=\x22低 low\x22 value=\x22low\x22 /\x3e
          \x3c/el-select\x3e
          \x3cel-select v-model=\x22recFilterHandled\x22 placeholder=\x22处理状态\x22 clearable style=\x22width: 160px; margin-left: 12px\x22 @change=\x22loadRecords\x22\x3e
            \x3cel-option label=\x22未处理\x22 :value=\x22false\x22 /\x3e
            \x3cel-option label=\x22已处理\x22 :value=\x22true\x22 /\x3e
          \x3c/el-select\x3e
          \x3cel-button @click=\x22loadRecords\x22 style=\x22margin-left: 12px\x22\x3e刷新\x3c/el-button\x3e
        \x3c/el-card\x3e

        \x3cel-card shadow=\x22never\x22 class=\x22table-card\x22\x3e
          \x3cel-table :data=\x22records\x22 stripe\x3e
            \x3cel-table-column prop=\x22id\x22 label=\x22ID\x22 width=\x2270\x22 /\x3e
            \x3cel-table-column prop=\x22rule_name\x22 label=\x22触发规则\x22 width=\x22200\x22 show-overflow-tooltip /\x3e
            \x3cel-table-column label=\x22预警等级\x22 width=\x22120\x22 align=\x22center\x22\x3e
              \x3ctemplate #default=\x22{ row }\x22\x3e\x3cel-tag :type=\x22riskTag(row.risk_level)\x22 size=\x22small\x22\x3e{{ riskText(row.risk_level) }}\x3c/el-tag\x3e\x3c/template\x3e
            \x3c/el-table-column\x3e
            \x3cel-table-column prop=\x22opinion_title\x22 label=\x22关联舆情\x22 min-width=\x22220\x22 show-overflow-tooltip /\x3e
            \x3cel-table-column prop=\x22event_title\x22 label=\x22关联事件\x22 width=\x22180\x22 show-overflow-tooltip /\x3e
            \x3cel-table-column prop=\x22trigger_reason\x22 label=\x22触发原因\x22 min-width=\x22220\x22 show-overflow-tooltip /\x3e
            \x3cel-table-column label=\x22状态\x22 width=\x22100\x22 align=\x22center\x22\x3e
              \x3ctemplate #default=\x22{ row }\x22\x3e\x3cel-tag :type=\x22row.handled ? \x27success\x27 : \x27danger\x27\x22 size=\x22small\x22\x3e{{ row.handled ? \x27已处理\x27 : \x27未处理\x27 }}\x3c/el-tag\x3e\x3c/template\x3e
            \x3c/el-table-column\x3e
            \x3cel-table-column label=\x22触发时间\x22 width=\x22180\x22\x3e
              \x3ctemplate #default=\x22{ row }\x22\x3e{{ formatTime(row.created_at) }}\x3c/template\x3e
            \x3c/el-table-column\x3e
            \x3cel-table-column label=\x22操作\x22 width=\x22100\x22 align=\x22center\x22\x3e
              \x3ctemplate #default=\x22{ row }\x22\x3e
                \x3cel-button v-if=\x22!row.handled\x22 type=\x22success\x22 size=\x22small\x22 link @click=\x22handleRecord(row)\x22\x3e标记处理\x3c/el-button\x3e
              \x3c/template\x3e
            \x3c/el-table-column\x3e
          \x3c/el-table\x3e
          \x3cdiv class=\x22pagination\x22\x3e
            \x3cel-pagination background layout=\x22total, prev, pager, next\x22 :total=\x22recordsTotal\x22 :current-page=\x22recordsPage\x22 :page-size=\x22recordsSize\x22 @current-change=\x22handleRecordsPage\x22 /\x3e
          \x3c/div\x3e
        \x3c/el-card\x3e
      \x3c/el-tab-pane\x3e
    \x3c/el-tabs\x3e

    \x3c!-- Rule Form Dialog --\x3e
    \x3cel-dialog v-model=\x22ruleDialogVisible\x22 :title=\x22isEditing ? \x27编辑规则\x27 : \x27新增规则\x27\x22 width=\x22600px\x22\x3e
      \x3cel-form :model=\x22ruleForm\x22 label-width=\x22100px\x22\x3e
        \x3cel-form-item label=\x22规则名称\x22\x3e\x3cel-input v-model=\x22ruleForm.name\x22 placeholder=\x22请输入规则名称\x22 /\x3e\x3c/el-form-item\x3e
        \x3cel-form-item label=\x22描述\x22\x3e\x3cel-input v-model=\x22ruleForm.description\x22 type=\x22textarea\x22 :rows=\x222\x22 placeholder=\x22描述该规则的用途\x22 /\x3e\x3c/el-form-item\x3e
        \x3cel-form-item label=\x22风险阈值\x22\x3e\x3cel-input-number v-model=\x22ruleForm.risk_threshold\x22 :min=\x220\x22 :max=\x22100\x22 /\x3e\x3c/el-form-item\x3e
        \x3cel-form-item label=\x22关键词匹配\x22\x3e\x3cel-input v-model=\x22ruleForm.keywords\x22 placeholder=\x22多个关键词用逗号分隔\x22 /\x3e\x3c/el-form-item\x3e
        \x3cel-form-item label=\x22来源过滤\x22\x3e\x3cel-input v-model=\x22ruleForm.sources\x22 placeholder=\x22多个来源用逗号分隔，留空表示不限\x22 /\x3e\x3c/el-form-item\x3e
        \x3cel-form-item label=\x22预警等级\x22\x3e
          \x3cel-select v-model=\x22ruleForm.risk_level\x22\x3e
            \x3cel-option label=\x22严重 critical\x22 value=\x22critical\x22 /\x3e
            \x3cel-option label=\x22高 high\x22 value=\x22high\x22 /\x3e
            \x3cel-option label=\x22中 medium\x22 value=\x22medium\x22 /\x3e
            \x3cel-option label=\x22低 low\x22 value=\x22low\x22 /\x3e
          \x3c/el-select\x3e
        \x3c/el-form-item\x3e
        \x3cel-form-item label=\x22启用\x22\x3e\x3cel-switch v-model=\x22ruleForm.enabled\x22 /\x3e\x3c/el-form-item\x3e
      \x3c/el-form\x3e
      \x3ctemplate #footer\x3e
        \x3cel-button @click=\x22ruleDialogVisible = false\x22\x3e取消\x3c/el-button\x3e
        \x3cel-button type=\x22primary\x22 :loading=\x22saving\x22 @click=\x22saveRule\x22\x3e保存\x3c/el-button\x3e
      \x3c/template\x3e
    \x3c/el-dialog\x3e
  \x3c/div\x3e
\x3c/template\x3e

\x3cscript setup lang=\x22ts\x22\x3e
import { onMounted, ref, reactive } from \x27vue\x27
import { ElMessage, ElMessageBox } from \x27element-plus\x27
import api from \x27@/api\x27
import type { AlertRule, AlertRuleListResponse, AlertRecord, AlertRecordListResponse, AlertEvaluateResponse } from \x27@/types\x27

const activeTab = ref(\x27rules\x27)
const loading = ref(false)
const saving = ref(false)
const evaluating = ref(false)

// Rules
const rules = ref\x3cAlertRule[]\x3e([])
const rulesTotal = ref(0)
const rulesPage = ref(1)
const rulesSize = ref(20)

// Records
const records = ref\x3cAlertRecord[]\x3e([])
const recordsTotal = ref(0)
const recordsPage = ref(1)
const recordsSize = ref(20)
const recFilterRisk = ref\x3cstring | null\x3e(null)
const recFilterHandled = ref\x3cboolean | null\x3e(null)

// Rule dialog
const ruleDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref\x3cnumber | null\x3e(null)
const ruleForm = reactive({ name: \x27\x27, description: \x27\x27, risk_threshold: 70, keywords: \x27\x27, sources: \x27\x27, risk_level: \x27high\x27, enabled: true })
const evalResult = ref\x3cAlertEvaluateResponse | null\x3e(null)

function riskTag(level: string): \x27danger\x27 | \x27warning\x27 | \x27success\x27 | \x27info\x27 {
  return ({ critical: \x27danger\x27, high: \x27danger\x27, medium: \x27warning\x27, low: \x27info\x27 } as const)[level] || \x27info\x27
}
function riskText(level: string): string { return ({ critical: \x27严重\x27, high: \x27高\x27, medium: \x27中\x27, low: \x27低\x27 } as const)[level] || level }
function formatTime(t: string): string { if (!t) return \x27-\x27; return t.replace(\x27T\x27, \x27 \x27).slice(0, 19) }

async function loadRules() {
  loading.value = true
  try {
    const { data } = await api.get\x3cAlertRuleListResponse\x3e(\x27/alerts/rules\x27, { params: { page: rulesPage.value, size: rulesSize.value } })
    rules.value = data.items; rulesTotal.value = data.total
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || \x27加载规则失败\x27) } finally { loading.value = false }
}

async function loadRecords() {
  loading.value = true
  try {
    const params: any = { page: recordsPage.value, size: recordsSize.value }
    if (recFilterRisk.value) params.risk_level = recFilterRisk.value
    if (recFilterHandled.value !== null) params.handled = recFilterHandled.value
    const { data } = await api.get\x3cAlertRecordListResponse\x3e(\x27/alerts/records\x27, { params })
    records.value = data.items; recordsTotal.value = data.total
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || \x27加载记录失败\x27) } finally { loading.value = false }
}

function openRuleDialog(rule: AlertRule | null) {
  if (rule) {
    isEditing.value = true; editingId.value = rule.id
    ruleForm.name = rule.name; ruleForm.description = rule.description
    ruleForm.risk_threshold = rule.risk_threshold; ruleForm.keywords = rule.keywords
    ruleForm.sources = rule.sources; ruleForm.risk_level = rule.risk_level; ruleForm.enabled = rule.enabled
  } else {
    isEditing.value = false; editingId.value = null
    ruleForm.name = \x27\x27; ruleForm.description = \x27\x27; ruleForm.risk_threshold = 70
    ruleForm.keywords = \x27\x27; ruleForm.sources = \x27\x27; ruleForm.risk_level = \x27high\x27; ruleForm.enabled = true
  }
  ruleDialogVisible.value = true
}

async function saveRule() {
  if (!ruleForm.name.trim()) { ElMessage.warning(\x27请输入规则名称\x27); return }
  saving.value = true
  try {
    if (isEditing.value && editingId.value) {
      await api.put(\x60/alerts/rules/\x24{editingId.value}\x60, ruleForm)
      ElMessage.success(\x27规则已更新\x27)
    } else {
      await api.post(\x27/alerts/rules\x27, ruleForm)
      ElMessage.success(\x27规则已创建\x27)
    }
    ruleDialogVisible.value = false
    await loadRules()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || \x27保存失败\x27) } finally { saving.value = false }
}

async function toggleRule(rule: AlertRule, val: boolean) {
  try {
    await api.put(\x60/alerts/rules/\x24{rule.id}\x60, { enabled: val })
    rule.enabled = val
    ElMessage.success(val ? \x27规则已启用\x27 : \x27规则已禁用\x27)
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || \x27操作失败\x27) }
}

async function deleteRule(rule: AlertRule) {
  try {
    await ElMessageBox.confirm(\x60确认删除规则「\x24{rule.name}」？\x60, \x27提示\x27, { confirmButtonText: \x27删除\x27, cancelButtonText: \x27取消\x27, type: \x27warning\x27 })
    await api.delete(\x60/alerts/rules/\x24{rule.id}\x60)
    ElMessage.success(\x27规则已删除\x27)
    await loadRules()
  } catch { /* cancelled */ }
}

async function handleEvaluate() {
  if (evaluating.value) return
  evaluating.value = true
  try {
    const { data } = await api.post\x3cAlertEvaluateResponse\x3e(\x27/alerts/evaluate\x27)
    evalResult.value = data
    ElMessage.success(\x60评估完成：检查 \x24{data.total_checked} 条，生成 \x24{data.alerts_created} 条预警\x60)
    if (activeTab.value === \x27records\x27) await loadRecords()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || \x27评估失败\x27) } finally { evaluating.value = false }
}

async function handleRecord(rec: AlertRecord) {
  try {
    await api.put(\x60/alerts/records/\x24{rec.id}/handle\x60)
    rec.handled = true
    ElMessage.success(\x27已标记为已处理\x27)
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || \x27操作失败\x27) }
}

function handleRulesPage(p: number) { rulesPage.value = p; loadRules() }
function handleRecordsPage(p: number) { recordsPage.value = p; loadRecords() }

onMounted(() => { loadRules() })
\x3c/script\x3e

\x3cstyle scoped\x3e
.alerts { height: 100%; }
.filter-card { margin-bottom: 16px; }
.table-card { margin-top: 0; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.eval-result { margin-left: 16px; color: #67c23a; font-size: 14px; }
\x3c/style\x3e
'''

pathlib.Path(r'C:\Users\Administrator\Desktop\YQ\frontend\src\views\Alerts.vue').write_text(alerts_vue, encoding='utf-8')
print('Alerts.vue created')
