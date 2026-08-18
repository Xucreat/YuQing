import { defineStore } from 'pinia'
import { ref } from 'vue'

// 当前进行中的采集任务（task_id / batch_id）持久化到 localStorage，
// 使「采集日志」页面在挂载/刷新后能恢复实时进度轮询，且不依赖 AppLayout 内部变量。
const TASK_KEY = 'collect_active_task_id'
const BATCH_KEY = 'collect_active_batch_id'
const SCOPE_KEY = 'collect_active_task_scope'

export const useCollectStore = defineStore('collect', () => {
  const activeTaskId = ref<string | null>(localStorage.getItem(TASK_KEY) || null)
  const activeBatchId = ref<string | null>(localStorage.getItem(BATCH_KEY) || null)
  const activeTaskScope = ref<'domestic' | 'foreign' | null>(
    (localStorage.getItem(SCOPE_KEY) as 'domestic' | 'foreign' | null) || null
  )

  function startTask(taskId: string, scope?: 'domestic' | 'foreign') {
    activeTaskId.value = taskId
    activeBatchId.value = null
    localStorage.setItem(TASK_KEY, taskId)
    localStorage.removeItem(BATCH_KEY)
    if (scope) {
      activeTaskScope.value = scope
      localStorage.setItem(SCOPE_KEY, scope)
    } else {
      activeTaskScope.value = null
      localStorage.removeItem(SCOPE_KEY)
    }
  }
  function setBatchId(batchId: string) {
    if (activeBatchId.value === batchId) return
    activeBatchId.value = batchId
    localStorage.setItem(BATCH_KEY, batchId)
  }
  function clear() {
    activeTaskId.value = null
    activeBatchId.value = null
    activeTaskScope.value = null
    localStorage.removeItem(TASK_KEY)
    localStorage.removeItem(BATCH_KEY)
    localStorage.removeItem(SCOPE_KEY)
  }
  return { activeTaskId, activeBatchId, activeTaskScope, startTask, setBatchId, clear }
})
