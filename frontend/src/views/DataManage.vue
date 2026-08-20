<template>
  <div class="dm-page">
    <Teleport defer to="#page-nav-target">
    <div class="page-nav">
      <div class="head-left">
        <h1 class="page-title">数据管理</h1>
        <div class="view-tabs">
          <button
            v-if="canReadKeyword"
            class="view-tab"
            :class="{ active: tab === 'keywords' }"
            role="tab"
            :aria-selected="tab === 'keywords'"
            @click="switchTab('keywords')"
          >
            关键词管理
          </button>
          <button
            v-if="canReadSource"
            class="view-tab"
            :class="{ active: tab === 'sources' }"
            role="tab"
            :aria-selected="tab === 'sources'"
            @click="switchTab('sources')"
          >
            数据源管理
          </button>
          <button
            v-if="canReadSource"
            class="view-tab"
            :class="{ active: tab === 'logs' }"
            role="tab"
            :aria-selected="tab === 'logs'"
            @click="switchTab('logs')"
          >
            采集日志
          </button>
          <button
            v-if="isSuperuser"
            class="view-tab"
            :class="{ active: tab === 'bocha-leads' }"
            role="tab"
            :aria-selected="tab === 'bocha-leads'"
            @click="switchTab('bocha-leads')"
          >
            AI线索审核
          </button>
        </div>
      </div>

      <template v-if="showScopeSwitch">
        <div class="head-divider"></div>
        <div class="scope-switch">
          <button
            class="scope-btn"
            :class="{ active: scope === 'domestic' }"
            role="tab"
            :aria-selected="scope === 'domestic'"
            @click="scope = 'domestic'"
          >
            国内
          </button>
          <button
            class="scope-btn"
            :class="{ active: scope === 'foreign' }"
            role="tab"
            :aria-selected="scope === 'foreign'"
            @click="scope = 'foreign'"
          >
            外网
          </button>
        </div>
      </template>
    </div>
    </Teleport>

    <!-- 子页面：keep-alive 保留各自状态（筛选/弹窗等） -->
    <keep-alive>
      <KeywordsView v-if="tab === 'keywords' && canReadKeyword && scope === 'domestic'" />
      <ForeignKeywordsView v-else-if="tab === 'keywords' && canReadKeyword && scope === 'foreign'" />
      <SourcesView v-else-if="tab === 'sources' && canReadSource && scope === 'domestic'" />
      <ForeignSourcesView v-else-if="tab === 'sources' && canReadSource && scope === 'foreign'" />
      <CollectionLogView v-else-if="tab === 'logs' && canReadSource && scope === 'domestic'" />
      <ForeignCollectionLogView v-else-if="tab === 'logs' && canReadSource && scope === 'foreign'" />
      <BochaLeadReviewView v-else-if="tab === 'bocha-leads' && isSuperuser" />
      <el-empty v-else description="权限不足，请联系管理员" />
    </keep-alive>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePermission } from '@/composables/usePermission'
import KeywordsView from '@/views/Keywords.vue'
import SourcesView from '@/views/Sources.vue'
import CollectionLogView from '@/views/CollectionLog.vue'
import BochaLeadReviewView from '@/views/BochaLeadReview.vue'
import ForeignKeywordsView from '@/views/foreign/ForeignKeywordsView.vue'
import ForeignSourcesView from '@/views/foreign/ForeignSourcesView.vue'
import ForeignCollectionLogView from '@/views/foreign/ForeignCollectionLogView.vue'

type TabKey = 'keywords' | 'sources' | 'logs' | 'bocha-leads'
type ScopeKey = 'domestic' | 'foreign'

const route = useRoute()
const router = useRouter()
// 数据源读接口后端已使用 sources:read 权限（非 require_admin），前端应与后端保持一致；
// 管理操作（增删改/启停）后端仍 require_admin，前端 SourcesView 内部按钮已做区分。
const { isSuperuser, hasPermission } = usePermission()
// RBAC-1：无 keywords:read 的用户不展示「关键词管理」tab（后端读接口亦已加 keywords:read）
const canReadKeyword = computed(() => hasPermission('keywords:read'))
// SEC3-02-fix：数据源+采集日志 tab 使用 sources:read 权限门控，与后端读接口一致
const canReadSource = computed(() => hasPermission('sources:read'))
// 外网子页门禁：外网关键词/数据源/采集日志分别对应独立的 foreign:* 权限
const canReadForeignKeyword = computed(() => hasPermission('foreign:keywords:read'))
const canReadForeignSource = computed(() => hasPermission('foreign:sources:read'))
// 采集日志（含外网）后端复用 foreign:sources:read
const canReadForeignLog = canReadForeignSource

// 初始 tab 来自路由 query（支持 /data?tab=sources 直达），默认关键词管理；
// 非超管即使带 ?tab=sources 也强制回退（后端会 403）；无关键词读权限时回退到超管可见页。
function resolveInitialTab(): TabKey {
  const q = route.query.tab
  if (q === 'bocha-leads' && isSuperuser.value) return q as TabKey
  if ((q === 'sources' || q === 'logs') && canReadSource.value) return q as TabKey
  if (canReadKeyword.value) return 'keywords'
  if (canReadSource.value) return 'sources'
  return 'keywords'
}
const tab = ref<TabKey>(resolveInitialTab())
// 国内/外网二级切换，跨关键词/数据源/采集日志三个子页共享
const scope = ref<ScopeKey>(route.query.scope === 'foreign' ? 'foreign' : 'domestic')
// 当前子页是否具备外网版本且用户有权访问
const canUseForeign = computed(() => {
  if (tab.value === 'keywords') return canReadForeignKeyword.value
  if (tab.value === 'sources') return canReadForeignSource.value
  if (tab.value === 'logs') return canReadForeignLog.value
  return false
})
const showScopeSwitch = computed(() => canUseForeign.value)
// 切换到无外网权限的子页时回落到国内，避免出现空白
watch(canUseForeign, (ok) => { if (!ok) scope.value = 'domestic' })
watch(
  () => route.query.scope,
  (value) => {
    const requested = value === 'foreign' ? 'foreign' : 'domestic'
    if (requested !== scope.value) scope.value = requested
  },
)
// 修复：从其他子页面（或站外）经 router.push 带 ?tab=... 跳转时，
// 组件已挂载不会重新初始化 tab，需监听 query.tab 变化以切换子页。
watch(
  () => route.query.tab,
  () => {
    const t = resolveInitialTab()
    if (t !== tab.value) tab.value = t
  },
)
watch(scope, (value) => {
  if (route.query.scope === value) return
  router.replace({ query: { ...route.query, scope: value } })
})

function switchTab(t: TabKey) {
  if (t === tab.value) return
  tab.value = t
  // 同步到 URL，方便刷新/分享后停留在同一子页
  router.replace({ query: { ...route.query, tab: t } })
}
</script>

<style scoped>
.dm-page { min-height: 100%; }
</style>
