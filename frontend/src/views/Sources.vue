<template>
  <div class="ds-page" v-loading="loading">
    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="filters">
        <el-select v-model="filterRegion" placeholder="全部区域" clearable class="f-select" @change="reload">
          <el-option v-for="o in regionOptions" :key="o.code" :label="o.name" :value="o.code" />
        </el-select>
        <el-select v-model="filterEnabled" placeholder="启用状态" clearable class="f-select" @change="reload">
          <el-option label="已启用" :value="true" />
          <el-option label="已停用" :value="false" />
        </el-select>
        <el-input v-model="filterQ" placeholder="搜索名称 / key" clearable class="f-input" @keyup.enter="reload" @clear="reload" />
        <button class="btn btn-ghost" @click="reload">刷新</button>
      </div>
      <div class="toolbar-right">
        <span class="count-tip">共 {{ total }} 个数据源</span>
        <button class="btn btn-primary" @click="openCreate">+ 新建采集源</button>
      </div>
    </div>

    <!-- 管理表格 -->
    <div class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>名称</th>
            <th>区域</th>
            <th style="width:96px">启用</th>
            <th style="width:120px">优先级</th>
            <th style="width:110px">最近状态</th>
            <th style="width:170px">最近运行时间</th>
            <th style="width:120px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sources" :key="s.id">
            <td>
              <div class="ds-name">{{ s.name }}</div>
              <div class="ds-key">{{ s.key }} · {{ s.type }}</div>
            </td>
            <td>
              <span v-if="s.scope_display === '全国'" class="pill pill-gray">全国</span>
              <span v-else class="pill pill-blue">{{ s.scope_display }}</span>
            </td>
            <td>
              <el-switch
                :model-value="s.enabled"
                :loading="s._saving"
                @change="(v: any) => onToggle(s, v)"
              />
            </td>
            <td>
              <el-input-number
                :model-value="s.priority"
                :min="0"
                :max="999"
                size="small"
                controls-position="right"
                @change="(v: any) => onPriority(s, v)"
              />
            </td>
            <td>
              <span v-if="s.latest_run_status" class="pill" :class="runPill(s.latest_run_status)">{{ runText(s.latest_run_status) }}</span>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <span v-if="s.latest_run_at">{{ formatTime(s.latest_run_at) }}</span>
              <span v-else class="muted">从未运行</span>
            </td>
            <td>
              <button class="btn btn-mini" @click="openHistory(s)">查看历史</button>
              <button class="btn btn-mini" @click="openConfig(s)">配置</button>
            </td>
          </tr>
          <tr v-if="!sources.length"><td colspan="7" class="empty-row">暂无数据源</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div class="pager" v-if="total > size">
      <el-pagination
        layout="prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="page"
        @current-change="onPage"
      />
    </div>

    <!-- 查看历史弹窗（仅采集历史） -->
    <el-dialog
      v-model="historyVisible"
      :title="'采集历史 · ' + (currentSource?.name || '')"
      width="760px"
      align-center
      class="apple-dialog"
      modal-class="apple-modal"
    >
      <div v-loading="historyLoading">
        <div class="card table-card">
          <table class="tbl hist-tbl">
            <thead>
              <tr>
                <th style="width:170px">时间</th>
                <th>采集器</th>
                <th style="width:70px">抓取</th>
                <th style="width:70px">新增</th>
                <th style="width:70px">分析</th>
                <th style="width:80px">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in history" :key="r.id">
                <td>{{ formatTime(r.start_time) }}</td>
                <td>{{ r.collector_name }}</td>
                <td>{{ r.fetched_raw }}</td>
                <td>{{ r.created }}</td>
                <td>{{ r.analyzed }}</td>
                <td><span class="pill" :class="runPill(r.status)">{{ runText(r.status) }}</span></td>
              </tr>
              <tr v-if="!history.length"><td colspan="6" class="empty-row">暂无采集记录</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <template #footer>
        <span class="dlg-foot">
          <button class="btn btn-ghost" @click="historyVisible = false">关闭</button>
        </span>
      </template>
    </el-dialog>

    <!-- 配置弹窗（仅 config_json） -->
    <el-dialog
      v-model="configVisible"
      :title="'配置 · ' + (currentSource?.name || '')"
      width="600px"
      align-center
      class="apple-dialog"
      modal-class="apple-modal"
    >
      <p class="dlg-sub">高级配置（config_json）</p>
      <el-input
        v-model="configDraft"
        type="textarea"
        :rows="10"
        placeholder='如 {"keywords":"河北,石家庄"}'
      />
      <template #footer>
        <span class="dlg-foot">
          <span v-if="configError" class="cfg-err">{{ configError }}</span>
          <button class="btn btn-ghost" @click="configVisible = false">关闭</button>
          <button class="btn btn-primary" :disabled="savingConfig" @click="saveConfig">保存配置</button>
        </span>
      </template>
    </el-dialog>

    <!-- 新建采集源弹窗 -->
    <el-dialog
      v-model="createVisible"
      title="新建采集源"
      width="660px"
      align-center
      class="apple-dialog"
      modal-class="apple-modal"
    >
      <div class="create-form" v-loading="creating">
        <div class="cf-row">
          <label class="cf-label">名称 <span class="req">*</span></label>
          <el-input v-model="form.name" placeholder="如 石家庄市政府网" />
        </div>
        <div class="cf-row">
          <label class="cf-label">标识 key <span class="req">*</span></label>
          <el-input v-model="form.key" placeholder="如 shijiazhuang_gov（字母/数字/下划线，唯一）" />
        </div>
        <div class="cf-row">
          <label class="cf-label">类型</label>
          <el-select v-model="form.type" class="cf-full">
            <el-option label="通用网站（列表 → 详情）" value="generic_site" />
            <el-option label="新闻网站" value="news_site" />
            <el-option label="政府网站" value="gov_site" />
            <el-option label="搜索引擎" value="search" />
            <el-option label="RSS" value="rss" />
          </el-select>
        </div>
        <div class="cf-row">
          <label class="cf-label">区域（不选 = 全国）</label>
          <el-select
            v-model="form.scope_region_codes"
            multiple
            collapse-tags
            clearable
            placeholder="不选 = 全国"
            class="cf-full"
          >
            <el-option v-for="o in regionOptions.slice(1)" :key="o.code" :label="o.name" :value="o.code" />
          </el-select>
        </div>
        <div class="cf-row cf-row-2">
          <div class="cf-col">
            <label class="cf-label">优先级</label>
            <el-input-number v-model="form.priority" :min="0" :max="999" size="small" controls-position="right" />
          </div>
          <div class="cf-col">
            <label class="cf-label">启用</label>
            <el-switch v-model="form.enabled" />
          </div>
        </div>
        <div class="cf-row">
          <label class="cf-label">配置 config_json <span class="req">*</span></label>
          <el-input v-model="form.config_json" type="textarea" :rows="13" placeholder="JSON 配置" />
          <div v-if="createConfigError" class="cfg-err">{{ createConfigError }}</div>
          <div class="cf-hint">保存时会用真实抓取校验：能取到正文才创建成功；否则返回失败提示。</div>
        </div>
      </div>
      <template #footer>
        <span class="dlg-foot">
          <span v-if="testMsg" class="test-msg" :class="testOk ? 'ok' : 'bad'">{{ testMsg }}</span>
          <button class="btn btn-ghost" :disabled="testing" @click="testCreate">测试连接</button>
          <button class="btn btn-ghost" @click="createVisible = false">取消</button>
          <button class="btn btn-primary" :disabled="creating || testing" @click="submitCreate">保存</button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { CollectorRunItem, DataSourceCreateRequest, DataSourceItem, DataSourceTestResult, RegionOption } from '@/types'

