<template>
  <el-drawer
    v-model="open"
    title="导出舆情报告"
    direction="rtl"
    size="460px"
    :close-on-click-modal="false"
    @open="onOpen"
  >
    <el-form
      label-position="top"
      class="report-form"
      v-loading="loadingModules"
      element-loading-text="加载模块清单…"
    >
      <el-form-item label="报告模板">
        <div class="tpl-row">
          <el-select
            v-model="selectedTemplateId"
            placeholder="选择模板以载入配置"
            :loading="loadingTemplates"
            @change="onTemplateSelected"
            class="tpl-select"
          >
            <el-option
              v-for="t in templates"
              :key="t.id"
              :value="t.id"
              :label="(t.is_public ? '🌐 ' : '') + t.name"
            />
          </el-select>
          <el-button
            v-if="selectedTemplateId && currentTemplateCanEdit"
            type="danger"
            link
            :loading="deleting"
            @click="onDeleteTemplate"
          >删除</el-button>
        </div>
        <div class="form-hint">模板 = 当前导出配置快照（不含投递方式）。🌐 为公共模板。</div>
      </el-form-item>

      <el-form-item label="报告名称">
        <el-input v-model="reportName" maxlength="40" show-word-limit placeholder="舆情监测报告" />
      </el-form-item>

      <el-form-item label="统计时间字段">
        <el-radio-group v-model="reportTimeField">
          <el-radio value="created_at">采集时间</el-radio>
          <el-radio value="publish_time">发布时间（缺失回退采集时间）</el-radio>
        </el-radio-group>
        <div class="form-hint">发布时间为空的数据将回退使用采集时间（COALESCE），不丢弃。</div>
      </el-form-item>

      <el-form-item label="统计时间范围">
        <el-radio-group v-model="reportRangeMode" class="range-mode">
          <el-radio value="preset">预设周期</el-radio>
          <el-radio value="custom">自定义区间</el-radio>
        </el-radio-group>
        <template v-if="reportRangeMode === 'preset'">
          <el-select v-model="reportPresetDays" class="range-control">
            <el-option :value="7" label="近 7 天" />
            <el-option :value="15" label="近 15 天" />
            <el-option :value="30" label="近 30 天" />
          </el-select>
        </template>
        <template v-else>
          <el-date-picker
            v-model="reportCustomRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            class="range-control"
          />
        </template>
      </el-form-item>

      <el-form-item label="报告模块（可增删与排序）">
        <ModuleSelector v-model="selectedModules" :modules="allModules" />
      </el-form-item>

      <el-form-item label="模块参数">
        <div v-if="selectedWithParams.length" class="param-zone">
          <div v-for="m in selectedWithParams" :key="'p-' + m.key" class="param-block">
            <div class="param-block-title">{{ m.title }}</div>
            <div v-if="moduleParams[m.key]" class="param-rows">
              <div class="param-row" v-for="p in m.params" :key="p.key">
                <span class="param-label">{{ p.label }}</span>
                <el-input-number
                  v-if="p.type === 'int'"
                  v-model="moduleParams[m.key][p.key]"
                  :min="p.min ?? undefined"
                  :max="p.max ?? undefined"
                  size="small"
                  controls-position="right"
                />
                <el-input v-else v-model="moduleParams[m.key][p.key]" size="small" />
              </div>
            </div>
          </div>
        </div>
        <div v-else class="form-hint">所选模块暂无可配置参数。</div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="open = false">取消</el-button>
      <el-button v-if="canManageTemplate" @click="openSaveDialog" :loading="savingTemplate">保存为模板</el-button>
      <el-button type="primary" :loading="reporting" @click="generateAndDownload">
        生成并下载 PDF
      </el-button>
    </template>

    <el-dialog v-model="saveDialogVisible" title="保存为模板" width="420px" append-to-body>
      <el-form label-position="top">
        <el-form-item label="模板名称">
          <el-input v-model="templateForm.name" maxlength="128" show-word-limit placeholder="周报模板" />
          <div v-if="templateNameConflict" class="form-hint warn">
            模板名称已存在（本人或公共模板中已有同名），请更换后再保存。
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="templateForm.description"
            type="textarea"
            :rows="2"
            maxlength="255"
            placeholder="可选"
          />
        </el-form-item>
        <el-form-item label="公开模板（所有用户可见）">
          <el-switch v-model="templateForm.is_public" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTemplate" :disabled="templateNameConflict" @click="saveAsTemplate">保存</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { ElMessage } from "element-plus"
