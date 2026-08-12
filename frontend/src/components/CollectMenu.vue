<template>
  <div v-if="canShowMenu" ref="wrapRef" class="collect-menu-wrap">
    <button class="cm-trigger" :disabled="collecting" @click="toggle">
      <span>采集</span>
      <span class="cm-chevron" :class="{ open }">▾</span>
    </button>

    <div v-if="open" class="collect-menu" @click.stop>
      <!-- 采集数据（国内） -->
      <button
        v-if="canCollectDomestic"
        class="cm-item"
        :disabled="collecting"
        title="采集全部已启用的国内数据源（舆情监测系统），完成后自动触发预警评估"
        @click="onDomestic"
      >
        <span class="cm-ico">🛰️</span>
        <span class="cm-text">
          <span class="cm-label">采集数据</span>
          <span class="cm-desc">国内数据源全量采集</span>
        </span>
      </button>

      <!-- 采集外网 RSS（按所选来源，可展开「选择来源」） -->
      <div v-if="canCollectSelected" class="cm-group">
        <button
          class="cm-item"
          :disabled="collecting || !selectedSourceIds.length"
          title="按所选外网来源采集 RSS 资讯；点击「选择来源」可指定采集范围"
          @click="onForeignSelected"
        >
          <span class="cm-ico">🌐</span>
          <span class="cm-text">
            <span class="cm-label">采集外网 RSS</span>
            <span class="cm-desc">已选 {{ selectedSourceIds.length }} 个来源</span>
          </span>
        </button>
        <button
          class="cm-sub-toggle"
          :disabled="collecting"
          :title="showPicker ? '收起选择来源' : '展开选择来源'"
          @click.stop="showPicker = !showPicker"
        >
          选择来源 {{ showPicker ? '▲' : '▼' }}
        </button>
        <div v-if="showPicker" class="cm-picker">
          <label v-for="s in approvedSources" :key="s.id" class="cm-source">
            <input v-model="selectedSourceIds" type="checkbox" :value="s.id" :disabled="collecting" />
            <span>{{ s.name }}</span>
          </label>
          <span v-if="!approvedSources.length" class="cm-muted">加载来源中…</span>
          <button
            class="cm-start"
            :disabled="collecting || !selectedSourceIds.length"
            @click.stop="onForeignSelected"
          >
            开始采集（{{ selectedSourceIds.length }}）
          </button>
        </div>
      </div>

      <!-- 采集全部已启用外网数据源 -->
      <button
        v-if="canCollectAll"
        class="cm-item"
        :disabled="collecting"
        title="采集所有已启用的外网数据源（需二次确认）"
        @click="onForeignAll"
      >
        <span class="cm-ico">🌍</span>
        <span class="cm-text">
          <span class="cm-label">采集全部已启用外网数据源</span>
          <span class="cm-desc">全部外网来源</span>
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useCollectionActions } from '@/composables/useCollectionActions'

const {
  collecting,
  approvedSources,
  selectedSourceIds,
  canShowMenu,
  canCollectDomestic,
  canCollectSelected,
  canCollectAll,
  loadApprovedSources,
  collectDomestic,
  collectForeignSelected,
  collectForeignAll,
} = useCollectionActions()

const open = ref(false)
const showPicker = ref(false)
const wrapRef = ref<HTMLElement | null>(null)

function toggle() {
  open.value = !open.value
  if (open.value) loadApprovedSources()
}
function close() {
  open.value = false
  showPicker.value = false
}
function onClickOutside(e: MouseEvent) {
  if (open.value && wrapRef.value && !wrapRef.value.contains(e.target as Node)) close()
}
function onKeyEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}
function onDomestic() {
  collectDomestic()
  close()
}
function onForeignSelected() {
  collectForeignSelected()
  close()
}
function onForeignAll() {
  collectForeignAll()
  close()
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  window.addEventListener('keydown', onKeyEsc)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
  window.removeEventListener('keydown', onKeyEsc)
})
</script>

<style scoped>
.collect-menu-wrap {
  position: relative;
  display: inline-flex;
}
/* 触发按钮：复刻原「采集数据」蓝色圆角主按钮观感 */
.cm-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  line-height: 1;
  color: #fff;
  background: #0071e3;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.18s ease, transform 0.12s ease, opacity 0.18s ease;
}
.cm-trigger:hover:not(:disabled) {
  background: #0077ed;
}
.cm-trigger:active:not(:disabled) {
  transform: scale(0.98);
}
.cm-trigger:disabled {
  opacity: 0.55;
  cursor: default;
}
.cm-chevron {
  display: inline-block;
  margin-left: 6px;
  font-size: 11px;
  transition: transform 0.15s ease;
}
.cm-chevron.open {
  transform: rotate(180deg);
}
.collect-menu {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: 280px;
  background: #fff;
  border: 1px solid #e8e8ed;
  border-radius: 14px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  padding: 6px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cm-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  background: transparent;
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
  color: #1d1d1f;
  font: inherit;
  transition: background-color 0.15s ease;
}
.cm-item:hover:not(:disabled) {
  background: #f0f0f3;
}
.cm-item:disabled {
  opacity: 0.5;
  cursor: default;
}
.cm-ico {
  font-size: 16px;
  flex: 0 0 auto;
}
.cm-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.cm-label {
  font-size: 14px;
  font-weight: 500;
}
.cm-desc {
  font-size: 11.5px;
  color: #86868b;
}
.cm-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
  border-top: 1px solid #f0f0f3;
  border-bottom: 1px solid #f0f0f3;
}
.cm-sub-toggle {
  align-self: flex-end;
  margin: 2px 4px 4px;
  border: none;
  background: transparent;
  color: #0071e3;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 8px;
}
.cm-sub-toggle:hover:not(:disabled) {
  background: #e8f1fd;
}
.cm-sub-toggle:disabled {
  opacity: 0.5;
  cursor: default;
}
.cm-picker {
  margin: 0 4px 6px;
  padding: 8px;
  background: #f7f7f9;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  overflow-y: auto;
}
.cm-source {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #1d1d1f;
  cursor: pointer;
}
.cm-source input {
  width: 15px;
  height: 15px;
  accent-color: #0071e3;
}
.cm-muted {
  font-size: 12px;
  color: #86868b;
}
.cm-start {
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 500;
  color: #fff;
  background: #0071e3;
  cursor: pointer;
  transition: background-color 0.18s ease;
}
.cm-start:hover:not(:disabled) {
  background: #0077ed;
}
.cm-start:disabled {
  opacity: 0.55;
  cursor: default;
}
</style>
