<template>
  <div class="app-shell">
    <!-- Light sidebar -->
    <aside class="sidebar" :class="{ collapsed: sidebarIsCollapsed }">
      <div class="brand">
        <div class="brand-logo">YQ</div>
        <div class="brand-name">
          舆情监测研判平台
        </div>
        <button
          class="sidebar-toggle"
          type="button"
          :aria-label="sidebarCollapsed ? '展开导航栏' : '收起导航栏'"
          :title="sidebarCollapsed ? '展开导航栏' : '收起导航栏'"
          @click="toggleSidebar"
        >{{ sidebarCollapsed ? '›' : '‹' }}</button>
      </div>

      <nav class="nav">
        <template v-for="item in menuItems" :key="item.separator ? 'separator' : item.to">
          <div v-if="item.separator" class="nav-sep"></div>
          <router-link
            v-else-if="item.visible !== false"
            :to="item.to || '/dashboard'"
            class="nav-item"
            :class="{ active: activeMenu === item.to, 'nav-item--screen': item.screen }"
            :title="item.label"
          >
            <span class="ico">{{ item.icon }}</span><span>{{ item.label }}</span>
          </router-link>
        </template>
      </nav>

      <div class="nav-spacer"></div>

      <div
        class="nav-user"
        :class="{ 'is-collapsed': sidebarIsCollapsed }"
        @click="handleNavUserClick"
      >
        <button
          class="avatar"
          type="button"
          :title="sidebarIsCollapsed ? '展开用户信息和导航' : undefined"
          :aria-label="sidebarIsCollapsed ? '展开用户信息和导航' : '当前用户'"
          @click.stop="handleNavUserClick"
        >{{ (authStore.username || 'A')[0].toUpperCase() }}</button>
        <div class="u-meta">
          <div class="u-name">{{ authStore.username || 'admin' }}</div>
          <div class="u-role">{{ roleLabel }}</div>
        </div>
        <div class="nav-bell-wrap">
          <button class="nav-bell" :class="{ active: messageRedDot }" title="消息提醒" @click.stop="toggleMessages">
            <span class="bell-ico">🔔</span>
            <span v-if="messageRedDot" class="bell-dot"></span>
          </button>
          <div v-if="menuVisible" class="msg-menu" @click.stop>
            <div class="msg-menu-item" :class="{ has: unreadCount > 0 }" @click="goAlerts">
              <span class="mm-ico">⚠️</span>
              <span class="mm-label">预警记录</span>
              <span v-if="unreadCount > 0" class="mm-count">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
            </div>
            <div class="msg-menu-item" :class="{ has: bochaPendingCount > 0 }" @click="goBocha">
              <span class="mm-ico">🤖</span>
              <span class="mm-label">AI线索审核</span>
              <span v-if="bochaPendingCount > 0" class="mm-count">{{ bochaPendingCount > 99 ? '99+' : bochaPendingCount }}</span>
            </div>
          </div>
        </div>
        <button class="u-out" title="退出登录" @click.stop="handleLogout">↩</button>
      </div>
    </aside>

    <!-- Main content -->
    <main class="main" :class="{ 'main--collapsed': sidebarIsCollapsed }">
      <header class="topbar">
        <div class="topbar-heading">
          <button
            class="mobile-menu-toggle"
            type="button"
            aria-label="打开导航菜单"
            title="打开导航菜单"
            @click="mobileNavOpen = true"
          >
            <span aria-hidden="true">☰</span>
            <span>菜单</span>
          </button>
          <div class="topbar-copy">
            <h1 class="h-page-title">{{ pageTitle }}</h1>
            <p class="h-page-sub">{{ pageSub }}</p>
          </div>
        </div>
        <div class="actions">
          <CollectMenu />
        </div>
      </header>

      <router-view />
    </main>

    <transition name="mobile-nav">
      <div v-if="mobileNavOpen" class="mobile-nav-layer" @click.self="closeMobileNav">
        <aside class="mobile-nav-drawer" aria-label="移动端导航">
          <div class="mobile-nav-header">
            <div class="brand-logo">YQ</div>
            <strong>舆情监测研判平台</strong>
            <button class="mobile-nav-close" type="button" aria-label="关闭导航菜单" title="关闭导航菜单" @click="closeMobileNav">×</button>
          </div>
          <nav class="nav">
            <template v-for="item in menuItems" :key="item.separator ? 'mobile-separator' : `mobile-${item.to}`">
              <div v-if="item.separator" class="nav-sep"></div>
              <router-link
                v-else-if="item.visible !== false"
                :to="item.to || '/dashboard'"
                class="nav-item"
                :class="{ active: activeMenu === item.to, 'nav-item--screen': item.screen }"
                :title="item.label"
                @click="closeMobileNav"
              >
                <span class="ico">{{ item.icon }}</span><span>{{ item.label }}</span>
              </router-link>
            </template>
          </nav>
          <div class="nav-user mobile-nav-user">
            <div class="avatar">{{ (authStore.username || 'A')[0].toUpperCase() }}</div>
            <div class="u-meta">
              <div class="u-name">{{ authStore.username || 'admin' }}</div>
              <div class="u-role">{{ roleLabel }}</div>
            </div>
            <div class="nav-bell-wrap">
              <button class="nav-bell" :class="{ active: messageRedDot }" title="消息提醒" @click.stop="toggleMessages">
                <span class="bell-ico">🔔</span>
                <span v-if="messageRedDot" class="bell-dot"></span>
              </button>
              <div v-if="menuVisible" class="msg-menu" @click.stop>
                <div class="msg-menu-item" :class="{ has: unreadCount > 0 }" @click="goAlerts">
                  <span class="mm-ico">⚠️</span>
                  <span class="mm-label">预警记录</span>
                  <span v-if="unreadCount > 0" class="mm-count">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
                </div>
                <div class="msg-menu-item" :class="{ has: bochaPendingCount > 0 }" @click="goBocha">
                  <span class="mm-ico">🤖</span>
                  <span class="mm-label">AI线索审核</span>
                  <span v-if="bochaPendingCount > 0" class="mm-count">{{ bochaPendingCount > 99 ? '99+' : bochaPendingCount }}</span>
                </div>
              </div>
            </div>
            <button class="u-out" title="退出登录" @click.stop="handleLogout">↩</button>
          </div>
        </aside>
      </div>
    </transition>

    <AlertToastHost />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores'
