<template>
  <div class="ai-search-page">
    <section class="search-panel">
      <el-form class="search-form" :model="form" label-position="top" @submit.prevent="search">
        <el-form-item label="查询关键词" class="keyword-field">
          <el-input v-model="form.query" size="large" clearable maxlength="512" placeholder="输入企业、事件、地点或风险关键词" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-select v-model="form.freshness" size="large">
            <el-option label="不限时间" value="noLimit" />
            <el-option label="最近一天" value="oneDay" />
            <el-option label="最近一周" value="oneWeek" />
            <el-option label="最近一月" value="oneMonth" />
            <el-option label="最近一年" value="oneYear" />
          </el-select>
        </el-form-item>
        <el-form-item label="返回数量">
          <el-input-number v-model="form.count" size="large" :min="1" :max="50" controls-position="right" />
        </el-form-item>
        <el-form-item label="来源范围">
          <el-select v-model="form.source" size="large">
            <el-option label="全网" value="all" />
            <el-option label="微博" value="weibo" />
            <el-option label="小红书" value="xiaohongshu" />
            <el-option label="自定义域名" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.source === 'custom'" label="自定义域名" class="custom-field">
          <el-input v-model="form.customInclude" size="large" placeholder="example.com|news.example.com" />
        </el-form-item>
        <el-form-item label="AI 总结">
          <el-switch v-model="form.answer" active-text="开启" inactive-text="关闭" />
        </el-form-item>
        <el-button class="search-button" type="primary" size="large" :loading="searching" @click="search">搜索</el-button>
      </el-form>
      <p class="source-notice">include 只是搜索域名限制，不代表拥有微博或小红书官方数据权限；登录限制、反爬限制和未收录内容仍可能无法返回。</p>
    </section>

    <el-alert v-if="errorMessage" class="state-alert" type="error" :closable="false" :title="errorMessage" />

    <section class="ai-content" v-loading="searching">
      <div class="main-column">
        <section v-if="answer || session" class="result-section answer-section">
          <div class="section-head"><h2>AI 总结</h2><span v-if="session">{{ session.answer_enabled ? '已启用' : '未启用' }}</span></div>
          <p v-if="answer" class="answer-text">{{ answer }}</p>
          <el-empty v-else description="本次搜索未返回 AI 总结" :image-size="68" />
        </section>

        <section class="result-section">
          <div class="section-head"><h2>参考网页</h2><span>{{ pages.length }} 条</span></div>
          <div v-if="pages.length" class="page-list">
            <article v-for="item in pages" :key="item.result_index ?? item.url" class="page-item">
              <div class="page-main">
                <div class="page-title-row">
                  <a class="page-title" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.title || item.url }}</a>
                  <el-tag size="small" effect="plain">{{ sourceTypeText(item.source_type) }}</el-tag>
                </div>
                <div class="page-meta"><span>{{ item.source_domain || '未知来源' }}</span><span v-if="item.publish_time">{{ formatTime(item.publish_time) }}</span></div>
                <p class="page-snippet">{{ item.snippet || '暂无摘要' }}</p>
                <a class="citation-link" :href="item.citation_url || item.url" target="_blank" rel="noopener noreferrer">引用链接</a>
              </div>
              <el-button type="primary" plain :disabled="savedIndexes.has(item.result_index ?? 0) || !session" :loading="savingIndex === (item.result_index ?? 0)" @click="saveLead(item)">
                {{ savedIndexes.has(item.result_index ?? 0) ? '已保存' : '保存为线索' }}
              </el-button>
            </article>
          </div>
          <el-empty v-else-if="!searching" description="暂无参考网页" :image-size="80" />
        </section>

        <section v-if="followUpQuestions.length" class="result-section">
          <div class="section-head"><h2>追问问题</h2><span>{{ followUpQuestions.length }} 条</span></div>
          <div class="question-list"><button v-for="question in followUpQuestions" :key="question" type="button" @click="form.query = question">{{ question }}</button></div>
        </section>
      </div>

      <aside class="side-column">
        <section class="result-section">
          <div class="section-head"><h2>图片结果</h2><span>{{ images.length }} 条</span></div>
          <div v-if="images.length" class="image-list">
            <a v-for="(image, index) in images" :key="String(image.url || image.imageUrl || image.src || index)" :href="image.url || image.imageUrl || image.src || '#'" target="_blank" rel="noopener noreferrer" class="image-item">
              <img v-if="image.url || image.imageUrl || image.src" :src="String(image.url || image.imageUrl || image.src)" :alt="String(image.title || '搜索图片')" loading="lazy" />
              <span>{{ image.title || image.url || image.imageUrl || '查看图片' }}</span>
            </a>
          </div>
          <el-empty v-else-if="!searching" description="暂无图片结果" :image-size="64" />
        </section>
        <section class="result-section">
          <div class="section-head"><h2>模态卡</h2><span>{{ modalCards.length }} 条</span></div>
          <div v-if="modalCards.length" class="modal-list">
            <article v-for="(card, index) in modalCards" :key="index" class="modal-item">
              <strong>{{ card.title || card.name || `卡片 ${index + 1}` }}</strong>
              <p>{{ card.description || card.content || card.text || JSON.stringify(card) }}</p>
            </article>
          </div>
          <el-empty v-else-if="!searching" description="暂无模态卡" :image-size="64" />
        </section>
      </aside>
    </section>

    <section v-if="session" class="raw-section">
      <details><summary>查看原始 JSON</summary><pre>{{ JSON.stringify(rawResponse, null, 2) }}</pre></details>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { storeToRefs } from 'pinia'
