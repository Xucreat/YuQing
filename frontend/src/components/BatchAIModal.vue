<template>
  <div v-if="visible" class="modal-mask" @click.self="close">
    <div class="modal-card compact-modal">
      <div class="modal-header">
        <div class="modal-title-wrap">
          <span class="modal-kicker">{{ kicker }}</span>
          <h3 class="modal-title">{{ title }}</h3>
        </div>
        <button class="modal-close" @click="close">✕</button>
      </div>
      <div class="modal-body batch-form">
        <label>研判范围
          <select v-model="form.scope" class="select" @change="onScopeChange">
            <option v-for="opt in scopeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </label>
        <label v-if="form.scope === 'recent' || form.scope === 'count'">最近条数
          <input v-model.number="form.recent_n" class="select" type="number" min="1" max="100000" />
        </label>
        <div v-if="form.scope === 'time'" class="date-range">
          <label>开始<input v-model="form.date_from" class="select" type="date" @change="clearPreview" /></label>
          <label>结束<input v-model="form.date_to" class="select" type="date" @change="clearPreview" /></label>
        </div>
        <p v-if="form.scope === 'selected'" class="form-note">将处理当前选中的 {{ selectedCount }} 条舆情。</p>
        <p v-if="form.scope === 'full' || form.scope === 'filters'" class="form-note warning-text">
          全量任务可能消耗大量 Token 并运行较长时间。AI 结果仍须人工复核后才会进入正式事件或预警。
        </p>
        <label class="check-line"><input v-model="form.only_unanalyzed" type="checkbox" @change="clearPreview" /> 仅处理未完成 AI 研判</label>
        <label class="check-line"><input v-model="form.force" type="checkbox" @change="clearPreview" /> 强制重新研判已有 AI 结果</label>

        <div v-if="preview" class="preview-box">
          <b>符合条件舆情 {{ preview.matched_count }} 条</b>
          <span>已有 AI 结果 {{ preview.existing_ai_result_count ?? 0 }} 条 · 待分析 {{ preview.pending_analysis_count }} 条</span>
          <span>预计 Token：{{ preview.estimated_token_usage }}</span>
          <span>预计耗时：{{ preview.estimated_duration_seconds }} 秒</span>
          <span>风险分布：高 {{ preview.risk_level_counts?.high ?? 0 }} · 中 {{ preview.risk_level_counts?.medium ?? 0 }} · 低 {{ preview.risk_level_counts?.low ?? 0 }}</span>
          <span>可能影响：事件候选 {{ preview.possible_event_count ?? 0 }} 个 · 预警 {{ preview.possible_alert_count ?? 0 }} 个</span>
          <span v-if="preview.preview_warning" class="warning-text">⚠ {{ preview.preview_warning }}</span>
          <span v-if="preview.token_budget_exceeded" class="warning-text">⚠ 预计 Token 超出预算，提交将被拦截，请缩小范围或调高预算。</span>
        </div>
        <p v-if="error" class="warning-text">{{ error }}</p>

        <div class="modal-footer">
          <button class="btn btn-ghost" @click="close">取消</button>
          <button class="btn btn-ghost" :disabled="previewLoading" @click="previewBatch">预览</button>
          <button class="btn btn-primary" :disabled="submitting || !preview || preview.token_budget_exceeded" @click="submitBatch">提交任务</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { reactive, ref } from 'vue'
import api from '@/api'

const props = defineProps<{
  visible: boolean
  kicker: string
  title?: string
  previewEndpoint: string
  submitEndpoint: string
  buildPayload: (form: any, fullConfirmation: boolean) => Record<string, any>
  scopeOptions: Array<{ value: string; label: string }>
  fullScopeValue: string
  selectedCount?: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'submitted', data: any): void
}>()

const form = reactive({
  scope: props.scopeOptions?.[0]?.value ?? 'recent',
  recent_n: 100,
  date_from: '',
  date_to: '',
  only_unanalyzed: true,
  force: false,
})

