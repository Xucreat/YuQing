<template>
  <transition name="alert-toast">
    <div v-if="toast" class="alert-toast-wrap" role="alert" aria-live="assertive">
      <div class="alert-toast" :style="{ '--risk': riskColor(top.risk_level) }" @click="onCardClick">
        <div class="at-icon">🔔</div>
        <div class="at-body">
          <div class="at-head">
            <span class="at-title">新预警</span>
            <span class="at-tag" :class="'is-' + top.risk_level">{{ riskText(top.risk_level) }}</span>
          </div>
          <div class="at-rule">{{ top.rule_name }}</div>
          <div class="at-opinion">{{ top.opinion_title || '（无关联舆情）' }}</div>
          <div class="at-foot">
            <button class="at-btn at-view" @click.stop="viewAlerts">
              查看{{ toast.count > 1 ? ' ' + toast.count + ' 条' : '' }}
            </button>
            <button class="at-btn at-later" @click.stop="laterAlerts">稍后</button>
          </div>
          <div class="at-progress"></div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAlertNotifier } from '@/composables/useAlertNotifier'
import { riskText, riskColor } from '@/utils/alert'

const { toast, viewAlerts, laterAlerts } = useAlertNotifier()
const top = computed(() => (toast.value?.items[0]) as any)

// 点击卡片空白处等同于「查看」（按钮已 .stop，不会触发）。
function onCardClick() {
  viewAlerts()
}
</script>

<style scoped>
.alert-toast-wrap {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 3000;
  pointer-events: none;
}
.alert-toast {
  pointer-events: auto;
  width: 340px;
  display: flex;
  gap: 12px;
  padding: 16px 16px 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.20), 0 2px 8px rgba(0, 0, 0, 0.10);
  cursor: pointer;
  overflow: hidden;
}
/* 左侧风险强调条 */
.alert-toast::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--risk, #0071e3);
}
.at-icon {
  font-size: 22px;
  line-height: 1;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.15));
}
.at-body { flex: 1; min-width: 0; }
.at-head { display: flex; align-items: center; justify-content: space-between; }
.at-title { font-size: 14.5px; font-weight: 600; color: #1d1d1f; letter-spacing: -0.01em; }
.at-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  color: #fff;
}
.at-tag.is-critical, .at-tag.is-high { background: #ff3b30; }
.at-tag.is-medium { background: #c77700; }
.at-tag.is-low { background: #0071e3; }
.at-rule { margin-top: 6px; font-size: 13px; font-weight: 500; color: #1d1d1f; }
.at-opinion {
  margin-top: 2px;
  font-size: 12.5px;
  color: #6e6e73;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.at-foot { margin-top: 12px; display: flex; gap: 8px; }
.at-btn {
  border: none;
  border-radius: 980px;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease, opacity 0.15s ease;
}
.at-view { background: #0071e3; color: #fff; }
.at-view:hover { background: #0077ed; }
.at-later { background: transparent; color: #86868b; }
.at-later:hover { background: rgba(0, 0, 0, 0.05); }
/* 10s 倒计时进度条 */
.at-progress {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--risk, #0071e3), transparent);
  transform-origin: left center;
  animation: at-progress-anim 10s linear forwards;
}
@keyframes at-progress-anim {
  from { transform: scaleX(1); }
  to { transform: scaleX(0); }
}

/* 入场动画：从右侧滑入 + 淡入 */
.alert-toast-enter-active { transition: transform 0.42s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.42s ease; }
.alert-toast-leave-active { transition: transform 0.3s ease, opacity 0.3s ease; }
.alert-toast-enter-from, .alert-toast-leave-to {
  opacity: 0;
  transform: translateX(40px) scale(0.98);
}

@media (prefers-reduced-motion: reduce) {
  .alert-toast-enter-active, .alert-toast-leave-active { transition: opacity 0.2s ease; }
  .alert-toast-enter-from, .alert-toast-leave-to { transform: none; }
  .at-progress { animation: none; display: none; }
}
</style>
