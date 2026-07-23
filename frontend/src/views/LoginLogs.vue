<template>
  <div class="logs-page" v-loading="loading">
    <el-card shadow="never" class="filter-card">
      <el-input
        v-model="username"
        placeholder="用户名"
        clearable
        style="width: 200px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-select
        v-model="status"
        placeholder="登录结果"
        clearable
        style="width: 160px; margin-left: 12px"
        @change="reload"
      >
        <el-option label="成功" value="success" />
        <el-option label="失败" value="failed" />
        <el-option label="退出" value="logout" />
      </el-select>
      <el-button type="primary" style="margin-left: 12px" @click="reload">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table :data="logs" stripe empty-text="暂无登录日志">
        <el-table-column type="index" :index="idxFn" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="140" show-overflow-tooltip />
        <el-table-column label="登录时间" min-width="180">
          <template #default="{ row }">{{ fmt(row.login_at) }}</template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP 地址" min-width="140" show-overflow-tooltip />
        <el-table-column label="登录结果" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="failure_reason" label="失败原因" min-width="160" show-overflow-tooltip />
        <el-table-column prop="user_agent" label="用户代理 / 设备" min-width="220" show-overflow-tooltip />
      </el-table>
      <div class="pagination">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :current-page="page"
          :page-size="size"
          @current-change="onPage"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

interface LoginLogItem {
  id: number
  user_id?: number | null
  username: string
  login_at: string
  ip_address?: string | null
  user_agent?: string | null
  status: string
  failure_reason?: string | null
}

const loading = ref(false)
const logs = ref<LoginLogItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const username = ref('')
const status = ref('')

function fmt(t: string | null): string {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}
function statusTag(s: string): 'success' | 'danger' | 'info' {
  if (s === 'success') return 'success'
  if (s === 'failed') return 'danger'
  return 'info'
}
function statusText(s: string): string {
  return ({ success: '成功', failed: '失败', logout: '退出' } as Record<string, string>)[s] || s
}
function idxFn(i: number): number {
  return (page.value - 1) * size.value + i + 1
}

async function reload() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: size.value }
    if (username.value) params.username = username.value
    if (status.value) params.status = status.value
    const { data } = await api.get('/login-logs', { params })
    logs.value = (data.items || []) as LoginLogItem[]
    total.value = data.total || 0
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载登录日志失败')
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  reload()
}
function resetFilters() {
  username.value = ''
  status.value = ''
  page.value = 1
  reload()
}

onMounted(reload)
</script>

<style scoped>
.logs-page { min-height: 100%; }
.filter-card { margin-bottom: 16px; }
.table-card { margin-top: 0; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
