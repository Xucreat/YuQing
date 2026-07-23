<template>
  <div class="keywords-page" v-loading="loading">
    <div class="toolbar">
      <div class="filters">
        <input v-model="filters.q" class="search" placeholder="搜索关键词..." @keyup.enter="handleSearch" />
        <select v-model="filters.type" class="select" @change="handleSearch">
          <option value="">类型（全部）</option>
          <option value="monitoring">监测词</option>
          <option value="sensitive">敏感词</option>
        </select>
        <select v-model="filters.source" class="select" @change="handleSearch">
          <option value="">来源（全部）</option>
          <option value="system">系统内置</option>
          <option value="custom">自定义</option>
        </select>
        <select v-model="filters.is_enabled" class="select" @change="handleSearch">
          <option value="">状态（全部）</option>
          <option value="enabled">启用</option>
          <option value="disabled">停用</option>
        </select>
        <select v-model="filters.category" class="select" @change="handleSearch">
          <option value="">分类（全部）</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
        <button class="btn btn-ghost" @click="handleSearch">搜索</button>
        <button class="btn btn-primary" @click="openCreate">+ 新增</button>
      </div>
    </div>

    <div class="legend">
      <span class="legend-item"><i class="dot dot-sys"></i>系统内置敏感词：可查看 / 筛选 / 启停，不可删除或篡改内容</span>
    </div>

    <div class="card table-card">
      <table class="tbl">
        <thead>
          <tr>
            <th style="width:60px">#</th>
            <th>关键词</th>
            <th style="width:90px">类型</th>
            <th style="width:90px">来源</th>
            <th style="width:80px">状态</th>
            <th style="width:80px">权重</th>
            <th style="width:130px">分类</th>
            <th style="width:170px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="row.id">
            <td>{{ (page - 1) * size + idx + 1 }}</td>
            <td><strong>{{ row.word }}</strong></td>
            <td>
              <span class="badge" :class="row.type === 'sensitive' ? 'badge-sensitive' : 'badge-monitoring'">
                {{ row.type === 'sensitive' ? '敏感词' : '监测词' }}
              </span>
            </td>
            <td>
              <span class="badge" :class="row.source === 'system' ? 'badge-system' : 'badge-custom'">
                {{ row.source === 'system' ? '系统' : '自定义' }}
              </span>
            </td>
            <td>
              <span class="badge" :class="row.is_enabled ? 'badge-on' : 'badge-off'">
                {{ row.is_enabled ? '启用' : '停用' }}
              </span>
            </td>
            <td>{{ row.weight }}</td>
            <td>{{ row.category }}</td>
            <td>
              <template v-if="isProtected(row)">
                <button class="btn btn-ghost btn-sm" @click="toggleEnabled(row)">
                  {{ row.is_enabled ? '停用' : '启用' }}
                </button>
                <span class="lock" title="系统内置敏感词受保护">🔒</span>
              </template>
              <template v-else>
                <button class="btn btn-ghost btn-sm" @click="openEdit(row)">编辑</button>
                <button class="btn btn-ghost btn-sm btn-danger" @click="handleDelete(row)">删除</button>
              </template>
            </td>
          </tr>
          <tr v-if="!rows.length && !loading">
            <td colspan="8" class="empty-row">暂无关键词</td>
          </tr>
        </tbody>
      </table>
      <div class="pager" v-if="total > 0">
        <span class="p-info">共 {{ total }} 条</span>
        <button :disabled="page <= 1" @click="page--; loadData()">&#8249;</button>
        <button v-for="p in pages" :key="p" :class="{ active: p === page }" @click="page = p; loadData()">{{ p }}</button>
        <button :disabled="page >= maxPage" @click="page++; loadData()">&#8250;</button>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑关键词' : '新增关键词'" width="440px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="form.type" :disabled="editProtected" placeholder="选择类型">
            <el-option label="监测关键词" value="monitoring" />
            <el-option label="敏感/风险词" value="sensitive" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="form.word" :disabled="editProtected" />
        </el-form-item>
        <el-form-item label="权重">
          <el-input-number v-model="form.weight" :min="1" :max="100" :disabled="editProtected" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" :disabled="editProtected" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
        <el-alert
          v-if="editProtected"
          type="warning"
          :closable="false"
          title="系统内置敏感词受保护，仅可切换启用状态，内容不可修改或删除。"
        />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import api from "@/api"

interface Keyword {
  id: number
  word: string
  weight: number
  category: string
  type: string
  source: string
  is_enabled: boolean
  created_at?: string | null
  updated_at?: string | null
}
interface ListResp {
  items: Keyword[]
  total: number
  page: number
  size: number
}

