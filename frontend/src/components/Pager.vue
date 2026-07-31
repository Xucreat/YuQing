<template>
  <el-config-provider :locale="zhCn">
    <el-pagination
      :background="background"
      :layout="layout"
      :total="total"
      :current-page="currentPage"
      :page-size="pageSize"
      @update:current-page="onUpdate"
      @current-change="onChange"
    />
  </el-config-provider>
</template>

<script setup lang="ts">
import { ElConfigProvider, ElPagination } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

withDefaults(
  defineProps<{
    total: number
    currentPage: number
    pageSize?: number
    layout?: string
    background?: boolean
  }>(),
  {
    pageSize: 10,
    layout: 'total, prev, pager, next, jumper',
    background: true,
  },
)

const emit = defineEmits<{
  'update:currentPage': [page: number]
  'current-change': [page: number]
}>()

function onUpdate(p: number) {
  emit('update:currentPage', p)
}
function onChange(p: number) {
  emit('current-change', p)
}
</script>