import { usePermission } from '@/composables/usePermission'
import { useAlertNotifier } from '@/composables/useAlertNotifier'
import AlertToastHost from '@/components/AlertToastHost.vue'
import CollectMenu from '@/components/CollectMenu.vue'
import api from '@/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { role, isSuperuser, hasPermission, hasAnyModulePermission } = usePermission()
const { redDot, unreadCount, openNotifications, start } = useAlertNotifier()
const bochaPendingCount = ref(0)
let bochaPendingTimer: number | null = null
const sidebarCollapsed = ref(localStorage.getItem('yq.sidebar.collapsed') === '1')
const mobileNavOpen = ref(false)
const compactViewport = ref(false)
const compactSidebarExpanded = ref(false)
let compactMediaQuery: MediaQueryList | null = null

const sidebarIsCollapsed = computed(() =>
  compactViewport.value ? !compactSidebarExpanded.value : sidebarCollapsed.value,
)

function toggleSidebar() {
  if (compactViewport.value) {
    compactSidebarExpanded.value = !compactSidebarExpanded.value
    return
  }
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('yq.sidebar.collapsed', sidebarCollapsed.value ? '1' : '0')
}

function handleNavUserClick() {
  if (!sidebarIsCollapsed.value) return
  if (compactViewport.value) {
    compactSidebarExpanded.value = true
    return
  }
  sidebarCollapsed.value = false
  localStorage.setItem('yq.sidebar.collapsed', '0')
}

function syncCompactViewport(event: MediaQueryList | MediaQueryListEvent) {
  compactViewport.value = event.matches
  if (!event.matches) compactSidebarExpanded.value = false
}

const messageRedDot = computed(() => redDot.value || bochaPendingCount.value > 0)
const roleLabel = computed(() => {
  const map: Record<string, string> = { admin: '管理员', analyst: '分析员', viewer: '观察员' }
  return map[role.value] || role.value || '未登录'
})
const hasSystemPerm = computed(() =>
  hasAnyModulePermission(['users', 'roles', 'login_logs', 'audit_logs']),
)
// RBAC-1：菜单可见性与路由 meta.permission / 后端权限保持一致，
// 避免用户点进去后满屏 403（观察员无 ai:search、无 keywords:read）。
const hasAiSearchPerm = computed(() => hasPermission('ai:search'))
// 数据管理下含「关键词管理」(keywords:read) 与超管专属的数据源/采集日志/AI线索审核
const hasDataPerm = computed(() => hasAnyModulePermission(['keywords', 'sources', 'collectors']))

