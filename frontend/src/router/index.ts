import DataManagePage from '@/views/DataManage.vue'
import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { usePermission } from '@/composables/usePermission'

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
    // AI 检索：需 ai:search（后端 /bocha/*、/anspire/* 已同步收敛为 ai:search）
    {
      path: '/ai-search',
      name: 'ai-search',
      component: () => import('@/views/AiSearch.vue'),
      meta: { requiresAuth: true, permission: 'ai:search' },
    },
    {
      path: '/ai-search/web',
      name: 'ai-search-web',
      component: () => import('@/views/AiSearch.vue'),
      meta: { requiresAuth: true, permission: 'ai:search' },
    },
    {
      path: '/ai-search/ai',
      name: 'ai-search-ai',
      component: () => import('@/views/AiSearch.vue'),
      meta: { requiresAuth: true, permission: 'ai:search' },
    },
    {
      path: '/ai-search/anspire',
      name: 'ai-search-anspire',
      component: () => import('@/views/AiSearch.vue'),
      meta: { requiresAuth: true, permission: 'ai:search' },
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
      meta: { requiresAuth: true, permission: 'events:read' },
    },
    {
      path: '/event/:id',
      name: 'event-detail',
      component: () => import('@/views/EventDetail.vue'),
      meta: { requiresAuth: true, permission: 'events:read' },
    },
    {
      path: '/alerts',
      name: 'alerts',
      component: () => import('@/views/Alerts.vue'),
      meta: { requiresAuth: true, permission: 'alerts:read' },
    },
    // 数据管理聚合页：默认子页为「关键词管理」，故整页门槛取 keywords:read。
    // 超管/持 keywords:read 的角色可进；观察者(viewer)无该权限 → 守卫提示并回退首页。
    // 页内「数据源/采集日志/AI线索审核」仍受 isSuperuser 控制，行为不变。
    {
      path: '/data',
      name: 'data',
      component: DataManagePage,
      meta: { requiresAuth: true, permission: 'keywords:read' },
    },
    // 旧路由重定向到数据管理聚合页的对应子页，保留已有书签
    { path: '/keywords', redirect: { name: 'data', query: { tab: 'keywords' } } },
    { path: '/sources', redirect: { name: 'data', query: { tab: 'sources' } } },
    // 系统管理：将用户管理/角色权限/登录日志/操作日志整合到一个页面，
    // 内部以横向导航（SystemAdmin.vue 的 el-tabs）切换四个子路由。其余功能不变。
    {
      path: '/system',
      name: 'system',
      component: () => import('@/views/SystemAdmin.vue'),
      meta: { requiresAuth: true },
      // 进入系统时按权限分流到首个可见子页；无系统权限则回退首页。
      redirect: (to) => {
        const { hasPermission } = usePermission()
        if (hasPermission('users:read')) return '/system/users'
        if (hasPermission('roles:read')) return '/system/roles'
        if (hasPermission('login_logs:read')) return '/system/login-logs'
        if (hasPermission('audit_logs:read')) return '/system/operation-logs'
        return { path: '/dashboard' }
      },
      children: [
        {
          path: 'users',
          name: 'users',
          component: () => import('@/views/Users.vue'),
          meta: { requiresAuth: true, permission: 'users:read' },
        },
        {
          path: 'roles',
          name: 'roles',
          component: () => import('@/views/Roles.vue'),
          meta: { requiresAuth: true, permission: 'roles:read' },
        },
        {
          path: 'login-logs',
          name: 'login-logs',
          component: () => import('@/views/LoginLogs.vue'),
          meta: { requiresAuth: true, permission: 'login_logs:read' },
        },
        {
          path: 'operation-logs',
          name: 'operation-logs',
          component: () => import('@/views/OperationLogs.vue'),
          meta: { requiresAuth: true, permission: 'audit_logs:read' },
        },
      ],
    },
    // 旧路由重定向到系统管理聚合页的对应子页，保留已有书签
    { path: '/users', redirect: { name: 'users' } },
    { path: '/roles', redirect: { name: 'roles' } },
    { path: '/login-logs', redirect: { name: 'login-logs' } },
    { path: '/operation-logs', redirect: { name: 'operation-logs' } },
    {
      path: '/propagation',
      name: 'propagation',
      component: () => import('@/views/Propagation.vue'),
      meta: { requiresAuth: true, permission: 'propagation:read' },
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

  // 路由级权限（前端体验层，非安全边界）：已登录但无权限 → 回退首页并提示。
  // RBAC 收口后已补齐：events / event 详情 → events:read；data（关键词管理）→ keywords:read；
  // ai-search 及子路由 → ai:search；alerts → alerts:read；propagation → propagation:read。
  // 报告能力无独立路由（Dashboard 内导出抽屉），由 reports:export / reports:manage 控制按钮。
  // 提示文案与全局 403 拦截保持一致。
  if (isLoggedIn && to.meta.permission) {
    const { canAccessRoute } = usePermission()
    if (!canAccessRoute(to.meta as Record<string, any>)) {
      ElMessage.warning('权限不足，请联系管理员')
      return { path: '/dashboard' }
    }
  }
  return true
})

export default router

