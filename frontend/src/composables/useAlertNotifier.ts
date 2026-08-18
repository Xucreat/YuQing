// 预警通知中心（单例）：
// - 每 20s 轮询 /api/alerts/unread?since=<上次已读时间>，检测新增预警；
// - 有新预警 → 右下角弹出苹果风通知（10s 自动消失 / 点「稍后」→ 红点常驻）；
// - 点「查看」或点侧栏红点 → 进入 /alerts?tab=records 并清除未读红点。
//
// 状态为模块级单例，AppLayout 与 AlertToastHost 共享同一份响应式数据。

import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import type { AlertRecord } from '@/types'

const STORAGE_CLEAR = 'alert_last_clear_ts'
const STORAGE_TOAST = 'alert_last_toast_ts'
const STORAGE_DOT = 'alert_red_dot'
// 外网预警未读独立基线（与国内互不干扰，避免首次访问互相污染红点/toast）
const STORAGE_FOREIGN_CLEAR = 'foreign_alert_last_clear_ts'
const STORAGE_FOREIGN_TOAST = 'foreign_alert_last_toast_ts'

const POLL_INTERVAL_MS = 20_000
const TOAST_TIMEOUT_MS = 10_000

// ===== 模块级单例状态 =====
const toast = ref<{ items: AlertRecord[]; count: number } | null>(null)
const redDot = ref<boolean>(localStorage.getItem(STORAGE_DOT) === '1')
const unreadCount = ref<number>(0)

let timer: number | null = null
let dismissTimer: number | null = null
let started = false

function nowIso(): string {
  return new Date().toISOString()
}

// 首次访问时把「已读基线」设为当前时间，避免把历史预警当成新预警弹窗。
function loadClearTs(): string {
  let v = localStorage.getItem(STORAGE_CLEAR)
  if (!v) {
    v = nowIso()
    localStorage.setItem(STORAGE_CLEAR, v)
  }
  return v
}
function loadToastTs(): string {
  let v = localStorage.getItem(STORAGE_TOAST)
  if (!v) {
    v = nowIso()
    localStorage.setItem(STORAGE_TOAST, v)
  }
  return v
}
function saveClearTs(v: string) { localStorage.setItem(STORAGE_CLEAR, v) }
function saveToastTs(v: string) { localStorage.setItem(STORAGE_TOAST, v) }
function setRedDot(v: boolean) {
  redDot.value = v
  localStorage.setItem(STORAGE_DOT, v ? '1' : '0')
}

// ===== 外网预警未读基线（独立 localStorage） =====
function loadForeignClearTs(): string {
  let v = localStorage.getItem(STORAGE_FOREIGN_CLEAR)
  if (!v) {
    v = nowIso()
    localStorage.setItem(STORAGE_FOREIGN_CLEAR, v)
  }
  return v
}
function loadForeignToastTs(): string {
  let v = localStorage.getItem(STORAGE_FOREIGN_TOAST)
  if (!v) {
    v = nowIso()
    localStorage.setItem(STORAGE_FOREIGN_TOAST, v)
  }
  return v
}
function saveForeignClearTs(v: string) { localStorage.setItem(STORAGE_FOREIGN_CLEAR, v) }
function saveForeignToastTs(v: string) { localStorage.setItem(STORAGE_FOREIGN_TOAST, v) }

export function useAlertNotifier() {
  const router = useRouter()
  const route = useRoute()

  async function poll() {
    // 未登录（如已退出）时不打扰后端。
    if (!localStorage.getItem('token')) return
    try {
      // —— 国内预警（原逻辑，零改动）——
      const since = loadClearTs()
      const { data } = await api.get<{ items: AlertRecord[]; total: number }>('/alerts/unread', { params: { since } })
      const items: any[] = (data.items || []).map((i) => ({ ...i, scope: 'domestic' }))
      unreadCount.value = data.total || 0

      const lastToast = new Date(loadToastTs()).getTime()
      const fresh: any[] = items.filter((i) => new Date(i.created_at).getTime() > lastToast)

      // —— 外网预警（新增分支，独立基线，合并进同一红点/toast）——
      let foreignFresh: any[] = []
      try {
        const fSince = loadForeignClearTs()
        const fResp = await api.get<{ items: any[]; total: number }>('/foreign/alerts/unread', { params: { since: fSince } })
        const fItems: any[] = fResp.data.items || []
        unreadCount.value = (unreadCount.value || 0) + (fResp.data.total || 0)
        const fLastToast = new Date(loadForeignToastTs()).getTime()
        foreignFresh = fItems.filter((i) => new Date(i.created_at).getTime() > fLastToast)
      } catch {
        // 外网接口异常不影响国内通知
      }

      // 合并弹窗：国内 fresh + 外网 foreignFresh，按产生时间倒序取前 3 条
      if (!toast.value) {
        const merged = [...fresh, ...foreignFresh]
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
          .slice(0, 3)
        if (merged.length > 0) {
          if (fresh.length > 0) {
            const maxTs = Math.max(...fresh.map((i) => new Date(i.created_at).getTime()))
            saveToastTs(new Date(maxTs).toISOString())
          }
          if (foreignFresh.length > 0) {
            const fMaxTs = Math.max(...foreignFresh.map((i) => new Date(i.created_at).getTime()))
            saveForeignToastTs(new Date(fMaxTs).toISOString())
          }
          toast.value = { items: merged, count: merged.length }
          armDismiss()
        }
      }
    } catch {
      // 网络/鉴权错误忽略（401 由 axios 拦截器统一处理跳登录）。
    }
  }

  function armDismiss() {
    if (dismissTimer) clearTimeout(dismissTimer)
    dismissTimer = window.setTimeout(() => dismissToast(false), TOAST_TIMEOUT_MS)
  }

  // viewed=true 表示用户主动查看（清除红点）；false 表示忽略（红点常驻）。
  function dismissToast(viewed: boolean) {
    if (dismissTimer) { clearTimeout(dismissTimer); dismissTimer = null }
    toast.value = null
    if (!viewed) setRedDot(true)
  }

  function viewAlerts() {
    // 按首条记录的 scope 分流跳转：外网 → 外网记录页，国内 → 保持原路径
    const scope = (toast.value?.items?.[0] as any)?.scope
    dismissToast(true)
    markVisited()
    router.push(scope === 'foreign' ? '/alerts?tab=records&scope=foreign' : '/alerts?tab=records')
  }

  function laterAlerts() {
    dismissToast(false)
  }

  // 进入预警记录列表即视为已读：重置基线时间并清除红点。
  function markVisited() {
    const now = nowIso()
    saveClearTs(now)
    saveToastTs(now)
    saveForeignClearTs(now)
    saveForeignToastTs(now)
    setRedDot(false)
    unreadCount.value = 0
  }

  function openNotifications() {
    markVisited()
    router.push('/alerts?tab=records')
  }

  function start() {
    if (started) return
    started = true
    poll()
    timer = window.setInterval(poll, POLL_INTERVAL_MS)
  }

  // 进入 /alerts 任意页即清除未读（已身处预警中心）。
  watch(
    () => route.path,
    (p) => { if (p.startsWith('/alerts')) markVisited() },
  )

  return { toast, redDot, unreadCount, start, viewAlerts, laterAlerts, openNotifications, markVisited }
}
