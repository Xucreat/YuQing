<template>
  <div class="donut-wrap">
    <svg class="donut-svg" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r="58" fill="none" stroke="#e8e8ed" stroke-width="16" />
      <circle
        v-for="(seg, i) in segments"
        :key="i"
        cx="70" cy="70" r="58"
        fill="none"
        :stroke="seg.color"
        stroke-width="16"
        :stroke-dasharray="seg.dashArray + ' ' + (364.4 - seg.dashArray)"
        :stroke-dashoffset="seg.dashOffset"
        stroke-linecap="round"
        :transform="'rotate(-90 70 70)'"
      />
      <text x="70" y="66" text-anchor="middle" font-size="28" font-weight="600" fill="#1d1d1f">
        {{ total }}
      </text>
      <text x="70" y="85" text-anchor="middle" font-size="10" fill="#86868b">
        总计
      </text>
    </svg>
    <div class="donut-legends">
      <div v-for="seg in segments" :key="seg.label" class="donut-legend">
        <span class="dl-dot" :style="{ background: seg.color }"></span>
        <span>{{ seg.label }}</span>
        <i>{{ seg.pct }}%</i>
        <b>{{ seg.count }}</b>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: { label: string; count: number; color: string }[]
}>()

const total = computed(() => props.data.reduce((s, d) => s + d.count, 0))

const circumference = 2 * Math.PI * 58 // ≈ 364.4

const segments = computed(() => {
  let offset = 0
  return props.data.map((d) => {
    const pct = total.value > 0 ? d.count / total.value : 0
    const dash = pct * circumference
    const seg = {
      ...d,
      pct: Math.round(pct * 100),
      dashArray: dash || 0,
      dashOffset: -offset,
    }
    offset += dash
    return seg
  })
})
</script>

<style scoped>
.donut-wrap {
  display: flex;
  align-items: center;
  gap: 22px;
  flex-wrap: wrap;
}
.donut-svg {
  width: 140px;
  height: 140px;
  flex-shrink: 0;
}
.donut-legends {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  min-width: 140px;
}
.donut-legend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #1d1d1f;
}
.dl-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex-shrink: 0;
}
.donut-legend b {
  margin-left: auto;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.donut-legend i {
  width: 42px;
  text-align: right;
  font-style: normal;
  color: #86868b;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}
</style>
