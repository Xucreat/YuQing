<template>
  <div class="cs-feed">
    <!-- 预警处置摘要（固定顶部，不随滚动） -->
    <div v-if="kind === 'alert' && alerts && alerts.length" class="cs-alert-summary">
      <span class="cs-alert-sum cs-mono"><i class="cs-sum-dot is-amber"></i>待处置 {{ pendingCount }}</span>
      <span class="cs-alert-sum cs-mono"><i class="cs-sum-dot is-teal"></i>已处置 {{ doneCount }}</span>
    </div>

    <!-- 空态 -->
    <div v-if="!hasRows" class="cs-feed-empty">
      {{ kind === 'alert' ? '暂无预警' : '暂无快讯' }}
    </div>

    <!-- 自动滚动视窗 -->
    <div v-else ref="viewportEl" class="cs-feed-viewport">
      <div
        ref="trackEl"
        class="cs-feed-track"
        :class="{ scrolling: overflowing }"
        :style="{ animationDuration: duration }"
      >
        <div v-for="copy in 2" :key="copy" class="cs-feed-copy">
          <!-- 实时快讯 -->
          <ul v-if="kind === 'recent'" class="cs-feed-list">
            <li v-for="o in recent" :key="'r' + copy + '-' + o.id" class="cs-feed-row">
              <span class="cs-badge cs-mono" :class="riskBadge(o.risk_score)">{{ o.risk_score }}</span>
              <div class="cs-feed-main">
                <div class="cs-feed-title">{{ o.title }}</div>
                <div class="cs-feed-meta cs-muted">
                  <span>{{ o.source }}</span>
                  <span>·</span>
                  <span>{{ o.region_name || '未知地区' }}</span>
                  <span>·</span>
                  <span class="cs-mono">{{ shortTime(o.created_at) }}</span>
                </div>
              </div>
              <span class="cs-badge" :class="sentBadge(o.sentiment)">{{ sentLabel(o.sentiment) }}</span>
            </li>
          </ul>

          <!-- 预警滚动 -->
          <ul v-else class="cs-feed-list">
            <li v-for="a in alerts" :key="'a' + copy + '-' + a.id" class="cs-feed-row">
              <span class="cs-badge cs-mono" :class="riskLevelBadge(a.risk_level)">{{ riskLevelText(a.risk_level) }}</span>
              <div class="cs-feed-main">
                <div class="cs-feed-title">{{ a.opinion_title || a.rule_name }}</div>
                <div class="cs-feed-meta cs-muted">
                  <span>{{ a.rule_name }}</span>
                  <span>·</span>
                  <span class="cs-mono">{{ shortTime(a.created_at) }}</span>
                </div>
              </div>
              <span class="cs-badge" :class="a.handled ? 'is-teal' : 'is-amber'">
                {{ a.handled ? '已处置' : '待处置' }}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { RecentOpinionItem, DashboardAlertItem } from '@/types/command-screen'

const props = defineProps<{
  kind: 'recent' | 'alert'
  recent?: RecentOpinionItem[] | null
  alerts?: DashboardAlertItem[] | null
}>()

const viewportEl = ref<HTMLElement | null>(null)
const trackEl = ref<HTMLElement | null>(null)
const overflowing = ref(false)

const rows = computed(() =>
  props.kind === 'recent' ? (props.recent ?? []) : (props.alerts ?? []),
)
const hasRows = computed(() => rows.value.length > 0)
const pendingCount = computed(() => (props.alerts ?? []).filter((a) => !a.handled).length)
const doneCount = computed(() => (props.alerts ?? []).filter((a) => a.handled).length)

// 滚动速度恒定：时长随条数线性增长；最少 8s 保证单条也平滑
const duration = computed(() => `${Math.max(rows.value.length * 2.4, 8)}s`)

/** 是否溢出：轨道为双份内容，-50% 为一份高度；仅当一份高度 > 视窗才滚动 */
function measure() {
  if (!viewportEl.value || !trackEl.value) return
  const oneCopy = trackEl.value.scrollHeight / 2
  overflowing.value = oneCopy > viewportEl.value.clientHeight + 1
}

function shortTime(s: string): string {
  if (!s) return '-'
  return s.replace('T', ' ').slice(5, 16)
}
function sentLabel(s: string): string {
  return ({ negative: '负面', neutral: '中性', positive: '正面' } as Record<string, string>)[s] || '中性'
}
function sentBadge(s: string): string {
  return ({ negative: 'is-rose', neutral: 'is-cyan', positive: 'is-teal' } as Record<string, string>)[s] || 'is-cyan'
}
function riskBadge(score: number): string {
  if (score >= 70) return 'is-rose'
  if (score >= 40) return 'is-amber'
  return 'is-teal'
}
function riskLevelBadge(l: string): string {
  return ({ critical: 'is-rose', high: 'is-rose', medium: 'is-amber', low: 'is-teal' } as Record<string, string>)[l] || 'is-cyan'
}
function riskLevelText(l: string): string {
  return ({ critical: '严重', high: '高', medium: '中', low: '低' } as Record<string, string>)[l] || l
}

let ro: ResizeObserver | null = null
onMounted(() => {
  nextTick(measure)
  if (viewportEl.value && typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => measure())
    ro.observe(viewportEl.value)
  }
})
onBeforeUnmount(() => {
  if (ro) { ro.disconnect(); ro = null }
})
// 数据刷新后重新测量（条数变化可能改变是否溢出）
watch(rows, () => nextTick(measure), { deep: true })
</script>

<style scoped>
.cs-feed { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.cs-feed-empty {
  flex: 1; display: flex; align-items: center; justify-content: center;
  color: var(--screen-ink-3); font-size: 13px;
}
.cs-feed-viewport { flex: 1; min-height: 0; overflow: hidden; }
.cs-feed-track { will-change: transform; }
.cs-feed-track.scrolling {
  animation-name: cs-feed-scroll;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}
/* 悬停暂停，便于阅读 */
.cs-feed-viewport:hover .cs-feed-track.scrolling { animation-play-state: paused; }
@keyframes cs-feed-scroll {
  from { transform: translateY(0); }
  to { transform: translateY(-50%); }
}
.cs-feed-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.cs-feed-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--screen-border);
  border-radius: var(--screen-radius);
  background: rgba(18, 35, 60, 0.4);
}
.cs-feed-main { flex: 1; min-width: 0; }
.cs-feed-title {
  font-size: 13.5px; color: var(--screen-ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cs-feed-meta { display: flex; align-items: center; gap: 6px; font-size: 11.5px; margin-top: 3px; }
.cs-alert-summary {
  display: flex; align-items: center; gap: 18px;
  padding: 6px 10px; margin-bottom: 8px;
  border: 1px solid var(--screen-border);
  border-radius: var(--screen-radius);
  background: rgba(18, 35, 60, 0.5);
}
.cs-alert-sum { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--screen-ink-2); }
.cs-sum-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.cs-sum-dot.is-amber { background: var(--screen-amber); box-shadow: 0 0 8px var(--screen-amber); }
.cs-sum-dot.is-teal { background: var(--screen-teal); box-shadow: 0 0 8px var(--screen-teal); }
@media (prefers-reduced-motion: reduce) {
  .cs-feed-track.scrolling { animation: none; }
}
</style>
