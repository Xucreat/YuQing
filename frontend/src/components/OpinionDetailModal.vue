<template>
  <Teleport to="body">
    <div v-if="modelValue" class="modal-mask" @click.self="close">
      <div class="modal-card">
        <div class="modal-header">
          <div class="modal-title-wrap">
            <span class="modal-kicker">舆情详情与 AI 分析</span>
            <h3 class="modal-title">{{ detail?.title || '加载中…' }}</h3>
          </div>
          <div class="modal-header-right">
            <a
              v-if="detail?.url"
              class="jump-link"
              :href="detail.url"
              target="_blank"
              rel="noopener"
            >🔗 跳转原文</a>
            <button class="modal-close" title="关闭" @click="close">✕</button>
          </div>
        </div>

        <div class="modal-body" v-loading="detailLoading">
          <template v-if="detail">
            <div class="detail-grid">
              <!-- Left: original text (live-fetched, longer than title) -->
              <div class="card card-pad">
                <div class="detail-meta">
                  <span>来源：{{ detail.source }}</span>
                  <span>发布时间：{{ formatTime(detail.publish_time) }}</span>
                </div>
                <div class="detail-divider"></div>
                <div class="detail-content" v-loading="originalLoading" element-loading-text="正在抓取来源页原文…">
                  <template v-if="originalParas.length">
                    <p v-for="(p, i) in originalParas" :key="i" class="orig-p">{{ p }}</p>
                  </template>
                  <p v-else-if="detail.content && !originalLoading">{{ detail.content }}</p>
                  <p v-else-if="!originalLoading" class="orig-empty">暂无原文内容。</p>
                </div>
                <div class="detail-foot-note" v-if="originalFetched && !originalParas.length && detail.content">
                  来源页暂无可抓取正文，已显示摘要。
                </div>
              </div>

              <!-- Right: AI flowing judgment report -->
              <div class="card card-pad ai-card">
                <div class="ai-header">
                  <span class="section-title">AI 研判报告</span>
                  <span class="pill" :class="statusPill(detail.analysis_status)">{{ statusText(detail.analysis_status) }}</span>
                </div>

                <div class="detail-divider"></div>

                <div class="report-meta">
                  <span class="meta-item">风险评分 <b :style="{ color: riskColor(detail.risk_score) }">{{ detail.risk_score }}</b></span>
                  <span class="meta-sep">·</span>
                  <span class="meta-item">级别 <b>{{ levelText(detail.risk_score) }}</b></span>
                  <span class="meta-sep">·</span>
                  <span class="meta-item">情感 <b>{{ sentimentText(detail.sentiment) }}</b></span>
                </div>

                <div class="report-body">
                  <p v-if="detail.summary" class="report-p">{{ detail.summary }}</p>
                  <p v-else class="report-p report-muted">暂无 AI 摘要。</p>
                  <p v-if="detail.analysis_suggestion" class="report-p">{{ detail.analysis_suggestion }}</p>
                </div>

                <div class="report-keywords" v-if="keywordList.length">
                  <span class="kw-label">关键词</span>
                  <span v-for="k in keywordList" :key="k" class="kw-tag">{{ k }}</span>
                </div>

                <div class="report-time" v-if="detail.analysis_time">
                  分析时间：{{ formatTime(detail.analysis_time) }}
                </div>

                <div class="detail-divider"></div>

                <div class="ai-actions">
                  <button
                    v-if="detail.analysis_status !== 'processing'"
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
          </template>
          <el-empty v-else description="未找到该舆情" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { Opinion } from '@/types'
import {
  riskColor, levelPill, levelText, sentimentPill, sentimentText, statusPill, statusText, formatTime,
} from '@/utils/opinion'

const props = withDefaults(defineProps<{
  modelValue: boolean
  opinionId?: number | null
}>(), { opinionId: null })

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const detailLoading = ref(false)
const originalLoading = ref(false)
const analyzing = ref(false)
const detail = ref<Opinion | null>(null)
const originalParas = ref<string[]>([])
const originalFetched = ref(false)

const keywordList = computed(() =>
  (detail.value?.keywords || '').split(',').map(k => k.trim()).filter(Boolean)
)

interface OriginalResult {
  url: string | null
  original: string[]
  fallback: string
  fetched: boolean
}

async function openDetail(id: number) {
  detailLoading.value = true
  originalLoading.value = true
  detail.value = null
  originalParas.value = []
  originalFetched.value = false
  try {
    const { data } = await api.get<Opinion>('/opinions/' + id)
    detail.value = data
  } catch (err: any) {
    if (err?.response?.status === 404) { detail.value = null }
    else { ElMessage.error(err?.response?.data?.detail || '加载详情失败') }
  } finally { detailLoading.value = false }
  // 弹窗实时抓取来源页原文（不阻塞主信息展示）
  try {
    const { data } = await api.get<OriginalResult>('/opinions/' + id + '/original')
    originalParas.value = Array.isArray(data.original) ? data.original : []
    originalFetched.value = true
  } catch {
    originalFetched.value = true
  } finally { originalLoading.value = false }
}

