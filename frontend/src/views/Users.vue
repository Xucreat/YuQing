<template>
  <div class="users-page" v-loading="loading">
    <div class="toolbar">
      <input class="toolbar-search" v-model="searchText" type="text" placeholder="搜索用户名" />
      <button class="btn btn-primary" @click="openAdd">+ 新增用户</button>
    </div>
    <div class="card">
      <table class="tbl">
        <thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>最后登录</th><th>创建时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="user in filteredUsers" :key="user.id">
            <td>{{ user.username }}</td>
            <td><span class="pill" :class="rolePill(user.role)">{{ roleText(user.role) }}</span></td>
            <td><span class="pill" :class="user.is_active ? 'pill-green' : 'pill-red'">{{ user.is_active ? '正常' : '禁用' }}</span></td>
            <td>{{ user.last_login ? new Date(user.last_login).toLocaleString('zh-CN') : '-' }}</td>
            <td>{{ new Date(user.created_at).toLocaleDateString('zh-CN') }}</td>
            <td class="actions">
              <button class="btn btn-mini" @click="openEdit(user)">编辑</button>
              <button v-if="canActivate" class="btn btn-mini" :class="{ 'is-disabled-action': cannotDeactivate(user) }" :disabled="cannotDeactivate(user) || userToggleId === user.id" :title="deactivateDisabledReason(user)" @click="toggleUser(user)">{{ userToggleId === user.id ? '处理中…' : (user.is_active ? '停用' : '启用') }}</button>
              <button class="btn btn-mini btn-danger" @click="handleDelete(user)" :disabled="user.username === 'admin'">删除</button>
            </td>
          </tr>
          <tr v-if="!filteredUsers.length"><td colspan="6" class="empty-row">暂无用户</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div class="modal">
        <h3>{{ editingId ? '编辑用户' : '新增用户' }}</h3>
        <div class="form-group"><label>用户名</label><input v-model="form.username" class="input" :disabled="!!editingId" /></div>
        <div v-if="!editingId" class="form-group"><label>初始密码</label><input v-model="form.password" type="password" class="input" autocomplete="new-password" /></div>
        <div class="form-group"><label>角色</label><select v-model="form.role" class="input" :disabled="!!editingId && selectedUser?.role === 'admin'" :title="editingId && selectedUser?.role === 'admin' ? '管理员角色不可修改' : undefined"><option value="admin">管理员</option><option value="analyst">分析员</option><option value="viewer">观察员</option></select><small v-if="editingId && selectedUser?.role === 'admin'" class="field-hint">管理员角色固定，仅可修改密码。</small></div>
        <div v-if="editingId && selectedUser" class="password-row"><span>密码管理</span><button class="btn btn-mini" @click="openPasswordDialog(selectedUser)">修改此用户密码</button></div>
        <div class="form-actions"><button class="btn" @click="showForm = false">关闭</button><button v-if="!(editingId && selectedUser?.role === 'admin')" class="btn btn-primary" @click="handleSave" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button></div>
      </div>
    </div>

    <div v-if="showPassword" class="modal-overlay" @click.self="closePasswordDialog">
      <div class="modal">
        <h3>{{ passwordMode === 'self' ? '修改我的密码' : `重置 ${selectedUser?.username || ''} 的密码` }}</h3>
        <div v-if="passwordMode === 'self'" class="form-group"><label>旧密码</label><input v-model="passwordForm.old_password" type="password" class="input" autocomplete="current-password" /></div>
        <div class="form-group"><label>新密码</label><input v-model="passwordForm.new_password" type="password" class="input" autocomplete="new-password" /></div>
        <div class="form-group"><label>确认新密码</label><input v-model="passwordForm.confirm_password" type="password" class="input" autocomplete="new-password" /></div>
        <p class="password-hint">密码至少 6 个字符；审计日志不会记录明文密码。</p>
        <div class="form-actions"><button class="btn" @click="closePasswordDialog">取消</button><button class="btn btn-primary" @click="submitPassword" :disabled="passwordSaving">{{ passwordSaving ? '提交中...' : '保存密码' }}</button></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { useAuthStore } from '@/stores'
