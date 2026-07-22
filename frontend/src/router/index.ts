import DataManagePage from '@/views/DataManage.vue'
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/opinions',
      name: 'opinions',
      component: () => import('@/views/Opinions.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/opinion/:id',
      name: 'opinion-detail',
      component: () => import('@/views/OpinionDetail.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/events',
      name: 'events',
      component: () => import('@/views/Events.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/event/:id',
      name: 'event-detail',
      component: () => import('@/views/EventDetail.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/alerts',
      name: 'alerts',
      component: () => import('@/views/Alerts.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/data',
      name: 'data',
      component: DataManagePage,
      meta: { requiresAuth: true },
    },
    // 旧路由重定向到数据管理聚合页的对应子页，保留已有书签
    { path: '/keywords', redirect: { name: 'data', query: { tab: 'keywords' } } },
    { path: '/sources', redirect: { name: 'data', query: { tab: 'sources' } } },
    {
      path: '/users',
      name: 'users',
      component: () => import('@/views/Users.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/propagation',
      name: 'propagation',
      component: () => import('@/views/Propagation.vue'),
      meta: { requiresAuth: true },
    },
    {
      // 指挥大屏：独立全屏布局（不套 AppLayout 侧边栏），复用现有认证机制
      path: '/command-screen',
      name: 'command-screen',
      component: () => import('@/views/CommandScreen.vue'),
      meta: { requiresAuth: true, layout: 'fullscreen' },
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token') || ''
  const isLoggedIn = !!token
  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !isLoggedIn) return { path: '/login' }
  if (to.path === '/login' && isLoggedIn) return { path: '/dashboard' }
  return true
})

export default router