import {
  getReportModules,
  generateReport,
  getTemplates,
  createTemplate,
  deleteTemplate,
} from "@/api/report"
import type {
  ReportModuleDef,
  ReportModuleParamDef,
  ReportModuleSelection,
  ReportTemplate,
  ReportTemplateConfig,
} from "@/api/report"
import ModuleSelector from "./ModuleSelector.vue"
import { usePermission } from "@/composables/usePermission"

// 抽屉开关（双向绑定，由父组件 Dashboard 通过 v-model 控制）
const open = defineModel<boolean>({ required: true })

const reporting = ref(false)
// 抽屉打开时拉取模块清单的加载态（防止重复点击 / 重复请求）
const loadingModules = ref(false)
const reportName = ref("舆情监测报告")
const reportTimeField = ref<"created_at" | "publish_time">("created_at")
const reportRangeMode = ref<"preset" | "custom">("preset")
const reportPresetDays = ref(7)
const reportCustomRange = ref<[string, string] | null>(null)
const allModules = ref<ReportModuleDef[]>([])
const selectedModules = ref<string[]>([])
// 每个模块的已编辑参数值：{ [moduleKey]: { [paramKey]: value } }
const moduleParams = ref<Record<string, Record<string, any>>>({})

// ===== Phase Report-4-A：模板相关状态 =====
const templates = ref<ReportTemplate[]>([])
const selectedTemplateId = ref<number | null>(null)
const loadingTemplates = ref(false)
const saveDialogVisible = ref(false)
const savingTemplate = ref(false)
const deleting = ref(false)
const templateForm = ref<{ name: string; description: string; is_public: boolean }>({
  name: "",
  description: "",
  is_public: false,
})

function buildDefaults(def: ReportModuleDef): Record<string, any> {
  const o: Record<string, any> = {}
  for (const p of def.params) o[p.key] = p.default
  return o
}

// 仅保留「带可配置参数」的已选模块，供参数编辑区渲染
const selectedWithParams = computed(() =>
  selectedModules.value
    .map((key) => allModules.value.find((m) => m.key === key))
    .filter((m): m is ReportModuleDef => !!m && !!m.params && m.params.length > 0),
)

// RBAC：模板的保存/编辑/删除属于 reports:manage（后端同名校验），
// 无该权限时隐藏「保存为模板」与「删除」，仅保留导出能力（reports:export）。
const { hasPermission } = usePermission()
const canManageTemplate = computed(() => hasPermission('reports:manage'))

// 当前选中的模板是否可编辑/删除（供前端隐藏删除按钮）
const currentTemplateCanEdit = computed(() => {
  const t = templates.value.find((t) => t.id === selectedTemplateId.value)
  return !!t && t.can_edit && canManageTemplate.value
})

// 保存模板时「名称不能重复」：与已加载模板列表（本人 + 公共）比较，
// 大小写/首尾空格不敏感。命中即视为冲突，禁用保存并提示。
const templateNameConflict = computed(() => {
  const name = templateForm.value.name.trim().toLowerCase()
  if (!name) return false
  return templates.value.some((t) => t.name.trim().toLowerCase() === name)
})

// 模块增删时同步 moduleParams：补齐新增模块的默认值，清理已移除模块
watch(
  selectedModules,
  (keys) => {
    const set = new Set(keys)
    for (const k of Object.keys(moduleParams.value)) {
      if (!set.has(k)) delete moduleParams.value[k]
    }
    for (const k of keys) {
      const def = allModules.value.find((m) => m.key === k)
      if (def && def.params && def.params.length && !moduleParams.value[k]) {
        moduleParams.value[k] = buildDefaults(def)
      }
    }
  },
  { deep: false },
)

async function onOpen() {
  // 防重复点击：正在加载时直接返回；已加载过则无需再请求
  if (loadingModules.value) return
  loadingModules.value = true
  try {
    const { data } = await getReportModules()
    allModules.value = data.modules || []
    if (!selectedModules.value.length) {
      selectedModules.value = [...(data.default_modules || allModules.value.map((m) => m.key))]
    }
    // 初始化默认选中模块的参数值
    for (const key of selectedModules.value) {
      const def = allModules.value.find((m) => m.key === key)
      if (def && def.params && def.params.length && !moduleParams.value[key]) {
        moduleParams.value[key] = buildDefaults(def)
      }
    }
  } catch {
    allModules.value = []
    selectedModules.value = []
    ElMessage.error("获取报告模块清单失败")
  } finally {
    loadingModules.value = false
  }
  // 模板清单独立加载（不阻塞模块）
  await loadTemplates()
}