interface Row extends DataSourceItem {
  _saving?: boolean
}

const DEFAULT_CONFIG = JSON.stringify(
  {
    source_name: '',
    list_urls: ['https://example.gov.cn/list/'],
    link_rule: { href_contains: '.html', max_links: 20 },
    content_selectors: ['div.content', 'div.article'],
    keywords: '河北,石家庄',
    max_articles: 5,
    timeout: 10,
  },
  null,
  2,
)

const loading = ref(false)
const sources = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const regionOptions = ref<RegionOption[]>([])
const filterRegion = ref<string>('')
const filterEnabled = ref<boolean | ''>('')
const filterQ = ref('')

const historyVisible = ref(false)
const configVisible = ref(false)
const currentSource = ref<Row | null>(null)
const history = ref<CollectorRunItem[]>([])
const historyLoading = ref(false)
const configDraft = ref('')
const configError = ref('')
const savingConfig = ref(false)

// —— 新建采集源 ——
const createVisible = ref(false)
const creating = ref(false)
const testing = ref(false)
const testMsg = ref('')
const testOk = ref(false)
const createConfigError = ref('')
const form = reactive({
  name: '',
  key: '',
  type: 'generic_site',
  scope_region_codes: [] as string[],
  priority: 50,
  enabled: true,
  config_json: DEFAULT_CONFIG,
})