const loading = ref(false)
const rows = ref<Keyword[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(50)
const categories = ref<string[]>([])

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const editProtected = ref(false)

const filters = reactive({ q: "", type: "", source: "", is_enabled: "", category: "" })
const form = reactive({
  word: "",
  weight: 10,
  category: "",
  type: "monitoring",
  is_enabled: true,
})

const maxPage = computed(() => Math.ceil(total.value / size.value) || 1)
const pages = computed(() => {
  const p: number[] = []
  const s = Math.max(1, page.value - 2)
  const e = Math.min(maxPage.value, page.value + 2)
  for (let i = s; i <= e; i++) p.push(i)
  return p
})

function isProtected(row: Keyword): boolean {
  return row.source === "system" && row.type === "sensitive"
}

async function loadData() {
  loading.value = true
  try {
    const params: any = { page: page.value, size: size.value }
    if (filters.q) params.q = filters.q
    if (filters.type) params.type = filters.type
    if (filters.source) params.source = filters.source
    if (filters.is_enabled) params.is_enabled = filters.is_enabled === "enabled"
    if (filters.category) params.category = filters.category
    const { data } = await api.get<ListResp>("/keywords", { params })
    rows.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error("加载失败")
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    const { data } = await api.get<string[]>("/keywords/categories")
    categories.value = data
  } catch {
    /* 忽略分类加载失败 */
  }
}

function openCreate() {
  isEdit.value = false
  editId.value = null
  editProtected.value = false
  form.word = ""
  form.weight = 10
  form.category = ""
  form.type = "monitoring"
  form.is_enabled = true
  dialogVisible.value = true
}

function openEdit(row: Keyword) {
  isEdit.value = true
  editId.value = row.id
  editProtected.value = isProtected(row)
  form.word = row.word
  form.weight = row.weight
  form.category = row.category
  form.type = row.type
  form.is_enabled = row.is_enabled
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.word.trim() && !editProtected.value) {
    ElMessage.warning("请输入关键词")
    return
  }
  try {
    if (isEdit.value && editId.value) {
      const payload: any = { is_enabled: form.is_enabled }
      if (!editProtected.value) {
        payload.word = form.word
        payload.weight = form.weight
        payload.category = form.category
        payload.type = form.type
      }
      await api.put("/keywords/" + editId.value, payload)
    } else {
      await api.post("/keywords", { ...form })
    }
    ElMessage.success(isEdit.value ? "更新成功" : "创建成功")
    dialogVisible.value = false
    loadData()
    loadCategories()
  } catch {
    ElMessage.error("保存失败")
  }
}

async function toggleEnabled(row: Keyword) {
  try {
    await api.put("/keywords/" + row.id, { is_enabled: !row.is_enabled })
    ElMessage.success(row.is_enabled ? "已停用" : "已启用")
    loadData()
  } catch {
    ElMessage.error("操作失败")
  }
}

async function handleDelete(row: Keyword) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.word}」？`, "提示", { type: "warning" })
    await api.delete("/keywords/" + row.id)
    ElMessage.success("删除成功")
    loadData()
  } catch (err: any) {
    if (err && err.response && err.response.status === 403) {
      ElMessage.error("系统内置敏感词不可删除")
    } else if (err && err.response) {
      ElMessage.error("删除失败")
    }
  }
}

function handleSearch() {
  page.value = 1
  loadData()
}

onMounted(() => {
  loadData()
  loadCategories()
})
</script>

<style scoped>
.keywords-page { min-height: 100% }
.toolbar { margin-bottom: 14px }
.filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap }
.search { height: 42px; padding: 0 14px; font-size: 14px; border: 1px solid #d2d2d7; border-radius: 12px; outline: none; min-width: 200px; box-sizing: border-box; color: #1d1d1f; background: #fff }
.search:focus { border-color: #0071e3; box-shadow: 0 0 0 4px rgba(0, 113, 227, .1) }
.select { height: 42px; padding: 0 14px; font-size: 14px; border: 1px solid #d2d2d7; border-radius: 12px; outline: none; background: #fff; box-sizing: border-box; color: #1d1d1f }
.btn { display: inline-flex; align-items: center; gap: 8px; border: none; border-radius: 980px; padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background-color .18s }
.btn-primary { background: #0071e3; color: #fff }
.btn-primary:hover { background: #0077ed }
.btn-ghost { background: #e8e8ed; color: #1d1d1f }
.btn-ghost:hover { background: #dededf }
.btn-sm { padding: 6px 14px; font-size: 13px }
.btn-danger { color: #ff3b30 }
.legend { margin-bottom: 12px; font-size: 12.5px; color: #86868b }
.legend-item { display: inline-flex; align-items: center; gap: 6px }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block }
.dot-sys { background: #ff9500 }
.card { background: #fff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0, 0, 0, .04), 0 12px 32px rgba(0, 0, 0, .05) }
.table-card { padding: 6px 6px 14px; overflow: hidden }
table.tbl { width: 100%; border-collapse: collapse; font-size: 14px }
table.tbl thead th { text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b; padding: 14px 18px; border-bottom: 1px solid #e8e8ed }
table.tbl tbody td { padding: 15px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f }
table.tbl tbody tr:hover { background: #fafafc }
table.tbl tbody tr:last-child td { border-bottom: none }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0 }
.badge { display: inline-block; padding: 2px 10px; border-radius: 980px; font-size: 12px; font-weight: 500 }
.badge-monitoring { background: #e8f1ff; color: #0071e3 }
.badge-sensitive { background: #ffece8; color: #ff3b30 }
.badge-system { background: #f0f0f3; color: #6e6e73 }
.badge-custom { background: #eafaf0; color: #1a9e4b }
.badge-on { background: #eafaf0; color: #1a9e4b }
.badge-off { background: #f0f0f3; color: #86868b }
.lock { margin-left: 6px; font-size: 13px }
.pager { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 16px 18px 0 }
.pager .p-info { color: #86868b; font-size: 13px; margin-right: auto }
.pager button { min-width: 34px; height: 34px; padding: 0 10px; border: 1px solid #d2d2d7; background: #fff; border-radius: 9px; color: #1d1d1f; font-size: 13.5px; cursor: pointer }
.pager button:hover:not(:disabled) { background: #e8e8ed }
.pager button.active { background: #1d1d1f; color: #fff; border-color: #1d1d1f }
.pager button:disabled { opacity: .4; cursor: default }
</style>