async function loadTemplates() {
  if (loadingTemplates.value) return
  loadingTemplates.value = true
  try {
    const { data } = await getTemplates()
    templates.value = data || []
  } catch {
    templates.value = []
  } finally {
    loadingTemplates.value = false
  }
}

/** 将模板配置回填到当前表单。 */
function applyConfigToForm(cfg: ReportTemplateConfig) {
  reportName.value = cfg.name || "舆情监测报告"
  reportTimeField.value = cfg.time_field || "created_at"
  if (cfg.range_type === "custom") {
    reportRangeMode.value = "custom"
    reportCustomRange.value =
      cfg.start_date && cfg.end_date ? [cfg.start_date, cfg.end_date] : null
  } else {
    reportRangeMode.value = "preset"
    reportPresetDays.value = cfg.range_days || 7
  }
  selectedModules.value = (cfg.modules || []).map((m) =>
    typeof m === "string" ? m : m.key,
  )
  // 参数回填
  const params: Record<string, Record<string, any>> = {}
  for (const m of cfg.modules || []) {
    if (typeof m === "string") continue
    const def = allModules.value.find((d) => d.key === m.key)
    if (def && def.params && def.params.length) {
      const stored = m.params || {}
      const out: Record<string, any> = {}
      for (const p of def.params) {
        out[p.key] = stored[p.key] !== undefined ? stored[p.key] : p.default
      }
      params[m.key] = out
    }
  }
  moduleParams.value = params
}

function onTemplateSelected() {
  const tpl = templates.value.find((t) => t.id === selectedTemplateId.value)
  if (!tpl) return
  applyConfigToForm(tpl.config_json)
}

/** 从当前表单构建模板配置（去除 delivery / recipients）。 */
function buildConfigFromForm(): ReportTemplateConfig {
  const isCustom = reportRangeMode.value === "custom"
  const modulesPayload: ReportModuleSelection[] = selectedModules.value.map((key) => {
    const def = allModules.value.find((m) => m.key === key)
    if (def && def.params && def.params.length) {
      return { key, params: collectParams(key, def) }
    }
    return key
  })
  return {
    name: reportName.value.trim() || "舆情监测报告",
    time_field: reportTimeField.value,
    range_type: isCustom ? "custom" : "last_n_days",
    range_days: isCustom ? 7 : reportPresetDays.value,
    start_date: isCustom && reportCustomRange.value ? reportCustomRange.value[0] : null,
    end_date: isCustom && reportCustomRange.value ? reportCustomRange.value[1] : null,
    modules: modulesPayload,
  }
}

function openSaveDialog() {
  templateForm.value = {
    name: reportName.value || "舆情监测报告",
    description: "",
    is_public: false,
  }
  saveDialogVisible.value = true
}

async function saveAsTemplate() {
  const name = templateForm.value.name.trim()
  if (!name) {
    ElMessage.warning("请输入模板名称")
    return
  }
  // 前端即时校验：与已加载模板（本人 + 公共）重名则拦截（后端 409 为兜底）
  if (templates.value.some((t) => t.name.trim().toLowerCase() === name.toLowerCase())) {
    ElMessage.warning(`模板名称已存在：${name}`)
    return
  }
  savingTemplate.value = true
  try {
    const config = buildConfigFromForm()
    const { data } = await createTemplate({
      name,
      description: templateForm.value.description || null,
      is_public: templateForm.value.is_public,
      config_json: config,
    })
    ElMessage.success("已保存为模板")
    saveDialogVisible.value = false
    await loadTemplates()
    selectedTemplateId.value = data.id
  } catch (e: any) {
    let msg = "保存模板失败"
    try {
      const text = e?.response?.data ? await e.response.data.text() : ""
      const j = text ? JSON.parse(text) : null
      if (j?.detail) msg = `保存模板失败：${j.detail}`
    } catch {
      /* 忽略解析失败，沿用默认提示 */
    }
    ElMessage.error(msg)
  } finally {
    savingTemplate.value = false
  }
}

