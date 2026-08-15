import { ref } from 'vue'

// 驾驶舱「国内 / 外网」视图共享开关：
// - Dashboard.vue 读取并据此切换内嵌视图
// - AppLayout.vue 顶栏的 radio-group 写入（仅 /dashboard 路由显示）
// 模块级单例 ref，保证两处始终同步。
export const cockpitScope = ref<'domestic' | 'foreign'>('domestic')
