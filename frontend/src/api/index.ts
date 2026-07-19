import axios, { type AxiosInstance } from 'axios'

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

export default api