import { useBochaAiSearchStore, type AiWebPage } from '@/stores/bochaAi'

const store = useBochaAiSearchStore()
const { form, session, pages, images, modalCards, followUpQuestions, savedIndexes } = storeToRefs(store)
const searching = ref(false)
const savingIndex = ref<number | null>(null)
const errorMessage = ref('')
const rawResponse = ref<Record<string, unknown>>({})
const answer = computed(() => session.value?.answer || '')
const platformIncludes = ref({ weibo: '', xiaohongshu: '' })

onMounted(async () => {
  try {
    const { data } = await api.get('/bocha/ai-search/options')
    if (data.platform_includes) platformIncludes.value = { ...platformIncludes.value, ...data.platform_includes }
  } catch { /* use configured defaults when options are unavailable */ }
})

function buildInclude() {
  if (form.value.source === 'weibo') return platformIncludes.value.weibo || '__missing__'
  if (form.value.source === 'xiaohongshu') return platformIncludes.value.xiaohongshu || '__missing__'
  if (form.value.source === 'custom') return form.value.customInclude.trim()
  return undefined
}

async function search() {
  const query = form.value.query.trim()
  const include = buildInclude()
  if ((form.value.source === 'weibo' || form.value.source === 'xiaohongshu') && include === '__missing__') return
  if (!query) { ElMessage.warning('请输入查询关键词'); return }
  if (form.value.source === 'custom' && !buildInclude()) { ElMessage.warning('请输入自定义域名'); return }
  searching.value = true
  errorMessage.value = ''
  try {
    const { data } = await api.post('/bocha/ai-search', {
      query,
      freshness: form.value.freshness,
      include: include === '__missing__' ? undefined : include,
      count: Math.min(Math.max(form.value.count, 1), 50),
      answer: form.value.answer,
      stream: false,
    }, { timeout: 35000 })
    store.setResult(data.session, data.web_pages || [], data.images || [], data.modal_cards || [], data.follow_up_questions || [])
    rawResponse.value = data.raw_response || {}
    ElMessage.success(`搜索完成，返回 ${data.total || 0} 条网页结果`)
  } catch (err: any) {
    if (err?.code === 'ECONNABORTED' || err?.message?.toLowerCase().includes('timeout')) errorMessage.value = 'AI Search 请求超时，请稍后重试'
    else errorMessage.value = err?.response?.data?.detail || 'AI Search 暂时不可用，请稍后重试'
  } finally { searching.value = false }
}