type MenuEntry = {
  to?: string
  label?: string
  icon?: string
  screen?: boolean
  separator?: boolean
  visible?: boolean
}

const menuItems = computed<MenuEntry[]>(() => [
  { to: '/dashboard', label: '驾驶舱', icon: '▤' },
  { to: '/opinions', label: '舆情列表', icon: '☰' },
  { to: '/foreign', label: '外网舆情', icon: '◎', visible: hasDataPerm.value },
  { to: '/ai-search', label: 'AI检索', icon: 'AI', visible: hasAiSearchPerm.value },
  { to: '/events', label: '事件中心', icon: '⚠' },
  { to: '/alerts', label: '预警中心', icon: '🔔' },
  { to: '/propagation', label: '传播溯源', icon: '📡' },
  { to: '/command-screen', label: '指挥大屏', icon: '▦', screen: true },
  { separator: true },
  { to: '/data', label: '数据管理', icon: '🗂', visible: hasDataPerm.value },
  { to: '/system', label: '系统管理', icon: '⚙', visible: hasSystemPerm.value },
])

function closeMobileNav() {
  mobileNavOpen.value = false
}

watch(() => route.path, closeMobileNav)

const activeMenu = computed(() => {
  if (route.path.startsWith('/ai-search')) return '/ai-search'
  if (route.path.startsWith('/opinion')) return '/opinions'
  if (route.path.startsWith('/event')) return '/events'
  if (route.path.startsWith('/system')) return '/system'
  return route.path
})

const pageTitle = computed(() => {
  const m: Record<string, string> = {
    '/dashboard': '驾驶舱',
    '/opinions': '舆情列表',
    '/foreign': '外网舆情',
    '/ai-search': 'AI检索',
    '/events': '事件中心',
    '/alerts': '预警中心',
    '/data': '数据管理',
    '/users': '用户管理',
    '/roles': '角色权限',
    '/login-logs': '登录日志',
    '/operation-logs': '操作日志',
    '/propagation': '传播溯源',
    '/system': '系统管理',
    '/system/users': '用户管理',
    '/system/roles': '角色权限',
    '/system/login-logs': '登录日志',
    '/system/operation-logs': '操作日志',
    '/command-screen': '指挥大屏',
  }
  if (route.path.startsWith('/opinion/')) return '舆情详情'
  if (route.path.startsWith('/event/')) return '事件详情'
  if (route.path.startsWith('/ai-search/')) return 'AI检索'
  return m[route.path] || '驾驶舱'
})

const pageSub = computed(() => {
  const m: Record<string, string> = {
    '/dashboard': '互联网舆情监测总览',
    '/opinions': '查看和管理所有舆情信息',
    '/foreign': '独立外网采集、去重、存储与展示',
    '/ai-search': '主动搜索外部舆情线索',
    '/events': '跟踪和管理舆情事件',
    '/alerts': '预警规则配置与预警记录',
    '/data': '管理舆情监测关键词与采集数据源',
    '/users': '管理系统用户与角色权限',
    '/roles': '管理系统角色与权限分配',
    '/login-logs': '查看用户登录与注销记录',
    '/operation-logs': '查看系统操作审计记录',
    '/propagation': '基于多源舆情数据的传播演化分析',
    '/system': '用户、角色权限与系统审计日志',
    '/system/users': '管理系统用户与角色权限',
    '/system/roles': '管理系统角色与权限分配',
    '/system/login-logs': '查看用户登录与注销记录',
    '/system/operation-logs': '查看系统操作审计记录',
    '/command-screen': '全域舆情实时态势驾驶舱',
  }
  if (route.path.startsWith('/opinion/')) return '舆情详细信息与AI分析'
  if (route.path.startsWith('/event/')) return '事件详情与关联舆情'
  if (route.path.startsWith('/ai-search/')) return '主动搜索外部舆情线索'
  return m[route.path] || ''
})

function handleLogout() {
  ElMessageBox.confirm('确认退出登录？', '提示', {
    confirmButtonText: '退出', cancelButtonText: '取消', type: 'warning',
  }).then(() => { authStore.logout(); router.push('/login') }).catch(() => {})
}

