<template>
  <header class="cs-header">
    <div class="cs-header-left">
      <div class="cs-logo">YQ</div>
      <div class="cs-titles">
        <h1 class="cs-title">公安互联网舆情监测研判 · 指挥大屏</h1>
        <p class="cs-subtitle">全域舆情态势 · 实时监测</p>
      </div>
    </div>

    <div class="cs-header-right">
      <div class="cs-status" :class="statusDotClass" :title="statusInfo.desc">
        <span class="cs-dot" :class="statusDotClass"></span>
        <span class="cs-status-code cs-mono">{{ statusInfo.code }}</span>
        <span class="cs-status-text">{{ statusInfo.text }} · {{ statusInfo.desc }}</span>
      </div>
      <div class="cs-clock cs-mono">{{ clock }}</div>
      <button class="cs-exit" type="button" title="返回系统" @click="$emit('exit')">↩ 返回系统</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { FeedStatus } from '@/types/command-screen'

const props = defineProps<{ status: FeedStatus }>()
const emit = defineEmits<{ exit: [] }>()

const statusDotClass = computed(() => ({
  'is-live': props.status === 'live',
  'is-stale': props.status === 'stale' || props.status === 'connecting',
  'is-down': props.status === 'down',
}))
// 明确展示 LIVE / STALE / DOWN 与含义，不能只靠一个圆点让用户自行判断数据是否最新
const STATUS_MAP: Record<FeedStatus, { code: string; text: string; desc: string }> = {
  connecting: { code: 'CONNECTING', text: '连接中', desc: '正在连接数据服务' },
  live: { code: 'LIVE', text: '实时', desc: '数据正常' },
  stale: { code: 'STALE', text: '延迟', desc: '暂未更新，显示最近成功结果' },
  down: { code: 'DOWN', text: '异常', desc: '无法连接数据服务' },
}
const statusInfo = computed(() => STATUS_MAP[props.status])

const clock = ref('')
let timer: ReturnType<typeof setInterval> | null = null
function tick() {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  clock.value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
onMounted(() => {
  tick()
  timer = setInterval(tick, 1000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.cs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 6px 2px;
}
.cs-header-left { display: flex; align-items: center; gap: 14px; }
.cs-logo {
  width: 42px; height: 42px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 18px; letter-spacing: 0.02em;
  color: #04121a;
  background: linear-gradient(135deg, var(--screen-primary), var(--screen-teal));
  box-shadow: var(--screen-glow);
}
.cs-title {
  margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0.04em;
  color: var(--screen-ink);
  text-shadow: 0 0 14px rgba(34, 211, 238, 0.25);
}
.cs-subtitle { margin: 2px 0 0; font-size: 12.5px; color: var(--screen-ink-3); letter-spacing: 0.06em; }
.cs-header-right { display: flex; align-items: center; gap: 18px; }
.cs-status { display: flex; align-items: center; gap: 7px; font-size: 13px; color: var(--screen-ink-2); }
.cs-status-code { font-weight: 800; letter-spacing: 0.08em; font-size: 13px; }
.cs-status.is-live .cs-status-code { color: var(--screen-teal); }
.cs-status.is-stale .cs-status-code { color: var(--screen-amber); }
.cs-status.is-down .cs-status-code { color: var(--screen-rose); }
.cs-clock {
  font-size: 18px; font-weight: 600; letter-spacing: 0.04em;
  color: var(--screen-primary-2);
  text-shadow: 0 0 12px rgba(34, 211, 238, 0.35);
}
.cs-exit {
  margin-left: 6px;
  border: 1px solid rgba(34, 211, 238, 0.35);
  background: rgba(34, 211, 238, 0.08);
  color: var(--screen-primary-2);
  font-size: 13px;
  font-weight: 600;
  padding: 7px 14px;
  border-radius: 10px;
  cursor: pointer;
  white-space: nowrap;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
.cs-exit:hover {
  background: rgba(34, 211, 238, 0.18);
  border-color: rgba(34, 211, 238, 0.55);
}
</style>
