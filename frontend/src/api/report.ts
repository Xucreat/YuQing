import api from './index'

/** 模块可配置参数的元信息（由后端 GET /reports/modules 下发，供前端渲染表单）。 */
export interface ReportModuleParamDef {
  key: string
  label: string
  type: string
  default: any
  min?: number | null
  max?: number | null
}

export interface ReportModuleDef {
  key: string
  name: string
  title: string
  description: string
  default_enabled: boolean
  params: ReportModuleParamDef[]
}

export interface ReportModulesResp {
  modules: ReportModuleDef[]
  default_modules: string[]
}

/** 模块选择项：可直接传 key 字符串，或带参数的对象（后端 Union[str, {key, params}]）。 */
export type ReportModuleSelection = string | { key: string; params: Record<string, any> }

/** POST /reports/export 请求体（与后端 ReportExportRequest 对齐）。 */
export interface ReportExportPayload {
  name: string
  time_field: 'created_at' | 'publish_time'
  range_type: 'last_n_days' | 'custom'
  range_days: number
  start_date: string | null
  end_date: string | null
  modules: ReportModuleSelection[]
  delivery: 'download'
}

/** 获取可配置报告的可选模块清单（含默认选中项与参数元信息）。 */
export function getReportModules() {
  return api.get<ReportModulesResp>('/reports/modules')
}

/** 按自定义配置生成并下载 PDF 报告（返回 blob）。Phase Report-2-P1 正式入口。 */
export function generateReport(payload: ReportExportPayload) {
  return api.post('/reports/export', payload, { responseType: 'blob' })
}

// ===== Phase Report-4-A：报告模板（保存/加载） =====

/** 模板里的导出配置快照（与 ReportExportPayload 同构，不含 delivery）。 */
export interface ReportTemplateConfig {
  name: string
  time_field: 'created_at' | 'publish_time'
  range_type: 'last_n_days' | 'custom'
  range_days: number
  start_date: string | null
  end_date: string | null
  modules: ReportModuleSelection[]
}

/** 创建模板请求体。 */
export interface ReportTemplateCreatePayload {
  name: string
  description?: string | null
  is_public: boolean
  config_json: ReportTemplateConfig
}

/** 更新模板请求体（全字段可选）。 */
export interface ReportTemplateUpdatePayload {
  name?: string
  description?: string | null
  is_public?: boolean
  config_json?: ReportTemplateConfig
}

/** 模板对外结构（含 can_edit 标记）。 */
export interface ReportTemplate {
  id: number
  name: string
  description?: string | null
  owner_id: number
  config_json: ReportTemplateConfig
  is_public: boolean
  created_at: string
  updated_at: string
  can_edit: boolean
}

/** 加载当前用户可访问的模板（自己的 + 公共）。需 reports:export。 */
export function getTemplates() {
  return api.get<ReportTemplate[]>('/reports/templates')
}

/** 保存为模板。需 reports:manage。 */
export function createTemplate(payload: ReportTemplateCreatePayload) {
  return api.post<ReportTemplate>('/reports/templates', payload)
}

/** 更新模板。需 reports:manage（仅 owner/admin 可操作）。 */
export function updateTemplate(id: number, payload: ReportTemplateUpdatePayload) {
  return api.put<ReportTemplate>(`/reports/templates/${id}`, payload)
}

/** 删除模板。需 reports:manage（仅 owner/admin 可操作）。 */
export function deleteTemplate(id: number) {
  return api.delete(`/reports/templates/${id}`)
}