async function onDeleteTemplate() {
  if (!selectedTemplateId.value) return
  deleting.value = true
  try {
    await deleteTemplate(selectedTemplateId.value)
    ElMessage.success("模板已删除")
    await loadTemplates()
    selectedTemplateId.value = null
  } catch (e: any) {
    let msg = "删除模板失败"
    try {
      const text = e?.response?.data ? await e.response.data.text() : ""
      const j = text ? JSON.parse(text) : null
      if (j?.detail) msg = `删除模板失败：${j.detail}`
    } catch {
      /* 忽略解析失败，沿用默认提示 */
    }
    ElMessage.error(msg)
  } finally {
    deleting.value = false
  }
}

function collectParams(key: string, def: ReportModuleDef): Record<string, any> {
  const stored = moduleParams.value[key] || {}
  const out: Record<string, any> = {}
  for (const p of def.params) {
    let v = stored[p.key]
    if (v === undefined || v === null || v === "") v = p.default
    if (p.type === "int" && v != null) v = Number(v)
    out[p.key] = v
  }
  return out
}

async function generateAndDownload() {
  if (!selectedModules.value.length) {
    ElMessage.warning("请至少选择一个报告模块")
    return
  }
  // 按当前顺序构建 modules（str 或 {key, params}），顺序即章节顺序
  const modulesPayload: ReportModuleSelection[] = selectedModules.value.map((key) => {
    const def = allModules.value.find((m) => m.key === key)
    if (def && def.params && def.params.length) {
      return { key, params: collectParams(key, def) }
    }
    return key
  })

  const isCustom = reportRangeMode.value === "custom"
  const payload = {
    name: reportName.value.trim() || "舆情监测报告",
    time_field: reportTimeField.value,
    range_type: isCustom ? ("custom" as const) : ("last_n_days" as const),
    range_days: isCustom ? 7 : reportPresetDays.value,
    start_date: isCustom && reportCustomRange.value ? reportCustomRange.value[0] : null,
    end_date: isCustom && reportCustomRange.value ? reportCustomRange.value[1] : null,
    modules: modulesPayload,
    delivery: "download" as const,
  }

  reporting.value = true
  try {
    const res = await generateReport(payload)
    const blob = new Blob([res.data], { type: res.data.type || "application/pdf" })
    // 禁止 0KB 下载：空响应视为生成失败
    if (blob.size === 0) {
      ElMessage.error("生成的报告为空，请调整筛选条件后重试")
      return
    }
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    // 文件名：报告名称 + 日期（YYYYMMDD）+ .pdf，便于归档区分
    const now = new Date()
    const ds = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`
    a.download = `${payload.name}_${ds}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success("报告已生成，开始下载")
    open.value = false
  } catch (e: any) {
    // blob 错误时后端返回 JSON（含 detail），需解析后提示
    let msg = "生成报告失败，请稍后重试"
    try {
      const text = e?.response?.data ? await e.response.data.text() : ""
      const j = text ? JSON.parse(text) : null
      if (j?.detail) msg = `报告生成失败：${j.detail}`
    } catch {
      /* 忽略解析失败，沿用默认提示 */
    }
    ElMessage.error(msg)
  } finally {
    reporting.value = false
  }
}
</script>

<style scoped>
.report-form .el-form-item { margin-bottom: 18px; }
.range-mode { display: block; margin-bottom: 8px; }
.range-control { width: 100%; }
.form-hint { font-size: 12px; color: #86868b; line-height: 1.5; margin-top: 6px; }
.form-hint.warn { color: #ff3b30; }
.tpl-row { display: flex; align-items: center; gap: 8px; width: 100%; }
.tpl-select { flex: 1; }

/* 模块参数编辑区 */
.param-zone { width: 100%; border: 1px solid #e8e8ed; border-radius: 10px; padding: 8px; background: #fafafd; }
.param-block { padding: 6px 8px; border-radius: 8px; background: #fff; border: 1px solid #eef0f3; margin-bottom: 6px; }
.param-block:last-child { margin-bottom: 0; }
.param-block-title { font-size: 13px; font-weight: 600; color: #1d1d1f; margin-bottom: 6px; }
.param-rows { display: flex; flex-direction: column; gap: 6px; }
.param-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.param-label { font-size: 13px; color: #555; }
.param-row .el-input-number,
.param-row .el-input { width: 150px; }
</style>
