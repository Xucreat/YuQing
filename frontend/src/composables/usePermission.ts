import { computed } from 'vue'
import { useAuthStore } from '@/stores'

// 统一前端权限判断入口。
// 规则必须与后端 is_superuser_user 保持一致：
//   1. is_superuser === true  → 全权限（含 role_permissions=0）
//   2. role === 'admin'       → 保持现有兼容行为（后端等价视为超管）
//   3. 普通用户               → 使用登录接口返回的实际 permissions
//   4. 前端权限控制仅用于 UI / 路由体验，不替代后端鉴权。
//
// 注意（RBAC-2C 审计发现）：后端 opinions:read / events:read / dashboard:read /
// keywords:read / alerts:read 等读权限接口当前仅校验登录、未强制 require_permission，
// 但登录返回 permissions 已包含这些读码；前端据此控制 UI/路由即可，差异已在代码与报告中记录。
export function usePermission() {
  const auth = useAuthStore()

  const role = computed(() => auth.role || '')
  // 与后端 is_superuser_user 完全一致：is_superuser 或 role=='admin'
  const isSuperuser = computed(() => !!auth.isSuperuser || role.value === 'admin')

  function hasPermission(permission: string): boolean {
    if (isSuperuser.value) return true
    return auth.permissions?.includes(permission) || auth.permissions?.includes('*') || false
  }

  function hasAnyPermission(perms: string[]): boolean {
    if (!perms || perms.length === 0) return true
    if (isSuperuser.value) return true
    return perms.some((p) => auth.permissions?.includes(p) || auth.permissions?.includes('*'))
  }

  function hasAllPermissions(perms: string[]): boolean {
    if (!perms || perms.length === 0) return true
    if (isSuperuser.value) return true
    return perms.every((p) => auth.permissions?.includes(p) || auth.permissions?.includes('*'))
  }

  // 兼容旧调用：单权限判断
  function can(permission: string): boolean {
    return hasPermission(permission)
  }

  // 路由级权限判断。routeMeta 约定：
  //   meta.permission  : 单个必需权限（满足即可）
  //   meta.permissions : 权限数组；默认需全部满足（hasAll）
  //   meta.permissionAny: true 时 meta.permissions 改为"满足任一即可"
  // 无 permission 相关 meta → 放行（仅依赖全局 requiresAuth）
  function canAccessRoute(meta: Record<string, any> | undefined): boolean {
    if (!meta) return true
    if (meta.permission) return hasPermission(meta.permission as string)
    if (Array.isArray(meta.permissions)) {
      return meta.permissionAny ? hasAnyPermission(meta.permissions) : hasAllPermissions(meta.permissions)
    }
    return true
  }

  return { role, isSuperuser, hasPermission, hasAnyPermission, hasAllPermissions, can, canAccessRoute }
}
