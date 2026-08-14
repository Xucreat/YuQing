<template>
  <el-dialog
    v-model="visible"
    title="事件处置"
    width="840px"
    align-center
    :close-on-click-modal="true"
    class="op-dialog"
    @open="onOpen"
  >
    <div v-if="event" class="op-modal-body">
      <div class="op-left">
        <div class="operation-header">
          <div>
            <div class="operation-current">
              当前处置状态
              <span class="pill" :class="eventStatusPill(event.status)">{{ eventStatusLabel(event.status) }}</span>
            </div>
          </div>
        </div>

        <div v-if="canUpdate" class="status-actions" aria-label="变更事件处置状态">
          <button
            v-for="option in statusButtons"
            :key="option.value"
            class="status-button"
            :class="{ current: event.status === option.value }"
            :disabled="busy || !canChangeStatus(option.value)"
            @click="changeStatus(option.value)"
          >
            {{ option.value === 'deprecated' ? '忽略事件' : option.label }}
          </button>
        </div>

        <div v-if="canUpdate" class="merge-split-actions">
          <button class="btn btn-ghost" :disabled="busy" @click="toggleMerge">
            {{ mergePanelOpen ? '收起合并' : '合并到其它事件' }}
          </button>
          <button class="btn btn-ghost" :disabled="busy" @click="toggleSplit">
            {{ splitPanelOpen ? '收起拆分' : '拆分舆情' }}
          </button>
        </div>

        <!-- 合并子面板：选择目标事件 + 原因 -->
        <div v-if="mergePanelOpen && canUpdate" class="sub-panel">
          <label>合并到目标事件（当前事件将归档，舆情迁移到目标）</label>
          <el-select
            v-model="mergeTargetId"
            filterable
            remote
            :remote-method="onMergeSearch"
            :loading="mergeSearching"
            placeholder="搜索目标事件（按标题）"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="c in mergeCandidates"
              :key="c.id"
              :label="`#${c.id} ${c.title}`"
              :value="c.id"
            />
          </el-select>
          <label style="margin-top: 12px">合并原因（可选）</label>
          <textarea
            v-model="mergeReason"
            maxlength="5000"
            rows="2"
            placeholder="填写合并原因"
            class="sub-textarea"
          ></textarea>
          <div class="sub-actions">
            <button
              class="btn btn-primary"
              :disabled="merging || !mergeTargetId"
              @click="submitMerge"
            >
              {{ merging ? '合并中' : '确认合并' }}
            </button>
          </div>
        </div>

        <!-- 拆分子面板：选择要迁出的舆情 + 原因 -->
        <div v-if="splitPanelOpen && canUpdate" class="sub-panel">
          <label>拆分舆情（选中的舆情将迁出，新建一个事件承载）</label>
          <el-select
            v-model="splitOpinionIds"
            multiple
            filterable
            placeholder="选择要拆出的舆情"
            style="width: 100%"
          >
            <el-option
              v-for="o in (event.opinions || [])"
              :key="o.id"
              :label="`#${o.id} ${o.title}`"
              :value="o.id"
            />
          </el-select>
          <label style="margin-top: 12px">拆分原因（可选）</label>
          <textarea
            v-model="splitReason"
            maxlength="5000"
            rows="2"
            placeholder="填写拆分原因"
            class="sub-textarea"
          ></textarea>
          <div class="sub-actions">
            <button
              class="btn btn-primary"
              :disabled="splitting || splitOpinionIds.length === 0"
              @click="submitSplit"
            >
              {{ splitting ? '拆分中' : '确认拆分' }}
            </button>
          </div>
        </div>

        <div v-if="canUpdate" class="note-editor">
          <textarea
            v-model="noteContent"
            maxlength="5000"
            rows="3"
            placeholder="填写核查、联络或处置进展"
            :disabled="busy"
          ></textarea>
          <div class="note-submit-row">
            <span>{{ noteContent.length }}/5000</span>
            <button class="btn btn-primary" :disabled="busy || !noteContent.trim()" @click="addNote">
              {{ savingNote ? '提交中' : '添加备注' }}
            </button>
          </div>
        </div>
      </div>

      <div class="op-right">
        <div class="op-right-title">
          处置记录<span class="op-count">{{ (event.actions || []).length }}</span>
        </div>
        <div class="op-right-scroll">
          <div class="action-timeline">
            <div v-for="action in (event.actions || [])" :key="action.id" class="timeline-item">
              <span class="timeline-dot"></span>
              <div class="timeline-body">
                <div class="timeline-meta">
                  <time>{{ formatTime(action.created_at) }}</time>
                  <strong>{{ action.username || (action.user_id ? `用户 ${action.user_id}` : '系统') }}</strong>
                  <span>{{ actionTypeText(action.action_type) }}</span>
                </div>
                <div class="timeline-content">
                  <template v-if="action.action_type === 'status_change' && action.old_status && action.new_status">
                    {{ eventStatusLabel(action.old_status) }} → {{ eventStatusLabel(action.new_status) }}
                  </template>
                  <template v-else>{{ action.content }}</template>
                </div>
              </div>
            </div>
            <div v-if="(event.actions || []).length === 0" class="timeline-empty">暂无处置记录</div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="op-loading">加载中…</div>
    <template #footer>
      <button class="btn btn-ghost" @click="visible = false">关闭</button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { usePermission } from '@/composables/usePermission'
