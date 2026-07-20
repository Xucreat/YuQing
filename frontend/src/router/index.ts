import KeywordsPage from '@/views/Keywords.vue'
import SourcesPage from '@/views/Sources.vue'
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
      path: '/keywords',
      name: 'keywords',
      component: KeywordsPage,
      meta: { requiresAuth: true },
    },
    {
      path: '/sources',
      name: 'sources',
      component: SourcesPage,
      meta: { requiresAuth: true },
    },
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

