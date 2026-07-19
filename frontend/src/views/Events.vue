<template>
  <div class="events" v-loading="loading">
    <div class="toolbar">
      <button class="btn btn-ghost" :disabled="aggregating" @click="handleAggregate">{{ aggregating ? '聚合中...' : '手动聚合' }}</button>
      <button class="btn btn-ghost" @click="loadData">刷新</button>
      <span v-if="lastResult" class="agg-result">
        聚合成功：新建 {{ lastResult.created }} · 更新 {{ lastResult.updated }} · 关联 {{ lastResult.linked }}
      </span>
    </div>

    <div class="card table-card">
      <table class="tbl">
        <thead>
          <tr>
            <th style="width:70px">ID</th>
            <th style="min-width:280px">事件标题</th>
            <th style="width:120px" class="col-center">风险等级</th>
            <th style="width:120px" class="col-center">关联舆情</th>
            <th style="width:100px" class="col-center">状态</th>
            <th style="width:170px">首次发现</th>
            <th style="width:170px">最后更新</th>
            <th style="width:80px" class="col-center">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="row.id" @click="$router.push('/event/' + row.id)" style="cursor:pointer">
            <td>{{ (page - 1) * size + idx + 1 }}</td>
            <td><span class="t-title">{{ row.title }}</span></td>
            <td class="col-center">
              <span class="pill" :class="riskPill(row.risk_level)"><span class="dot"></span>{{ riskText(row.risk_level) }}</span>
            </td>
            <td class="col-center risk-num">{{ row.opinion_count }}</td>
            <td class="col-center"><span class="pill pill-green"><span class="dot"></span>{{ row.status }}</span></td>
            <td>{{ formatTime(row.first_time) }}</td>
            <td>{{ formatTime(row.last_time) }}</td>
            <td class="col-center" @click.stop>
              <button class="btn-icon btn-delete" title="删除事件" @click="handleDelete(row)">🗑</button>
            </td>
          </tr>
          <tr v-if="rows.length===0 && !loading">
            <td colspan="8" class="empty-row">暂无事件数据</td>
          </tr>
        </tbody>
      </table>

      <div class="pager" v-if="total > 0">
        <span class="p-info">共 {{ total }} 条</span>
        <button :disabled="page<=1" @click="page--; loadData()">‹</button>
        <button v-for="p in pages" :key="p" :class="{ active: p === page }" @click="page=p; loadData()">{{ p }}</button>
        <button :disabled="page>=maxPage" @click="page++; loadData()">›</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { EventItem, EventListResponse, EventCreateResponse } from '@/types'

const loading = ref(false)
const aggregating = ref(false)
const rows = ref<EventItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const lastResult = ref<EventCreateResponse | null>(null)

const maxPage = computed(() => Math.ceil(total.value / size.value) || 1)
const pages = computed(() => {
  const p: number[] = []
  const mp = maxPage.value
  const start = Math.max(1, page.value - 2)
  const end = Math.min(mp, page.value + 2)
  for (let i = start; i <= end; i++) p.push(i)
  return p
})

function riskPill(level: string): string {
  return ({ high: 'pill-red', medium: 'pill-orange', low: 'pill-green' } as const)[level] || 'pill-gray'
}
function riskText(level: string): string { return { high: '高风险', medium: '中风险', low: '低风险' }[level] || level }
function formatTime(t: string | null): string { if (!t) return '-'; return t.replace('T', ' ').slice(0, 19) }

async function loadData() {
  loading.value = true
  try {
    const { data } = await api.get<EventListResponse>('/events', { params: { page: page.value, size: size.value } })
    rows.value = data.items; total.value = data.total
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '加载事件列表失败') } finally { loading.value = false }
}

async function handleAggregate() {
  if (aggregating.value) return
  aggregating.value = true
  try {
    const { data } = await api.post<EventCreateResponse>('/events/aggregate')
    lastResult.value = data
    ElMessage.success('聚合完成：新建 ' + data.created + '，更新 ' + data.updated + '，关联 ' + data.linked)
    page.value = 1; await loadData()
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '聚合失败') } finally { aggregating.value = false }
}

async function handleDelete(row: EventItem) {
  try {
    const { ElMessageBox } = await import('element-plus')
    await ElMessageBox.confirm(
      `确认删除事件「${row.title}」？关联的舆情不会被删除，仅解除关联。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.delete('/events/' + row.id)
    ElMessage.success('事件已删除')
    await loadData()
  } catch { /* cancelled or error */ }
}

onMounted(loadData)
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
.agg-result { font-size: 13px; color: #34c759; margin-left: 8px; }
.btn { display: inline-flex; align-items: center; gap: 8px; border: none; border-radius: 980px; padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background-color 0.18s ease; }
.btn-ghost { background: #e8e8ed; color: #1d1d1f; }
.btn-ghost:hover { background: #dededf; }

.card { background: #ffffff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05); }
.table-card { padding: 6px 6px 14px; overflow: hidden; }

table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
table.tbl thead th {
  text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b;
  padding: 14px 18px; border-bottom: 1px solid #e8e8ed; white-space: nowrap;
}
table.tbl tbody td {
  padding: 15px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; vertical-align: middle;
}
table.tbl tbody tr { transition: background-color 0.12s ease; }
table.tbl tbody tr:hover { background: #fafafc; }
table.tbl tbody tr:last-child td { border-bottom: none; }
.col-center { text-align: center; }
.t-title { font-weight: 500; color: #1d1d1f; }
.risk-num { font-weight: 600; font-variant-numeric: tabular-nums; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }

.pill {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px;
  border-radius: 980px; font-size: 13px; font-weight: 500; line-height: 1.4; white-space: nowrap;
}
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }

.pager { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 16px 18px 0; }
.pager .p-info { color: #86868b; font-size: 13px; margin-right: auto; }
.pager button {
  min-width: 34px; height: 34px; padding: 0 10px; border: 1px solid #d2d2d7;
  background: #ffffff; border-radius: 9px; color: #1d1d1f; font-size: 13.5px;
  cursor: pointer; transition: background 0.15s ease;
}
.pager button:hover:not(:disabled) { background: #e8e8ed; }
.pager button.active { background: #1d1d1f; color: #fff; border-color: #1d1d1f; }
.pager button:disabled { opacity: 0.4; cursor: default; }

.btn-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border: none; border-radius: 8px;
  background: transparent; cursor: pointer; font-size: 16px;
  transition: background 0.15s ease;
}
.btn-delete:hover { background: rgba(255,59,48,0.1); }
</style>
