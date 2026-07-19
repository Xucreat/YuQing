<template>
  <div class="opinions" v-loading="loading">
    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="12" align="middle">
        <el-col :span="5">
          <el-select
            v-model="filters.source"
            placeholder="来源（全部）"
            clearable
            @change="handleSearch"
          >
            <el-option
              v-for="s in sourceOptions"
              :key="s"
              :label="s"
              :value="s"
            />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select
            v-model="filters.risk_level"
            placeholder="情感（全部）"
            clearable
            @change="handleSearch"
          >
            <el-option label="负面 negative" value="negative" />
            <el-option label="中性 neutral" value="neutral" />
            <el-option label="正面 positive" value="positive" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-input
            v-model="filters.keyword"
            placeholder="关键词 / 标题 / 内容"
            clearable
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleRefresh">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card">
      <el-table :data="rows" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="标题" min-width="260">
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row.id)">
              {{ row.title }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="150" />
        <el-table-column label="风险评分" width="110" align="center">
          <template #default="{ row }">
            <span :style="{ color: riskColor(row.risk_score), fontWeight: 600 }">
              {{ row.risk_score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="情感" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="sentimentTag(row.sentiment)" size="small">
              {{ sentimentText(row.sentiment) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分析状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.analysis_status)" size="small">
              {{ statusText(row.analysis_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.publish_time) }}
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          background
          layout="total, prev, pager, next, sizes"
          :total="total"
          :current-page="page"
          :page-size="size"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { Opinion, OpinionListResponse } from '@/types'

const router = useRouter()

const loading = ref(false)
const rows = ref<Opinion[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const sourceOptions = ref<string[]>([])

const filters = reactive({
  source: '',
  risk_level: '',
  keyword: '',
})

function riskColor(score: number): string {
  if (score >= 70) return '#f56c6c' // 红
  if (score >= 40) return '#e6a23c' // 橙
  return '#67c23a' // 绿
}

function sentimentTag(s: string): 'success' | 'danger' | 'info' {
  if (s === 'negative') return 'danger'
  if (s === 'positive') return 'success'
  return 'info'
}
function sentimentText(s: string): string {
  return { negative: '负面', positive: '正面', neutral: '中性' }[s] || s
}

function statusTag(s: string): 'success' | 'danger' | 'warning' | 'info' {
  return (
    (
      {
        completed: 'success',
        failed: 'danger',
        processing: 'warning',
        pending: 'info',
      } as const
    )[s] || 'info'
  )
}
function statusText(s: string): string {
  return (
    { completed: '已完成', failed: '失败', processing: '分析中', pending: '待分析' }[
      s
    ] || s
  )
}

function formatTime(t: string | null): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: size.value }
    if (filters.source) params.source = filters.source
    if (filters.risk_level) params.risk_level = filters.risk_level
    if (filters.keyword) params.keyword = filters.keyword
    const { data } = await api.get<OpinionListResponse>('/opinions', { params })
    rows.value = data.items
    total.value = data.total
    // 从当前数据提取来源选项（并入已有集合，避免筛选后丢失）
    const set = new Set(sourceOptions.value)
    data.items.forEach((o) => o.source && set.add(o.source))
    sourceOptions.value = Array.from(set)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载舆情列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadData()
}

function handleRefresh() {
  filters.source = ''
  filters.risk_level = ''
  filters.keyword = ''
  page.value = 1
  loadData()
}

function handlePageChange(p: number) {
  page.value = p
  loadData()
}

function handleSizeChange(s: number) {
  size.value = s
  page.value = 1
  loadData()
}

function goDetail(id: number) {
  router.push(`/opinion/${id}`)
}

onMounted(loadData)
</script>

<style scoped>
.filter-card {
  margin-bottom: 16px;
}
.table-card {
  min-height: 200px;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
