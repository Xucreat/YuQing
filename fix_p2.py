import pathlib

BASE = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ")

# --- Fix 1: Add COLLECTOR_TYPE=mock to .env ---
env_path = BASE / ".env"
env = env_path.read_text(encoding="utf-8")
if "COLLECTOR_TYPE" not in env:
    env += "\nCOLLECTOR_TYPE=mock\n"
    env_path.write_text(env, encoding="utf-8")
    print("Fix 1: Added COLLECTOR_TYPE=mock to .env")

# --- Fix 2: Add event detail navigation to Propagation.vue ---
prop_vue = BASE / "frontend" / "src" / "views" / "Propagation.vue"
t = prop_vue.read_text(encoding="utf-8")

# Add router import
t = t.replace(
    "import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'",
    "import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'\nimport { useRouter } from 'vue-router'"
)

# Add router instance
t = t.replace(
    "const loading = ref(false)",
    "const router = useRouter()\nconst loading = ref(false)"
)

# Add click handler for event detail navigation on the event item
t = t.replace(
    "              @click=\"selectEvent(ev)\"",
    "              @click=\"selectEvent(ev)\"\n              @dblclick=\"router.push('/event/' + ev.event_id)\""
)

prop_vue.write_text(t, encoding="utf-8")
print("Fix 2: Added event detail navigation to Propagation.vue (double-click)")

# --- Fix 3: Auto-evaluation in Dashboard after collection ---
dash_vue = BASE / "frontend" / "src" / "views" / "Dashboard.vue"
d = dash_vue.read_text(encoding="utf-8")

# Add AlertEvaluateResponse import
d = d.replace(
    "import type { DashboardStats, EventListResponse, TrendPoint, KeywordCount, CollectorRunResponse } from '@/types'",
    "import type { DashboardStats, EventListResponse, TrendPoint, KeywordCount, CollectorRunResponse, AlertEvaluateResponse } from '@/types'"
)

# Replace handleCollect to call evaluate after collection
old_handle = """async function handleCollect() {
  if (collecting.value) return
  collecting.value = true
  try {
    const { data } = await api.post<CollectorRunResponse>('/collector/run')
    ElMessage.success(`采集完成：新增 ${data.created} 条，分析 ${data.analyzed} 条`)
    await loadData()
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.response?.data?.message
    if (err?.response?.status === 429) ElMessage.warning('采集过于频繁，请稍后重试')
    else ElMessage.error(msg || '采集失败')
  } finally { collecting.value = false }
}"""

new_handle = """async function handleCollect() {
  if (collecting.value) return
  collecting.value = true
  try {
    const { data } = await api.post<CollectorRunResponse>('/collector/run')
    ElMessage.success(`采集完成：新增 ${data.created} 条，分析 ${data.analyzed} 条`)
    await loadData()
    // Auto-trigger alert evaluation after collection
    try {
      const evalRes = await api.post<AlertEvaluateResponse>('/alerts/evaluate')
      if (evalRes.data.alerts_created > 0) {
        ElMessage.success(`预警评估完成：生成 ${evalRes.data.alerts_created} 条新预警`)
      }
    } catch (_) { /* evaluation failure shouldn't block collection */ }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.response?.data?.message
    if (err?.response?.status === 429) ElMessage.warning('采集过于频繁，请稍后重试')
    else ElMessage.error(msg || '采集失败')
  } finally { collecting.value = false }
}"""

if old_handle in d:
    d = d.replace(old_handle, new_handle)
    dash_vue.write_text(d, encoding="utf-8")
    print("Fix 3: Added auto-evaluation after collection in Dashboard")
else:
    print("Fix 3: handleCollect pattern not found - trying alternate")
    if "handleCollect" in d:
        print("  Function exists but pattern mismatch")
    else:
        print("  Function not found")