import { usePermission } from '@/composables/usePermission'

interface UserItem { id: number; username: string; role: string; is_active: boolean; last_login: string | null; created_at: string }
type PasswordMode = 'self' | 'admin'

const authStore = useAuthStore()
const { hasPermission } = usePermission()
const canActivate = hasPermission('users:activate')
const loading = ref(false)
const saving = ref(false)
const passwordSaving = ref(false)
const userToggleId = ref<number | null>(null)
const users = ref<UserItem[]>([])
const searchText = ref('')
const filteredUsers = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  if (!q) return users.value
  return users.value.filter((u) => u.username.toLowerCase().includes(q))
})
const showForm = ref(false)
const showPassword = ref(false)
const editingId = ref<number | null>(null)
const selectedUser = ref<UserItem | null>(null)
const passwordMode = ref<PasswordMode>('admin')
const form = ref({ username: '', password: '', role: 'analyst' })
const passwordForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const currentUsername = computed(() => authStore.username || '')
const activeAdminCount = computed(() => users.value.filter((user) => user.role === 'admin' && user.is_active).length)
function cannotDeactivate(user: UserItem) {
  return user.username === currentUsername.value || (user.role === 'admin' && user.is_active && activeAdminCount.value <= 1)
}
function deactivateDisabledReason(user: UserItem) {
  if (user.username === currentUsername.value) return '当前登录用户不可停用'
  if (user.role === 'admin' && user.is_active && activeAdminCount.value <= 1) return '最后一个启用中的超级管理员不可停用'
  return undefined
}
function rolePill(role: string): string { return ({ admin: 'pill-blue', analyst: 'pill-green', viewer: 'pill-gray' } as Record<string, string>)[role] || 'pill-gray' }
function roleText(role: string): string { return ({ admin: '管理员', analyst: '分析员', viewer: '观察员' } as Record<string, string>)[role] || role }

async function loadUsers() {
  loading.value = true
  try { users.value = (await api.get('/users')).data.items || [] } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '加载用户失败') } finally { loading.value = false }
}
function openAdd() { editingId.value = null; selectedUser.value = null; form.value = { username: '', password: '', role: 'analyst' }; showForm.value = true }
function openEdit(user: UserItem) { editingId.value = user.id; selectedUser.value = user; form.value = { username: user.username, password: '', role: user.role }; showForm.value = true }

async function handleSave() {
  if (!form.value.username.trim()) return ElMessage.warning('请输入用户名')
  if (!editingId.value && form.value.password.length < 6) return ElMessage.warning('初始密码至少需要 6 个字符')
  saving.value = true
  try {
    if (editingId.value) await api.put(`/users/${editingId.value}`, { role: form.value.role })
    else await api.post('/users', form.value)
    ElMessage.success(editingId.value ? '用户已更新' : '用户已创建')
    showForm.value = false
    await loadUsers()
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '操作失败') } finally { saving.value = false }
}

function openPasswordDialog(user: UserItem) {
  selectedUser.value = user
  passwordMode.value = user.username === currentUsername.value ? 'self' : 'admin'
  passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
  showPassword.value = true
}
function closePasswordDialog() { if (!passwordSaving.value) showPassword.value = false }
async function submitPassword() {
  const values = passwordForm.value
  if (passwordMode.value === 'self' && !values.old_password) return ElMessage.warning('请输入旧密码')
  if (!values.new_password || values.new_password.length < 6) return ElMessage.warning('新密码至少需要 6 个字符')
  if (values.new_password !== values.confirm_password) return ElMessage.warning('两次输入的新密码不一致')
  passwordSaving.value = true
  try {
    if (passwordMode.value === 'self') {
      await api.post('/users/me/password', values)
      ElMessage.success('密码修改成功，请重新登录')
      authStore.logout()
      window.location.assign('/login')
    } else {
      await api.post(`/users/${selectedUser.value!.id}/reset-password`, { new_password: values.new_password })
      ElMessage.success('用户密码已重置')
      showPassword.value = false
    }
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '密码操作失败') } finally { passwordSaving.value = false }
}
async function toggleUser(user: UserItem) {
  if (cannotDeactivate(user)) return ElMessage.warning(deactivateDisabledReason(user) || '该用户不可停用')
  userToggleId.value = user.id
  try {
    const action = user.is_active ? 'deactivate' : 'activate'
    await api.post(`/users/${user.id}/${action}`)
    ElMessage.success(user.is_active ? '用户已停用' : '用户已启用')
    await loadUsers()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '用户状态更新失败')
  } finally {
    userToggleId.value = null
  }
}
async function handleDelete(user: UserItem) {
  try { await ElMessageBox.confirm(`确认删除用户 ${user.username}？`, '警告', { type: 'warning' }); await api.delete(`/users/${user.id}`); ElMessage.success('用户已删除'); await loadUsers() } catch { /* cancellation */ }
}
onMounted(loadUsers)
</script>

