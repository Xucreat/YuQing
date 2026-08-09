<template>
  <div class="fw-block">
    <div class="toolbar">
      <input v-model="keywordFilters.q" class="input" placeholder="搜索关键词" @keyup.enter="loadKeywords" />
      <select v-model="keywordFilters.category" class="input" @change="loadKeywords">
        <option value="">全部主题</option>
        <option v-for="item in keywordCategories" :key="item" :value="item">{{ item }}</option>
      </select>
      <select v-model="keywordFilters.type" class="input" @change="loadKeywords">
        <option value="">全部类型</option>
        <option value="monitoring">监测词</option>
        <option value="sensitive">敏感词</option>
      </select>
      <select v-model="keywordFilters.enabled" class="input" @change="loadKeywords">
        <option value="">全部状态</option>
        <option value="true">启用</option>
        <option value="false">停用</option>
      </select>
      <button class="btn btn-primary" @click="openCreate">新增关键词</button>
      <button class="btn btn-secondary" @click="loadKeywords">刷新</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>关键词</th><th>主题</th><th>类型</th><th>来源</th><th>权重</th><th>风险权重</th><th>状态</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in keywords" :key="row.id">
            <td>{{ row.word }}</td>
            <td>{{ row.category }}</td>
            <td>{{ row.type || 'monitoring' }}</td>
            <td>{{ row.source || 'system' }}</td>
            <td>{{ row.weight ?? 10 }}</td>
            <td>{{ row.severity_weight ?? 0 }}</td>
            <td><span class="status" :class="{ on: row.is_enabled }">{{ row.is_enabled ? '启用' : '停用' }}</span></td>
            <td class="actions">
              <button class="link-btn" :disabled="keywordSaving" @click="toggleKeyword(row)">{{ row.is_enabled ? '停用' : '启用' }}</button>
              <button class="link-btn" @click="editKeyword(row)">编辑</button>
              <button class="link-btn danger" @click="removeKeyword(row.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!keywords.length"><td colspan="8" class="empty">暂无外网关键词</td></tr>
        </tbody>
      </table>
    </div>
    <div class="toolbar">
      <button class="btn btn-secondary" :disabled="keywordSaving" @click="bulkToggleKeywords(true)">批量启用全部当前结果</button>
      <button class="btn btn-secondary" :disabled="keywordSaving" @click="bulkToggleKeywords(false)">批量停用全部当前结果</button>
    </div>
    <Pager v-if="keywordTotal > 0" :total="keywordTotal" v-model:current-page="keywordPage" :page-size="keywordSize" @current-change="loadKeywords" />
  <el-dialog v-model="keywordDialogVisible" :title="editingKeywordId ? '编辑关键词' : '新增关键词'" width="440px">
    <el-form :model="keywordDraft" label-width="80px">
      <el-form-item label="关键词">
        <el-input v-model="keywordDraft.word" placeholder="输入外网关键词" />
      </el-form-item>
      <el-form-item label="分类">
        <el-input v-model="keywordDraft.category" placeholder="如 general" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="keywordDraft.type" placeholder="选择类型">
          <el-option label="监测词" value="monitoring" />
          <el-option label="敏感词" value="sensitive" />
        </el-select>
      </el-form-item>
      <el-form-item label="权重">
        <el-input-number v-model="keywordDraft.weight" :min="0" :max="100" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="keywordDraft.is_enabled" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="keywordDialogVisible = false">取消</el-button>
      <el-button type="primary" :disabled="keywordSaving" @click="saveKeyword">保存</el-button>
    </template>
  </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Pager from '@/components/Pager.vue'
import api from '@/api'

type Keyword = {
  id: number
  word: string
  category: string
  type: 'monitoring' | 'sensitive'
  source: 'system' | 'custom'
  weight: number
  severity_weight: number
  rule_config?: Record<string, unknown>
  is_enabled: boolean
}