function close() { emit('update:modelValue', false) }

async function triggerAnalyze() {
  if (analyzing.value || !detail.value) return
  const id = detail.value.id
  analyzing.value = true
  try {
    const { data } = await api.post<Opinion>('/analyze/' + id)
    detail.value = data
    ElMessage.success('AI 分析完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'AI 分析失败，请稍后重试')
    openDetail(id)
  } finally { analyzing.value = false }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.modelValue) close()
}

watch(
  () => [props.modelValue, props.opinionId],
  ([visible, id]) => {
    if (visible && id != null) openDetail(id as number)
  },
)

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.modal-mask {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.42);
  backdrop-filter: saturate(140%) blur(2px);
  display: flex; align-items: center; justify-content: center;
  padding: 32px 20px; animation: maskIn 0.16s ease;
}
@keyframes maskIn { from { opacity: 0; } to { opacity: 1; } }
.modal-card {
  width: min(960px, 100%);
  max-height: calc(100vh - 64px);
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 24px 70px rgba(0,0,0,0.30);
  display: flex; flex-direction: column;
  overflow: hidden;
  animation: cardIn 0.18s ease;
}
@keyframes cardIn { from { transform: translateY(10px) scale(0.99); opacity: 0; } to { transform: none; opacity: 1; } }
.modal-header {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  padding: 18px 22px; border-bottom: 1px solid #e8e8ed;
}
.modal-title-wrap { min-width: 0; }
.modal-kicker { font-size: 12px; font-weight: 600; color: #86868b; letter-spacing: 0.04em; text-transform: uppercase; }
.modal-title { font-size: 18px; font-weight: 600; margin: 4px 0 0; color: #1d1d1f; line-height: 1.35; word-break: break-word; }
.modal-header-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.jump-link {
  display: inline-flex; align-items: center; gap: 6px;
  color: #0071e3; font-size: 13.5px; font-weight: 500; text-decoration: none;
  padding: 7px 14px; border-radius: 980px; background: #eaf2fd; white-space: nowrap;
  transition: background 0.15s ease;
}
.jump-link:hover { background: #dbe9fb; text-decoration: underline; }
.modal-close {
  width: 34px; height: 34px; border-radius: 50%; border: none; background: #e8e8ed;
  color: #1d1d1f; font-size: 15px; cursor: pointer; transition: background 0.15s ease;
}
.modal-close:hover { background: #dededf; }
.modal-body { padding: 18px 22px 22px; overflow-y: auto; }

.detail-grid {
  display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; align-items: start;
}
.detail-meta { display: flex; flex-wrap: wrap; gap: 8px 22px; font-size: 13px; color: #6e6e73; margin-bottom: 6px; }
.detail-divider { height: 1px; background: #e8e8ed; margin: 16px 0; }
.detail-content { font-size: 15px; line-height: 1.85; color: #2b2b2e; white-space: pre-wrap; }
.orig-p { margin: 0 0 14px; text-indent: 2em; }
.orig-p:last-child { margin-bottom: 0; }
.orig-empty { margin: 0; color: #86868b; }
.detail-foot-note { margin-top: 12px; font-size: 12.5px; color: #86868b; text-align: right; }

.ai-header { display: flex; align-items: center; justify-content: space-between; }
.section-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }

/* Flowing judgment report */
.report-meta {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  font-size: 14px; color: #6e6e73; margin-bottom: 14px;
}
.report-meta .meta-item b { color: #1d1d1f; font-weight: 600; }
.report-meta .meta-sep { color: #d2d2d7; }
.report-body { margin-bottom: 14px; }
.report-p {
  font-size: 15px; line-height: 1.85; color: #2b2b2e;
  margin: 0 0 12px; text-indent: 2em;
}
.report-p:last-child { margin-bottom: 0; }
.report-muted { color: #86868b; text-indent: 0; }
.report-keywords { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px; }
.kw-label { font-size: 13px; color: #86868b; margin-right: 2px; }
.kw-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.kw-tag { background: #e8f1fd; color: #0071e3; padding: 5px 12px; border-radius: 980px; font-size: 13px; font-weight: 500; }
.report-time { font-size: 12.5px; color: #86868b; }
.ai-actions { margin-top: 6px; }
.ai-status-line { display: flex; align-items: center; gap: 10px; }
.spinner {
  width: 15px; height: 15px; border-radius: 50%;
  border: 2px solid #d2d2d7; border-top-color: #0071e3;
  animation: spin 0.7s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 1100px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