async function saveLead(item: AiWebPage) {
  if (!session.value || item.result_index == null) return
  savingIndex.value = item.result_index
  try {
    await api.post('/bocha/ai-leads', { session_id: session.value.id, result_index: item.result_index })
    store.markSaved(item.result_index)
    ElMessage.success('已保存为 AI Search 线索')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '保存线索失败')
  } finally { savingIndex.value = null }
}

function sourceTypeText(value: string) {
  return ({ weibo: '微博', xiaohongshu: '小红书', web: '网页' } as Record<string, string>)[value] || value || '网页'
}

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.ai-search-page { min-width: 0; }
.search-panel, .result-section, .raw-section { background: #fff; border: 1px solid var(--el-border-color-lighter); border-radius: 10px; }
.search-panel { padding: 18px 20px; margin-bottom: 16px; }
.search-form { display: grid; grid-template-columns: minmax(220px, 1fr) 150px 130px 150px 150px 110px; gap: 12px; align-items: end; }
.keyword-field { min-width: 0; }
.search-button { width: 100%; }
.source-notice { margin: 6px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
.state-alert { margin-bottom: 16px; }
.ai-content { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 16px; align-items: start; }
.main-column, .side-column { display: grid; gap: 16px; min-width: 0; }
.result-section { padding: 16px; min-width: 0; }
.section-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 12px; color: var(--el-text-color-secondary); font-size: 13px; }
.section-head h2 { margin: 0; color: var(--el-text-color-primary); font-size: 17px; }
.answer-text { margin: 0; white-space: pre-wrap; line-height: 1.75; color: var(--el-text-color-regular); }
.page-list { display: grid; gap: 0; }
.page-item { display: flex; justify-content: space-between; gap: 16px; padding: 14px 0; border-top: 1px solid var(--el-border-color-lighter); }
.page-item:first-child { border-top: 0; padding-top: 0; }
.page-main { min-width: 0; }
.page-title-row { display: flex; gap: 8px; align-items: center; }
.page-title { color: var(--el-color-primary); font-weight: 600; line-height: 1.4; overflow-wrap: anywhere; }
.page-meta { display: flex; gap: 12px; margin-top: 5px; color: var(--el-text-color-secondary); font-size: 12px; }
.page-snippet { margin: 7px 0; line-height: 1.5; color: var(--el-text-color-regular); }
.citation-link { font-size: 12px; }
.question-list { display: flex; flex-wrap: wrap; gap: 8px; }
.question-list button { max-width: 100%; padding: 7px 10px; border: 1px solid var(--el-border-color); border-radius: 6px; background: #fff; color: var(--el-color-primary); cursor: pointer; text-align: left; overflow-wrap: anywhere; }
.image-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.image-item { display: grid; gap: 5px; min-width: 0; color: var(--el-color-primary); font-size: 12px; }
.image-item img { width: 100%; aspect-ratio: 1.35; object-fit: cover; border-radius: 6px; background: var(--el-fill-color-light); }
.image-item span { overflow-wrap: anywhere; }
.modal-list { display: grid; gap: 10px; }
.modal-item { padding: 10px; background: var(--el-fill-color-light); border-radius: 6px; }
.modal-item p { margin: 5px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--el-text-color-regular); font-size: 13px; line-height: 1.5; }
.raw-section { margin-top: 16px; padding: 12px 16px; }
.raw-section pre { max-height: 360px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; }
@media (max-width: 1100px) { .search-form { grid-template-columns: minmax(220px, 1fr) repeat(3, minmax(120px, 1fr)); } .custom-field { grid-column: span 2; } .search-button { grid-column: span 1; } }
@media (max-width: 760px) { .search-form { grid-template-columns: 1fr 1fr; } .keyword-field, .custom-field { grid-column: 1 / -1; } .ai-content { grid-template-columns: 1fr; } .page-item { align-items: flex-start; flex-direction: column; } .page-item .el-button { align-self: flex-start; } }
</style>
