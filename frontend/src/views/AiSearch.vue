<template>
  <div class="ai-search-shell">
    <Teleport to="#page-nav-target">
    <div class="page-nav">
      <div class="head-left">
        <h1 class="page-title">AI检索</h1>
        <div class="view-tabs">
          <button
            class="view-tab"
            :class="{ active: !isAiSearch && !isAnspireSearch }"
            type="button"
            :disabled="(!isAiSearch && !isAnspireSearch) && navigating"
            @click="go('/ai-search/web')"
          >
            Bocha 网页搜索
          </button>
          <button
            class="view-tab"
            :class="{ active: isAiSearch }"
            type="button"
            :disabled="isAiSearch && navigating"
            @click="go('/ai-search/ai')"
          >
            AI 搜索（Bocha）
          </button>
          <button class="view-tab" :class="{ active: isAnspireSearch }" type="button" @click="go('/ai-search/anspire')">Anspire 网页搜索</button>
        </div>
      </div>
    </div>
    </Teleport>

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

.search-tab-content {
  min-height: 0;
  transition: opacity .15s ease;
}

.search-tab-content.loading {
  opacity: .72;
}

</style>
