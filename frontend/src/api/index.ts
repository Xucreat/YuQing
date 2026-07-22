import axios, { type AxiosError, type AxiosInstance } from 'axios'

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

// —— 401 自动跳登录 ——
// 路由守卫只判断 token「是否存在」，不校验有效期；过期 token 仍非空字符串，
// 会导致所有 API 返回 401 而前端静默空屏。这里统一兜底：遇到 401 清掉过期
// token 并跳转登录页，避免用户看到一片空白的大屏。
// - 并发轮询可能同时触发多个 401：用 redirectingToLogin 标志位保证只跳一次；
// - 已在 /login 时不重复跳转，避免循环。
let redirectingToLogin = false
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      const alreadyOnLogin = window.location.pathname === '/login'
      if (!alreadyOnLogin && !redirectingToLogin) {
        redirectingToLogin = true
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export default api

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

