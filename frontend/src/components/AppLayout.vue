<template>
  <el-container class="app-layout">
    <el-aside width="220px" class="app-aside">
      <div class="logo">
        <span class="logo-title">舆情监测研判平台</span>
        <span class="logo-sub">大厂县公安</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="app-menu"
        background-color="#1f2d3d"
        text-color="#c0ccda"
        active-text-color="#ffd04b"
      >
        <el-menu-item index="/dashboard">
          <span class="menu-ico">▤</span><span>驾驶舱</span>
        </el-menu-item>
        <el-menu-item index="/opinions">
          <span class="menu-ico">☰</span><span>舆情列表</span>
        </el-menu-item>
        <el-menu-item index="/events">
          <span class="menu-ico">⚠</span><span>事件中心</span>
        </el-menu-item>
        <el-menu-item index="/alerts">
          <span class="menu-ico">🔔</span><span>预警中心</span>
        </el-menu-item>
        <el-menu-item index="/propagation">
          <span class="menu-ico">📡</span><span>传播溯源</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <span class="header-title">互联网舆情监测研判平台</span>
          <el-button type="primary" size="small" :loading="collecting" @click="handleCollect"
            style="margin-left: 16px;">
            采集数据
          </el-button>
        </div>
        <el-dropdown @command="handleCommand">
          <span class="user-dropdown">
            <span class="user-ico">👤</span>
            <span class="username">{{ authStore.username || 'admin' }}</span>
            <span class="caret">▾</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores'
import api from '@/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const collecting = ref(false)

const activeMenu = computed(() => {
  if (route.path.startsWith('/opinion')) return '/opinions'
  if (route.path.startsWith('/event')) return '/events'
  return route.path
})

async function handleCollect() {
  if (collecting.value) return
  collecting.value = true
  try {
    const { data } = await api.post('/collector/run')
    ElMessage.success(`采集完成：新增 ${data.created} 条，分析 ${data.analyzed} 条`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.response?.data?.message || '采集失败')
  } finally {
    collecting.value = false
  }
}

function handleCommand(command: string) {
  if (command === 'logout') {
    ElMessageBox.confirm('确认退出登录？', '提示', {
      confirmButtonText: '退出', cancelButtonText: '取消', type: 'warning',
    }).then(() => { authStore.logout(); router.push('/login') }).catch(() => {})
  }
}
</script>

<style scoped>
.app-layout { height: 100vh; }
.app-aside { background-color: #1f2d3d; display: flex; flex-direction: column; }
.logo { height: 60px; display: flex; flex-direction: column; justify-content: center; padding-left: 20px; color: #fff; border-bottom: 1px solid #2a3a4d; }
.logo-title { font-size: 16px; font-weight: 600; }
.logo-sub { font-size: 12px; color: #8a9bb0; margin-top: 2px; }
.app-menu { border-right: none; flex: 1; }
.menu-ico { display: inline-block; width: 20px; text-align: center; margin-right: 6px; font-size: 15px; }
.app-header { display: flex; align-items: center; justify-content: space-between; background-color: #fff; border-bottom: 1px solid #e4e7ed; height: 60px; }
.header-left { display: flex; align-items: center; }
.header-title { font-size: 16px; font-weight: 600; color: #303133; }
.user-dropdown { display: flex; align-items: center; gap: 6px; cursor: pointer; color: #606266; outline: none; }
.user-ico { font-size: 15px; }
.username { font-size: 14px; }
.caret { font-size: 12px; color: #909399; }
.app-main { background-color: #f0f2f5; padding: 20px; }
</style>
