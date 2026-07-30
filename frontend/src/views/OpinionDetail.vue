<template>
  <div class="detail" v-loading="loading">
    <div class="detail-back">
      <button class="btn btn-ghost" @click="goBack">← 返回</button>
    </div>

    <div class="detail-grid" v-if="opinion">
      <!-- Left: original text -->
      <div class="card card-pad-lg">
        <h2 class="detail-title">{{ opinion.title }}</h2>
        <div class="detail-meta">
          <span>来源：{{ opinion.source }}</span>
          <span>发布时间：{{ formatTime(opinion.publish_time) }}</span>
        </div>
        <div class="detail-meta" v-if="opinion.url">
          <a class="detail-url" :href="opinion.url" target="_blank" rel="noopener">{{ opinion.url }}</a>
        </div>
        <div class="detail-divider"></div>
        <div class="detail-content">{{ opinion.content }}</div>
      </div>

      <!-- Right: AI analysis -->
      <div class="detail-right">
      <div class="card card-pad-lg admission-card">
        <div class="ai-header">
          <span class="section-title">准入分析</span>
          <span class="pill pill-blue">{{ contentTypeText(opinion.content_type) }}</span>
        </div>
        <div class="detail-divider"></div>
        <div class="admission-score">
          <span class="admission-score-label">相关性</span>
          <b :class="relevanceClass(opinion.relevance_score)">{{ formatRelevance(opinion.relevance_score) }}</b>
        </div>
        <div v-if="admissionItems.length" class="admission-list">
          <div v-for="item in admissionItems" :key="item.label" class="admission-row">
            <span>{{ item.label }}</span>
            <b>{{ item.value }}</b>
          </div>
        </div>
        <div v-else class="ai-text muted-admission">{{ defaultAdmissionText }}</div>
      </div>

      <div class="card card-pad-lg ai-card">
        <div class="ai-header">
          <span class="section-title">AI 分析</span>
          <span class="pill" :class="statusPill(opinion.analysis_status)">{{ statusText(opinion.analysis_status) }}</span>
        </div>

        <div class="detail-divider"></div>

        <div class="ai-block">
          <div class="ai-label">风险评分</div>
          <div class="risk-big" :style="{ color: riskColor(opinion.risk_score) }">{{ opinion.risk_score }}</div>
        </div>

        <div class="ai-block">
          <div class="ai-label">情感</div>
          <span class="pill" :class="sentimentPill(opinion.sentiment)"><span class="dot"></span>{{ sentimentText(opinion.sentiment) }}</span>
        </div>

        <div class="ai-block">
          <div class="ai-label">AI 摘要</div>
          <div class="ai-text">{{ opinion.summary || '暂无' }}</div>
        </div>

        <div class="ai-block">
          <div class="ai-label">关键词</div>
          <div class="kw-tags" v-if="keywordList.length">
            <span v-for="k in keywordList" :key="k" class="kw-tag">{{ k }}</span>
          </div>
          <span v-else class="ai-text">暂无</span>
        </div>

        <div class="ai-block">
          <div class="ai-label">研判建议</div>
          <div class="ai-text">{{ opinion.analysis_suggestion || '暂无' }}</div>
        </div>

        <div class="ai-block">
          <div class="ai-label">分析时间</div>
          <div class="ai-text">{{ formatTime(opinion.analysis_time) }}</div>
        </div>

        <div class="detail-divider"></div>

        <div class="ai-actions">
          <button
            v-if="opinion.analysis_status !== 'processing'"
            class="btn btn-primary btn-block"
            :disabled="analyzing"
            @click="triggerAnalyze"
          >
            {{ analyzing ? '分析中...' : '触发 AI 分析' }}
          </button>
          <div v-else class="ai-status-line">
            <span class="spinner"></span>
            <span class="ai-text">AI 分析进行中...</span>
          </div>
        </div>
      </div>
      </div>
    </div>

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
  (opinion.value?.keywords || '').split(',').map(k => k.trim()).filter(Boolean)
)

const CONTENT_TYPE_TEXT: Record<string, string> = {
  complaint: '投诉举报',
  consultation: '咨询求助',
  risk_event: '风险事件',
  public_affairs: '公共事务',
  news: '新闻',
  policy: '政策政务',
  advertising: '广告',
  entertainment: '娱乐',
  irrelevant: '无关',
}

function contentTypeText(type?: string | null): string {
  return type ? (CONTENT_TYPE_TEXT[type] || type) : '未标注'
}

function formatRelevance(score?: number | null): string {
  return score == null ? '-' : `${score} 分`
}

function relevanceClass(score?: number | null): string {
  if (score == null) return 'score-empty'
  if (score >= 60) return 'score-high'
  if (score >= 40) return 'score-low'
  return 'score-filtered'
}

const admissionItems = computed(() => {
  const reason = opinion.value?.admission_reason
  if (!reason || typeof reason !== 'object' || reason.policy === 'default_allow_non_weibo') return []
  const items: { label: string; value: string }[] = []
  const add = (label: string, value: any) => {
    const arr = Array.isArray(value) ? value.filter(Boolean) : []
    if (arr.length) items.push({ label, value: arr.slice(0, 5).join('、') })
  }
  add('地域命中', reason.region_hits)
  add('公共事务', reason.public_hits)
  add('诉求词', reason.demand_hits)
  add('风险词', reason.risk_hits)
  return items
})