function runPill(s: string): string {
  const m: Record<string, string> = {
    running: 'pill-green', success: 'pill-green', partial: 'pill-orange',
    failed: 'pill-red', error: 'pill-red', unknown: 'pill-gray',
  }
  return m[s] || 'pill-gray'
}
function runText(s: string): string {
  const m: Record<string, string> = {
    running: '运行中', success: '成功', partial: '部分成功',
    failed: '失败', error: '异常', unknown: '未知',
  }
  return m[s] || s
}
function formatTime(t: string | null): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

async function reload() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: size.value }
    if (filterRegion.value) params.region_code = filterRegion.value
    if (filterEnabled.value !== '') params.enabled = filterEnabled.value
    if (filterQ.value) params.q = filterQ.value
    const { data } = await api.get<{ items: Row[]; total: number; region_options: RegionOption[] }>(
      '/admin/data-sources',
      { params },
    )
    sources.value = data.items || []
    total.value = data.total || 0
    if (data.region_options) regionOptions.value = data.region_options
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载数据源失败')
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  reload()
}

async function onToggle(row: Row, val: boolean) {
  const prev = row.enabled
  row.enabled = val
  row._saving = true
  try {
    await api.patch('/admin/data-sources/' + row.id, { enabled: val })
    ElMessage.success(val ? '已启用' : '已停用')
  } catch (e: any) {
    row.enabled = prev
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    row._saving = false
  }
}

async function onPriority(row: Row, val: number) {
  if (val == null || isNaN(val)) return
  const prev = row.priority
  row.priority = val // 乐观更新，即时响应界面
  try {
    await api.patch('/admin/data-sources/' + row.id, { priority: val })
    ElMessage.success('优先级已更新')
  } catch (e: any) {
    row.priority = prev // 失败回滚
    ElMessage.error(e?.response?.data?.detail || '更新失败')
  }
}