async function refreshBochaPendingCount() {
  if (!localStorage.getItem('token') || !isSuperuser.value) {
    bochaPendingCount.value = 0
    return
  }
  try {
    const { data } = await api.get<{ total: number }>('/admin/bocha/leads', {
      params: { status: 'new', page: 1, size: 1 },
    })
    bochaPendingCount.value = data.total || 0
  } catch {
    bochaPendingCount.value = 0
  }
}

const menuVisible = ref(false)
function toggleMessages() {
  menuVisible.value = !menuVisible.value
}
function goAlerts() {
  menuVisible.value = false
  openNotifications()
}
function goBocha() {
  menuVisible.value = false
  router.push({ path: '/data', query: { tab: 'bocha-leads' } })
}
function closeMenuOutside(e: MouseEvent) {
  if (menuVisible.value && !(e.target as HTMLElement).closest('.nav-bell-wrap')) {
    menuVisible.value = false
  }
}
function onKeyEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') menuVisible.value = false
}

function handleBochaLeadsRefresh() {
  refreshBochaPendingCount()
}

// 启动预警通知轮询（单例，仅首次挂载生效）。
onMounted(() => {
  compactMediaQuery = window.matchMedia('(max-width: 1100px) and (min-width: 601px)')
  syncCompactViewport(compactMediaQuery)
  compactMediaQuery.addEventListener?.('change', syncCompactViewport)
  start()
  refreshBochaPendingCount()
  bochaPendingTimer = window.setInterval(refreshBochaPendingCount, 20_000)
  window.addEventListener('bocha-leads-refresh', handleBochaLeadsRefresh)
  document.addEventListener('click', closeMenuOutside)
  window.addEventListener('keydown', onKeyEsc)
})

onUnmounted(() => {
  compactMediaQuery?.removeEventListener?.('change', syncCompactViewport)
  compactMediaQuery = null
  if (bochaPendingTimer) {
    window.clearInterval(bochaPendingTimer)
    bochaPendingTimer = null
  }
  window.removeEventListener('bocha-leads-refresh', handleBochaLeadsRefresh)
  document.removeEventListener('click', closeMenuOutside)
  window.removeEventListener('keydown', onKeyEsc)
})
</script>

<style scoped>
/* ---- Shell ---- */
.app-shell {
  display: flex;
  min-height: 100vh;
  background: #f5f5f7;
}

/* ---- Sidebar ---- */
.sidebar {
  width: 246px;
  box-sizing: border-box;
  flex-shrink: 0;
  padding: 26px 16px;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  overflow-y: auto;
  z-index: 100;
  display: flex;
  flex-direction: column;
  background: #f5f5f7;
  border-right: 1px solid #e8e8ed;
  transition: width 0.2s ease, padding 0.2s ease;
}
.sidebar.collapsed {
  width: 78px;
  padding-left: 10px;
  padding-right: 10px;
}
.sidebar-toggle {
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  margin-left: auto;
  border: 1px solid #d2d2d7;
  border-radius: 8px;
  background: #fff;
  color: #6e6e73;
  font-size: 22px;
  line-height: 20px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}
