<template>
  <div class="seg-group">
    <button
      v-for="opt in options"
      :key="opt.value"
      class="seg-btn"
      :class="{ active: modelValue === opt.value }"
      @click="$emit('update:modelValue', opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: string | number
  options: { label: string; value: string | number }[]
}>()

defineEmits<{
  'update:modelValue': [value: string | number]
}>()
</script>

<style scoped>
.seg-group {
  display: inline-flex;
  background: #e8e8ed;
  border-radius: 980px;
  padding: 3px;
  gap: 2px;
}
.seg-btn {
  border: none;
  background: transparent;
  color: #6e6e73;
  font-size: 13px;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: 980px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
}
.seg-btn:hover { color: #1d1d1f; }
.seg-btn.active {
  background: #fff;
  color: #1d1d1f;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 4px 14px rgba(0,0,0,0.05);
}
</style>