async function openHistory(row: Row) {
  currentSource.value = row
  historyVisible.value = true
  configError.value = ''
  historyLoading.value = true
  history.value = []
  try {
    const { data } = await api.get<{ items: CollectorRunItem[] }>(
      '/admin/data-sources/' + row.id + '/runs',
      { params: { page: 1, size: 20 } },
    )
    history.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

function openConfig(row: Row) {
  currentSource.value = row
  configDraft.value = row.config_json || '{}'
  configError.value = ''
  configVisible.value = true
}

async function saveConfig() {
  if (!currentSource.value) return
  configError.value = ''
  try {
    JSON.parse(configDraft.value || '{}')
  } catch {
    configError.value = 'config_json 不是合法 JSON'
    return
  }
  savingConfig.value = true
  try {
    await api.patch('/admin/data-sources/' + currentSource.value.id, {
      config_json: configDraft.value,
    })
    currentSource.value.config_json = configDraft.value
    ElMessage.success('配置已保存')
    configVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    savingConfig.value = false
  }
}

onMounted(reload)

function openCreate() {
  createConfigError.value = ''
  testMsg.value = ''
  testOk.value = false
  createVisible.value = true
}

function buildPayload(): DataSourceCreateRequest {
  // source_name 缺失时回退为名称，保证「查看历史」按 name 关联能命中
  const cfgObj = JSON.parse(form.config_json || '{}')
  if (!cfgObj.source_name) cfgObj.source_name = form.name.trim()
  return {
    name: form.name.trim(),
    key: form.key.trim(),
    type: form.type,
    scope_region_codes: (form.scope_region_codes || []).join(','),
    priority: form.priority,
    enabled: form.enabled,
    config_json: JSON.stringify(cfgObj),
  }
}

async function testCreate() {
  let ok = false
  try {
    JSON.parse(form.config_json || '{}')
  } catch {
    createConfigError.value = 'config_json 不是合法 JSON'
    return
  }
  createConfigError.value = ''
  testing.value = true
  testMsg.value = ''
  try {
    const { data } = await api.post<DataSourceTestResult>('/admin/data-sources/test', buildPayload())
    ok = !!data.ok
    testOk.value = ok
    if (ok) {
      const t = data.test || {}
      testMsg.value =
        `测试通过：列表页获取到 ${t.fetched_links ?? 0} 个链接` +
        (t.sample_content_len ? `，示例详情页正文 ${t.sample_content_len} 字` : '')
    } else {
      testMsg.value = '测试未通过：' + (data.error || '未知原因')
    }
  } catch (e: any) {
    testOk.value = false
    testMsg.value = '测试失败：' + (e?.response?.data?.detail || e?.message || '请求异常')
  } finally {
    testing.value = false
  }
}

async function submitCreate() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  if (!form.key.trim()) {
    ElMessage.warning('请填写标识 key')
    return
  }
  try {
    JSON.parse(form.config_json || '{}')
  } catch {
    createConfigError.value = 'config_json 不是合法 JSON'
    return
  }
  createConfigError.value = ''
  creating.value = true
  try {
    const { data } = await api.post<DataSourceItem & { test?: any }>('/admin/data-sources', buildPayload())
    const t = data.test || {}
    ElMessage.success(`添加成功，测试抓取通过（列表页获取到 ${t.fetched_links ?? 0} 个链接）`)
    createVisible.value = false
    Object.assign(form, {
      name: '', key: '', type: 'generic_site',
      scope_region_codes: [], priority: 50, enabled: true, config_json: DEFAULT_CONFIG,
    })
    reload()
  } catch (e: any) {
    // 后端真实抓取校验失败 / 参数错误 / key 重复：返回失败提示，不关闭弹窗
    ElMessage.error(e?.response?.data?.detail || '添加失败')
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.ds-page { min-height: 100%; }
.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 18px; gap: 12px; flex-wrap: wrap;
}
.filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.f-select { width: 160px; }
.f-input { width: 200px; }
.count-tip { font-size: 13px; color: #86868b; }

.card {
  background: #fff; border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 12px 32px rgba(0,0,0,.05);
  padding: 6px 6px 14px; overflow: hidden;
}
table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
table.tbl thead th {
  text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b;
  padding: 14px 18px; border-bottom: 1px solid #e8e8ed;
}
table.tbl tbody td { padding: 13px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; vertical-align: middle; }
table.tbl tbody tr:last-child td { border-bottom: none; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }

.ds-name { font-size: 14px; font-weight: 600; color: #1d1d1f; }
.ds-key { font-size: 12px; color: #86868b; margin-top: 2px; }

.pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; border-radius: 980px; font-size: 12px; font-weight: 500;
}
.pill-blue { background: rgba(0,122,255,0.1); color: #007aff; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.muted { color: #b0b0b5; }

.pager { display: flex; justify-content: flex-end; margin-top: 16px; }

.btn {
  display: inline-flex; align-items: center; justify-content: center;
  border: none; border-radius: 980px; padding: 8px 16px; font-size: 14px;
  font-weight: 500; cursor: pointer; transition: background-color .18s, opacity .18s;
}
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover { background: #0077ed; }
.btn-primary:disabled { opacity: .55; cursor: default; }
.btn-ghost { background: #f5f5f7; color: #1d1d1f; }
.btn-ghost:hover { background: #e8e8ed; }
.btn-mini { background: transparent; color: #0071e3; padding: 4px 10px; font-size: 13px; }
.btn-mini:hover { background: #e8f1fd; }

.dlg-sub { font-size: 15px; font-weight: 600; margin: 0 0 10px; color: #1d1d1f; }
.table-card {
  padding: 0 6px 14px;     /* 去掉顶部内边距，避免吸顶表头与窗口顶之间出现空隙 */
  max-height: 56vh;        /* 内容过长时弹窗内出现纵向滚动窗 */
  overflow: auto;
  background: #fff;        /* 任何亚像素缝隙显示白色而非底下滚动内容 */
}
/* 苹果风细滚动条 */
.table-card::-webkit-scrollbar { width: 8px; height: 8px; }
.table-card::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 8px; }
.table-card::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.32); }
.table-card::-webkit-scrollbar-track { background: transparent; }
.hist-tbl td, .hist-tbl th { white-space: nowrap; }
.hist-tbl thead th {
  position: sticky; top: 0; z-index: 2;
  background: #fff;        /* 不透明背景，滚动内容不会从表头下方透出 */
  border-bottom: 1px solid #e8e8ed;  /* 实线分隔，避免阴影抗锯齿造成的缝隙 */
}
.hist-tbl td { padding: 12px 18px; }
.dlg-foot { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.cfg-err { color: #ff3b30; font-size: 12.5px; margin-right: auto; }

/* 工具栏右侧：计数 + 新建按钮 */
.toolbar-right { display: flex; align-items: center; gap: 14px; }
/* 新建采集源表单 */
.create-form { display: flex; flex-direction: column; gap: 16px; }
.cf-row { display: flex; flex-direction: column; gap: 6px; }
.cf-row-2 { flex-direction: row; gap: 28px; }
.cf-col { display: flex; flex-direction: column; gap: 6px; }
.cf-label { font-size: 13px; font-weight: 500; color: #1d1d1f; }
.cf-label .req { color: #ff3b30; }
.cf-full { width: 100%; }
.cf-hint { font-size: 12px; color: #86868b; }
.test-msg { font-size: 12.5px; margin-right: auto; }
.test-msg.ok { color: #1a8e3c; }
.test-msg.bad { color: #ff3b30; }
</style>

<style>
/* 苹果风弹窗：仅作用于带 apple-dialog 类的 el-dialog（被 teleport 到 body，需全局样式） */
.apple-dialog {
  border-radius: 22px;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.22), 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  background: #fff;
}
.apple-dialog .el-dialog__header {
  padding: 22px 26px 10px;
  margin-right: 0;
}
.apple-dialog .el-dialog__title {
  font-size: 17px;
  font-weight: 600;
  color: #1d1d1f;
  letter-spacing: 0.2px;
}
.apple-dialog .el-dialog__headerbtn {
  top: 20px;
  right: 20px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  transition: background-color 0.18s;
}
.apple-dialog .el-dialog__headerbtn:hover {
  background: #f0f0f3;
}
.apple-dialog .el-dialog__headerbtn .el-dialog__close {
  color: #86868b;
  font-size: 18px;
  font-weight: 400;
}
.apple-dialog .el-dialog__headerbtn:hover .el-dialog__close {
  color: #1d1d1f;
}
.apple-dialog .el-dialog__body {
  padding: 4px 26px 10px;
  color: #1d1d1f;
  font-size: 14px;
}
.apple-dialog .el-dialog__footer {
  padding: 14px 26px 22px;
}

/* 背景遮罩毛玻璃 */
.apple-modal {
  background: rgba(0, 0, 0, 0.34);
  backdrop-filter: saturate(160%) blur(8px);
  -webkit-backdrop-filter: saturate(160%) blur(8px);
}
</style>
