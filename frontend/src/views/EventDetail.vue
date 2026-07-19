<template>
  <div class="event-detail" v-loading="loading">
    <!-- Event 头 -->
    <div class="event-header">
      <div class="event-title-row">
        <h2>{{ event.title }}</h2>
        <el-tag :type="riskTag(event.risk_level)" size="large">{{ riskText(event.risk_level) }}</el-tag>
      </div>
      <div class="event-meta">
        <span>关联舆情：<b>{{ event.total_opinions }}</b> 条</span>
        <span>首次发现：{{ formatTime(event.first_time) }}</span>
        <span>最后更新：{{ formatTime(event.last_time) }}</span>
      </div>
      <div v-if="event.description" class="event-desc">{{ event.description }}</div>
    </div>

    <!-- 关联舆情列表 -->
    <el-card shadow="never" class="opinions-card">
      <template #header><span>关联舆情列表 ({{ event.total_opinions }})</span></template>
      <el-table :data="event.opinions" stripe style="width: 100%"
        @row-click="(row: any) => $router.push('/opinion/' + row.id)"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="280" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="160" />
        <el-table-column label="情感" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="sentimentTag(row.sentiment)" size="small">{{ sentimentText(row.sentiment) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="risk_score" label="风险分" width="90" align="center" />
        <el-table-column label="分析状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.analysis_status === 'completed' ? 'success' : 'info'" size="small">
              {{ row.analysis_status === 'completed' ? '已完成' : row.analysis_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" width="170">
          <template #default="{ row }">{{ formatTime(row.publish_time) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const route = useRoute()
const loading = ref(false)

interface EventDetail {
  id: number
  title: string
  risk_level: string
  opinion_count: number
  status: string
  first_time: string | null
  last_time: string | null
  description: string
  keyword: string
  opinions: any[]
  total_opinions: number
}

const event = ref<EventDetail>({
  id: 0, title: '', risk_level: '', opinion_count: 0, status: '',
  first_time: null, last_time: null, description: '', keyword: '',
  opinions: [], total_opinions: 0,
})

function riskTag(level: string): 'danger' | 'warning' | 'success' | 'info' {
  return ({ high: 'danger', medium: 'warning', low: 'success' } as const)[level] || 'info'
}
function riskText(level: string): string {
  return { high: '高风险', medium: '中风险', low: '低风险' }[level] || level
}

function sentimentTag(s: string): 'success' | 'danger' | 'info' {
  return { positive: 'success', negative: 'danger', neutral: 'info' }[s] as any || 'info'
}
function sentimentText(s: string): string {
  return { positive: '正面', negative: '负面', neutral: '中性' }[s] || s
}

function formatTime(t: string | null): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

async function loadData() {
  loading.value = true
  try {
    const id = route.params.id
    const { data } = await api.get<EventDetail>('/events/' + id)
    event.value = { ...event.value, ...data }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载事件详情失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.event-detail { min-height: 100%; }
.event-header { margin-bottom: 20px; }
.event-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.event-title-row h2 { margin: 0; font-size: 20px; color: #303133; }
.event-meta { display: flex; gap: 24px; font-size: 13px; color: #909399; margin-bottom: 10px; }
.event-desc { font-size: 14px; color: #606266; background: #f8f9fa; padding: 12px 16px; border-radius: 6px; }
.opinions-card .el-table { cursor: pointer; }
</style>
