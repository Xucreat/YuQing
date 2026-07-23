<template>
  <div class="logs-page" v-loading="loading">
    <el-card shadow="never" class="filter-card">
      <el-input
        v-model="operator"
        placeholder="操作人"
        clearable
        style="width: 180px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-input
        v-model="action"
        placeholder="操作类型 (如 CREATE/UPDATE/DELETE)"
        clearable
        style="width: 260px; margin-left: 12px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-select
        v-model="result"
        placeholder="操作结果"
        clearable
        style="width: 160px; margin-left: 12px"
        @change="reload"
      >
        <el-option label="成功" value="success" />
        <el-option label="失败" value="failed" />
      </el-select>
      <el-button type="primary" style="margin-left: 12px" @click="reload">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table :data="logs" stripe empty-text="暂无操作日志">
        <el-table-column type="index" :index="idxFn" label="ID" width="70" />
        <el-table-column prop="operator_username_snapshot" label="操作人" width="160" />
        <el-table-column label="操作类型" width="150">
          <template #default="{ row }">
            <el-tag :type="actionTag(row.action)" size="small">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="资源类型" width="150" />
        <el-table-column prop="resource_id" label="资源 ID" width="140" />
        <el-table-column label="操作结果" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.result === 'success' ? 'success' : 'danger'" size="small">
              {{ row.result === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作时间" width="180">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP 地址" width="160" />
        <el-table-column prop="details_json" label="详情" width="400" />
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

interface OperationLogItem {
  id: number
  operator_user_id?: number | null
  operator_username_snapshot?: string | null
  action: string
  resource_type?: string | null
  resource_id?: string | null
  target_user_id?: number | null
  ip_address?: string | null
  result: string
  details_json?: string | null
  created_at: string
}

const loading = ref(false)
const logs = ref<OperationLogItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const operator = ref('')
const action = ref('')
const result = ref('')

function fmt(t: string | null): string {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}
function actionTag(a: string): 'primary' | 'warning' | 'danger' | 'success' | 'info' {
  if (a === 'DELETE' || a === 'ROLE_DELETE') return 'danger'
  if (a === 'CREATE' || a === 'ROLE_CREATE') return 'success'
  if (a === 'PASSWORD_RESET') return 'warning'
  return 'info'
}
function idxFn(i: number): number {
  return (page.value - 1) * size.value + i + 1
}

async function reload() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: size.value }
    if (operator.value) params.operator = operator.value
    if (action.value) params.action = action.value
    if (result.value) params.result = result.value
    const { data } = await api.get('/operation-logs', { params })
    logs.value = (data.items || []) as OperationLogItem[]
    total.value = data.total || 0
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载操作日志失败')
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  reload()
}
function resetFilters() {
  operator.value = ''
  action.value = ''
  result.value = ''
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
