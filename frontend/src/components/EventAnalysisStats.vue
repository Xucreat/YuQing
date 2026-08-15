<template>
  <section v-if="statistics || situation" class="stat-panel">
    <h3 class="section-title">研判与统计</h3>
    <div class="stat-grid">
      <div class="stat-item" v-if="(statistics?.source_count != null) || (situation?.source_distribution?.length)">
        <span class="stat-label">来源数量</span>
        <strong>{{ statistics?.source_count ?? (situation?.source_distribution?.length || 0) }} 个</strong>
      </div>
      <div class="stat-item" v-if="situation?.data_window?.first_time || situation?.data_window?.last_time">
        <span class="stat-label">时间范围</span>
        <strong>{{ formatTime(situation?.data_window?.first_time) }} - {{ formatTime(situation?.data_window?.last_time) }}</strong>
      </div>
      <div class="stat-item" v-if="statistics">
        <span class="stat-label">风险分布</span>
        <span class="dist-pills">
          <span class="pill pill-red"><span class="dot"></span>高 {{ statistics.risk_distribution?.high ?? 0 }}</span>
          <span class="pill pill-orange"><span class="dot"></span>中 {{ statistics.risk_distribution?.medium ?? 0 }}</span>
          <span class="pill pill-green"><span class="dot"></span>低 {{ statistics.risk_distribution?.low ?? 0 }}</span>
        </span>
      </div>
      <div class="stat-item" v-if="situation?.risk_shadow">
        <span class="stat-label">影子风险</span>
        <strong>{{ situation.risk_shadow?.score ?? '-' }} 分</strong>
      </div>
      <div class="stat-item" v-if="situation?.data_sufficiency">
        <span class="stat-label">数据充分性</span>
        <strong>{{ sufficiencyText(situation.data_sufficiency?.level) }}</strong>
      </div>
    </div>
    <div class="risk-factor-list" v-if="(situation?.risk_factors || []).length">
      <span v-for="factor in (situation.risk_factors || [])" :key="factor.factor" class="risk-factor">
        {{ factor.description }}
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  statistics?: {
    source_count?: number | null
    opinion_count?: number | null
    risk_distribution?: { high?: number; medium?: number; low?: number } | null
  } | null
  situation?: {
    source_distribution?: { source: string; count: number }[] | null
    data_window?: { first_time?: string | null; last_time?: string | null } | null
    risk_shadow?: { score?: number | null } | null
    data_sufficiency?: { level?: string } | null
    risk_factors?: { factor: string; description: string }[] | null
  } | null
}>()

function formatTime(t: string | null | undefined): string {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 19)
}
function sufficiencyText(value: string | undefined): string {
  return ({ sufficient: '充分', limited: '有限', insufficient: '不足' } as Record<string, string>)[value || ''] || '未知'
}
</script>

<style scoped>
.stat-panel { margin-bottom: 20px; padding: 18px 20px; background: #fff; border: 1px solid #e8e8ed; border-radius: 12px; }
.section-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }
.stat-grid { display: flex; flex-wrap: wrap; gap: 1px; margin-top: 14px; background: #e8e8ed; border-radius: 10px; overflow: hidden; }
.stat-item { flex: 1 1 180px; display: flex; flex-direction: column; gap: 6px; padding: 14px 18px; background: #fff; }
.stat-label { font-size: 12px; color: #86868b; }
.stat-item strong { font-size: 16px; color: #1d1d1f; }
.dist-pills { display: inline-flex; flex-wrap: wrap; gap: 6px; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px; border-radius: 980px; font-size: 13px; font-weight: 500; line-height: 1.4; white-space: nowrap; }
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.risk-factor-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.risk-factor { padding: 5px 9px; border-radius: 6px; background: #f5f7fb; color: #3a3a3c; font-size: 12px; }
</style>