.sidebar-toggle:hover {
  background: #e8f1fd;
  color: #0071e3;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px 22px;
}
.brand-logo {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  flex-shrink: 0;
  background: linear-gradient(135deg, #0071e3, #42a5f5);
  color: #fff;
  font-weight: 700;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand-name {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.25;
  letter-spacing: -0.01em;
  color: #1d1d1f;
}
.brand-name small {
  display: block;
  font-size: 11.5px;
  color: #86868b;
  font-weight: 400;
}
.sidebar.collapsed .brand {
  justify-content: flex-start;
  gap: 0;
  padding-top: 38px;
  padding-left: 0;
  padding-right: 0;
}
.sidebar.collapsed .brand-name,
.sidebar.collapsed .nav-item > span:not(.ico),
.sidebar.collapsed .u-meta {
  display: none;
}
.sidebar.collapsed .sidebar-toggle {
  position: absolute;
  top: 18px;
  right: 8px;
  margin: 0;
}

/* ---- Nav ---- */
.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  border-radius: 12px;
  color: #6e6e73;
  font-size: 14.5px;
  font-weight: 500;
  text-decoration: none;
  transition: background-color 0.15s ease, color 0.15s ease;
}
.sidebar.collapsed .nav-item {
  justify-content: center;
  gap: 0;
  padding-left: 8px;
  padding-right: 8px;
}
.nav-item:hover {
  background: #e8e8ed;
  color: #1d1d1f;
}
.nav-item.active {
  background: #e9e9ec;
  color: #1d1d1f;
  font-weight: 600;
}
.nav-item .ico {
  width: 20px;
  text-align: center;
  font-size: 16px;
}
/* 指挥大屏：独立「全屏驾驶舱」模式入口，视觉上与常规页面区分 */
.nav-item--screen {
  color: #0071e3;
}
.nav-item--screen .ico {
  color: #0071e3;
}
.nav-item--screen:hover {
  background: #e8f1fd;
  color: #0071e3;
}
.nav-item--screen.active {
  background: #e8f1fd;
  color: #0071e3;
}
.nav-spacer {
  flex: 1;
}
/* 系统管理分组分隔线 */
.nav-sep {
  height: 1px;
  margin: 8px 14px;
  background: #e8e8ed;
}
.sidebar.collapsed .nav-sep {
  margin-left: 8px;
  margin-right: 8px;
}

/* ---- User ---- */
.nav-user {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 4px 14px rgba(0,0,0,0.05);
  display: flex;
  align-items: center;
  gap: 10px;
}
.nav-user.is-collapsed { cursor: pointer; }
.sidebar.collapsed .nav-user {
  justify-content: center;
  flex-wrap: wrap;
  gap: 4px;
  padding-left: 6px;
  padding-right: 6px;
}
.sidebar.collapsed .nav-bell-wrap,
.sidebar.collapsed .u-out {
  margin-left: 0;
}
.avatar {
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: #e8f1fd;
  color: #0071e3;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  font-family: inherit;
  cursor: pointer;
}
.u-name { font-size: 13.5px; font-weight: 600; color: #1d1d1f; }
.u-role { font-size: 11.5px; color: #86868b; }
.u-out {
  margin-left: auto;
  border: none;
  background: transparent;
  color: #86868b;
  font-size: 15px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 8px;
}
.u-out:hover {
  background: #e8e8ed;
  color: #1d1d1f;
}

/* ---- 预警通知铃铛 + 红点 ---- */
.nav-bell {
  position: relative;
  border: none;
  background: transparent;
  color: #86868b;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  padding: 6px 7px;
  border-radius: 10px;
  transition: background-color 0.15s ease, color 0.15s ease;
}
.nav-bell:hover { background: #e8e8ed; color: #1d1d1f; }
.nav-bell.active { color: #1d1d1f; }
.bell-ico { display: block; }
.bell-dot {
  position: absolute;
  top: 1px;
  right: 1px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #ff3b30;
  box-shadow: 0 0 0 2px #fff;
  animation: bell-pop 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes bell-pop {
  from { transform: scale(0.4); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

/* ---- 铃铛上拉消息菜单 ---- */
.nav-bell-wrap { position: relative; margin-left: auto; }
.msg-menu {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 50%;
  transform: translateX(-50%);
  width: 208px;
  background: #fff;
  border: 1px solid #e8e8ed;
  border-radius: 14px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.12);
  padding: 6px;
  z-index: 200;
}
.msg-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  color: #6e6e73;
  font-size: 14px;
  transition: background-color 0.15s ease, color 0.15s ease;
}
.msg-menu-item:hover { background: #f0f0f3; color: #1d1d1f; }
.msg-menu-item.has { color: #1d1d1f; font-weight: 500; }
.sidebar.collapsed .msg-menu {
  position: fixed;
  left: 90px;
  bottom: 24px;
  z-index: 300;
  transform: none;
}
.mm-ico { font-size: 15px; }
.mm-label { flex: 1; }
.mm-count {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #ff3b30;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
}

/* ---- Main ---- */
.main {
  flex: 1;
  min-width: 0;
  margin-left: 246px;
  margin-right: 0;
  margin-top: 0;
  margin-bottom: 0;
  padding: 34px 44px 60px;
  transition: margin-left 0.2s ease;
}
.main--collapsed {
  margin-left: 78px;
}

/* ---- Topbar ---- */
.topbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 26px;
}
.topbar-heading {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}
.topbar-copy { min-width: 0; }
.h-page-title {
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0;
  color: #1d1d1f;
}
.h-page-sub {
  font-size: 14px;
  color: #6e6e73;
  margin: 4px 0 0;
}
.actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
.mobile-menu-toggle,
.mobile-nav-layer {
  display: none;
}

/* ---- Buttons ---- */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
  border-radius: 980px;
  padding: 10px 20px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.18s ease, transform 0.12s ease, opacity 0.18s ease;
  user-select: none;
}
.btn:active { transform: scale(0.98); }
.btn-primary {
  background: #0071e3;
  color: #fff;
}
.btn-primary:hover { background: #0077ed; }
.btn-primary:disabled { opacity: 0.55; cursor: default; }

/* ---- Responsive ---- */
/*
 * Keep a compact navigation rail available on small desktop/tablet widths.
 * Hiding the fixed sidebar at 820px made a resized browser lose its primary
 * navigation even though the page itself was still usable as a desktop view.
 */
@media (max-width: 1100px) and (min-width: 601px) {
  .sidebar.collapsed {
    width: 78px;
    padding-left: 10px;
    padding-right: 10px;
  }
  .sidebar.collapsed .brand {
    justify-content: flex-start;
    gap: 0;
    padding-top: 38px;
    padding-left: 0;
    padding-right: 0;
  }
  .sidebar.collapsed .brand-name,
  .sidebar.collapsed .nav-item > span:not(.ico),
  .sidebar.collapsed .u-meta {
    display: none;
  }
  .sidebar.collapsed .sidebar-toggle {
    display: none;
  }
  .sidebar.collapsed .nav-item {
    justify-content: center;
    gap: 0;
    padding-left: 8px;
    padding-right: 8px;
  }
  .sidebar.collapsed .nav-sep { margin-left: 8px; margin-right: 8px; }
  .sidebar.collapsed .nav-user {
    justify-content: center;
    flex-wrap: wrap;
    gap: 4px;
    padding-left: 6px;
    padding-right: 6px;
  }
  .main--collapsed {
    margin-left: 78px;
    padding: 28px 28px 48px;
  }
  .main:not(.main--collapsed) { padding: 28px 28px 48px; }
  .h-page-title { font-size: 24px; }
}

@media (max-width: 600px) {
  .sidebar { display: none; }
  .main { margin-left: 0; padding: 24px 18px 48px; }
  .topbar {
    align-items: flex-start;
    flex-wrap: wrap;
    margin-bottom: 20px;
  }
  .topbar-heading { flex: 1 1 auto; }
  .actions { flex: 0 0 auto; }
  .mobile-menu-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    flex: 0 0 auto;
    min-height: 36px;
    padding: 7px 11px;
    border: 1px solid #d2d2d7;
    border-radius: 10px;
    background: #fff;
    color: #1d1d1f;
    font: inherit;
    font-size: 13px;
    cursor: pointer;
  }
  .mobile-nav-layer {
    position: fixed;
    inset: 0;
    z-index: 500;
    display: block;
    background: rgba(29, 29, 31, 0.32);
  }
  .mobile-nav-drawer {
    width: min(300px, 84vw);
    height: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 20px 14px 24px;
    background: #f5f5f7;
    box-shadow: 12px 0 32px rgba(0, 0, 0, 0.16);
  }
  .mobile-nav-header {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 40px;
    margin-bottom: 20px;
  }
  .mobile-nav-header .brand-logo { width: 34px; height: 34px; font-size: 16px; }
  .mobile-nav-header strong { flex: 1; min-width: 0; font-size: 14px; line-height: 1.35; }
  .mobile-nav-close {
    width: 32px;
    height: 32px;
    flex: 0 0 32px;
    border: 1px solid #d2d2d7;
    border-radius: 9px;
    background: #fff;
    color: #6e6e73;
    font-size: 22px;
    line-height: 1;
    cursor: pointer;
  }
  .mobile-nav-drawer .nav { flex: 1 1 auto; gap: 4px; }
  .mobile-nav-drawer .nav-item { padding: 12px 14px; }
  .mobile-nav-user {
    flex: 0 0 auto;
    margin-top: 20px;
  }
}
.mobile-nav-enter-active,
.mobile-nav-leave-active { transition: opacity 0.18s ease; }
.mobile-nav-enter-active .mobile-nav-drawer,
.mobile-nav-leave-active .mobile-nav-drawer { transition: transform 0.2s ease; }
.mobile-nav-enter-from,
.mobile-nav-leave-to { opacity: 0; }
.mobile-nav-enter-from .mobile-nav-drawer,
.mobile-nav-leave-to .mobile-nav-drawer { transform: translateX(-100%); }
</style>