import { EVENT_STATUS_OPTIONS, eventStatusLabel, eventStatusPill } from '@/utils/event'

interface EventActionItem {
  id: number
  action_type: string
  content?: string | null
  old_status?: string | null
  new_status?: string | null
  created_at: string
  username?: string | null
  user_id?: number | null
}

interface DispEvent {
  id: number
  title?: string
  status: string
  actions: EventActionItem[]
  opinions?: { id: number; title: string }[]
}

interface CandidateEvent {
  id: number
  title: string
}

type EventStatus = 'active' | 'verifying' | 'processing' | 'resolved' | 'closed' | 'deprecated' | 'archived'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    eventId: number | null
    scope?: 'domestic' | 'foreign'
  }>(),
  { scope: 'domestic' },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'updated', id: number): void
}>()

const { hasPermission } = usePermission()

const base = computed(() => (props.scope === 'foreign' ? '/foreign/events' : '/events'))
const canUpdate = computed(() =>
  hasPermission(props.scope === 'foreign' ? 'foreign:events:write' : 'events:write'),
)

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const event = ref<DispEvent | null>(null)
const savingStatus = ref(false)
const savingNote = ref(false)
const noteContent = ref('')

// 合并 / 拆分子面板状态
const mergePanelOpen = ref(false)
const splitPanelOpen = ref(false)
const mergeTargetId = ref<number | null>(null)
const mergeReason = ref('')
const merging = ref(false)
const mergeCandidates = ref<CandidateEvent[]>([])
const mergeSearching = ref(false)
const splitOpinionIds = ref<number[]>([])
const splitReason = ref('')
const splitting = ref(false)

const busy = computed(() => savingStatus.value || savingNote.value || merging.value || splitting.value)

// 状态按钮：6 个原有状态 + 归档（archived）
const statusButtons = computed(() => [
  ...EVENT_STATUS_OPTIONS,
  { value: 'archived', label: '归档' },
])

// 状态流转规则（与后端 events.py 一致）
const nextStatus: Partial<Record<EventStatus, EventStatus>> = {
  active: 'verifying',
  verifying: 'processing',
  processing: 'resolved',
  resolved: 'closed',
}
const DEPRECATE_ALLOWED_FROM: EventStatus[] = ['active', 'verifying', 'processing']

function canChangeStatus(target: EventStatus): boolean {
  const current = event.value?.status as EventStatus | undefined
  if (!current || target === current) return false
  if (target === 'active') return true
  if (target === 'archived') return current !== 'archived'
  if (target === 'deprecated') return DEPRECATE_ALLOWED_FROM.includes(current)
  return nextStatus[current] === target
}

