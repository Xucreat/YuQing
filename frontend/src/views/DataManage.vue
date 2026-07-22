<template>
  <div class="dm-page">
    <!-- 横向导航栏：在两个子页面间切换 -->
    <div class="segmented" role="tablist">
      <button
        class="seg"
        :class="{ active: tab === 'keywords' }"
        role="tab"
        :aria-selected="tab === 'keywords'"
        @click="switchTab('keywords')"
      >
        关键词管理
      </button>
      <button
        class="seg"
        :class="{ active: tab === 'sources' }"
        role="tab"
        :aria-selected="tab === 'sources'"
        @click="switchTab('sources')"
      >
        数据源管理
      </button>
    </div>

    <!-- 子页面：keep-alive 保留各自状态（筛选/弹窗等） -->
    <keep-alive>
      <KeywordsView v-if="tab === 'keywords'" />
      <SourcesView v-else />
    </keep-alive>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import KeywordsView from '@/views/Keywords.vue'
import SourcesView from '@/views/Sources.vue'

type TabKey = 'keywords' | 'sources'

const route = useRoute()
const router = useRouter()

// 初始 tab 来自路由 query（支持 /data?tab=sources 直达），默认关键词管理
const tab = ref<TabKey>(route.query.tab === 'sources' ? 'sources' : 'keywords')

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
  background: #f0f0f3;
  border-radius: 12px;
  padding: 4px;
  gap: 4px;
  margin-bottom: 20px;
}
.seg {
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
