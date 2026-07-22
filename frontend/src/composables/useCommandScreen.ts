/**
 * 指挥大屏 API 数据层。
 *
 * 目标（本阶段固定策略，不做用户可配置）：
 *   stats  : 30s 轮询
 *   recent : 15s 轮询
 *   alerts : 15s 轮询
 * 后端已有进程内 TTL 缓存（10s），前端轮询间隔与之匹配。
 *
 * 关键要求：
 * - 复用现有 @/api（axios 实例，自动带 Bearer token）；
 * - loading / error 状态清晰；
 * - 保留上一份成功数据，请求失败时不黑屏，仅切换状态（数据延迟 / 连接异常）；
 * - 组件卸载清理定时器；
 * - 请求失败不会产生多个重复定时器；
 * - 防竞态：旧响应不会覆盖新响应；
 * - 页面重新进入（组件重新挂载）时重新获取数据。
 */
import { onBeforeUnmount, onMounted, ref, shallowRef, type Ref } from 'vue'
import api from '@/api'
import type {
  CommandScreenStats,
  RecentOpinionItem,
  DashboardAlertItem,
  FeedStatus,
} from '@/types/command-screen'
import type { RegionChildren, KpiTrends } from '@/types'

/** 集中定义的刷新间隔常量（毫秒），未来按真实运行情况调整 */
export const REFRESH_INTERVALS = {
  stats: 30_000,
  recent: 15_000,
  alerts: 15_000,
} as const

export interface PolledResource<T> {
  /** 最近一次成功的数据（失败时保留上一份，不会被置空） */
  data: Ref<T | null>
  /** 首次加载中（有数据后不再为 true，避免刷新时整屏 loading） */
  loading: Ref<boolean>
  /** 最近一次请求是否出错 */
  error: Ref<unknown | null>
  /** 连接状态：connecting / live / stale / down */
  status: Ref<FeedStatus>
  /** 手动刷新一次 */
  refresh: () => Promise<void>
  /** 启动轮询（幂等：重复调用不会产生多个定时器） */
  start: () => void
  /** 停止轮询并清理定时器 */
  stop: () => void
}

/**
 * 通用轮询器。绑定组件生命周期：挂载即启动，卸载即清理。
 * @param fetcher 返回 Promise 的取数函数
 * @param intervalMs 轮询间隔
 */
export function usePolledResource<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
): PolledResource<T> {
  const data = shallowRef<T | null>(null)
  const loading = ref(false)
  const error = ref<unknown | null>(null)
  const status = ref<FeedStatus>('connecting')

  let timer: ReturnType<typeof setInterval> | null = null
  // 防竞态：每次请求自增序号，仅接受最新一次请求的结果
  let seq = 0
  let hasData = false
  let stopped = false

  async function refresh(): Promise<void> {
    const mySeq = ++seq
    if (!hasData) loading.value = true
    try {
      const result = await fetcher()
      // 丢弃过期响应（更晚发起的请求已经回来或已停止）
      if (mySeq !== seq || stopped) return
      data.value = result
      hasData = true
      error.value = null
      status.value = 'live'
    } catch (err) {
      if (mySeq !== seq || stopped) return
      error.value = err
      // 有历史数据 → 数据延迟（stale）；从未成功 → 连接异常（down）
      status.value = hasData ? 'stale' : 'down'
    } finally {
      if (mySeq === seq) loading.value = false
    }
  }

  function start(): void {
    stopped = false
    // 幂等：先清掉可能存在的旧定时器，杜绝重复定时器叠加
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    void refresh()
    timer = setInterval(() => void refresh(), intervalMs)
  }

  function stop(): void {
    stopped = true
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  onMounted(start)
  onBeforeUnmount(stop)

  return { data, loading, error, status, refresh, start, stop }
}

/** 大屏总览统计（stats，30s）。days 为窗口天数，默认 7。 */
export function useCommandScreenStats(days: Ref<number> | number = 7) {
  const getDays = () => (typeof days === 'number' ? days : days.value)
  return usePolledResource<CommandScreenStats>(async () => {
    const { data } = await api.get<CommandScreenStats>('/dashboard/stats', {
      params: { days: getDays() },
    })
    return data
  }, REFRESH_INTERVALS.stats)
}

/** 实时快讯（recent，15s） */
export function useCommandScreenRecent(limit = 8) {
  return usePolledResource<RecentOpinionItem[]>(async () => {
    const { data } = await api.get<RecentOpinionItem[]>('/dashboard/recent', {
      params: { limit },
    })
    return data
  }, REFRESH_INTERVALS.recent)
}

/** 预警滚动（alerts，15s） */
export function useCommandScreenAlerts(limit = 8) {
  return usePolledResource<DashboardAlertItem[]>(async () => {
    const { data } = await api.get<DashboardAlertItem[]>('/dashboard/alerts', {
      params: { limit },
    })
    return data
  }, REFRESH_INTERVALS.alerts)
}

/**
 * 快讯 + 预警的聚合封装（两条独立 15s 轮询，互不影响）。
 * 便于页面一次性拿到两路 feed 及各自状态。
 */
export function useCommandScreenFeed(opts?: { recentLimit?: number; alertLimit?: number }) {
  const recent = useCommandScreenRecent(opts?.recentLimit ?? 8)
  const alerts = useCommandScreenAlerts(opts?.alertLimit ?? 8)
  return { recent, alerts }
}

/**
 * 监测信源数（KPI「监测信源」）。
 *
 * 数据口径说明（重要）：
 * - 后端 /dashboard/stats 的 `sources` 字段是「窗口内按提及频次 Top{N}」的来源分布，
 *   服务端 TOP_SOURCES 上限为 10，只能给出「窗口内来源榜」，不能代表在监信源总数。
 * - 真正语义上的「监测信源」= 当前启用中的采集数据源数量，由
 *   /admin/data-sources?enabled=true 的 total 给出（本环境 = 22）。
 * - 该端点需要 admin 角色；非 admin 调用会 403 → 此处降级为 stats.sources.length，
 *   由调用方（KpiBar）兜底，绝不伪造数字。
 * - 轮询节奏与 stats 一致（30s）；该值 quasi-static，但保留 polling 以维持 live 状态。
 */
export function useCommandScreenSourceCount() {
  return usePolledResource<{ total: number }>(async () => {
    const { data } = await api.get<{ total: number }>('/admin/data-sources', {
      params: { enabled: true, size: 1 },
    })
    return { total: data.total }
  }, REFRESH_INTERVALS.stats)
}

/**
 * 地区下钻取数：点击省级地图后，按省名拉取下属市/县分布。
 * 仅在用户点击时调用（非轮询）；返回的 cities 已按市上卷，可直接与市级 GeoJSON 按名称匹配着色。
 */
export async function fetchRegionChildren(
  province: string,
  days = 7,
): Promise<RegionChildren> {
  const { data } = await api.get<RegionChildren>('/dashboard/region-children', {
    params: { province, days },
  })
  return data
}

/**
 * KPI sparkline 趋势数据（14 天日值序列）。
 * 返回 opinions / high_risk / events 三组趋势，前端据此绘制 SVG 折线图。
 * 调用频率与 stats 一致（30s），后端有 TTL 缓存。
 */
export async function fetchKpiTrends(days = 14): Promise<KpiTrends> {
  const { data } = await api.get<KpiTrends>('/dashboard/kpi-trends', {
    params: { days },
  })
  return data
}