const preview = ref<any>(null)
const previewLoading = ref(false)
const submitting = ref(false)
const error = ref('')

function close() {
  emit('update:visible', false)
}
function clearPreview() {
  preview.value = null
  error.value = ''
}
function onScopeChange() {
  clearPreview()
}

async function previewBatch() {
  previewLoading.value = true
  error.value = ''
  try {
    const { data } = await api.post(props.previewEndpoint, props.buildPayload(form, false))
    preview.value = data
  } catch (err: any) {
    preview.value = null
    error.value = err?.response?.data?.detail || '批量研判预览失败'
  } finally {
    previewLoading.value = false
  }
}

async function doSubmit(fullConfirmation: boolean) {
  if (!preview.value) return
  submitting.value = true
  error.value = ''
  try {
    const { data } = await api.post(props.submitEndpoint, props.buildPayload(form, fullConfirmation))
    emit('submitted', data)
    close()
  } catch (err: any) {
    const status = err?.response?.status
    const detail = err?.response?.data?.detail || '批量 AI 研判提交失败'
    if (status === 403) error.value = `权限不足，无法提交批量 AI 研判：${detail}`
    else if (status === 422 && /[Tt]oken/.test(detail)) error.value = `Token 超出预算，已拦截提交：${detail}`
    else if (status === 422) error.value = `提交被拒绝：${detail}`
    else if (status === 409) error.value = `已有等价批量任务在运行：${detail}`
    else error.value = detail
  } finally {
    submitting.value = false
  }
}

async function submitBatch() {
  if (form.scope === props.fullScopeValue) {
    try {
      await ElMessageBox.confirm(
        `确认提交全量 AI 研判？当前匹配 ${preview.value.matched_count} 条，预计消耗 ${preview.value.estimated_token_usage} Token，可能运行较长时间。`,
        '全量 AI 研判二次确认',
        { type: 'warning', confirmButtonText: '确认提交', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
    await doSubmit(true)
  } else {
    await doSubmit(false)
  }
}

// 父组件提交后想重置预览态时调用
function reset() {
  preview.value = null
  error.value = ''
}

defineExpose({ reset })
</script>

<style scoped>
.modal-mask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-card { background: #fff; border-radius: 14px; width: 460px; max-width: 92vw; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25); overflow: hidden; }
.compact-modal { width: 460px; }
.modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 16px 18px 10px; }
.modal-title-wrap { display: flex; flex-direction: column; gap: 2px; }
.modal-kicker { font-size: 12px; color: #0071e3; font-weight: 600; letter-spacing: 0.4px; }
.modal-title { margin: 0; font-size: 18px; color: #1d1d1f; }
.modal-close { border: 0; background: transparent; font-size: 18px; color: #86868b; cursor: pointer; line-height: 1; }
.modal-body { padding: 6px 18px 18px; display: flex; flex-direction: column; gap: 12px; }
.batch-form label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #515154; }
.batch-form .select { padding: 8px 10px; border: 1px solid #d2d2d7; border-radius: 8px; font-size: 13px; background: #fff; color: #1d1d1f; }
.date-range { display: flex; gap: 10px; }
.date-range label { flex: 1; }
.check-line { flex-direction: row !important; align-items: center; gap: 8px !important; }
.form-note { font-size: 12px; color: #86868b; margin: 0; }
.warning-text { color: #c4563c; font-size: 12px; margin: 0; }
.preview-box { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; border: 1px solid #dbe9fb; background: #f5f9ff; border-radius: 10px; color: #515154; font-size: 13px; }
.preview-box b { color: #0071e3; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
.btn { border: 0; border-radius: 9px; padding: 8px 14px; font-size: 13px; cursor: pointer; }
.btn-ghost { background: #f0f0f2; color: #1d1d1f; }
.btn-primary { background: #0071e3; color: #fff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