<style scoped>
.users-page { min-height: 100%; }.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }.section-title { font-size: 19px; font-weight: 600; color: #1d1d1f; margin: 0; }.toolbar-search { height: 36px; padding: 0 12px; border: 1px solid #d2d2d7; border-radius: 8px; background: #fff; color: #1d1d1f; font: inherit; font-size: 13px; min-width: 220px; outline: none; transition: border-color .15s ease, box-shadow .15s ease; }.toolbar-search::placeholder { color: #a1a1a6; }.toolbar-search:focus { border-color: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,.15); }.card { background: #fff; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 12px 32px rgba(0,0,0,.05); padding: 6px 6px 14px; overflow: hidden; }.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }.tbl th { text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b; padding: 14px 18px; border-bottom: 1px solid #e8e8ed; }.tbl td { padding: 15px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; }.actions { white-space: nowrap; }.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }.btn { display: inline-flex; align-items: center; justify-content: center; border: 0; border-radius: 6px; padding: 8px 16px; font-size: 14px; cursor: pointer; }.btn-primary { background: #0071e3; color: #fff; }.btn-primary:disabled { opacity: .55; cursor: default; }.btn-mini { background: transparent; color: #0071e3; padding: 4px 10px; }.btn-mini:hover { background: #e8f1fd; }.btn-danger { color: #ff3b30; }.btn-danger:disabled { opacity: .45; }.pill { display: inline-flex; padding: 3px 10px; border-radius: 999px; font-size: 12px; }.pill-blue { background: #e8f1fd; color: #0071c9; }.pill-green { background: #e8f7ed; color: #1a8e3c; }.pill-red { background: #fff0ef; color: #d93025; }.pill-gray { background: #f0f0f2; color: #6e6e73; }.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; z-index: 1000; }.modal { background: #fff; border-radius: 8px; padding: 28px 30px; width: 440px; max-width: 90vw; box-shadow: 0 20px 60px rgba(0,0,0,.15); }.modal h3 { margin: 0 0 20px; font-size: 18px; }.form-group { margin-bottom: 14px; }.form-group label { display: block; font-size: 13px; color: #6e6e73; margin-bottom: 4px; }.input { width: 100%; padding: 10px 12px; border: 1px solid #e8e8ed; border-radius: 6px; font-size: 14px; box-sizing: border-box; background: #f5f5f7; }.form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }.password-row { display: flex; align-items: center; justify-content: space-between; border-top: 1px solid #eee; padding-top: 14px; color: #6e6e73; font-size: 13px; }.password-hint { color: #86868b; font-size: 12px; line-height: 1.5; }
 .btn:disabled, .is-disabled-action { color: #a1a1a6 !important; background: #f1f1f3 !important; opacity: 1; cursor: not-allowed; pointer-events: none; }.input:disabled { color: #8e8e93; background: #ededf0; border-color: #dedee3; cursor: not-allowed; }.field-hint { display: block; margin-top: 5px; color: #8e8e93; font-size: 12px; }
@media (max-width: 680px) { .card { overflow-x: auto; }.tbl { min-width: 700px; }.modal { padding: 22px; } }
</style>
