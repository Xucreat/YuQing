import * as echarts from 'echarts'
import {
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  type Ref,
} from 'vue'

/**
 * useEcharts —— 指挥大屏可复用的 ECharts 封装。
 *
 * 设计说明：
 * - 现有 Dashboard.vue / Propagation.vue 均使用「全量引入」`import * as echarts`，
 *   本项目当前没有按需引入（tree-shaking）基础设施。为与现有代码保持一致、且遵循
 *   「不为理论上的 tree-shaking 大范围重构」的要求，这里同样使用全量引入。
 *   如后续统一做按需引入，只需改这一个文件的 import。
 * - 统一处理：DOM 初始化 / dispose / window resize / ResizeObserver / option 更新 /
 *   组件卸载清理，避免在页面里到处写 echarts.init。
 */

export interface UseEchartsOptions {
  /** 主题名或主题对象（大屏用暗色，多数直接在 option 里配色即可，可不传） */
  theme?: string | object
  /** echarts.init 的初始化参数，如 { renderer: 'canvas' } */
  initOptions?: echarts.EChartsInitOpts
  /** 是否自动跟随容器/窗口尺寸变化 resize，默认 true */
  autoResize?: boolean
}

export function useEcharts(
  target?: Ref<HTMLElement | null>,
  options: UseEchartsOptions = {},
) {
  // 允许外部传入模板 ref；不传则内部创建，交给调用方绑定到 DOM。
  const el = target ?? ref<HTMLElement | null>(null)
  // 用 shallowRef 存放实例，避免 Vue 对 echarts 内部做深度响应式代理。
  const chart = shallowRef<echarts.ECharts | null>(null)

  let ro: ResizeObserver | null = null
  let rafId = 0

  /** resize 合并到下一帧，避免 ResizeObserver / window resize 高频抖动 */
  function resize(): void {
    if (!chart.value) return
    if (rafId) cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(() => {
      rafId = 0
      chart.value?.resize()
    })
  }

  /** 初始化实例（幂等：已初始化则直接返回） */
  function init(): echarts.ECharts | null {
    if (chart.value) return chart.value
    if (!el.value) return null
    chart.value = echarts.init(el.value, options.theme, options.initOptions)
    if (options.autoResize !== false) {
      window.addEventListener('resize', resize)
      if (typeof ResizeObserver !== 'undefined') {
        ro = new ResizeObserver(resize)
        ro.observe(el.value)
      }
    }
    return chart.value
  }

  /** 更新 option（未初始化时先初始化）。notMerge 默认 false，保持增量合并。 */
  function setOption(
    option: echarts.EChartsOption,
    opts?: echarts.SetOptionOpts,
  ): void {
    if (!chart.value) init()
    chart.value?.setOption(option, opts)
  }

  /** 显示/隐藏 loading 遮罩 */
  function showLoading(text = ''): void {
    chart.value?.showLoading('default', {
      text,
      color: '#22d3ee',
      textColor: '#a9c2da',
      maskColor: 'rgba(6, 11, 22, 0.35)',
    })
  }
  function hideLoading(): void {
    chart.value?.hideLoading()
  }

  /** 彻底清理：解绑监听、断开观察、dispose 实例 */
  function dispose(): void {
    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = 0
    }
    window.removeEventListener('resize', resize)
    if (ro) {
      ro.disconnect()
      ro = null
    }
    if (chart.value) {
      chart.value.dispose()
      chart.value = null
    }
  }

  onMounted(() => {
    // 容器可能尚未拿到尺寸，init 幂等，图表 option 由调用方在数据到位后 setOption。
    init()
  })
  onBeforeUnmount(() => {
    dispose()
  })

  return { el, chart, init, setOption, resize, showLoading, hideLoading, dispose }
}

/**
 * registerMapOnce —— 幂等注册地图（避免重复注册开销）。
 * GeoJSON 由调用方从本地静态资源（/geo/*.json）fetch 后传入，不依赖外网 CDN。
 */
const _registeredMaps = new Set<string>()
export function registerMapOnce(name: string, geoJson: object): void {
  if (_registeredMaps.has(name)) return
  echarts.registerMap(name, geoJson as any)
  _registeredMaps.add(name)
}

export { echarts }
