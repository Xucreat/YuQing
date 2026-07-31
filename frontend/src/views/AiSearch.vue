<template>
  <div class="ai-search-shell">
    <nav class="search-tabs" aria-label="AI 检索模式">
      <button
        class="search-tab"
        :class="{ active: !isAiSearch && !isAnspireSearch }"
        type="button"
        :disabled="(!isAiSearch && !isAnspireSearch) && navigating"
        @click="go('/ai-search/web')"
      >
        Bocha 网页搜索
      </button>
      <button
        class="search-tab"
        :class="{ active: isAiSearch }"
        type="button"
        :disabled="isAiSearch && navigating"
        @click="go('/ai-search/ai')"
      >
        AI 搜索（Bocha）
      </button>
      <button class="search-tab" :class="{ active: isAnspireSearch }" type="button" @click="go('/ai-search/anspire')">Anspire 网页搜索</button>
    </nav>

    <div class="search-tab-content" :class="{ loading: navigating }">
      <AnspireSearch v-if="isAnspireSearch" />
      <WebSearch v-else-if="!isAiSearch" />
      <AiSearchPanel v-else />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WebSearch from './WebSearch.vue'
import AiSearchPanel from './AiSearchPanel.vue'
import AnspireSearch from './AnspireSearch.vue'

const route = useRoute()
const router = useRouter()
const navigating = ref(false)
const isAiSearch = computed(() => route.path === '/ai-search/ai')
const isAnspireSearch = computed(() => route.path === '/ai-search/anspire')

async function go(path: string) {
  if (route.path === path || navigating.value) return
  navigating.value = true
  try {
    await router.push(path)
  } finally {
    navigating.value = false
  }
}
</script>

<style scoped>
.ai-search-shell {
  min-width: 0;
}

.search-tabs {
  display: flex;
  gap: 6px;
  min-height: 44px;
  margin-bottom: 16px;
  overflow-x: auto;
  border-bottom: 1px solid var(--el-border-color-lighter);
  scrollbar-width: thin;
}

.search-tab {
  flex: 0 0 auto;
  min-width: 112px;
  height: 44px;
  padding: 0 18px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: color .2s ease, border-color .2s ease;
}

.search-tab:hover:not(:disabled),
.search-tab.active {
  color: var(--el-color-primary);
}

.search-tab.active {
  border-bottom-color: var(--el-color-primary);
}

.search-tab:disabled {
  cursor: wait;
  opacity: .75;
}

.search-tab-content {
  min-height: 0;
  transition: opacity .15s ease;
}

.search-tab-content.loading {
  opacity: .72;
}

@media (max-width: 640px) {
  .search-tabs {
    margin-bottom: 12px;
  }

  .search-tab {
    min-width: 104px;
    padding: 0 14px;
  }
}
</style>
