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
            <td><span class="role-name">{{ r.name }}</span><span class="role-code">{{ r.code }}</span></td>
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
        <div class="perm-groups">
          <div v-for="g in groupedPermissions" :key="g.group" class="perm-group">
            <div class="perm-group-title">{{ g.label }}</div>
            <div class="perm-grid">
              <label v-for="p in g.perms" :key="p.code" class="perm-item" :class="{ disabled: isAdminRole }">
                <input
                  type="checkbox"
                  :checked="selected.has(p.code)"
                  :disabled="isAdminRole"
                  @change="toggle(p.code, ($event.target as HTMLInputElement).checked)"
                />
                <span class="perm-code">{{ p.code }}</span>
                <span class="perm-name">{{ p.name }}</span>
                <span class="perm-desc" :title="p.description">{{ p.description }}</span>
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
          <div class="perm-groups compact">
            <div v-for="g in groupedPermissions" :key="g.group" class="perm-group">
              <div class="perm-group-title">{{ g.label }}</div>
              <div class="perm-grid">
                <label v-for="p in g.perms" :key="p.code" class="perm-item">
                  <input type="checkbox" :checked="createSelected.has(p.code)" @change="toggleCreate(p.code, ($event.target as HTMLInputElement).checked)" />
                  <span class="perm-code">{{ p.code }}</span>
                  <span class="perm-name">{{ p.name }}</span>
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
const roles = ref<RoleOut[]>([])
const catalog = ref<PermissionCatalogItem[]>([])

// 业务模块分组顺序与中文标签（与后端 Permission.group 一一对应；仅基于真实存在的 26 个权限）
const GROUP_LABEL: Record<string, string> = {
  舆情管理: '舆情',
  事件管理: '事件',
  关键词管理: '关键词',
  用户管理: '用户',
  角色管理: '角色',
  权限管理: '权限',
  告警管理: '预警',
  报告: '报告',
  数据源: '数据源',
  采集管理: '采集器',
  传播溯源: '传播',
  驾驶舱: '驾驶舱',
  审计: '审计/登录日志',
}
const GROUP_ORDER: Record<string, number> = {
  舆情管理: 1, 事件管理: 2, 关键词管理: 3, 用户管理: 4, 角色管理: 5, 权限管理: 6,
  告警管理: 7, 报告: 8, 数据源: 9, 采集管理: 10, 传播溯源: 11, 驾驶舱: 12, 审计: 13,
}

const groupedPermissions = computed(() => {
  const map = new Map<string, PermissionCatalogItem[]>()
  for (const p of catalog.value) {
    if (!map.has(p.group)) map.set(p.group, [])
    map.get(p.group)!.push(p)
  }
  return [...map.entries()]
    .sort((a, b) => (GROUP_ORDER[a[0]] ?? 99) - (GROUP_ORDER[b[0]] ?? 99))
    .map(([group, perms]) => ({ group, label: GROUP_LABEL[group] || group, perms }))
})

// —— 权限编辑 ——
const editorOpen = ref(false)
const editingRole = ref<RoleOut | null>(null)
const selected = ref<Set<string>>(new Set())
const isAdminRole = computed(() => editingRole.value?.code === 'admin')

function toggle(code: string, checked: boolean) {
  const s = new Set(selected.value)
  if (checked) s.add(code); else s.delete(code)
  selected.value = s
}

async function openEditor(r: RoleOut) {
  editingRole.value = r
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

.perm-groups { display: flex; flex-direction: column; gap: 14px; margin: 8px 0 4px; }
.perm-groups.compact { max-height: 46vh; overflow-y: auto; }
.perm-group-title { font-size: 13px; font-weight: 600; color: #1d1d1f; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e8e8ed; }
.perm-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 18px; }
.perm-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #1d1d1f; cursor: pointer; }
.perm-item.disabled { opacity: 0.7; cursor: default; }
.perm-item input { margin: 0; }
.perm-code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px; color: #0071e3; }
.perm-name { font-weight: 500; }
.perm-desc { color: #86868b; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 120px; }

.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; color: #6e6e73; margin-bottom: 4px; }
.input { width: 100%; padding: 10px 12px; border: 1px solid #e8e8ed; border-radius: 12px; font-size: 14px; outline: none; box-sizing: border-box; background: #f5f5f7; }
.input:focus { border-color: #0071e3; background: #fff; }
.form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
</style>