const defaultAdmissionText = computed(() => {
  const reason = opinion.value?.admission_reason
  const source = String(reason?.source || opinion.value?.source || '')
  if (reason?.policy === 'default_allow_non_weibo') {
    return source.includes('政府') || source.includes('政务') ? '政府来源默认准入' : '新闻来源默认准入'
  }
  return '系统默认准入'
})

function riskColor(score: number): string {
  if (score >= 70) return '#ff3b30'
  if (score >= 40) return '#ff9f0a'
  return '#34c759'
}
function sentimentPill(s: string): string {
  return { negative: 'pill-red', positive: 'pill-green', neutral: 'pill-gray' }[s] || 'pill-gray'
}
function sentimentText(s: string): string {
  return { negative: '负面', positive: '正面', neutral: '中性' }[s] || s
}
function statusPill(s: string): string {
  return ({ completed: 'pill-green', failed: 'pill-red', processing: 'pill-orange', pending: 'pill-gray' } as const)[s] || 'pill-gray'
}
function statusText(s: string): string {
  return ({ completed: '已完成', failed: '失败', processing: '分析中', pending: '待分析' } as const)[s] || s
}
function formatTime(t: string | null | undefined): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

async function loadData() {
  loading.value = true
  try {
    const { data } = await api.get<Opinion>('/opinions/' + opinionId.value)
    opinion.value = data
  } catch (err: any) {
    if (err?.response?.status === 404) { opinion.value = null }
    else { ElMessage.error(err?.response?.data?.detail || '加载详情失败') }
  } finally { loading.value = false }
}

async function triggerAnalyze() {
  if (analyzing.value) return
  analyzing.value = true
  try {
    const { data } = await api.post<Opinion>('/analyze/' + opinionId.value)
    opinion.value = data
    ElMessage.success('AI 分析完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'AI 分析失败，请稍后重试')
    loadData()
  } finally { analyzing.value = false }
}

function goBack() { router.back() }

onMounted(loadData)
</script>

<style scoped>
.detail { min-height: 100%; }
.detail-back { margin-bottom: 18px; }
.detail-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 18px;
  align-items: start;
}
.detail-right { display: flex; flex-direction: column; gap: 18px; }

.card {
  background: #ffffff;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05);
}
.card-pad-lg { padding: 28px 30px; }

.detail-title { font-size: 22px; font-weight: 600; letter-spacing: -0.01em; margin: 0 0 14px; line-height: 1.35; color: #1d1d1f; }
.detail-meta { display: flex; flex-wrap: wrap; gap: 8px 22px; font-size: 13px; color: #6e6e73; margin-bottom: 6px; }
.detail-divider { height: 1px; background: #e8e8ed; margin: 18px 0; }
.detail-content { font-size: 15px; line-height: 1.85; color: #2b2b2e; white-space: pre-wrap; }
.detail-url { color: #0071e3; word-break: break-all; font-size: 13.5px; text-decoration: none; }
.detail-url:hover { text-decoration: underline; }

.ai-header { display: flex; align-items: center; justify-content: space-between; }
.section-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }

.ai-block { margin-bottom: 18px; }
.ai-label { font-size: 12.5px; color: #86868b; font-weight: 600; margin-bottom: 8px; letter-spacing: 0.02em; text-transform: uppercase; }
.ai-text { font-size: 14.5px; line-height: 1.7; color: #1d1d1f; }
.risk-big { font-size: 44px; font-weight: 600; letter-spacing: -0.02em; line-height: 1; }

.pill {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px;
  border-radius: 980px; font-size: 13px; font-weight: 500; line-height: 1.4; white-space: nowrap;
}
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.pill-blue { background: #e8f1fd; color: #0071e3; }

.kw-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.kw-tag { background: #e8f1fd; color: #0071e3; padding: 5px 12px; border-radius: 980px; font-size: 13px; font-weight: 500; }

.ai-actions { margin-top: 6px; }
.ai-status-line { display: flex; align-items: center; gap: 10px; }
.admission-card {
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 78%);
  border: 1px solid #e3eefb;
}
.admission-score { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.admission-score-label { font-size: 13px; color: #86868b; font-weight: 600; }
.admission-score b { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
.score-high { color: #1a8e3c; }
.score-low { color: #c77700; }
.score-filtered { color: #ff3b30; }
.score-empty { color: #6e6e73; }
.admission-list { display: grid; gap: 8px; }
.admission-row {
  display: grid; grid-template-columns: 84px minmax(0, 1fr); gap: 10px;
  font-size: 13.5px; line-height: 1.5;
}
.admission-row span { color: #86868b; }
.admission-row b { color: #1d1d1f; font-weight: 600; word-break: break-word; }
.muted-admission { color: #86868b; }

.btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; border: none; border-radius: 980px; padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background-color 0.18s ease, opacity 0.18s ease; }
.btn:active { transform: scale(0.98); }
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover { background: #0077ed; }
.btn-primary:disabled { opacity: 0.55; cursor: default; }
.btn-ghost { background: #e8e8ed; color: #1d1d1f; }
.btn-ghost:hover { background: #dededf; }
.btn-block { width: 100%; justify-content: center; }

.spinner {
  width: 15px; height: 15px; border-radius: 50%;
  border: 2px solid #d2d2d7; border-top-color: #0071e3;
  animation: spin 0.7s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 1100px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
