<template>
  <div class="roles-page" v-loading="loading">
    <div class="toolbar">
      <h3 class="section-title">角色权限</h3>
      <button v-if="canWrite" class="btn btn-primary" @click="openCreate">+ 新建角色</button>
    </div>

    <div class="card">
      <table class="tbl">
        <thead><tr>
          <th>角色名</th><th>显示名</th><th>类型</th><th>权限数</th><th>用户数</th><th>状态</th><th>操作</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in roles" :key="r.id">
            <td><span class="role-name">{{ r.name }}</span><span v-if="r.code && r.code !== r.name" class="role-code">{{ r.code }}</span></td>
            <td>{{ r.display_name }}</td>
            <td>
              <span v-if="r.is_system" class="pill pill-purple">系统角色</span>
              <span v-else class="pill pill-gray">自定义</span>
            </td>
            <td>{{ r.permissions.length }}</td>
            <td>{{ r.user_count }}</td>
            <td>
              <span class="pill" :class="r.is_enabled ? 'pill-green' : 'pill-red'">{{ r.is_enabled ? '启用' : '禁用' }}</span>
            </td>
            <td class="ops">
              <button class="btn btn-mini" @click="openEditor(r)">权限</button>
              <button v-if="canWrite" class="btn btn-mini" :class="{ 'is-disabled-action': r.is_system }" :disabled="r.is_system || roleToggleId === r.id" :title="r.is_system ? '系统角色不可停用' : undefined" @click="toggleRole(r)">{{ roleToggleId === r.id ? '处理中…' : (r.is_enabled ? '停用' : '启用') }}</button>
              <button v-if="canDelete && !r.is_system" class="btn btn-mini btn-danger" @click="handleDelete(r)">删除</button>
              <span v-else-if="r.is_system" class="muted">—</span>
            </td>
          </tr>
          <tr v-if="!roles.length"><td colspan="7" class="empty-row">暂无角色</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 权限编辑 / 查看抽屉 -->
    <div v-if="editorOpen" class="modal-overlay" @click.self="closeEditor">
      <div class="modal modal-wide">
        <h3>{{ editingRole?.display_name || '' }} · 权限配置</h3>
        <p v-if="isAdminRole" class="banner">
          该角色为<strong>超管角色</strong>，拥有全部权限（后端按 <code>role='admin'</code> 或 <code>is_superuser</code> 放行），无需单独勾选。
        </p>
        <div class="permission-mode-bar">
          <div>
            <strong>权限配置</strong>
            <span>默认展示四类外网组合权限；外网旧细粒度权限保留在兼容区，其他权限保持原样。</span>
          </div>
          <button type="button" class="compatibility-toggle" :aria-expanded="showLegacyPermissions" @click="showLegacyPermissions = !showLegacyPermissions">
            {{ showLegacyPermissions ? '收起兼容权限' : `展开兼容权限（${legacyPermissionCount}项）` }}
          </button>
        </div>
        <div class="perm-groups">
          <div v-for="g in visiblePermissionGroups" :key="g.group" class="perm-group" :class="{ 'foreign-combined-group': g.group === 'Foreign combined', 'legacy-permission-group': isForeignLegacyGroup(g.group) }">
            <div class="perm-group-title">{{ g.label }}</div>
            <div v-if="g.group === 'Foreign combined'" class="perm-group-note">
              四类组合权限按业务场景归类；保存后由后端自动展开为兼容的细粒度权限。
            </div>
            <div class="perm-grid">
              <label v-for="p in g.perms" :key="p.code" class="perm-item" :class="{ disabled: isAdminRole }">
                <input
                  type="checkbox"
                  :checked="selected.has(p.code)"
                  :disabled="isAdminRole"
                  @change="toggle(p.code, ($event.target as HTMLInputElement).checked)"
                />
                <span class="perm-copy">
                  <span class="perm-line"><span class="perm-code">{{ p.code }}</span><span class="perm-name">{{ permNameLabel(p) }}</span></span>
                  <span v-if="g.group !== 'Foreign combined'" class="perm-desc">{{ p.description }}</span>
                </span>
                <el-tooltip v-if="g.group === 'Foreign combined' || (p.description && p.description.length > 42)" :content="p.description || permNameLabel(p)" placement="top" :show-after="200">
                  <button type="button" class="perm-help" :aria-label="`${permNameLabel(p)}说明`" @click.prevent.stop>?</button>
                </el-tooltip>
              </label>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn" @click="closeEditor">关闭</button>
          <button v-if="canWrite && !isAdminRole" class="btn btn-primary" @click="savePermissions" :disabled="saving">
            {{ saving ? '保存中...' : '保存权限' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 新建角色 -->
    <div v-if="createOpen" class="modal-overlay" @click.self="createOpen = false">
      <div class="modal modal-wide">
        <h3>新建角色</h3>
        <div class="form-group">
          <label>角色代码（code，英文唯一）</label>
          <input v-model="createForm.code" class="input" placeholder="如 custom_analyst" />
        </div>
        <div class="form-group">
          <label>角色名（name，唯一）</label>
          <input v-model="createForm.name" class="input" placeholder="如 custom_analyst" />
        </div>
        <div class="form-group">
          <label>显示名</label>
          <input v-model="createForm.display_name" class="input" placeholder="如 自定义分析员" />
        </div>
        <div class="form-group">
          <label>描述</label>
          <input v-model="createForm.description" class="input" placeholder="可选" />
        </div>
        <div class="form-group">
          <label>初始权限</label>
          <div class="permission-mode-bar compact-mode-bar">
            <span>默认显示四类外网组合权限；外网旧细粒度权限保留在兼容区。</span>
            <button type="button" class="compatibility-toggle" :aria-expanded="showLegacyCreate" @click="showLegacyCreate = !showLegacyCreate">
              {{ showLegacyCreate ? '收起兼容权限' : `展开兼容权限（${legacyPermissionCount}项）` }}
            </button>
          </div>
          <div class="perm-groups compact">
            <div v-for="g in visibleCreatePermissionGroups" :key="g.group" class="perm-group" :class="{ 'foreign-combined-group': g.group === 'Foreign combined', 'legacy-permission-group': isForeignLegacyGroup(g.group) }">
              <div class="perm-group-title">{{ g.label }}</div>
              <div v-if="g.group === 'Foreign combined'" class="perm-group-note">四类组合权限保存后由后端自动展开为兼容的细粒度权限。</div>
              <div class="perm-grid">
                <label v-for="p in g.perms" :key="p.code" class="perm-item">
                  <input type="checkbox" :checked="createSelected.has(p.code)" @change="toggleCreate(p.code, ($event.target as HTMLInputElement).checked)" />
                  <span class="perm-copy"><span class="perm-line"><span class="perm-code">{{ p.code }}</span><span class="perm-name">{{ permNameLabel(p) }}</span></span><span v-if="g.group !== 'Foreign combined'" class="perm-desc">{{ p.description }}</span></span>
                  <el-tooltip v-if="g.group === 'Foreign combined' || (p.description && p.description.length > 42)" :content="p.description || permNameLabel(p)" placement="top" :show-after="200"><button type="button" class="perm-help" :aria-label="`${permNameLabel(p)}说明`" @click.prevent.stop>?</button></el-tooltip>
                </label>
              </div>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn" @click="createOpen = false">取消</button>
          <button class="btn btn-primary" @click="createRole" :disabled="saving">{{ saving ? '创建中...' : '创建' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { usePermission } from '@/composables/usePermission'
import type { PermissionCatalogItem, RoleOut } from '@/types'

const { hasPermission } = usePermission()
const canWrite = hasPermission('roles:write')
const canDelete = hasPermission('roles:delete')

const loading = ref(false)
const saving = ref(false)
const roleToggleId = ref<number | null>(null)
const roles = ref<RoleOut[]>([])
const catalog = ref<PermissionCatalogItem[]>([])

// 业务模块分组顺序与中文标签（与后端 Permission.group 一一对应）
// 修正：后端实际 group 为「预警管理」，此前写成「告警管理」导致该组落到未知分组、排序失效。
const GROUP_LABEL: Record<string, string> = {
  舆情管理: '舆情',
  事件管理: '事件',
  关键词管理: '关键词',
  用户管理: '用户',
  角色管理: '角色',
  权限管理: '权限',
  预警管理: '预警',
  报告: '报告',
  AI能力: 'AI 能力',
  数据源: '数据源',
  采集管理: '采集器',
  传播溯源: '传播',
  驾驶舱: '驾驶舱',
  审计: '审计/登录日志',
  外网风险: '外网风险',
  'Foreign alerts': '外网告警',
  'Foreign events': '外网事件',
  'Foreign sources': '外网数据源',
  'Foreign combined': '外网组合权限',
}
const GROUP_ORDER: Record<string, number> = {
  舆情管理: 1, 事件管理: 2, 关键词管理: 3, 用户管理: 4, 角色管理: 5, 权限管理: 6,
  预警管理: 7, 报告: 8, AI能力: 9, 数据源: 10,   采集管理: 11, 传播溯源: 12, 驾驶舱: 13, 审计: 14,
  'Foreign combined': 0, 外网风险: 15, 'Foreign sources': 16, 'Foreign alerts': 17, 'Foreign events': 18,
}

// 外网权限项中文名（后端 permission.name 为英文描述，弹窗内需中文化展示）
const PERM_NAME_LABEL: Record<string, string> = {
  'foreign:read': '外网查看（组合）',
  'foreign:data:manage': '外网数据管理（组合）',
  'foreign:analysis': '外网分析（组合）',
  'foreign:alerts:manage': '外网预警管理（组合）',
  'foreign:alerts:acknowledge': '确认外网告警',
  'foreign:alerts:enable': '启用外网告警规则',
  'foreign:alerts:evaluate': '评估外网告警',
  'foreign:alerts:read': '查看外网告警',
  'foreign:alerts:resolve': '处理外网告警',
  'foreign:alerts:rules:read': '查看外网告警规则',
  'foreign:alerts:rules:write': '编辑外网告警规则',
  'foreign:alerts:suppress': '屏蔽外网告警',
  'foreign:events:candidates:read': '查看外网事件候选',
  'foreign:events:confirm': '确认外网事件候选',
  'foreign:events:merge': '合并外网事件',
  'foreign:events:read': '查看外网事件',
  'foreign:events:rebuild': '重建外网事件候选',
  'foreign:events:split': '拆分外网事件',
  'foreign:events:status': '变更外网事件状态',
  'foreign:ai:analyze': '用 AI 分析外网',
  'foreign:alerts:ai-admit': '准入外网 AI 告警',
  'foreign:events:auto-aggregate': '外网事件自动聚合',
  'foreign:events:write': '外网事件写入',
  'foreign:keywords:read': '查看外网关键词',
  'foreign:keywords:write': '编辑外网关键词',
  'foreign:opinions:read': '查看外网舆情',
  'foreign:sources:read': '查看外网数据源',
  'foreign:sources:test': '测试外网数据源',
  'foreign:sources:write': '编辑外网数据源',
}
function permNameLabel(p: PermissionCatalogItem) {
  return PERM_NAME_LABEL[p.code] || p.name
}

const groupedPermissions = computed(() => {
  const map = new Map<string, PermissionCatalogItem[]>()
  for (const p of catalog.value) {
    if (!map.has(p.group)) map.set(p.group, [])
    map.get(p.group)!.push(p)
  }
  return [...map.entries()]
    .sort((a, b) => (GROUP_ORDER[a[0]] ?? 99) - (GROUP_ORDER[b[0]] ?? 99))
    .map(([group, perms]) => ({ group, label: GROUP_LABEL[group] || group, perms: perms.sort((a, b) => a.code.localeCompare(b.code)) }))
})

// —— 权限编辑 ——
const editorOpen = ref(false)
const editingRole = ref<RoleOut | null>(null)
const selected = ref<Set<string>>(new Set())
const isAdminRole = computed(() => editingRole.value?.code === 'admin')
const showLegacyPermissions = ref(false)
const showLegacyCreate = ref(false)
const FOREIGN_LEGACY_GROUPS = new Set(['外网风险', 'Foreign sources', 'Foreign alerts', 'Foreign events'])
function isForeignLegacyGroup(group: string) { return FOREIGN_LEGACY_GROUPS.has(group) }
const legacyPermissionGroups = computed(() => groupedPermissions.value.filter((group) => isForeignLegacyGroup(group.group)))
const visiblePermissionGroups = computed(() => groupedPermissions.value.filter((group) => !isForeignLegacyGroup(group.group) || showLegacyPermissions.value))
const visibleCreatePermissionGroups = computed(() => groupedPermissions.value.filter((group) => !isForeignLegacyGroup(group.group) || showLegacyCreate.value))
const legacyPermissionCount = computed(() => legacyPermissionGroups.value.reduce((total, group) => total + group.perms.length, 0))

function toggle(code: string, checked: boolean) {
  const s = new Set(selected.value)
  if (checked) s.add(code); else s.delete(code)
  selected.value = s
}

async function openEditor(r: RoleOut) {
  editingRole.value = r
  showLegacyPermissions.value = false
  // admin 角色：权限列表为空但后端按超管放行，UI 全选展示（只读）
  selected.value = isAdminRole.value ? new Set(catalog.value.map((p) => p.code)) : new Set(r.permissions)
  editorOpen.value = true
}
function closeEditor() { editorOpen.value = false; editingRole.value = null }

async function savePermissions() {
  if (!editingRole.value || isAdminRole.value) return
  saving.value = true
  try {
    await api.put('/roles/' + editingRole.value.id, { permissions: [...selected.value] })
    ElMessage.success('权限已保存')
    await loadRoles()
    closeEditor()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// —— 新建角色 ——
const createOpen = ref(false)
const createSelected = ref<Set<string>>(new Set())
const createForm = ref({ code: '', name: '', display_name: '', description: '' })

function toggleCreate(code: string, checked: boolean) {
  const s = new Set(createSelected.value)
  if (checked) s.add(code); else s.delete(code)
  createSelected.value = s
}
function openCreate() {
  createForm.value = { code: '', name: '', display_name: '', description: '' }
  createSelected.value = new Set()
  showLegacyCreate.value = false
  createOpen.value = true
}
async function createRole() {
  if (!createForm.value.code || !createForm.value.name) return ElMessage.warning('请填写角色代码与名称')
  saving.value = true
  try {
    await api.post('/roles', {
      code: createForm.value.code,
      name: createForm.value.name,
      display_name: createForm.value.display_name || createForm.value.name,
      description: createForm.value.description || '',
      is_enabled: true,
      permissions: [...createSelected.value],
    })
    ElMessage.success('角色已创建')
    createOpen.value = false
    await loadRoles()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}

async function toggleRole(role: RoleOut) {
  if (role.is_system) return ElMessage.warning('系统角色不可停用')
  roleToggleId.value = role.id
  try {
    await api.put('/roles/' + role.id, { is_enabled: !role.is_enabled })
    ElMessage.success(role.is_enabled ? '角色已停用' : '角色已启用')
    await loadRoles()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '角色状态更新失败')
  } finally {
    roleToggleId.value = null
  }
}

async function handleDelete(r: RoleOut) {
  if (r.is_system) return ElMessage.warning('系统角色不可删除')
  try {
    await ElMessageBox.confirm(`确认删除角色 ${r.display_name}（${r.name}）？此操作不可恢复`, '警告', { type: 'warning' })
    await api.delete('/roles/' + r.id)
    ElMessage.success('已删除')
    await loadRoles()
  } catch (e: any) {
    if (e !== 'cancel' && e?.response) ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function loadRoles() {
  const { data } = await api.get('/roles')
  roles.value = data as RoleOut[]
}
async function loadCatalog() {
  const { data } = await api.get('/permissions')
  catalog.value = data as PermissionCatalogItem[]
}

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([loadCatalog(), loadRoles()])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.roles-page { min-height: 100%; }
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.section-title { font-size: 19px; font-weight: 600; color: #1d1d1f; margin: 0; }
.card { background: #fff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05); padding: 6px 6px 14px; overflow: hidden; }
table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
table.tbl thead th { text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b; padding: 14px 18px; border-bottom: 1px solid #e8e8ed; }
table.tbl tbody td { padding: 15px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; vertical-align: middle; }
table.tbl tbody tr:last-child td { border-bottom: none; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }
.role-name { font-weight: 600; margin-right: 8px; }
.role-code { font-size: 12px; color: #86868b; font-family: "SF Mono", Menlo, Consolas, monospace; }
.ops { display: flex; gap: 6px; flex-wrap: wrap; }
.btn { display: inline-flex; align-items: center; justify-content: center; border: none; border-radius: 980px; padding: 8px 16px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background-color 0.18s, opacity 0.18s; }
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover { background: #0077ed; }
.btn-primary:disabled { opacity: 0.55; cursor: default; }
.btn:disabled, .is-disabled-action { color: #a1a1a6 !important; background: #f1f1f3 !important; opacity: 1; cursor: not-allowed; pointer-events: none; }
.btn-mini { background: transparent; color: #0071e3; padding: 4px 12px; font-size: 13px; }
.btn-mini:hover { background: #e8f1fd; }
.btn-danger { color: #ff3b30; }
.btn-danger:hover { background: rgba(255,59,48,0.08); }
.pill { display: inline-flex; padding: 3px 10px; border-radius: 980px; font-size: 12px; font-weight: 500; }
.pill-blue { background: rgba(0,122,255,0.1); color: #007aff; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-purple { background: rgba(120,80,220,0.12); color: #6a3fd6; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.muted { color: #c7c7cc; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 20px; padding: 28px 30px; width: 460px; max-width: 92vw; max-height: 88vh; overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.15); }
.modal-wide { width: 760px; }
.modal h3 { margin: 0 0 16px; font-size: 18px; font-weight: 600; }
.banner { background: rgba(120,80,220,0.08); color: #5a32c0; border-radius: 12px; padding: 10px 14px; font-size: 13px; margin: 0 0 16px; }
.banner code { background: rgba(120,80,220,0.12); padding: 1px 6px; border-radius: 6px; }

.permission-mode-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 0 0 14px; padding: 11px 14px; border: 1px solid #e8e8ed; border-radius: 12px; background: #fafafc; color: #6e6e73; font-size: 12px; line-height: 1.5; }
.permission-mode-bar strong { display: block; color: #1d1d1f; font-size: 13px; margin-bottom: 2px; }
.compact-mode-bar { margin: 8px 0 10px; }
.compact-mode-bar > span { flex: 1; }
.compatibility-toggle { flex: 0 0 auto; border: 1px solid #d2d2d7; border-radius: 980px; padding: 7px 12px; background: #fff; color: #0071e3; font-size: 12px; cursor: pointer; }
.compatibility-toggle:hover, .compatibility-toggle:focus-visible { border-color: #0071e3; background: #f5f9ff; outline: none; }
.perm-groups { display: flex; flex-direction: column; gap: 14px; margin: 8px 0 4px; }
.perm-groups.compact { max-height: 46vh; overflow-y: auto; }
.perm-group-title { font-size: 13px; font-weight: 600; color: #1d1d1f; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e8e8ed; }
.perm-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 18px; }
.perm-item { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 10px; min-width: 0; font-size: 13px; color: #1d1d1f; cursor: pointer; }
.perm-item.disabled { opacity: 0.7; cursor: default; }
.perm-item input { margin: 0; }
.perm-copy { display: grid; gap: 4px; min-width: 0; }
.perm-line { display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px 12px; min-width: 0; }
.perm-code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px; color: #0071e3; }
.perm-name { font-weight: 500; }
.perm-desc { color: #86868b; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.perm-help { display: inline-grid; place-items: center; width: 20px; height: 20px; padding: 0; border: 1px solid #c7c7cc; border-radius: 50%; background: #fff; color: #6e6e73; font-size: 12px; font-weight: 600; cursor: help; }
.perm-help:hover, .perm-help:focus-visible { border-color: #0071e3; color: #0071e3; outline: none; }
.foreign-combined-group { padding: 14px 16px 16px; border: 1px solid #d9e8f8; border-radius: 14px; background: #f8fbff; }
.foreign-combined-group .perm-group-title { color: #006dcc; border-bottom-color: #cfe2f5; }
.perm-group-note { margin: -2px 0 10px; color: #6e88a5; font-size: 12px; line-height: 1.5; }
.foreign-combined-group .perm-grid { grid-template-columns: 1fr; gap: 10px; }
.foreign-combined-group .perm-item { grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; column-gap: 12px; padding: 12px 14px; border: 1px solid #e7eef7; border-radius: 10px; background: #fff; }
.foreign-combined-group .perm-line { align-items: center; }
.legacy-permission-group { padding: 10px 12px; border: 1px solid #f0f0f3; border-radius: 12px; background: #fff; }

.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; color: #6e6e73; margin-bottom: 4px; }
.input { width: 100%; padding: 10px 12px; border: 1px solid #e8e8ed; border-radius: 12px; font-size: 14px; outline: none; box-sizing: border-box; background: #f5f5f7; }
.input:focus { border-color: #0071e3; background: #fff; }
.form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
</style>
