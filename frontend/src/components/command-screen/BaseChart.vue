<template>
  <div ref="chartEl" class="cs-chart"></div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import { useEcharts } from '@/composables/useEcharts'

/**
 * BaseChart —— 通用 ECharts 容器。
 * 只负责「拿到 option → 渲染」，实例生命周期/resize/dispose 全部交给 useEcharts。
 * 各业务图表只需把算好的 option 传进来，避免到处写 echarts.init。
 */
const props = defineProps<{
  option: EChartsOption | null
  /** 数据未就绪时是否显示 loading 遮罩 */
  loading?: boolean
}>()

const chartEl = ref<HTMLElement | null>(null)
const { setOption, showLoading, hideLoading } = useEcharts(chartEl, {
  initOptions: { renderer: 'canvas' },
})

watch(
  () => props.option,
  (opt) => {
    if (opt) {
      hideLoading()
      // notMerge:true 保证切换数据时不残留旧 series
      setOption(opt, { notMerge: true })
    }
  },
  { immediate: true, deep: true },
)

watch(
  () => props.loading,
  (v) => {
    if (v && !props.option) showLoading('加载中')
    else hideLoading()
  },
  { immediate: true },
)
</script>

<style scoped>
.cs-chart {
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>
