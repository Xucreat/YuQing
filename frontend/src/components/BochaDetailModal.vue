<template>
  <Teleport to="body">
    <div v-if="modelValue" class="modal-mask" @click.self="close">
      <div class="modal-card">
        <div class="modal-header">
          <div class="modal-title-wrap">
            <span class="modal-kicker">AI检索线索详情</span>
            <h3 class="modal-title">{{ item?.title || item?.url || '详情' }}</h3>
          </div>
          <div class="modal-header-right">
            <a
              v-if="item?.url"
              class="jump-link"
              :href="item.url"
              target="_blank"
              rel="noopener"
            >
              跳转原文
            </a>
            <button class="modal-close" title="关闭" @click="close">×</button>
          </div>
        </div>

        <div class="modal-body">
          <template v-if="item">
            <div class="detail-grid">
              <div class="card card-pad">
                <div class="detail-meta">
                  <span>来源：{{ item.source_name || '未知来源' }}</span>
                  <span>发布时间：{{ formatTime(item.publish_time) }}</span>
                  <span v-if="leadQuery">检索词：{{ leadQuery }}</span>
                  <span v-if="statusText">状态：{{ statusText }}</span>
                </div>
                <div class="detail-divider"></div>
                <div class="detail-content">
                  <p v-if="summaryText" class="orig-p">{{ summaryText }}</p>
                  <p v-if="snippetText && snippetText !== summaryText" class="orig-p">{{ snippetText }}</p>
                  <p v-if="!summaryText && !snippetText" class="orig-empty">暂无摘要内容。</p>
                </div>
              </div>

              <div class="card card-pad side-card">
                <div class="section-title">线索信息</div>
                <div class="detail-divider"></div>
                <dl class="info-list">
                  <div>
                    <dt>标题</dt>
                    <dd>{{ item.title || '-' }}</dd>
                  </div>
                  <div>
                    <dt>来源</dt>
                    <dd>{{ item.source_name || '-' }}</dd>
                  </div>
                  <div>
                    <dt>链接</dt>
                    <dd class="url-text">{{ item.url || '-' }}</dd>
                  </div>
                  <div v-if="resultIndex != null">
                    <dt>结果序号</dt>
                    <dd>{{ resultIndex + 1 }}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </template>
          <el-empty v-else description="暂无详情" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import type { BochaLead, LeadStatus, SearchResult } from '@/stores/bocha'

type DetailItem = Partial<Omit<SearchResult, 'result_index'> & BochaLead> & {
  result_index?: number | null
}

const props = defineProps<{
  modelValue: boolean
  item?: DetailItem | null
  query?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const leadQuery = computed(() => props.query || props.item?.query || '')
const summaryText = computed(() => props.item?.summary || '')
const snippetText = computed(() => props.item?.snippet || '')
const resultIndex = computed(() => props.item?.result_index ?? null)
const statusText = computed(() => {
  const status = props.item?.status as LeadStatus | undefined
  if (!status) return ''
  const map: Record<LeadStatus, string> = {
    new: '待确认',
    confirmed: '已确认',
    rejected: '已驳回',
    promoted: '已晋级',
  }
  return map[status] || status
})

function formatTime(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function close() {
  emit('update:modelValue', false)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.modelValue) close()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.42);
  backdrop-filter: saturate(140%) blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 20px;
}

.modal-card {
  width: min(920px, 100%);
  max-height: calc(100vh - 64px);
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.30);
  border: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid #e8e8ed;
}

.modal-title-wrap {
  min-width: 0;
}

.modal-kicker {
  font-size: 12px;
  font-weight: 600;
  color: #86868b;
}

.modal-title {
  font-size: 18px;
  font-weight: 600;
  margin: 4px 0 0;
  color: #1d1d1f;
  line-height: 1.35;
  word-break: break-word;
}

.modal-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.jump-link {
  color: #0071e3;
  font-size: 13.5px;
  font-weight: 500;
  text-decoration: none;
  padding: 7px 14px;
  border-radius: 980px;
  background: #eaf2fd;
  white-space: nowrap;
}

.modal-close {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: #e8e8ed;
  color: #1d1d1f;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}

.modal-body {
  padding: 18px 22px 22px;
  overflow-y: auto;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(260px, 0.65fr);
  gap: 16px;
  align-items: start;
}

.card {
  background: #fff;
  border: 1px solid #e8e8ed;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 12px 32px rgba(0, 0, 0, 0.05);
}

.card-pad {
  padding: 22px 24px;
}

.side-card {
  background: linear-gradient(180deg, #f7faff 0%, #fff 76%);
  border-color: #e3eefb;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 22px;
  font-size: 13px;
  color: #6e6e73;
}

.detail-divider {
  height: 1px;
  background: #e8e8ed;
  margin: 16px 0;
}

.detail-content {
  font-size: 15px;
  line-height: 1.85;
  color: #2b2b2e;
  white-space: pre-wrap;
}

.orig-p {
  margin: 0 0 14px;
  text-indent: 2em;
}

.orig-empty {
  margin: 0;
  color: #86868b;
}

.section-title {
  font-size: 17px;
  font-weight: 600;
  color: #1d1d1f;
}

.info-list {
  display: grid;
  gap: 14px;
  margin: 0;
}

.info-list div {
  min-width: 0;
}

.info-list dt {
  font-size: 12.5px;
  color: #86868b;
  margin-bottom: 4px;
}

.info-list dd {
  margin: 0;
  color: #1d1d1f;
  font-size: 14px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.url-text {
  color: #0071e3;
}

@media (max-width: 920px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
