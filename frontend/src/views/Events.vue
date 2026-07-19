<template>
  <div class="events" v-loading="loading">
    <el-card shadow="never" class="op-card">
      <el-button type="warning" :loading="aggregating" @click="handleAggregate">手动聚合</el-button>
      <el-button @click="loadData">刷新</el-button>
      <span v-if="lastResult" class="agg-result">
        聚合成功：新建 {{ lastResult.created }} · 更新 {{ lastResult.updated }} · 关联 {{ lastResult.linked }}
      </span>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table :data="rows" stripe style="width: 100%" @row-click="(row: any) => $router.push('/event/' + row.id)">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="事件标题" min-width="280" show-overflow-tooltip />
        <el-table-column label="风险等级" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="riskTag(row.risk_level)" size="small">{{ riskText(row.risk_level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="opinion_count" label="关联舆情数" width="120" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag type="success" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="首次发现" width="180">
          <template #default="{ row }">{{ formatTime(row.first_time) }}</template>
        </el-table-column>
        <el-table-column label="最后更新" width="180">
          <template #default="{ row }">{{ formatTime(row.last_time) }}</template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          background layout="total, prev, pager, next, sizes"
          :total="total" :current-page="page" :page-size="size"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="handlePageChange" @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { EventItem, EventListResponse, EventCreateResponse } from '@/types'

const loading = ref(false)
const aggregating = ref(false)
const rows = ref<EventItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const lastResult = ref<EventCreateResponse | null>(null)

function riskTag(level: string): 'danger' | 'warning' | 'success' | 'info' {
  return ({ high: 'danger', medium: 'warning', low: 'success' } as const)[level] || 'info'
}
function riskText(level: string): string { return { high: '高', medium: '中', low: '低' }[level] || level }
function formatTime(t: string | null): string { if (!t) return '-'; return t.replace('T', ' ').slice(0, 19) }

async function loadData() {
  loading.value = true
  try {
    const { data } = await api.get<EventListResponse>('/events', { params: { page: page.value, size: size.value } })
    rows.value = data.items; total.value = data.total
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '加载事件列表失败') } finally { loading.value = false }
}

async function handleAggregate() {
  if (aggregating.value) return
  aggregating.value = true
  try {
    const { data } = await api.post<EventCreateResponse>('/events/aggregate')
    lastResult.value = data
    ElMessage.success(`聚合完成：新建 ${data.created}，更新 ${data.updated}，关联 ${data.linked}`)
    page.value = 1; await loadData()
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '聚合失败') } finally { aggregating.value = false }
}

function handlePageChange(p: number) { page.value = p; loadData() }
function handleSizeChange(s: number) { size.value = s; page.value = 1; loadData() }

onMounted(loadData)
</script>

<style scoped>
.op-card { margin-bottom: 16px; }
.agg-result { margin-left: 16px; font-size: 13px; color: #67c23a; }
.table-card { min-height: 200px; }
.table-card .el-table { cursor: pointer; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
