<template>
  <div class="app-shell">
    <!-- Light sidebar -->
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-logo">YQ</div>
        <div class="brand-name">
          舆情监测研判平台
          <small>大厂县公安</small>
        </div>
      </div>

      <nav class="nav">
        <router-link to="/dashboard" class="nav-item" :class="{ active: activeMenu === '/dashboard' }">
          <span class="ico">▤</span><span>驾驶舱</span>
        </router-link>
        <router-link to="/opinions" class="nav-item" :class="{ active: activeMenu === '/opinions' }">
          <span class="ico">☰</span><span>舆情列表</span>
        </router-link>
        <router-link to="/events" class="nav-item" :class="{ active: activeMenu === '/events' }">
          <span class="ico">⚠</span><span>事件中心</span>
        </router-link>
        <router-link to="/alerts" class="nav-item" :class="{ active: activeMenu === '/alerts' }">
          <span class="ico">🔔</span><span>预警中心</span>
        </router-link>
        <router-link to="/keywords" class="nav-item" :class="{ active: activeMenu === '/keywords' }">
          <span class="ico">☷</span><span>关键词管理</span>
        </router-link>
        <router-link to="/sources" class="nav-item" :class="{ active: activeMenu === '/sources' }">
          <span class="ico">✴</span><span>数据源管理</span>
        </router-link>
        <router-link to="/propagation" class="nav-item" :class="{ active: activeMenu === '/propagation' }">
          <span class="ico">📡</span><span>传播溯源</span>
        </router-link>
      </nav>

      <div class="nav-spacer"></div>

      <div class="nav-user">
        <div class="avatar">{{ (authStore.username || 'A')[0].toUpperCase() }}</div>
        <div>
          <div class="u-name">{{ authStore.username || 'admin' }}</div>
          <div class="u-role">{{ roleLabel }}</div>
        </div>
        <button class="u-out" title="退出登录" @click="handleLogout">↩</button>
      </div>
    </aside>

    <!-- Main content -->
    <main class="main">
      <header class="topbar">
        <div>
          <h1 class="h-page-title">{{ pageTitle }}</h1>
          <p class="h-page-sub">{{ pageSub }}</p>
        </div>
        <div class="actions">
          <button class="btn btn-primary" :disabled="collecting" @click="handleCollect">
            {{ collecting ? '采集中...' : '采集数据' }}
          </button>
        </div>
      </header>

      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores'
import { usePermission } from '@/composables/usePermission'
import api from '@/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { role } = usePermission()
const isAdmin = computed(() => role.value === 'admin')
const roleLabel = computed(() => {
  const map: Record<string, string> = { admin: '管理员', analyst: '分析员', viewer: '观察员' }
  return map[role.value] || role.value || '未登录'
})
const collecting = ref(false)

const activeMenu = computed(() => {
  if (route.path.startsWith('/opinion')) return '/opinions'
  if (route.path.startsWith('/event')) return '/events'
  return route.path
})

const pageTitle = computed(() => {
  const m: Record<string, string> = {
    '/dashboard': '驾驶舱',
    '/opinions': '舆情列表',
    '/events': '事件中心',
    '/alerts': '预警中心',
    '/keywords': '关键词管理',
    '/sources': '数据源管理',
    '/users': '用户管理',
    '/propagation': '传播溯源',
  }
  if (route.path.startsWith('/opinion/')) return '舆情详情'
  if (route.path.startsWith('/event/')) return '事件详情'
  return m[route.path] || '驾驶舱'
})

const pageSub = computed(() => {
  const m: Record<string, string> = {
    '/dashboard': '互联网舆情监测总览',
    '/opinions': '查看和管理所有舆情信息',
    '/events': '跟踪和管理舆情事件',
    '/alerts': '预警规则配置与预警记录',
    '/keywords': '管理舆情监测关键词与命中规则',
    '/sources': '配置舆情采集的数据来源',
    '/users': '管理系统用户与角色权限',
    '/propagation': '溯源分析舆情传播路径',
  }
  if (route.path.startsWith('/opinion/')) return '舆情详细信息与AI分析'
  if (route.path.startsWith('/event/')) return '事件详情与关联舆情'
  return m[route.path] || ''
})

async function handleCollect() {
  if (collecting.value) return
  collecting.value = true
  try {
    const { data } = await api.post('/collector/run');
    // 安全读取：后端未返回时回退为 0，避免 undefined 拼接到提示文案。
    const fetchedRaw = data.fetched_raw ?? 0;
    const created = data.created ?? 0;
    const analyzed = data.analyzed ?? 0;
    if (fetchedRaw === 0) {
      ElMessage.warning('采集完成：未抓取到新内容，数据源暂无可读数据');
    } else if (created === 0) {
      ElMessage.warning('采集完成：抓取 ' + fetchedRaw + ' 条，均为已存在数据');
    } else {
      ElMessage.success('采集完成：新增 ' + created + ' 条，分析 ' + analyzed + ' 条');
    }
    // trigger a page reload for active view
    window.dispatchEvent(new CustomEvent('data-refresh'))
    // Auto-trigger alert evaluation after collection
    try {
      const evalRes = await api.post('/alerts/evaluate')
      if (evalRes.data.alerts_created > 0) {
        ElMessage.success('预警评估完成：生成 ' + evalRes.data.alerts_created + ' 条新预警')
      }
    } catch (_) { /* evaluation failure should not block collection */ }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.response?.data?.message || '采集失败')
  } finally {
    collecting.value = false
  }
}

function handleLogout() {
  ElMessageBox.confirm('确认退出登录？', '提示', {
    confirmButtonText: '退出', cancelButtonText: '取消', type: 'warning',
  }).then(() => { authStore.logout(); router.push('/login') }).catch(() => {})
}
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
  flex-shrink: 0;
  padding: 26px 16px;
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f7;
  border-right: 1px solid #e8e8ed;
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
.nav-spacer {
  flex: 1;
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
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #e8f1fd;
  color: #0071e3;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
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

/* ---- Main ---- */
.main {
  flex: 1;
  min-width: 0;
  max-width: 1440px;
  margin: 0 auto;
  padding: 34px 44px 60px;
}

/* ---- Topbar ---- */
.topbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 26px;
}
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
@media (max-width: 820px) {
  .sidebar { display: none; }
  .main { padding: 24px 18px 48px; }
}
</style>

