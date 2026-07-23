<template>
  <div class="sys-admin">
    <!-- 横向导航栏：在四个子页面间切换（其余功能不变，仅做页面整合） -->
    <el-tabs v-model="activeTab" class="sys-tabs" @tab-change="onTabChange">
      <el-tab-pane v-if="canUsers" label="用户管理" name="users" />
      <el-tab-pane v-if="canRoles" label="角色权限" name="roles" />
      <el-tab-pane v-if="canLoginLogs" label="登录日志" name="login-logs" />
      <el-tab-pane v-if="canOperationLogs" label="操作日志" name="operation-logs" />
    </el-tabs>

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
const { hasPermission } = usePermission()

const TABS = ['users', 'roles', 'login-logs', 'operation-logs'] as const

const canUsers = computed(() => hasPermission('users:read'))
const canRoles = computed(() => hasPermission('roles:read'))
const canLoginLogs = computed(() => hasPermission('login_logs:read'))
const canOperationLogs = computed(() => hasPermission('audit_logs:read'))
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
/* 横向导航栏贴合页面浅色风格 */
.sys-tabs {
  margin-bottom: 4px;
}
.sys-tabs :deep(.el-tabs__header) {
  margin: 0 0 18px;
}
.sys-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  font-weight: 500;
  height: 44px;
  line-height: 44px;
}
.sys-tabs :deep(.el-tabs__item.is-active) {
  font-weight: 600;
}
.sys-body {
  min-height: 320px;
}
</style>
