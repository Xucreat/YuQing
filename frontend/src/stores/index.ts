import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

// 鉴权 store（Phase 4 + RBAC-2D：登录、token + 用户名 + 角色 + 权限 + 超管标记持久化、路由守卫）
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const role = ref<string>(localStorage.getItem('role') || '')
  const permissions = ref<string[]>(JSON.parse(localStorage.getItem('permissions') || '[]'))
  const username = ref<string>(localStorage.getItem('username') || '')
  const isSuperuser = ref<boolean>(localStorage.getItem('is_superuser') === '1')

  const isLoggedIn = computed(() => !!token.value)

  function setRole(r: string) { role.value = r; localStorage.setItem('role', r) }
  function setPermissions(p: string[]) { permissions.value = p; localStorage.setItem('permissions', JSON.stringify(p)) }
  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }
  function setIsSuperuser(v: boolean) {
    isSuperuser.value = v
    if (v) localStorage.setItem('is_superuser', '1')
    else localStorage.removeItem('is_superuser')
  }

  function setUsername(name: string) {
    username.value = name
    localStorage.setItem('username', name)
  }

  function logout() {
    role.value = ''; permissions.value = []; isSuperuser.value = false
    localStorage.removeItem('role'); localStorage.removeItem('permissions'); localStorage.removeItem('is_superuser')
    token.value = ''
    username.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
  }

  return { token, username, role, permissions, isSuperuser, isLoggedIn, setToken, setUsername, setRole, setPermissions, setIsSuperuser, logout }
})