const keywords = ref<Keyword[]>([])
const keywordSaving = ref(false)
const keywordCategories = ref<string[]>([])
const keywordPage = ref(1)
const keywordSize = 50
const keywordTotal = ref(0)
const keywordFilters = reactive({ q: '', category: '', type: '', enabled: '' })
const keywordDraft = reactive({ word: '', category: 'general', type: 'monitoring' as 'monitoring' | 'sensitive', weight: 10, is_enabled: true })
const editingKeywordId = ref<number | null>(null)
const keywordDialogVisible = ref(false)

async function loadKeywords() {
  loading.value = true
  try {
    const params: Record<string, string | number | boolean> = { page: keywordPage.value, size: keywordSize }
    if (keywordFilters.q) params.q = keywordFilters.q
    if (keywordFilters.category) params.category = keywordFilters.category
    if (keywordFilters.type) params.type = keywordFilters.type
    if (keywordFilters.enabled) params.is_enabled = keywordFilters.enabled === 'true'
    const [list, categories] = await Promise.all([
      api.get('/foreign/keywords', { params }),
      api.get('/foreign/keywords/categories'),
    ])
    keywords.value = list.data.items || []
    keywordTotal.value = list.data.total || 0
    keywordCategories.value = categories.data.items || []
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '外网关键词加载失败')
  } finally { loading.value = false }
}

function openCreate() {
  editingKeywordId.value = null
  keywordDraft.word = ''
  keywordDraft.category = 'general'
  keywordDraft.type = 'monitoring'
  keywordDraft.weight = 10
  keywordDraft.is_enabled = true
  keywordDialogVisible.value = true
}
async function saveKeyword() {
  if (keywordSaving.value) return
  const word = keywordDraft.word.trim()
  if (!word) { ElMessage.warning('请输入关键词'); return }
  keywordSaving.value = true
  try {
    const payload = { word, category: keywordDraft.category.trim() || 'general', type: keywordDraft.type, weight: keywordDraft.weight, severity_weight: 0, is_enabled: keywordDraft.is_enabled, source: editingKeywordId.value ? undefined : 'custom' }
    if (editingKeywordId.value) {
      await api.patch(`/foreign/keywords/${editingKeywordId.value}`, payload)
      ElMessage.success('外网关键词已更新')
    } else {
      await api.post('/foreign/keywords', payload)
      ElMessage.success('外网关键词已新增')
    }
    keywordDialogVisible.value = false
    editingKeywordId.value = null
    keywordDraft.word = ''
    await loadKeywords()
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '外网关键词保存失败') } finally { keywordSaving.value = false }
}

async function toggleKeyword(row: Keyword) {
  if (keywordSaving.value) return
  keywordSaving.value = true
  try { await api.patch(`/foreign/keywords/${row.id}`, { is_enabled: !row.is_enabled }); await loadKeywords() } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '外网关键词更新失败') } finally { keywordSaving.value = false }
}

async function removeKeyword(id: number) {
  try {
    await ElMessageBox.confirm('确认删除这个外网关键词？', '删除关键词', { type: 'warning' })
    await api.delete(`/foreign/keywords/${id}`)
    await loadKeywords()
    ElMessage.success('外网关键词已删除')
  } catch (err: any) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(err?.response?.data?.detail || '外网关键词删除失败')
  }
}

function editKeyword(row: Keyword) {
  editingKeywordId.value = row.id
  keywordDraft.word = row.word
  keywordDraft.category = row.category
  keywordDraft.type = row.type || 'monitoring'
  keywordDraft.weight = row.weight ?? 10
  keywordDraft.is_enabled = row.is_enabled
  keywordDialogVisible.value = true
}

async function bulkToggleKeywords(isEnabled: boolean) {
  if (keywordSaving.value || !keywords.value.length) return
  keywordSaving.value = true
  try { await api.post('/foreign/keywords/bulk-status', { keyword_ids: keywords.value.map(row => row.id), is_enabled: isEnabled }); await loadKeywords(); ElMessage.success('外网关键词状态已批量更新') } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '批量更新失败') } finally { keywordSaving.value = false }
}

// 本地 loading 状态（供模板与共享样式使用）
const loading = ref(false)

onMounted(loadKeywords)
</script>

<style scoped src="./foreign-ui.css" />
