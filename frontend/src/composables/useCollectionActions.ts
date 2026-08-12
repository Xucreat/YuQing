import { ref, computed, h } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { pollTask } from '@/api'
import { useCollectStore } from '@/stores/collect'
import { usePermission } from '@/composables/usePermission'

// 模块级共享状态（单例）：顶栏菜单与外国页共用同一份采集状态，
// 避免「选择来源」等状态在多处各自维护导致不一致。
const collecting = ref(false)
const approvedSources = ref<Array<{ id: number; name: string }>>([])
const selectedSourceIds = ref<number[]>([])

export function useCollectionActions() {
  const { isSuperuser, hasPermission } = usePermission()
  const router = useRouter()
  const collectStore = useCollectStore()

  // 可见性：拥有任一采集权限即显示统一的「采集」入口。
  const canCollectDomestic = computed(() => isSuperuser.value)
  const canCollectSelected = computed(() => hasPermission('foreign:sources:collect'))
  const canCollectAll = computed(() => hasPermission('foreign:sources:collect_all'))
  const canShowMenu = computed(
    () => canCollectDomestic.value || canCollectSelected.value || canCollectAll.value,
  )

  async function loadApprovedSources() {
    try {
      const { data } = await api.get('/foreign/sources/approved')
      approvedSources.value = (data.items || []).map((item: any) => ({ id: item.id, name: item.name }))
      const available = new Set(approvedSources.value.map((item) => item.id))
      selectedSourceIds.value = selectedSourceIds.value.filter((id) => available.has(id))
      if (!selectedSourceIds.value.length) selectedSourceIds.value = approvedSources.value.map((item) => item.id)
    } catch {
      approvedSources.value = []
      selectedSourceIds.value = []
    }
  }

  // 国内采集：与原 AppLayout.handleCollect 行为一致（含进度提示、数据刷新、预警评估）。
  async function collectDomestic() {
    if (collecting.value) return
    collecting.value = true
    try {
      const { data } = await api.post('/collector/run')
      collectStore.startTask(data.task_id, 'domestic')
      ElMessage({
        type: 'info',
        duration: 6000,
        message: h('span', [
          '采集任务已启动，后台运行中…',
          h('span', {
            style: 'color:#409eff;cursor:pointer;margin-left:4px;',
            onClick: () => router.push({ path: '/data', query: { tab: 'logs' } }),
          }, '查看实时采集进度'),
        ]),
      })
      const res = await pollTask(data.task_id)
      if (res.status === 'success') {
        const r = res.result || {}
        const fetchedRaw = r.fetched_raw ?? 0
        const created = r.created ?? 0
        const analyzed = r.analyzed ?? 0
        const commentsSkipped = r.comments_skipped ?? 0
        const admissionFiltered = r.admission_filtered ?? 0
        const governanceText = (commentsSkipped || admissionFiltered)
          ? '，评论跳过 ' + commentsSkipped + ' 条，准入过滤 ' + admissionFiltered + ' 条'
          : ''
        if (fetchedRaw === 0) {
          ElMessage.warning('采集完成：未抓取到新内容，数据源暂无可读数据')
        } else if (created === 0) {
          ElMessage.warning('采集完成：抓取 ' + fetchedRaw + ' 条，未形成新舆情' + governanceText)
        } else {
          ElMessage.success('采集完成：新增 ' + created + ' 条，分析 ' + analyzed + ' 条' + governanceText)
        }
        window.dispatchEvent(new CustomEvent('data-refresh'))
        try {
          const evalRes = await api.post('/alerts/evaluate')
          if (evalRes.data.alerts_created > 0) {
            ElMessage.success('预警评估完成：生成 ' + evalRes.data.alerts_created + ' 条新预警')
          }
        } catch (_) { /* 评估失败不阻塞采集 */ }
      } else if (res.status === 'failed') {
        ElMessage.error('采集失败：' + (res.error || res.message || '未知错误'))
      }
    } catch (err: any) {
      ElMessage.error(err?.response?.data?.detail || err?.response?.data?.message || '采集失败')
    } finally {
      collecting.value = false
    }
  }

  // 外网 RSS：按所选来源采集（默认全选），与原 ForeignWorkspace.collectNow 一致。
  async function collectForeignSelected() {
    if (collecting.value) return
    collecting.value = true
    try {
      const { data } = await api.post('/foreign/collect', { source_ids: selectedSourceIds.value })
      // 关键：启动后写入 scope='foreign'，使国外采集日志页的 live-card 激活（修复串台）。
      collectStore.startTask(data.task_id, 'foreign')
      // 与国内一致：点击即弹出去后台运行的提示，并提供实时进度超链接（不再等到采集完成才提示）
      ElMessage({
        type: 'info',
        duration: 6000,
        message: h('span', [
          '采集任务已启动，后台运行中…',
          h('span', {
            style: 'color:#409eff;cursor:pointer;margin-left:4px;',
            onClick: () => router.push({ path: '/data', query: { tab: 'logs', scope: 'foreign' } }),
          }, '查看实时采集进度'),
        ]),
      })
      const result = await pollTask(data.task_id)
      if (result.status === 'success') {
        ElMessage.success(`外网采集完成：新增 ${result.result?.created || 0} 条，已自动规则研判 ${result.result?.analyzed || 0} 条`)
        window.dispatchEvent(new CustomEvent('foreign-data-refresh'))
      } else {
        ElMessage.error(result.error || '外网采集失败')
      }
    } catch (err: any) {
      ElMessage.error(err?.response?.data?.detail || err?.response?.data?.message || err?.message || '外网采集失败')
    } finally {
      collecting.value = false
    }
  }

  // 外网全量：采集所有已启用来源（带确认），与原 ForeignWorkspace.collectAll 一致。
  async function collectForeignAll() {
    try {
      await ElMessageBox.confirm(
        '将采集所有已启用的外网数据源，是否继续？',
        '确认全量外网采集',
        { type: 'warning', confirmButtonText: '全量采集', cancelButtonText: '取消' },
      )
    } catch (err) {
      if (err === 'cancel' || err === 'close') return
      throw err
    }
    if (collecting.value) return
    collecting.value = true
    try {
      const { data } = await api.post('/foreign/collect', { all_sources: true })
      // 关键：启动后写入 scope='foreign'，使国外采集日志页的 live-card 激活（修复串台）。
      collectStore.startTask(data.task_id, 'foreign')
      // 与国内一致：点击即弹出去后台运行的提示，并提供实时进度超链接（不再等到采集完成才提示）
      ElMessage({
        type: 'info',
        duration: 6000,
        message: h('span', [
          '采集任务已启动，后台运行中…',
          h('span', {
            style: 'color:#409eff;cursor:pointer;margin-left:4px;',
            onClick: () => router.push({ path: '/data', query: { tab: 'logs', scope: 'foreign' } }),
          }, '查看实时采集进度'),
        ]),
      })
      const result = await pollTask(data.task_id)
      if (result.status === 'success') {
        ElMessage.success(`外网全量采集完成：新增 ${result.result?.created || 0} 条，已自动规则研判 ${result.result?.analyzed || 0} 条`)
        window.dispatchEvent(new CustomEvent('foreign-data-refresh'))
      } else {
        ElMessage.error(result.error || '外网采集失败')
      }
    } catch (err: any) {
      ElMessage.error(err?.response?.data?.detail || err?.response?.data?.message || err?.message || '外网采集失败')
    } finally {
      collecting.value = false
    }
  }

  return {
    collecting,
    approvedSources,
    selectedSourceIds,
    canCollectDomestic,
    canCollectSelected,
    canCollectAll,
    canShowMenu,
    loadApprovedSources,
    collectDomestic,
    collectForeignSelected,
    collectForeignAll,
  }
}
