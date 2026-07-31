<template>
  <div class="dm-page">
    <!-- 横向导航栏：在两个子页面间切换 -->
    <div class="segmented" role="tablist">
      <button
        v-if="canReadKeyword"
        class="seg"
        :class="{ active: tab === 'keywords' }"
        role="tab"
        :aria-selected="tab === 'keywords'"
        @click="switchTab('keywords')"
      >
        关键词管理
      </button>
      <button
        v-if="isSuperuser"
        class="seg"
        :class="{ active: tab === 'sources' }"
        role="tab"
        :aria-selected="tab === 'sources'"
        @click="switchTab('sources')"
      >
        数据源管理
      </button>
      <button
        v-if="isSuperuser"
        class="seg"
        :class="{ active: tab === 'logs' }"
        role="tab"
        :aria-selected="tab === 'logs'"
        @click="switchTab('logs')"
      >
        采集日志
      </button>
      <button
        v-if="isSuperuser"
        class="seg"
        :class="{ active: tab === 'bocha-leads' }"
        role="tab"
        :aria-selected="tab === 'bocha-leads'"
        @click="switchTab('bocha-leads')"
      >
        AI线索审核
      </button>
    </div>

    <!-- 子页面：keep-alive 保留各自状态（筛选/弹窗等） -->
    <keep-alive>
      <KeywordsView v-if="tab === 'keywords' && canReadKeyword" />
      <SourcesView v-else-if="tab === 'sources' && isSuperuser" />
      <CollectionLogView v-else-if="tab === 'logs' && isSuperuser" />
      <BochaLeadReviewView v-else-if="tab === 'bocha-leads' && isSuperuser" />
      <el-empty v-else description="权限不足，请联系管理员" />
    </keep-alive>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePermission } from '@/composables/usePermission'
import KeywordsView from '@/views/Keywords.vue'
import SourcesView from '@/views/Sources.vue'
import CollectionLogView from '@/views/CollectionLog.vue'
import BochaLeadReviewView from '@/views/BochaLeadReview.vue'

type TabKey = 'keywords' | 'sources' | 'logs' | 'bocha-leads'

const route = useRoute()
const router = useRouter()
// 数据源接口后端实际使用 require_admin（即超管专属），与 sources:read/write 种子权限不一致；
// 前端据此将「数据源管理」tab 仅对超管可见，不按 sources:* 判断（RBAC-2C 审计结论）。
const { isSuperuser, hasPermission } = usePermission()
// RBAC-1：无 keywords:read 的用户不展示「关键词管理」tab（后端读接口亦已加 keywords:read）
const canReadKeyword = computed(() => hasPermission('keywords:read'))

// 初始 tab 来自路由 query（支持 /data?tab=sources 直达），默认关键词管理；
// 非超管即使带 ?tab=sources 也强制回退（后端会 403）；无关键词读权限时回退到超管可见页。
function resolveInitialTab(): TabKey {
  const q = route.query.tab
  if (isSuperuser.value && (q === 'sources' || q === 'logs' || q === 'bocha-leads')) return q as TabKey
  if (canReadKeyword.value) return 'keywords'
  return isSuperuser.value ? 'sources' : 'keywords'
}
const tab = ref<TabKey>(resolveInitialTab())

function switchTab(t: TabKey) {
  if (t === tab.value) return
  tab.value = t
  // 同步到 URL，方便刷新/分享后停留在同一子页
  router.replace({ query: { ...route.query, tab: t } })
}
</script>

<style scoped>
.dm-page { min-height: 100%; }
.segmented {
  display: inline-flex;
  max-width: 100%;
  background: #f0f0f3;
  border-radius: 12px;
  padding: 4px;
  gap: 4px;
  margin-bottom: 20px;
  overflow-x: auto;
  overflow-y: hidden;
  box-sizing: border-box;
  -webkit-overflow-scrolling: touch;
}
.seg {
  flex: 0 0 auto;
  border: none;
  background: transparent;
  padding: 8px 20px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 500;
  color: #1d1d1f;
  cursor: pointer;
  transition: background-color 0.18s, box-shadow 0.18s, color 0.18s;
  user-select: none;
}
.seg:hover { color: #0071e3; }
.seg.active {
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  font-weight: 600;
  color: #1d1d1f;
}
</style>
