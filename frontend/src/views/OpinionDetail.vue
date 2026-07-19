<template>
  <div class="detail" v-loading="loading">
    <div class="toolbar">
      <el-button @click="goBack">← 返回</el-button>
    </div>

    <el-row :gutter="20" v-if="opinion">
      <!-- 左栏：原文 -->
      <el-col :span="14">
        <el-card shadow="never">
          <template #header><span>舆情原文</span></template>
          <h2 class="title">{{ opinion.title }}</h2>
          <div class="meta">
            <span>来源：{{ opinion.source }}</span>
            <span>发布时间：{{ formatTime(opinion.publish_time) }}</span>
          </div>
          <div class="meta" v-if="opinion.url">
            链接：
            <el-link type="primary" :href="opinion.url" target="_blank">
              {{ opinion.url }}
            </el-link>
          </div>
          <el-divider />
          <div class="content">{{ opinion.content }}</div>
        </el-card>
      </el-col>

      <!-- 右栏：AI 分析 -->
      <el-col :span="10">
        <el-card shadow="never" class="ai-card">
          <template #header>
            <div class="ai-header">
              <span>AI 分析</span>
              <el-tag :type="statusTag(opinion.analysis_status)" size="small">
                {{ statusText(opinion.analysis_status) }}
              </el-tag>
            </div>
          </template>

          <div class="ai-block">
            <div class="ai-label">风险评分</div>
            <div class="risk-score" :style="{ color: riskColor(opinion.risk_score) }">
              {{ opinion.risk_score }}
            </div>
          </div>

          <div class="ai-block">
            <div class="ai-label">情感</div>
            <el-tag :type="sentimentTag(opinion.sentiment)" size="small">
              {{ sentimentText(opinion.sentiment) }}
            </el-tag>
          </div>

          <div class="ai-block">
            <div class="ai-label">AI 摘要</div>
            <div class="ai-text">{{ opinion.summary || '暂无' }}</div>
          </div>

          <div class="ai-block">
            <div class="ai-label">关键词</div>
            <div>
              <template v-if="keywordList.length">
                <el-tag
                  v-for="k in keywordList"
                  :key="k"
                  class="kw-tag"
                  size="small"
                >
                  {{ k }}
                </el-tag>
              </template>
              <span v-else class="ai-text">暂无</span>
            </div>
          </div>

          <div class="ai-block">
            <div class="ai-label">研判建议</div>
            <div class="ai-text">{{ opinion.analysis_suggestion || '暂无' }}</div>
          </div>

          <div class="ai-block">
            <div class="ai-label">分析时间</div>
            <div class="ai-text">{{ formatTime(opinion.analysis_time) }}</div>
          </div>

          <el-divider />
          <el-button
            v-if="opinion.analysis_status !== 'processing'"
            type="primary"
            :loading="analyzing"
            @click="triggerAnalyze"
          >
            触发 AI 分析
          </el-button>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-else-if="!loading" description="未找到该舆情" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { Opinion } from '@/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const analyzing = ref(false)
const opinion = ref<Opinion | null>(null)

const opinionId = computed(() => Number(route.params.id))

const keywordList = computed(() =>
  (opinion.value?.keywords || '')
    .split(',')
    .map((k) => k.trim())
    .filter(Boolean),
)

function riskColor(score: number): string {
  if (score >= 70) return '#f56c6c'
  if (score >= 40) return '#e6a23c'
  return '#67c23a'
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
function formatTime(t: string | null | undefined): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

async function loadData() {
  loading.value = true
  try {
    const { data } = await api.get<Opinion>(`/opinions/${opinionId.value}`)
    opinion.value = data
  } catch (err: any) {
    if (err?.response?.status === 404) {
      opinion.value = null
    } else {
      ElMessage.error(err?.response?.data?.detail || '加载详情失败')
    }
  } finally {
    loading.value = false
  }
}

async function triggerAnalyze() {
  if (analyzing.value) return
  analyzing.value = true
  try {
    const { data } = await api.post<Opinion>(`/analyze/${opinionId.value}`)
    opinion.value = data
    ElMessage.success('AI 分析完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'AI 分析失败，请稍后重试')
    // 失败后刷新以反映 failed 状态
    loadData()
  } finally {
    analyzing.value = false
  }
}

function goBack() {
  router.back()
}

onMounted(loadData)
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
}
.title {
  margin: 0 0 12px;
  font-size: 20px;
  color: #303133;
}
.meta {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.content {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
  white-space: pre-wrap;
}
.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ai-block {
  margin-bottom: 16px;
}
.ai-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}
.ai-text {
  font-size: 14px;
  line-height: 1.7;
  color: #303133;
}
.risk-score {
  font-size: 34px;
  font-weight: 700;
}
.kw-tag {
  margin: 0 6px 6px 0;
}
</style>