function formatTime(t: string | null): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}
function actionTypeText(value: string): string {
  return (
    { status_change: '状态变更', note: '备注', assign: '指派', resolve: '解决' } as Record<string, string>
  )[value] || value
}
function errorMessage(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function loadDetail() {
  if (!props.eventId) return
  try {
    const { data } = await api.get<DispEvent>(`${base.value}/${props.eventId}`)
    event.value = {
      id: data.id,
      title: data.title,
      status: data.status,
      actions: data.actions || [],
      opinions: data.opinions || [],
    }
  } catch (err: any) {
    ElMessage.error(errorMessage(err, '加载事件详情失败'))
  }
}

function onOpen() {
  mergePanelOpen.value = false
  splitPanelOpen.value = false
  mergeTargetId.value = null
  mergeReason.value = ''
  splitOpinionIds.value = []
  splitReason.value = ''
  noteContent.value = ''
  loadDetail()
  if (props.scope === 'domestic') fetchMergeCandidates('')
}

watch(
  () => [props.modelValue, props.eventId],
  ([open]) => {
    if (open) onOpen()
  },
)

async function changeStatus(target: EventStatus) {
  if (!canChangeStatus(target) || !event.value) return
  savingStatus.value = true
  try {
    await api.patch(`${base.value}/${event.value.id}/status`, { status: target })
    ElMessage.success(`处置状态已更新为${eventStatusLabel(target)}`)
    await loadDetail()
    emit('updated', event.value.id)
  } catch (err: any) {
    ElMessage.error(errorMessage(err, '更新处置状态失败'))
  } finally {
    savingStatus.value = false
  }
}

async function addNote() {
  const content = noteContent.value.trim()
  if (!content || !event.value) return
  savingNote.value = true
  try {
    await api.post(`${base.value}/${event.value.id}/actions`, { action_type: 'note', content })
    noteContent.value = ''
    ElMessage.success('事件备注已添加')
    await loadDetail()
    emit('updated', event.value.id)
  } catch (err: any) {
    ElMessage.error(errorMessage(err, '添加事件备注失败'))
  } finally {
    savingNote.value = false
  }
}

function toggleMerge() {
  mergePanelOpen.value = !mergePanelOpen.value
  if (mergePanelOpen.value && mergeCandidates.value.length === 0) fetchMergeCandidates('')
}
function toggleSplit() {
  splitPanelOpen.value = !splitPanelOpen.value
}

async function fetchMergeCandidates(keyword: string) {
  if (!props.eventId) return
  mergeSearching.value = true
  try {
    const { data } = await api.get(base.value, {
      params: { title: keyword || undefined, size: 30, page: 1 },
    })
    mergeCandidates.value = (data.items || [])
      .filter((e: CandidateEvent) => e.id !== props.eventId)
      .map((e: CandidateEvent) => ({ id: e.id, title: e.title }))
  } catch {
    mergeCandidates.value = []
  } finally {
    mergeSearching.value = false
  }
}
function onMergeSearch(keyword: string) {
  fetchMergeCandidates(keyword)
}

async function submitMerge() {
  if (!mergeTargetId.value || !event.value) return
  merging.value = true
  try {
    await api.post(`${base.value}/${event.value.id}/merge`, {
      target_event_id: mergeTargetId.value,
      reason: mergeReason.value.trim(),
    })
    ElMessage.success('事件已合并到目标事件')
    mergePanelOpen.value = false
    mergeTargetId.value = null
    mergeReason.value = ''
    await loadDetail()
    emit('updated', event.value.id)
  } catch (err: any) {
    ElMessage.error(errorMessage(err, '合并事件失败'))
  } finally {
    merging.value = false
  }
}

async function submitSplit() {
  if (splitOpinionIds.value.length === 0 || !event.value) return
  splitting.value = true
  try {
    await api.post(`${base.value}/${event.value.id}/split`, {
      opinion_ids: splitOpinionIds.value,
      reason: splitReason.value.trim(),
    })
    ElMessage.success('已拆分选中的舆情')
    splitPanelOpen.value = false
    splitOpinionIds.value = []
    splitReason.value = ''
    await loadDetail()
    emit('updated', event.value.id)
  } catch (err: any) {
    ElMessage.error(errorMessage(err, '拆分事件失败'))
  } finally {
    splitting.value = false
  }
}
</script>

<style scoped>
.op-modal-body { display: flex; gap: 24px; align-items: stretch; min-height: 0; height: 520px; }
.op-left { flex: 1 1 0; min-width: 0; overflow-y: auto; padding-right: 4px; }
.op-right {
  flex: 0 0 440px; min-width: 0; position: relative; overflow: hidden;
  border: 1px solid #e8e8ed; border-radius: 12px; background: #fff;
}
.operation-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.operation-current { display: flex; align-items: center; gap: 10px; margin-top: 10px; color: #6e6e73; font-size: 13px; }
.status-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.status-button {
  border: 1px solid #d2d2d7; background: #fff; color: #1d1d1f; border-radius: 6px;
  min-width: 84px; height: 36px; padding: 0 14px; cursor: pointer; font-size: 13px;
}
.status-button:hover:not(:disabled) { border-color: #0071e3; color: #0066cc; }
.status-button.current { border-color: #1d1d1f; background: #1d1d1f; color: #fff; }
.status-button:disabled { cursor: not-allowed; opacity: 0.48; }

.merge-split-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.sub-panel {
  margin-top: 14px; border: 1px solid #e8e8ed; border-radius: 10px; padding: 14px 16px; background: #fafafc;
}
.sub-panel label { font-size: 13px; color: #6e6e73; display: block; margin-bottom: 6px; }
.sub-textarea {
  box-sizing: border-box; width: 100%; resize: vertical; border: 1px solid #d2d2d7; border-radius: 6px;
  padding: 11px 12px; color: #1d1d1f; background: #fff; font: inherit; line-height: 1.6;
}
.sub-textarea:focus { outline: none; border-color: #0071e3; box-shadow: 0 0 0 2px rgba(0,113,227,0.12); }
.sub-actions { display: flex; justify-content: flex-end; margin-top: 10px; }

.note-editor { margin-top: 18px; max-width: 760px; }
.note-editor textarea {
  box-sizing: border-box; width: 100%; resize: vertical; border: 1px solid #d2d2d7; border-radius: 6px;
  padding: 11px 12px; color: #1d1d1f; background: #fff; font: inherit; line-height: 1.6;
}
.note-editor textarea:focus { outline: none; border-color: #0071e3; box-shadow: 0 0 0 2px rgba(0,113,227,0.12); }
.note-submit-row { display: flex; justify-content: flex-end; align-items: center; gap: 12px; margin-top: 8px; color: #86868b; font-size: 12px; }

.op-right-title {
  position: relative; z-index: 1; background: #fff;
  display: flex; align-items: center; gap: 8px;
  height: 48px; padding: 0 16px; box-sizing: border-box;
  font-size: 14px; font-weight: 600; color: #1d1d1f;
}
.op-right-scroll {
  position: absolute; top: 48px; left: 0; right: 0; bottom: 0;
  overflow-y: auto; padding: 2px 16px 14px;
}
.op-count {
  font-size: 12px; font-weight: 500; color: #86868b;
  background: #f0f0f3; border-radius: 980px; padding: 1px 8px;
}
.op-loading { padding: 40px; text-align: center; color: #86868b; }
.timeline-item { position: relative; display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: 10px; padding-bottom: 18px; }
.timeline-item:not(:last-child)::before { content: ''; position: absolute; left: 5px; top: 12px; bottom: 0; width: 1px; background: #d2d2d7; }
.timeline-dot { width: 11px; height: 11px; margin-top: 4px; border-radius: 50%; background: #0071e3; z-index: 1; }
.timeline-meta { display: flex; flex-wrap: wrap; gap: 12px; color: #86868b; font-size: 12px; }
.timeline-meta strong { color: #1d1d1f; font-weight: 600; }
.timeline-content { margin-top: 5px; color: #3a3a3c; font-size: 14px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.timeline-empty { color: #86868b; padding: 10px 0 4px; font-size: 14px; }

.btn { display: inline-flex; align-items: center; gap: 8px; border: none; border-radius: 980px; padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background-color 0.18s ease; }
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #0066cc; }
.btn-ghost { background: #e8e8ed; color: #1d1d1f; }
.btn-ghost:hover { background: #dededf; }
.btn:disabled { cursor: not-allowed; opacity: 0.5; }

.pill {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px;
  border-radius: 980px; font-size: 13px; font-weight: 500; line-height: 1.4; white-space: nowrap;
}
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }

@media (max-width: 860px) {
  .op-modal-body { flex-direction: column; height: auto; }
  .op-right { flex: 1 1 auto; width: 100%; max-height: 340px; position: static; display: flex; flex-direction: column; }
  .op-right-scroll { position: static; flex: 1 1 auto; min-height: 0; }
}
</style>
