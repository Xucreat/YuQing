<template>
  <div class="fw-block">
    <div class="toolbar">
      <button class="btn btn-secondary" @click="loadRuns">刷新日志</button>
      <span class="muted">仅显示 scope=foreign 的采集记录</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>来源</th><th>开始</th><th>结束</th><th>状态</th><th>抓取</th><th>命中</th><th>新增</th><th>去重</th><th>代理</th><th>失败原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in runs" :key="row.id">
            <td>{{ row.collector_name }}</td>
            <td>{{ formatTime(row.start_time) }}</td>
            <td>{{ formatTime(row.end_time) }}</td>
            <td><span class="status" :class="{ on: row.status === 'success' }">{{ row.status }}</span></td>
            <td>{{ row.fetched_raw }}</td>
            <td>{{ row.matched }}</td>
            <td>{{ row.created }}</td>
            <td>{{ row.duplicate }}</td>
            <td>{{ row.proxy_used ? '是' : '否' }}</td>
            <td class="error-cell">{{ row.error_msg || '-' }}</td>
          </tr>
          <tr v-if="!runs.length"><td colspan="10" class="empty">暂无外网采集日志</td></tr>
        </tbody>
      </table>
    </div>
    <Pager v-if="runTotal > 0" :total="runTotal" v-model:current-page="runPage" :page-size="runSize" @current-change="loadRuns" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Pager from '@/components/Pager.vue'
import api from '@/api'

type Run = {
  id: number
  collector_name: string
  start_time?: string | null
  end_time?: string | null
  status: string
  fetched_raw: number
  matched: number
  created: number
  duplicate: number
  proxy_used: boolean
  error_msg?: string | null
}

const runs = ref<Run[]>([])
const loading = ref(false)
const runPage = ref(1)
const runSize = 20
const runTotal = ref(0)

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}

async function loadRuns() {
  loading.value = true
  try {
    const { data } = await api.get('/foreign/collection-runs', { params: { page: runPage.value, size: runSize } })
    runs.value = data.items || []
    runTotal.value = data.total || 0
  } finally { loading.value = false }
}

onMounted(loadRuns)
</script>

<style scoped src="./foreign-ui.css" />
