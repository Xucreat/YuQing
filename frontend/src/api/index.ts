import axios, { type AxiosError, type AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores'

// 统一 API 客户端（Phase 3 细化：拦截器、错误处理）
const api: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// —— 401 统一处理（未认证 / Token 已失效）——
// 路由守卫只判断 token「是否存在」，不校验有效期；过期 token 仍非空字符串，
// 会导致所有 API 返回 401 而前端静默空屏。这里统一兜底：
//   1. 清除 access token；
//   2. 清空当前用户状态（role / permissions / is_superuser / username）；
//   3. 跳转登录页；
//   4. 给出明确提示「登录状态已失效，请重新登录」。
// 区分 401 与 403：仅 401 触发登出跳转；403（已登录但无权限）由调用处按业务提示，
// 不在此统一登出。
// - 并发轮询可能同时触发多个 401：用 redirectingToLogin 标志位保证只跳一次；
// - 已在 /login 时不重复跳转，避免循环。
// —— 403 统一处理（已登录但权限不足）——
// RBAC 收口前的问题：部分调用点 catch 为空（如事件删除），后端 403 被静默吞掉，
// 用户看到删除确认框却得不到任何反馈，误以为删除成功。
// 这里统一兜底提示，并在 error 上打标 __permissionDenied，
// 供调用点判断「已由全局提示过」，避免重复弹两条消息。
// 注意：不改动 401 逻辑，登录过期机制保持原样。
const PERMISSION_DENIED_TEXT = '权限不足，请联系管理员'
// 后端 403 有两类：
//   (a) RBAC 权限不足：require_permission → "Permission denied"；require_admin → "Admin required"；
//   (b) 业务规则禁止：如「系统内置敏感词不可删除」（带中文业务语义的 detail）。
// 只有 (a) 才走统一「权限不足，请联系管理员」提示；(b) 保持由调用点展示后端 detail，
// 否则会把业务原因误报成权限问题。
const RBAC_DENY_DETAILS = new Set(['permission denied', 'admin required', 'forbidden'])
function isRbacDenyDetail(detail: unknown): boolean {
  if (detail === undefined || detail === null || detail === '') return true
  if (typeof detail !== 'string') return false
  return RBAC_DENY_DETAILS.has(detail.trim().toLowerCase())
}

let lastPermissionToastAt = 0
function notifyPermissionDenied() {
  // 并发请求可能同时 403（如页面同时拉多个接口），1 秒内只提示一次。
  const now = Date.now()
  if (now - lastPermissionToastAt < 1000) return
  lastPermissionToastAt = now
  ElMessage.error(PERMISSION_DENIED_TEXT)
}

let redirectingToLogin = false
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 403) {
      const detail = (error.response?.data as any)?.detail
      if (isRbacDenyDetail(detail)) {
        ;(error as any).__permissionDenied = true
        notifyPermissionDenied()
      }
    }
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      try {
        useAuthStore().logout()
      } catch {
        /* pinia 未初始化时忽略，仅清 token 即可 */
      }
      const alreadyOnLogin = window.location.pathname === '/login'
      if (!alreadyOnLogin && !redirectingToLogin) {
        redirectingToLogin = true
        ElMessage.error('登录状态已失效，请重新登录')
        // 懒加载 router，避免 api → router → views → api 的循环依赖；SPA 跳转保留提示文案
        import('@/router')
          .then((m) => m.default.push('/login'))
          .catch(() => {
            window.location.href = '/login'
          })
          .finally(() => {
            // 跳转后重置标志，便于下次登录失效再次触发
            redirectingToLogin = false
          })
      }
    }
    return Promise.reject(error)
  },
)

export default api

/**
 * 该错误是否为 RBAC 403 权限不足（全局拦截器已统一提示，调用点不必重复提示）。
 * 业务型 403（后端返回中文业务 detail，如「系统内置敏感词不可删除」）返回 false，
 * 调用点应继续按 detail 提示用户。
 */
export function isPermissionDenied(err: any): boolean {
  return !!err?.__permissionDenied
}

// —— 权限缓存刷新（GET /api/auth/me）——
// 应用启动时若本地存在 token，则拉取服务端**实时**权限覆盖 localStorage 缓存，
// 使管理员改完角色权限后，用户「刷新页面即可同步」，无需退出重登。
// 失败时静默返回 null（401 已由上面的拦截器统一处理），不影响登录流程。
export type MeResponse = {
  id: number
  username: string
  display_name?: string | null
  role: string
  roles: string[]
  permissions: string[]
  is_superuser: boolean
  is_active: boolean
}

export async function fetchMe(): Promise<MeResponse | null> {
  try {
    const { data } = await api.get<MeResponse>('/auth/me')
    return data
  } catch {
    return null
  }
}

// —— 后台任务轮询 ——
// 采集/聚合等耗时操作改为后台任务：接口先返回 task_id，前端轮询此任务直到终态。
// opts.intervalMs 轮询间隔（默认 1.5s），opts.timeoutMs 最长等待（默认 10 分钟）。
export async function pollTask(
  taskId: string,
  opts?: { intervalMs?: number; timeoutMs?: number },
): Promise<any> {
  const interval = opts?.intervalMs ?? 1500
  const timeout = opts?.timeoutMs ?? 10 * 60 * 1000
  const deadline = Date.now() + timeout
  // 首次立即查询，避免无谓等待
  while (true) {
    const { data } = await api.get(`/tasks/${taskId}`)
    if (data.status === 'success' || data.status === 'failed') {
      return data
    }
    if (Date.now() >= deadline) {
      throw new Error('任务轮询超时，请稍后在采集/聚合状态中确认结果')
    }
    await new Promise((r) => setTimeout(r, interval))
  }
}

