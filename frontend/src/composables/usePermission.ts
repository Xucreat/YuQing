import { computed } from 'vue'
import { useAuthStore } from '@/stores'

export function usePermission() {
  const auth = useAuthStore()

  const role = computed(() => auth.role || '')

  function can(permission: string): boolean {
    if (role.value === 'admin') return true
    return auth.permissions?.includes(permission) || auth.permissions?.includes('*') || false
  }

  return { can, role }
}
