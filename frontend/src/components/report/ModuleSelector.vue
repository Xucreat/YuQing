<template>
  <div class="module-list">
    <div v-for="(key, idx) in model" :key="key" class="module-item">
      <span class="module-idx">{{ idx + 1 }}</span>
      <span class="module-title">{{ titleOf(key) }}</span>
      <span class="module-ops">
        <el-button link :disabled="idx === 0" @click="move(idx, -1)" title="上移">↑</el-button>
        <el-button link :disabled="idx === model.length - 1" @click="move(idx, 1)" title="下移">↓</el-button>
        <el-button link type="danger" @click="remove(idx)" title="移除">✕</el-button>
      </span>
    </div>
    <div v-if="available.length" class="module-add">
      <span class="add-label">添加模块：</span>
      <el-select v-model="toAdd" placeholder="选择未选模块" @change="add" clearable>
        <el-option
          v-for="m in available"
          :key="m.key"
          :value="m.key"
          :label="m.title"
        />
      </el-select>
    </div>
    <div v-if="!model.length" class="form-hint warn">未选择任何模块，生成将失败。</div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import type { ReportModuleDef } from "@/api/report"

// 选中的模块 key 列表（双向绑定，支持增删与排序）
const model = defineModel<string[]>({ required: true })

const props = defineProps<{
  modules: ReportModuleDef[]
}>()

const toAdd = ref("")

const available = computed(() =>
  props.modules.filter((m) => !model.value.includes(m.key)),
)

function titleOf(key: string): string {
  return props.modules.find((m) => m.key === key)?.title || key
}

function move(idx: number, dir: number) {
  const j = idx + dir
  if (j < 0 || j >= model.value.length) return
  const arr = [...model.value]
  ;[arr[idx], arr[j]] = [arr[j], arr[idx]]
  model.value = arr
}

function remove(idx: number) {
  const arr = [...model.value]
  arr.splice(idx, 1)
  model.value = arr
}

function add(key: string) {
  if (key && !model.value.includes(key)) {
    model.value = [...model.value, key]
  }
  toAdd.value = ""
}
</script>

<style scoped>
.module-list { border: 1px solid #e8e8ed; border-radius: 10px; padding: 8px; background: #fafafd; }
.module-item {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 8px; border-radius: 8px; background: #fff;
  border: 1px solid #eef0f3; margin-bottom: 6px;
}
.module-idx {
  flex: 0 0 22px; height: 22px; line-height: 22px; text-align: center;
  background: #0071e3; color: #fff; border-radius: 50%; font-size: 12px;
}
.module-title { flex: 1; font-size: 14px; color: #1d1d1f; }
.module-ops { display: flex; align-items: center; gap: 2px; }
.module-ops .el-button { margin-left: 0; padding: 0 6px; font-size: 14px; }
.module-add { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.module-add .add-label { font-size: 13px; color: #555; white-space: nowrap; }
.module-add .el-select { flex: 1; }
</style>
