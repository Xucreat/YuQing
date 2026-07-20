<template>
  <div class="users-page" v-loading="loading">
    <div class="toolbar">
      <h3 class="section-title">用户管理</h3>
      <button class="btn btn-primary" @click="openAdd">+ 新增用户</button>
    </div>

    <div class="card">
      <table class="tbl">
        <thead><tr>
          <th>用户名</th><th>角色</th><th>状态</th><th>最后登录</th><th>创建时间</th><th>操作</th>
        </tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }}</td>
            <td><span class="pill" :class="rolePill(u.role)">{{ roleText(u.role) }}</span></td>
            <td><span class="pill" :class="u.is_active ? 'pill-green' : 'pill-red'">{{ u.is_active ? '正常' : '禁用' }}</span></td>
            <td>{{ u.last_login ? new Date(u.last_login).toLocaleString('zh-CN') : '-' }}</td>
            <td>{{ new Date(u.created_at).toLocaleDateString('zh-CN') }}</td>
            <td>
              <button class="btn btn-mini" @click="openEdit(u)">编辑</button>
              <button class="btn btn-mini btn-danger" @click="handleDelete(u)" :disabled="u.username === 'admin'">删除</button>
            </td>
          </tr>
          <tr v-if="!users.length"><td colspan="6" class="empty-row">暂无用户</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div class="modal">
        <h3>{{ editingId ? '编辑用户' : '新增用户' }}</h3>
        <div class="form-group">
          <label>用户名</label>
          <input v-model="form.username" class="input" :disabled="!!editingId" />
        </div>
        <div class="form-group">
          <label>密码{{ editingId ? '（留空不修改）' : '' }}</label>
          <input v-model="form.password" type="password" class="input" />
        </div>
        <div class="form-group">
          <label>角色</label>
          <select v-model="form.role" class="input">
            <option value="admin">管理员</option>
            <option value="analyst">分析员</option>
            <option value="viewer">观察员</option>
          </select>
        </div>
        <div class="form-actions">
          <button class="btn" @click="showForm = false">取消</button>
          <button class="btn btn-primary" @click="handleSave" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

interface UserItem { id: number; username: string; role: string; is_active: boolean; last_login: string | null; created_at: string }

const loading = ref(false)
const saving = ref(false)
const users = ref<UserItem[]>([])
const showForm = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ username: '', password: '', role: 'analyst' })

function rolePill(r: string): string { return ({ admin: 'pill-blue', analyst: 'pill-green', viewer: 'pill-gray' } as any)[r] || 'pill-gray' }
function roleText(r: string): string { return ({ admin: '管理员', analyst: '分析员', viewer: '观察员' } as any)[r] || r }

async function loadUsers() {
  loading.value = true
  try { const { data } = await api.get('/users'); users.value = data.items } catch (e: any) { ElMessage.error('加载失败') } finally { loading.value = false }
}

function openAdd() { editingId.value = null; form.value = { username: '', password: '', role: 'analyst' }; showForm.value = true }
function openEdit(u: UserItem) { editingId.value = u.id; form.value = { username: u.username, password: '', role: u.role }; showForm.value = true }

async function handleSave() {
  if (!form.value.username) return ElMessage.warning('请输入用户名')
  if (!editingId.value && !form.value.password) return ElMessage.warning('请输入密码')
  saving.value = true
  try {
    if (editingId.value) {
      await api.put('/users/' + editingId.value, { role: form.value.role, password: form.value.password || undefined })
      ElMessage.success('更新成功')
    } else {
      await api.post('/users', form.value)
      ElMessage.success('创建成功')
    }
    showForm.value = false
    await loadUsers()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') } finally { saving.value = false }
}

async function handleDelete(u: UserItem) {
  try {
    await ElMessageBox.confirm('确认删除用户 ' + u.username + '？', '警告', { type: 'warning' })
    await api.delete('/users/' + u.id)
    ElMessage.success('已删除')
    await loadUsers()
  } catch { /* cancelled */ }
}

onMounted(loadUsers)
</script>

<style scoped>
.users-page { min-height: 100%; }
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.section-title { font-size: 19px; font-weight: 600; color: #1d1d1f; margin: 0; }
.card { background: #fff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05); padding: 6px 6px 14px; overflow: hidden; }
table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
table.tbl thead th { text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b; padding: 14px 18px; border-bottom: 1px solid #e8e8ed; }
table.tbl tbody td { padding: 15px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; }
table.tbl tbody tr:last-child td { border-bottom: none; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }
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
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 20px; padding: 28px 30px; width: 420px; max-width: 90vw; box-shadow: 0 20px 60px rgba(0,0,0,0.15); }
.modal h3 { margin: 0 0 20px; font-size: 18px; font-weight: 600; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; color: #6e6e73; margin-bottom: 4px; }
.input { width: 100%; padding: 10px 12px; border: 1px solid #e8e8ed; border-radius: 12px; font-size: 14px; outline: none; box-sizing: border-box; background: #f5f5f7; }
.input:focus { border-color: #0071e3; background: #fff; }
.form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
</style>
