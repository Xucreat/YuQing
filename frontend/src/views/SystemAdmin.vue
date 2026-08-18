<template>
  <div class="sys-admin">
    <Teleport to="#page-nav-target">
    <div class="page-nav">
      <div class="head-left">
        <h1 class="page-title">系统管理</h1>
        <div class="view-tabs">
          <button v-if="canUsers" class="view-tab" :class="{ active: activeTab === 'users' }" @click="onTabChange('users')">用户管理</button>
          <button v-if="canRoles" class="view-tab" :class="{ active: activeTab === 'roles' }" @click="onTabChange('roles')">角色权限</button>
          <button v-if="canLoginLogs" class="view-tab" :class="{ active: activeTab === 'login-logs' }" @click="onTabChange('login-logs')">登录日志</button>
          <button v-if="canOperationLogs" class="view-tab" :class="{ active: activeTab === 'operation-logs' }" @click="onTabChange('operation-logs')">操作日志</button>
        </div>
      </div>
    </div>
    </Teleport>

    <div class="sys-body">
      <router-view v-if="hasAny" />
      <el-empty v-else description="当前账号无系统管理权限" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePermission } from '@/composables/usePermission'

const route = useRoute()
const router = useRouter()
const { hasModulePermission } = usePermission()

const TABS = ['users', 'roles', 'login-logs', 'operation-logs'] as const

const canUsers = computed(() => hasModulePermission('users'))
const canRoles = computed(() => hasModulePermission('roles'))
const canLoginLogs = computed(() => hasModulePermission('login_logs'))
const canOperationLogs = computed(() => hasModulePermission('audit_logs'))
const hasAny = computed(
  () => canUsers.value || canRoles.value || canLoginLogs.value || canOperationLogs.value,
)

const firstPermitted = computed(() => {
  if (canUsers.value) return 'users'
  if (canRoles.value) return 'roles'
  if (canLoginLogs.value) return 'login-logs'
  return 'operation-logs'
})

const activeTab = ref<string>(firstPermitted.value)

// 同步高亮态与当前路由（直接进入子路由或浏览器前进/后退时也能正确选中）
watch(
  () => route.path,
  (p) => {
    const seg = p.split('/')[2] || ''
    if ((TABS as readonly string[]).includes(seg)) activeTab.value = seg
  },
  { immediate: true },
)

function onTabChange(name: string | number) {
  router.push('/system/' + name)
}
</script>

<style scoped>
.sys-admin {
  display: flex;
  flex-direction: column;
}
.sys-body {
  min-height: 320px;
}
</style>
