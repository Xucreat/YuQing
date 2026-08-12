<template>
  <div class="foreign-page" v-loading="loading">
    <div class="tabs" role="tablist">
      <button v-for="tab in visibleTabs" :key="tab.value" class="tab" :class="{ active: activeTab === tab.value }" @click="switchTab(tab.value)">
        {{ tab.label }}
      </button>
      <div class="tab-actions">
        <details class="source-picker"><summary>选择来源</summary><div class="source-picker-menu"><label v-for="source in approvedSources" :key="source.id"><input v-model="selectedSourceIds" type="checkbox" :value="source.id" /> {{ source.name }}</label><span v-if="!approvedSources.length" class="muted">暂无已批准外网来源</span></div></details>
        <span class="source-scope-label">已批准数据源：{{ approvedSourceLabel }}</span>
        <button v-if="canCollectSelected" class="btn btn-primary btn-sm" :disabled="collecting || !selectedSourceIds.length" @click="collectNow">
        {{ collecting ? '采集中...' : '采集外网 RSS' }}
        </button>
        <button v-if="canCollectAll" class="btn btn-secondary btn-sm" :disabled="collecting" @click="collectAll">采集全部已启用外网数据源</button>
      </div>
    </div>

    <section v-if="activeTab === 'dashboard'" class="panel visualization-panel">
      <div class="schedule-status" :class="{ disabled: !scheduleStatus?.enabled }"><strong>外网自动采集</strong><span>{{ scheduleStatus?.enabled ? '已启用' : '部署级开关已关闭' }}</span><span>已注册：{{ scheduleStatus?.registered ? '是' : '否' }}</span><span>运行中：{{ scheduleStatus?.running ? '是' : '否' }}</span><span>符合来源：{{ scheduleStatus?.eligible_source_count ?? 0 }}</span><span v-if="scheduleStatus?.last_run">最近运行：{{ zh(scheduleStatus.last_run.status) }} {{ formatTime(scheduleStatus.last_run.ended_at || scheduleStatus.last_run.started_at) }}</span><span v-if="scheduleStatus?.last_run?.error_summary" class="error-text">{{ scheduleStatus.last_run.error_summary }}</span></div>
      <div class="fw-dash-head">
        <div>
          <h2 class="fw-dash-title">外网舆情看板</h2>
          <p class="muted">面向外网公开来源采集的舆情概览（仅外网数据）</p>
        </div>
        <div class="toolbar" style="margin-bottom:0">
          <label class="muted">统计窗口
            <select v-model.number="visualizationDays" class="input" @change="loadDashboard">
              <option :value="1">近 1 天</option><option :value="7">近 7 天</option><option :value="30">近 30 天</option><option :value="90">近 90 天</option>
            </select>
          </label>
          <button class="btn btn-primary" @click="loadDashboard">刷新看板</button>
          <span v-if="visualizationStale" class="stale-badge">数据较旧</span>
        </div>
      </div>
      <div v-if="visualizationError" class="error-state"><span>{{ visualizationError }}</span><button class="btn btn-secondary" @click="loadDashboard">重试</button></div>
      <div v-else-if="dashboardSummary" class="fw-dash">
        <div class="fw-kpi-grid">
          <div class="fw-kpi"><span class="fw-kpi-label">文章总数</span><strong class="fw-kpi-value">{{ dashboardSummary.articles.total }}</strong><small>{{ dashboardSummary.articles.window_new }} 条在窗口内</small></div>
          <div class="fw-kpi"><span class="fw-kpi-label">数据源</span><strong class="fw-kpi-value">{{ dashboardSummary.articles.sources }}</strong><small>{{ dashboardSummary.articles.languages?.en || 0 }} 英文 / {{ dashboardSummary.articles.languages?.zh || 0 }} 中文</small></div>
          <div class="fw-kpi"><span class="fw-kpi-label">风险已完成</span><strong class="fw-kpi-value">{{ dashboardSummary.risk.completed }}</strong><small>{{ dashboardSummary.risk.failed }} 失败 · {{ dashboardSummary.risk.pending }} 待处理</small></div>
          <div class="fw-kpi"><span class="fw-kpi-label">已确认事件</span><strong class="fw-kpi-value">{{ dashboardSummary.events.confirmed }}</strong><small>{{ dashboardSummary.events.candidate }} 候选</small></div>
          <div class="fw-kpi"><span class="fw-kpi-label">外网告警</span><strong class="fw-kpi-value">{{ dashboardSummary.alerts.total }}</strong><small>{{ dashboardSummary.alerts.by_status?.triggered || 0 }} 已触发</small></div>
          <div class="fw-kpi"><span class="fw-kpi-label">外网采集</span><strong class="fw-kpi-value">{{ dashboardSummary.collection?.success ?? 0 }}</strong><small>成功 / 失败 {{ dashboardSummary.collection?.failed ?? 0 }} · {{ zh(dashboardSummary.collection?.latest?.status || 'unknown') }}</small></div>
        </div>
                <div class="fw-dash-grid">
          <article class="fw-card fw-card-trend fw-col-1">
            <header class="fw-card-head">
              <h3>每日趋势</h3>
              <div class="fw-legend">
                <button v-for="item in trendSeriesOptions" :key="item.key" type="button" class="fw-legend-item" :class="{ off: !trendSeriesOn[item.key] }" @click="toggleTrendSeries(item.key)">
                  <i :style="{ background: item.color }"></i>{{ item.label }}
                </button>
              </div>
            </header>
            <div v-show="(dashboardTrends?.items || []).length" ref="trendChartRef" class="fw-chart"></div>
            <p v-if="!(dashboardTrends?.items || []).length" class="empty">该窗口内暂无趋势数据</p>
          </article>
          <article class="fw-card fw-card-alert fw-col-2">
            <header class="fw-card-head">
              <h3>外网告警</h3>
              <span class="muted">滚动播报 · 共 {{ alertFeed.length }} 条</span>
            </header>
            <div v-if="!alertFeed.length" class="empty">该窗口内暂无外网告警</div>
            <div v-else class="fw-alert-feed">
              <div class="fw-alert-summary">
                <span class="fw-alert-sum"><i class="fw-sum-dot is-amber"></i>待处置 {{ alertPendingCount }}</span>
                <span class="fw-alert-sum"><i class="fw-sum-dot is-teal"></i>已处置 {{ alertDoneCount }}</span>
              </div>
              <div ref="alertViewportEl" class="fw-alert-viewport">
                <div ref="alertTrackEl" class="fw-alert-track" :class="{ scrolling: alertFeedOverflow }" :style="{ animationDuration: alertScrollDuration }">
                  <ul class="fw-alert-list">
                    <li v-for="a in alertFeed" :key="'a-' + a.id" class="fw-alert-row" @click="openAlertTarget(a)">
                      <span class="fw-badge fw-mono" :class="severityBadge(a.severity)">{{ severityText(a.severity) }}</span>
                      <div class="fw-alert-main">
                        <div class="fw-alert-title">{{ a.title || '未命名告警' }}</div>
                        <div class="fw-alert-meta">{{ a.rule_snapshot?.name || a.source_name_snapshot || '外网告警' }} · {{ shortTime(a.triggered_at) }}</div>
                      </div>
                      <span class="fw-badge" :class="isHandled(a.status) ? 'is-teal' : 'is-amber'">{{ zh(a.status) }}</span>
                    </li>
                  </ul>
                  <div v-if="alertNeedScroll" class="fw-alert-copy">
                    <ul class="fw-alert-list">
                      <li v-for="a in alertFeed" :key="'b-' + a.id" class="fw-alert-row" @click="openAlertTarget(a)">
                        <span class="fw-badge fw-mono" :class="severityBadge(a.severity)">{{ severityText(a.severity) }}</span>
                        <div class="fw-alert-main">
                          <div class="fw-alert-title">{{ a.title || '未命名告警' }}</div>
                          <div class="fw-alert-meta">{{ a.rule_snapshot?.name || a.source_name_snapshot || '外网告警' }} · {{ shortTime(a.triggered_at) }}</div>
                        </div>
                        <span class="fw-badge" :class="isHandled(a.status) ? 'is-teal' : 'is-amber'">{{ zh(a.status) }}</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </article>
          <article class="fw-card fw-card-source fw-col-1">
            <header class="fw-card-head">
              <h3>数据源分布</h3>
              <span class="muted">近 {{ visualizationDays }} 天 · 各来源文章量</span>
            </header>
            <div v-show="(dashboardSources?.items || []).length" ref="sourceChartRef" class="fw-chart fw-chart-tall"></div>
            <p v-if="!(dashboardSources?.items || []).length" class="empty">该窗口内暂无数据源分布</p>
          </article>
          <article class="fw-card fw-col-2"><h3>风险分布</h3><div v-show="(dashboardRisk?.risk_levels && Object.keys(dashboardRisk.risk_levels || {}).length)" ref="riskChartRef" class="fw-chart fw-chart-tall"></div><p v-if="!dashboardRisk || !Object.keys(dashboardRisk.risk_levels || {}).length" class="empty">暂无已完成风险结果</p></article>
          <article class="fw-card fw-card-hotword fw-col-1">
            <header class="fw-card-head">
              <h3>外网热词</h3>
              <span class="muted">近 {{ visualizationDays }} 天 · 共 {{ hotwordItems.length }} 个热词</span>
            </header>
            <div v-show="hotwordItems.length" ref="hotwordChartRef" class="fw-chart"></div>
            <p v-if="!hotwordItems.length" class="empty">该窗口内暂无外网热词</p>
          </article>
          <article class="fw-card fw-col-2"><h3>事件状态</h3><div v-for="(count, label) in dashboardEvents?.formal_events" :key="label" class="distribution-row"><span>{{ zh(label) }}</span><strong>{{ count }}</strong></div><p v-if="!dashboardEvents || !Object.keys(dashboardEvents.formal_events || {}).length" class="empty">暂无外网事件</p></article>

        </div>
<div class="visualization-meta">数据范围：{{ formatTime(dashboardSummary.window_start) }} - {{ formatTime(dashboardSummary.window_end) }} · 更新于：{{ formatTime(dashboardSummary.data_as_of) }}</div>
      </div>
      <div v-else class="state">加载外网看板中...</div>
    </section>



    <section v-if="activeTab === 'opinions'" class="panel">
      <div class="toolbar">
        <input v-model="opinionFilters.q" class="input" placeholder="搜索标题、摘要、正文" @keyup.enter="loadOpinions" />
        <select v-model="opinionFilters.source" class="input" @change="loadOpinions">
          <option value="">全部来源</option>
          <option v-for="source in opinionSources" :key="source" :value="source">{{ source }}</option>
        </select>
        <input v-model="opinionFilters.keyword" class="input" placeholder="命中关键词" @keyup.enter="loadOpinions" />
        <select v-model="riskFilters.language" class="input" @change="loadOpinions(); loadRisk()">
          <option value="">全部语言</option><option value="zh">中文</option><option value="en">英文</option><option value="mixed">中英混合</option><option value="unknown">未知</option>
        </select>
        <select v-model="riskSource" class="input" aria-label="risk view source" @change="setRiskSource(riskSource)">
          <option value="rule">系统规则</option><option value="ai">AI 研判</option>
        </select>
        <span class="muted">当前查看口径：{{ displaySourceLabel() }}</span>
        <select v-model="riskFilters.risk_level" class="input" @change="loadOpinions(); loadRisk()">
          <option value="">全部风险等级</option><option value="high">高</option><option value="medium">中</option><option value="low">低</option><option value="unknown">未知</option>
        </select>
        <select v-model="riskFilters.analysis_status" class="input" @change="loadOpinions(); loadRisk()">
          <option value="">全部分析状态</option><option value="completed">完成</option><option value="skipped">跳过</option><option value="failed">失败</option>
        </select>
        <input v-model="opinionFilters.date_from" class="input date-input" type="date" title="发布时间起始" @change="loadOpinions" />
        <input v-model="opinionFilters.date_to" class="input date-input" type="date" title="发布时间截止" @change="loadOpinions" />
        <button class="btn btn-secondary" @click="loadOpinions">搜索</button>
        <span class="muted">AI 研判结果仅用于辅助分析，不改变系统正式风险和告警</span>
      </div>
      <div class="table-wrap tbl-scroll">
        <table>
          <thead><tr><th>标题</th><th>来源快照</th><th>命中关键词</th><th>发布时间</th><th>采集时间</th><th>当前风险分</th><th>当前等级</th><th>风险来源</th><th>规则 / AI</th><th>情感</th><th>风险类别</th><th>命中风险词</th><th>分析状态</th><th>分析时间</th><th>版本</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in opinions" :key="row.id" @click="openOpinion(row.id)">
              <td class="title-cell">{{ row.title || '无标题' }}</td>
              <td>{{ row.source_name_snapshot }}</td>
              <td><span v-for="word in row.matched_keywords" :key="word" class="tag">{{ word }}</span></td>
              <td>{{ formatTime(row.published_at) }}</td>
              <td>{{ formatTime(row.collected_at) }}</td>
              <td>{{ displayOf(row)?.risk_score ?? '-' }}</td>
              <td><span class="status" :class="{ on: displayOf(row)?.risk_level === 'high' }">{{ zh(displayOf(row)?.risk_level) }}</span></td>
              <td><span class="src-tag" :class="{ ai: displayOf(row)?.source === 'ai' }">{{ displayOf(row)?.source === 'ai' ? 'AI 研判' : '系统规则' }}</span></td>
              <td class="dual-cell">
                <span>规则 {{ ruleOf(row)?.risk_score ?? '-' }}</span>
                <span class="muted">{{ aiHistoryLabel(row) }}</span>
              </td>
              <td>{{ zh(displayOf(row)?.sentiment) }}</td>
              <td>{{ zh(ruleOf(row)?.risk_category) }}</td>
              <td>
                <span v-for="term in (riskOf(row.id)?.matched_terms || [])" :key="term.word" class="tag">{{ term.word }}</span>
                <span v-if="!(riskOf(row.id)?.matched_terms || []).length" class="muted">无</span>
              </td>
              <td><span class="status" :class="{ on: ruleOf(row)?.analysis_status === 'completed' }">{{ zh(ruleOf(row)?.analysis_status) }}</span></td>
              <td>{{ formatTime(displayOf(row)?.evaluated_at) }}</td>
              <td>{{ displayOf(row)?.model_version || '-' }}</td>
              <td class="actions">
                <button class="link-btn" :disabled="!canAnalyzeRisk" @click.stop="analyzeRisk(row.id)">{{ ruleOf(row) ? '重新分析' : '分析' }}</button>
              </td>
            </tr>
            <tr v-if="!opinions.length"><td colspan="16" class="empty">暂无外网舆情</td></tr>
          </tbody>
        </table>
      </div>
      <div class="pager" v-if="opinionTotal > 0">
        <Pager :total="opinionTotal" v-model:current-page="opinionPage" :page-size="opinionSize" @current-change="loadOpinions" />
      </div>
    </section>


    <section v-else-if="activeTab === 'events'" class="panel">
      <div class="alert-scope-note">外网自动聚合：{{ eventAutoStatus?.enabled ? '已启用' : '已停用' }} · 调度已注册：{{ eventAutoStatus?.scheduler_registered ? '是' : '否' }} · 置信度阈值 {{ eventAutoStatus?.confidence_threshold ?? '-' }} · 时间窗口 {{ eventAutoStatus?.time_window_hours ?? '-' }} 小时</div>
      <div class="toolbar">
        <button class="btn btn-secondary" @click="loadEvents">刷新外网事件</button>
        <button class="btn btn-secondary" :disabled="rebuildingEvents" @click="rebuildEvents">
          {{ rebuildingEvents ? '重建中...' : '候选 Dry-Run' }}
        </button>
        <span class="muted">候选只进入外网事件表，必须人工确认后才形成正式事件</span>
      </div>
      <div v-if="eventLoadError" class="state error-state">
        <span>外网事件加载失败：{{ eventLoadError }}</span>
        <button class="btn btn-secondary" @click="loadEvents">重试</button>
      </div>
      <div v-if="eventRunFailures.length" class="event-failures">
        <strong>外网事件运行失败</strong>
        <div v-for="run in eventRunFailures" :key="run.id" class="event-failure-row">
          <span class="status failed">失败</span>
          <span>{{ formatTime(run.finished_at || run.started_at) }}</span>
          <span>{{ run.error_message || '运行失败，未提供错误摘要' }}</span>
        </div>
      </div>
      <div class="subtabs">
        <button class="tab" :class="{ active: eventSection === 'candidates' }" @click="eventSection = 'candidates'">事件候选</button>
        <button class="tab" :class="{ active: eventSection === 'confirmed' }" @click="eventSection = 'confirmed'">外网事件</button>
      </div>
      <div v-if="eventSection === 'candidates'" class="table-wrap">
        <table>
          <thead><tr><th>标题</th><th>语言</th><th>审核来源</th><th>置信度</th><th>文章数</th><th>来源数</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in eventCandidates" :key="row.id">
              <td class="title-cell">{{ row.title || '无标题' }}</td>
               <td>{{ zh(row.language) }}</td>
               <td>{{ zh(row.review_source || 'manual') }}</td>
              <td>{{ Math.round(row.confidence * 100) }}%</td>
              <td>{{ row.opinion_count }}</td>
              <td>{{ row.source_count }}</td>
              <td><span class="status" :class="{ on: row.candidate_status === 'converted' }">{{ zh(row.candidate_status) }}</span></td>
              <td class="actions">
                <button v-if="row.candidate_status === 'candidate'" class="link-btn" :disabled="!canConfirmEvents || eventActionKey === `candidate-confirm-${row.id}`" @click="confirmCandidate(row)">确认</button>
                <button v-if="row.candidate_status === 'candidate'" class="link-btn danger" :disabled="!canConfirmEvents || eventActionKey === `candidate-reject-${row.id}`" @click="rejectCandidate(row)">拒绝</button>
              </td>
            </tr>
            <tr v-if="!eventCandidates.length"><td colspan="8" class="empty">暂无外网事件候选</td></tr>
          </tbody>
        </table>
      </div>
      <div v-else class="table-wrap">
        <table>
          <thead><tr><th>标题</th><th>语言</th><th>确认来源</th><th>状态</th><th>风险快照</th><th>热度</th><th>文章数</th><th>来源数</th><th>置信度</th><th>首次出现</th><th>最近出现</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in foreignEvents" :key="row.id" @click="loadEventDetail(row.id)">
              <td class="title-cell">{{ row.title || '无标题' }}</td>
               <td>{{ zh(row.language) }}</td>
               <td>{{ zh(row.confirmation_source || 'manual') }}</td>
              <td><span class="status" :class="{ on: row.event_status === 'monitoring', failed: row.event_status === 'failed' }">{{ zh(row.event_status) }}</span></td>
              <td>{{ zh(row.risk_level) }}</td>
              <td>{{ row.heat_score ?? '-' }}</td>
              <td>{{ row.opinion_count }}</td>
              <td>{{ row.source_count }}</td>
              <td>{{ Math.round(row.confidence * 100) }}%</td>
              <td>{{ formatTime(row.first_seen_at) }}</td>
              <td>{{ formatTime(row.last_seen_at) }}</td>
              <td><button class="link-btn" :disabled="!canChangeEventStatus || eventActionKey === `event-close-${row.id}`" @click.stop="closeEvent(row)">关闭</button><button class="link-btn" :disabled="!canChangeEventStatus || eventActionKey === `event-archive-${row.id}`" @click.stop="archiveEvent(row)">归档</button></td>
            </tr>
            <tr v-if="!foreignEvents.length"><td colspan="12" class="empty">暂无已确认外网事件</td></tr>
          </tbody>
        </table>
      </div>
      <article v-if="selectedForeignEvent" class="event-detail">
        <div class="event-provenance">
          <strong>事件溯源</strong>
          <span>确认来源：{{ zh(selectedForeignEvent.confirmation_source || 'manual') }}</span>
          <span>审核来源：{{ zh(selectedForeignEvent.auto_aggregation?.review_source) }}</span>
          <span>置信度：{{ Math.round((selectedForeignEvent.confidence || 0) * 100) }}%</span>
          <span>文章数：{{ selectedForeignEvent.opinion_count }} · 来源数：{{ selectedForeignEvent.source_count }}</span>
          <details v-if="selectedForeignEvent.auto_aggregation?.evidence"><summary>聚合证据</summary><pre>{{ JSON.stringify(selectedForeignEvent.auto_aggregation.evidence, null, 2) }}</pre></details>
        </div>
        <div class="event-detail-head">
          <h3>{{ selectedForeignEvent.title }}</h3>
          <div class="actions"><button class="link-btn" :disabled="!canChangeEventStatus || Boolean(eventActionKey)" @click="closeEvent(selectedForeignEvent)">关闭事件</button><button class="link-btn" :disabled="!canMergeEvents || Boolean(eventActionKey)" @click="mergeEvent(selectedForeignEvent)">合并</button><button class="link-btn" :disabled="!canSplitEvents || Boolean(eventActionKey)" @click="splitEvent(selectedForeignEvent)">拆分</button><button class="link-btn" @click="selectedForeignEvent = null">关闭详情</button></div>
        </div>
        <p class="muted">{{ zh(selectedForeignEvent.language) }} · {{ zh(selectedForeignEvent.event_status) }} · {{ selectedForeignEvent.opinion_count }} 篇文章</p>
        <div class="event-metrics">
          <span>热度：{{ selectedForeignEvent.heat_score ?? '-' }}</span>
          <span>首次出现：{{ formatTime(selectedForeignEvent.first_seen_at) }}</span>
          <span>最近出现：{{ formatTime(selectedForeignEvent.last_seen_at) }}</span>
        </div>
        <p>{{ selectedForeignEvent.summary || '暂无摘要' }}</p>
        <div v-for="opinion in selectedForeignEvent.opinions" :key="opinion.id" class="event-opinion">
          <strong>{{ opinion.title }}</strong>
          <span class="muted">{{ opinion.source_name_snapshot }} · {{ formatTime(opinion.published_at) }}</span>
          <a :href="opinion.url" target="_blank" rel="noreferrer" class="original">原文</a>
        </div>
      </article>
    </section>

    <ForeignOpinionDetailModal v-model="detailVisible" :opinion-id="detailId" :risk-source="riskSource" @update:risk-source="setRiskSource" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import * as echarts from 'echarts'
import 'echarts-wordcloud'
 import { ElMessage, ElMessageBox } from 'element-plus'
import api, { pollTask } from '@/api'
import { useRoute, useRouter } from 'vue-router'
import { usePermission } from '@/composables/usePermission'
import ForeignOpinionDetailModal from '@/views/foreign/ForeignOpinionDetailModal.vue'
import Pager from '@/components/Pager.vue'

type Tab = 'dashboard' | 'opinions' | 'events'
// 后端统一「当前有效风险」解析结果（app/services/foreign_effective_risk.py）。
// 舆情列表、舆情详情、外网告警三处共用同一份结构，前端只负责展示，不再自行判定。
type EffectiveRisk = {
  source: 'rule' | 'ai'
  risk_score: number | null
  risk_level: string
  sentiment: string
  model_name?: string | null
  model_version?: string | null
  evaluated_at?: string | null
  alert_id?: number | null
  alert_status?: string | null
  reason?: 'rule_baseline' | 'not_analyzed'
  fallback?: boolean
  fallback_reason?: string
}
type RuleRiskBrief = {
  source: 'rule'
  risk_result_id: number
  risk_score: number | null
  risk_level: string
  sentiment: string
  risk_category: string
  analysis_status: string
  model_name?: string | null
  model_version?: string | null
  evaluated_at?: string | null
}
type AIRiskBrief = {
  source: 'ai'
  ai_result_id: number
  risk_score: number | null
  risk_level: string
  sentiment: string
  status: string
  model_name?: string | null
  model_version?: string | null
  evaluated_at?: string | null
  is_current_evaluation: boolean
  alert_id?: number | null
  alert_status?: string | null
  alert_active: boolean
  in_effect: boolean
}
type EffectiveRiskView = {
  effective_risk?: EffectiveRisk | null
  display_risk?: EffectiveRisk | null
  rule_risk?: RuleRiskBrief | null
  latest_ai_risk?: AIRiskBrief | null
  alert?: { id: number; status: string; severity: string; evaluation_source: string; risk_score: number | null; risk_level: string; expires_at?: string | null; is_active: boolean } | null
}
type Keyword = { id: number; word: string; category: string; type: 'monitoring' | 'sensitive'; source: 'system' | 'custom'; weight: number; severity_weight: number; rule_config?: Record<string, unknown>; is_enabled: boolean }
type Source = { id: number; key: string; name: string; feeds: string[]; language?: string; enabled: boolean; schedule_enabled: boolean; schedule_interval_minutes?: number; class_path?: string; proxy_env?: string; proxy_configured?: boolean; timeout?: number; max_retries?: number; max_items?: number; request_interval?: number; max_content_length?: number; respect_robots?: boolean }
type Opinion = { id: number; title: string; summary: string; content: string; url: string; source_name_snapshot: string; matched_keywords: string[]; published_at?: string | null; collected_at?: string | null; rule_result?: RiskResult | null; ai_result?: AIResult | null; analysis_runs?: Array<{ id: number; analyzer_type: string; status: string; started_at?: string | null; finished_at?: string | null; error_message?: string | null }> } & EffectiveRiskView
type AIResult = { id: number; status: string; model_version: string; summary: string; sentiment: string; risk_score?: number | null; keywords: string[]; suggestion: string; error_message?: string | null; analyzed_at?: string | null }
type Run = { id: number; collector_name: string; start_time?: string | null; end_time?: string | null; status: string; fetched_raw: number; matched: number; created: number; duplicate: number; proxy_used: boolean; error_msg?: string | null }
type RiskResult = {
  id: number
  foreign_opinion_id: number
  content_hash: string
  language: string
  risk_score: number | null
  risk_level: string
  sentiment: string
  sentiment_confidence?: number | null
  risk_category: string
  matched_terms: Array<{ word: string; language: string; category: string; severity_weight: number }>
  explanation: string
  analyzer_type: string
  model_name?: string | null
  model_version: string
  analysis_status: string
  error_message?: string | null
  analyzed_at?: string | null
  is_current: boolean
  opinion: Opinion
}
type EventCandidate = {
  id: number
  title: string
  summary: string
  language: string
  candidate_status: string
  confidence: number
  opinion_count: number
  source_count: number
  review_source?: string
  evidence_json?: Record<string, unknown>
}
type ForeignEvent = {
  id: number
  title: string
  summary: string
  language: string
  event_status: string
  confirmation_source?: string
  auto_aggregation?: { review_source?: string; evidence?: Record<string, unknown> }
  risk_level: string
  opinion_count: number
  source_count: number
  confidence: number
  heat_score: number | null
  first_seen_at?: string | null
  last_seen_at?: string | null
  opinions?: Array<{ id: number; title: string; source_name_snapshot: string; url: string; summary?: string; content?: string; published_at?: string | null }>
}
type ForeignEventRun = {
  id: number
  status: string
  started_at?: string | null
  finished_at?: string | null
  error_message?: string | null
}
type ForeignAlert = {
  id: number
  rule_id?: number | null
  foreign_opinion_id?: number | null
  foreign_risk_result_id?: number | null
  foreign_event_id?: number | null
  severity: string
  status: string
  evaluation_source?: 'rule' | 'ai'
  title: string
  message: string
  rule_snapshot?: { name?: string; rule_type?: string }
  opinion_title_snapshot?: string
  event_title_snapshot?: string
  foreign_ai_result_id?: number | null
  opinion?: Opinion | null
  event?: ForeignEvent | null
  risk_score?: number | null
  risk_level: string
  expires_at?: string | null
  is_active?: boolean
  triggered_at?: string | null
  acknowledged_at?: string | null
  resolved_at?: string | null
  suppressed_at?: string | null
} & EffectiveRiskView
type VisualizationSummary = any
type HotwordItem = { word: string; language: string; count: number; trend: string; sources: string[] }

type WorkspaceTab = Tab | 'alerts' | 'alertRules'
const tabs: { value: WorkspaceTab; label: string }[] = [
  { value: 'dashboard', label: '外网 Dashboard' },
  { value: 'opinions', label: '国外舆情' },
  { value: 'events', label: '外网事件' },
]
// Legacy alert tabs remain routable for old bookmarks but are intentionally not rendered here.
const visibleTabs = tabs.filter((item) => item.value !== 'alerts' && item.value !== 'alertRules')
const route = useRoute()
const router = useRouter()
const { hasPermission } = usePermission()
function normalizeTab(value: unknown): Tab {
  const valid: Tab[] = ['dashboard', 'opinions', 'events']
  return valid.includes(value as Tab) ? (value as Tab) : 'dashboard'
}

const activeTab = ref<Tab>(normalizeTab(route.query.tab))
const loading = ref(false)
const collecting = ref(false)
const approvedSources = ref<Array<{ id: number; name: string }>>([])
const approvedSourceIds = computed(() => approvedSources.value.map((source) => source.id))
const selectedSourceIds = ref<number[]>([])
const selectedSourceLabel = computed(() => selectedSourceIds.value.length
  ? approvedSources.value.filter((source) => selectedSourceIds.value.includes(source.id)).map((source) => source.name || String(source.id)).join('、')
  : '未选择')
const approvedSourceLabel = computed(() => approvedSources.value.length
  ? approvedSources.value.map((source) => source.name || String(source.id)).join('、')
  : '暂无')
const keywords = ref<Keyword[]>([])
const scheduleStatus = ref<any | null>(null)
const opinions = ref<Opinion[]>([])
const runs = ref<Run[]>([])
const risks = ref<RiskResult[]>([])
const eventCandidates = ref<EventCandidate[]>([])
const foreignEvents = ref<ForeignEvent[]>([])
const eventRunFailures = ref<ForeignEventRun[]>([])
const eventAutoStatus = ref<{ enabled: boolean; confidence_threshold: number; time_window_hours: number; scheduler_registered: boolean } | null>(null)
const eventLoadError = ref<string | null>(null)
const selectedForeignEvent = ref<ForeignEvent | null>(null)
const eventSection = ref<'candidates' | 'confirmed'>('candidates')
const rebuildingEvents = ref(false)
const eventActionKey = ref<string | null>(null)
const eventDetailLoadingId = ref<number | null>(null)
const visualizationDays = ref(7)
const visualizationError = ref<string | null>(null)
const visualizationStale = ref(false)
const dashboardSummary = ref<VisualizationSummary | null>(null)
const dashboardRisk = ref<VisualizationSummary | null>(null)
const dashboardEvents = ref<VisualizationSummary | null>(null)
const dashboardTrends = ref<VisualizationSummary | null>(null)
const dashboardAlerts = ref<VisualizationSummary | null>(null)
const dashboardSources = ref<VisualizationSummary | null>(null)
const hotwordItems = ref<HotwordItem[]>([])
const hotwordTrendItems = ref<Array<{ date: string; words: Record<string, number> }>>([])
const hotwordMeta = ref<any>({})
const hotwordLanguage = ref('')
const opinionSources = ref<string[]>([])
const opinionTotal = ref(0)
const opinionPage = ref(1)
const opinionSize = 20
const riskTotal = ref(0)
const riskPage = ref(1)
// 后端 /foreign/risk 的 size 上限为 100（Query(..., le=100)），超过会 422，
// 合并表需要覆盖当前舆情页的全部风险结果，因此分页循环拉取。
const riskSize = 100
const riskMaxPages = 20
const detailVisible = ref(false)
const detailId = ref<number | null>(null)
type RiskSource = 'rule' | 'ai'
const riskSource = ref<RiskSource>(
  window.localStorage.getItem('foreign-risk-source') === 'ai' ? 'ai' : 'rule',
)
function setRiskSource(value: RiskSource) {
  riskSource.value = value === 'ai' ? 'ai' : 'rule'
  window.localStorage.setItem('foreign-risk-source', riskSource.value)
  loadOpinions()
}
const opinionLoading = ref(false)
const riskByOpinion = computed(() => {
  const m = new Map<number, any>()
  for (const r of risks.value) m.set(r.foreign_opinion_id, r)
  return m
})
function riskOf(id: number) { return riskByOpinion.value.get(id) || null }
// 统一「当前有效风险」读取：只读后端 resolver 结果，前端不做任何等级推导，
// 保证舆情列表 / 舆情详情 / 外网告警 / 统一预警中心四处展示完全一致。
function effOf(row: EffectiveRiskView | null | undefined): EffectiveRisk | null {
  return row?.effective_risk || null
}
function displayOf(row: EffectiveRiskView | null | undefined): EffectiveRisk | null {
  return row?.display_risk || effOf(row)
}
function ruleOf(row: EffectiveRiskView | null | undefined): RuleRiskBrief | null {
  return row?.rule_risk || null
}
function aiOf(row: EffectiveRiskView | null | undefined): AIRiskBrief | null {
  return row?.latest_ai_risk || null
}
function effSourceLabel(row: EffectiveRiskView | null | undefined) {
  const eff = effOf(row)
  if (!eff) return '-'
  if (eff.reason === 'not_analyzed') return '未研判'
  return '规则'
}
// AI 结果始终保留为历史，不参与当前有效风险。
function aiHistoryLabel(row: EffectiveRiskView | null | undefined) {
  const ai = aiOf(row)
  if (!ai) return '未做 AI 研判'
  const score = ai.risk_score === null || ai.risk_score === undefined ? '-' : ai.risk_score
  return `AI ${score}（历史）`
}
function displaySourceLabel() {
  return riskSource.value === 'ai' ? 'AI 研判' : '系统规则'
}
// 枚举值中文映射（仅前端展示，不改变任何接口取值）
const ZH_DICT: Record<string, string> = {
  high: '高', medium: '中', low: '低', critical: '紧急', unknown: '未知', none: '无', other: '其他',
  positive: '正面', negative: '负面', neutral: '中性',
  completed: '已完成', pending: '待处理', processing: '进行中', running: '运行中', queued: '排队中',
  failed: '失败', success: '成功', partial: '部分成功', skipped: '已跳过', error: '异常',
  candidate: '候选', converted: '已转正', confirmed: '已确认', rejected: '已拒绝', merged: '已合并',
  monitoring: '监测中', closed: '已关闭', archived: '已归档', split: '已拆分', dismissed: '已忽略',
  triggered: '待处理', acknowledged: '已确认', resolved: '已解决', suppressed: '已抑制',
  manual: '人工', auto: '自动', automatic: '自动', rule: '规则', system: '系统',
  enabled: '已启用', disabled: '已停用', included: '已纳入', excluded: '未纳入',
  zh: '中文', en: '英文', mixed: '中英混合',
  risk_score: '风险分', risk_level: '风险等级', risk_category: '风险类别',
  keyword_combo: '关键词组合', confirmed_event: '确认事件',
}
function zh(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  const key = String(value)
  return ZH_DICT[key] || key
}
const aiAnalyzing = ref(false)
const keywordSaving = ref(false)
const keywordCategories = ref<string[]>([])
const keywordPage = ref(1)
const keywordSize = 50
const keywordTotal = ref(0)
const keywordFilters = reactive({ q: '', category: '', type: '', enabled: '' })
const keywordDraft = reactive({ word: '', category: 'general', type: 'monitoring' as 'monitoring' | 'sensitive', weight: 10 })
const editingKeywordId = ref<number | null>(null)
const opinionFilters = reactive({ q: '', source: '', keyword: '', date_from: '', date_to: '' })
const riskFilters = reactive({ q: '', source: '', language: '', sentiment: '', risk_level: '', analysis_status: '', date_from: '', date_to: '' })
const canAnalyzeRisk = hasPermission('foreign:risk:analyze')
const canAnalyzeAI = hasPermission('foreign:ai:analyze')
const canConfirmEvents = hasPermission('foreign:events:confirm')
const canChangeEventStatus = hasPermission('foreign:events:status')
const canMergeEvents = hasPermission('foreign:events:merge')
const canSplitEvents = hasPermission('foreign:events:split')
const canCollectSelected = computed(() => hasPermission('foreign:sources:collect'))
const canCollectAll = computed(() => hasPermission('foreign:sources:collect_all'))

async function loadApprovedSources() {
  try {
    const { data } = await api.get('/foreign/sources/approved')
    approvedSources.value = (data.items || []).map((item: any) => ({ id: item.id, name: item.name }))
    const available = new Set(approvedSources.value.map((item) => item.id))
    selectedSourceIds.value = selectedSourceIds.value.filter((id) => available.has(id))
    if (!selectedSourceIds.value.length) selectedSourceIds.value = approvedSources.value.map((item) => item.id)
  } catch {
    approvedSources.value = []
    selectedSourceIds.value = []
  }
}

async function loadScheduleStatus() {
  try { scheduleStatus.value = (await api.get('/foreign/collection-schedule/status')).data }
  catch { scheduleStatus.value = { enabled: false, registered: false, running: false, eligible_source_count: 0 } }
}

function switchTab(tab: WorkspaceTab) {
  router.push({ path: '/foreign', query: { ...route.query, tab } })
}
function loadTab(tab: Tab) {
  if (tab === 'dashboard') { loadDashboard(); loadScheduleStatus() }
  if (tab === 'opinions') { loadOpinions(); loadRisk() }
  if (tab === 'events') loadEvents()
}
function visualizationFailure(err: any) {
  const status = err?.response?.status
  const code = err?.response?.data?.error_code
  if (code === 'FOREIGN_VISUALIZATION_QUERY_FAILED' || status === 503) return '外网可视化数据暂时不可用'
  if (status === 403) return '当前账号没有外网可视化权限'
  if (status === 422) return '外网可视化请求参数无效'
  return '外网可视化数据加载失败，请稍后重试'
}
/* ===== 外网看板图表：每日趋势折线 + 热词词云（复用驾驶舱同款 echarts 配色/交互） ===== */
const trendChartRef = ref<HTMLElement>()
const hotwordChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let hotwordChart: echarts.ECharts | null = null
const sourceChartRef = ref<HTMLElement>()
let sourceChart: echarts.ECharts | null = null
const riskChartRef = ref<HTMLElement>()
let riskChart: echarts.ECharts | null = null
const RISK_MAP: Record<string, { name: string; color: string }> = {
  critical: { name: '紧急', color: '#ff3b30' },
  high: { name: '高', color: '#ff6b35' },
  medium: { name: '中', color: '#ff9f0a' },
  low: { name: '低', color: '#34c759' },
  unknown: { name: '未知', color: '#8e8e93' },
  none: { name: '无', color: '#c7c7cc' },
  other: { name: '其他', color: '#af52de' },
}
const alertFeed = ref<any[]>([])
const alertViewportEl = ref<HTMLElement>()
const alertTrackEl = ref<HTMLElement>()
const alertFeedOverflow = ref(false)
const alertNeedScroll = ref(false)
const alertScrollDuration = ref('18s')
const alertPendingCount = computed(() => (alertFeed.value || []).filter((a: any) => a.status === 'triggered').length)
const alertDoneCount = computed(() => (alertFeed.value || []).length - alertPendingCount.value)
let alertResizeObserver: ResizeObserver | null = null
type TrendKey = 'articles' | 'risk_completed' | 'risk_failed' | 'events' | 'alerts'
const trendSeriesOptions: Array<{ key: TrendKey; label: string; color: string }> = [
  { key: 'articles', label: '文章', color: '#0071e3' },
  { key: 'risk_completed', label: '风险完成', color: '#34c759' },
  { key: 'risk_failed', label: '风险失败', color: '#ff3b30' },
  { key: 'events', label: '事件', color: '#ff9f0a' },
  { key: 'alerts', label: '告警', color: '#af52de' },
]
const trendSeriesOn = reactive<Record<TrendKey, boolean>>({
  articles: true, risk_completed: true, risk_failed: true, events: true, alerts: true,
})
function toggleTrendSeries(key: TrendKey) {
  trendSeriesOn[key] = !trendSeriesOn[key]
  renderTrendChart()
}
function renderTrendChart() {
  if (!trendChart) return
  const items: any[] = (dashboardTrends.value as any)?.items || []
  const series = trendSeriesOptions
    .filter((item) => trendSeriesOn[item.key])
    .map((item) => ({
      name: item.label,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      data: items.map((row) => row[item.key] ?? 0),
      lineStyle: { width: item.key === 'articles' ? 2.5 : 1.8, color: item.color },
      itemStyle: { color: item.color },
      areaStyle: item.key === 'articles'
        ? { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(0,113,227,0.12)' }, { offset: 1, color: 'rgba(0,113,227,0)' }]) }
        : undefined,
    }))
  trendChart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(29,29,31,0.94)', borderColor: 'transparent', textStyle: { color: '#fff', fontSize: 12 } },
    grid: { left: 44, right: 20, top: 12, bottom: 30 },
    xAxis: { type: 'category', data: items.map((row) => row.date), axisLine: { lineStyle: { color: '#e8e8ed' } }, axisTick: { show: false }, axisLabel: { color: '#86868b', fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#f0f0f2' } }, axisLabel: { color: '#86868b', fontSize: 11 } },
    series,
  }, { notMerge: true })
}
function renderHotwordChart() {
  if (!hotwordChart) return
  const items = hotwordItems.value || []
  if (!items.length) { hotwordChart.clear(); return }
  const max = Math.max(...items.map((item) => item.count || 0), 1)
  const data = items.map((item) => ({
    name: item.word,
    value: item.count,
    textStyle: { color: `hsl(${(item.count / max) * 210 + 200}, 70%, ${60 - (item.count / max) * 30}%)` },
  }))
  hotwordChart.setOption({
    tooltip: {
      show: true,
      backgroundColor: 'rgba(29,29,31,0.94)',
      borderColor: 'transparent',
      textStyle: { color: '#fff', fontSize: 12 },
      formatter: (params: any) => {
        const raw = items.find((item) => item.word === params.name)
        if (!raw) return `${params.name}: ${params.value}`
        const trend = raw.trend === 'up' ? '↑ 上升' : raw.trend === 'down' ? '↓ 下降' : '→ 持平'
        return `${raw.word}<br/>近 ${visualizationDays.value} 天：${raw.count}<br/>语言：${zh(raw.language)}<br/>趋势：${trend}<br/>来源：${(raw.sources || []).join('、') || '-'}`
      },
    },
    series: [{
      type: 'wordCloud', shape: 'circle', left: 'center', top: 'center', width: '92%', height: '92%',
      sizeRange: [14, 40], rotationRange: [-30, 30], gridSize: 8, layoutAnimation: true,
      textStyle: { fontFamily: 'sans-serif', fontWeight: 'bold' },
      emphasis: { textStyle: { color: '#0071e3' } },
      data,
    }],
  }, { notMerge: true })
}
function severityText(s: string): string {
  return zh(s)
}
function severityBadge(s: string): string {
  if (s === 'critical' || s === 'high') return 'is-rose'
  if (s === 'medium') return 'is-amber'
  if (s === 'low') return 'is-teal'
  return 'is-cyan'
}
function shortTime(s: string): string {
  if (!s) return ''
  const d = new Date(s)
  const pad = (n: number) => String(n).padStart(2, '0')
  return pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
}
function isHandled(status: string): boolean {
  return status !== 'triggered'
}
function renderSourceChart() {
  if (!sourceChart) return
  const items: any[] = (dashboardSources.value as any)?.items || []
  const top = [...items].sort((a: any, b: any) => (b.opinion_count || 0) - (a.opinion_count || 0)).slice(0, 10)
  const names = top.map((it: any) => it.source_name_snapshot || it.source || it.source_key || '未知')
  const values = top.map((it: any) => it.opinion_count || 0)
  sourceChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(29,29,31,0.94)', borderColor: 'transparent', textStyle: { color: '#fff', fontSize: 12 } },
    grid: { left: 8, right: 24, top: 10, bottom: 6, containLabel: true },
    xAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#f0f0f2' } }, axisLabel: { color: '#86868b', fontSize: 11 } },
    yAxis: { type: 'category', inverse: true, data: names, axisLine: { lineStyle: { color: '#e8e8ed' } }, axisTick: { show: false }, axisLabel: { color: '#1d1d1f', fontSize: 12 } },
    series: [{
      type: 'bar', data: values, barWidth: 14,
      itemStyle: { borderRadius: [0, 6, 6, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#0a84ff' }, { offset: 1, color: '#0071e3' }]) },
      label: { show: true, position: 'right', color: '#86868b', fontSize: 11 },
    }],
  }, { notMerge: true })
}
function renderRiskChart() {
  if (!riskChart) return
  const levels = (dashboardRisk.value as any)?.risk_levels
  if (!levels || !Object.keys(levels).length) { riskChart.clear(); return }
  const entries = Object.entries(levels) as Array<[string, number]>
  const total = entries.reduce((acc: number, [, v]) => acc + (Number(v) || 0), 0) || 1
  const data = entries.map(([label, count]) => {
    const m = RISK_MAP[label] ?? { name: zh(label), color: '#8e8e93' }
    return { name: m.name, value: Number(count) || 0, itemStyle: { color: m.color } }
  })
  const pctOf = (v: number) => ((v / total) * 100).toFixed(1)
  riskChart.setOption({
    tooltip: { trigger: 'item', backgroundColor: 'rgba(29,29,31,0.94)', borderColor: 'transparent', textStyle: { color: '#fff', fontSize: 12 }, formatter: (p: any) => `${p.name}<br/>${p.value} 条 · 占比 ${pctOf(p.value)}%` },
    legend: { bottom: 0, left: 'center', itemWidth: 10, itemHeight: 10, textStyle: { color: '#515154', fontSize: 11 }, formatter: (name: string) => { const it = data.find((d) => d.name === name); return it ? `${name} ${pctOf(it.value)}%` : name } },
    graphic: { type: 'text', left: 'center', top: '38%', style: { text: `${total}\n风险结果`, textAlign: 'center', fill: '#1d1d1f', fontSize: 20, fontWeight: 700, lineHeight: 22 } },
    series: [{ type: 'pie', radius: ['46%', '68%'], center: ['50%', '44%'], avoidLabelOverlap: true, label: { show: false }, data }],
  }, { notMerge: true })
}
function measureAlertFeed() {
  const vp = alertViewportEl.value
  const tr = alertTrackEl.value
  if (!vp || !tr) { alertFeedOverflow.value = false; alertNeedScroll.value = false; return }
  const oneHeight = tr.scrollHeight
  const portHeight = vp.clientHeight
  const overflow = oneHeight > portHeight + 4
  alertFeedOverflow.value = overflow
  alertNeedScroll.value = overflow
  if (overflow) {
    alertScrollDuration.value = Math.max((alertFeed.value || []).length * 2.4, 10) + 's'
  }
}

async function ensureDashboardCharts() {
  await nextTick()
  // tab 切换会销毁 DOM，实例失联后需要重建
  if (trendChart && !trendChart.getDom()?.isConnected) { trendChart.dispose(); trendChart = null }
  if (hotwordChart && !hotwordChart.getDom()?.isConnected) { hotwordChart.dispose(); hotwordChart = null }
  if (sourceChart && !sourceChart.getDom()?.isConnected) { sourceChart.dispose(); sourceChart = null }
  if (riskChart && !riskChart.getDom()?.isConnected) { riskChart.dispose(); riskChart = null }
  if (trendChartRef.value && !trendChart) trendChart = echarts.init(trendChartRef.value)
  if (hotwordChartRef.value && !hotwordChart) hotwordChart = echarts.init(hotwordChartRef.value)
  if (sourceChartRef.value && !sourceChart) sourceChart = echarts.init(sourceChartRef.value)
  if (riskChartRef.value && !riskChart) riskChart = echarts.init(riskChartRef.value)
  renderTrendChart()
  renderHotwordChart()
  renderSourceChart()
  renderRiskChart()
  await nextTick()
  measureAlertFeed()
  if (alertViewportEl.value && !alertResizeObserver) {
    alertResizeObserver = new ResizeObserver(() => measureAlertFeed())
    alertResizeObserver.observe(alertViewportEl.value)
  }
}
function handleDashboardResize() {
  trendChart?.resize()
  hotwordChart?.resize()
  sourceChart?.resize()
  riskChart?.resize()
}
onMounted(() => window.addEventListener('resize', handleDashboardResize))
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleDashboardResize)
  trendChart?.dispose(); trendChart = null
  hotwordChart?.dispose(); hotwordChart = null
  sourceChart?.dispose(); sourceChart = null
  riskChart?.dispose(); riskChart = null
  alertResizeObserver?.disconnect(); alertResizeObserver = null
})
function markVisualizationFresh(data: any) {
  const asOf = data?.data_as_of ? new Date(data.data_as_of).getTime() : Date.now()
  visualizationStale.value = Date.now() - asOf > 15 * 60 * 1000
}
async function loadDashboard() {
  loading.value = true
  visualizationError.value = null
  try {
    const params = { days: visualizationDays.value }
    const hotwordParams: Record<string, string | number> = { days: visualizationDays.value, limit: 30 }
    if (hotwordLanguage.value) hotwordParams.language = hotwordLanguage.value
    const emptyItems = { data: { items: [] } }
    const [summary, trends, risk, events, alerts, sourceStats, hotwords, hotwordTrends, alertFeedData] = await Promise.all([
      api.get('/foreign/dashboard/summary', { params }),
      api.get('/foreign/dashboard/trends', { params }),
      api.get('/foreign/dashboard/risk', { params }),
      api.get('/foreign/dashboard/events', { params }),
      api.get('/foreign/dashboard/alerts', { params }),
      api.get('/foreign/dashboard/sources', { params }),
      // 热词接口单独降级：即使无权限或失败也不影响整个看板渲染
      api.get('/foreign/hotwords', { params: hotwordParams }).catch(() => emptyItems),
      api.get('/foreign/hotwords/trends', { params: hotwordParams }).catch(() => emptyItems),
      api.get('/foreign/alerts', { params: { size: 30 } }).catch(() => ({ data: { items: [] } })),
    ])
    dashboardSummary.value = summary.data
    dashboardTrends.value = trends.data
    dashboardRisk.value = risk.data
    dashboardEvents.value = events.data
    dashboardAlerts.value = alerts.data
    dashboardSources.value = sourceStats.data
    alertFeed.value = (alertFeedData as any)?.data?.items || []
    hotwordItems.value = (hotwords as any).data.items || []
    hotwordTrendItems.value = (hotwordTrends as any).data.items || []
    hotwordMeta.value = (hotwords as any).data
    markVisualizationFresh(summary.data)
    await ensureDashboardCharts()
  } catch (err: any) {
    visualizationError.value = visualizationFailure(err)
    dashboardSummary.value = null
  } finally { loading.value = false }
}
async function loadHotwords() {
  loading.value = true
  visualizationError.value = null
  try {
    const params: Record<string, string | number> = { days: visualizationDays.value, limit: 30 }
    if (hotwordLanguage.value) params.language = hotwordLanguage.value
    const [response, trendResponse] = await Promise.all([
      api.get('/foreign/hotwords', { params }),
      api.get('/foreign/hotwords/trends', { params }),
    ])
    hotwordItems.value = response.data.items || []
    hotwordTrendItems.value = trendResponse.data.items || []
    hotwordMeta.value = response.data
    markVisualizationFresh(response.data)
    await ensureDashboardCharts()
  } catch (err: any) {
    visualizationError.value = visualizationFailure(err)
    hotwordItems.value = []
  } finally { loading.value = false }
}
function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}
function operationRequestId(prefix: string) {
  const random = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${prefix}-${random}`.slice(0, 128)
}
async function loadKeywords() {
  loading.value = true
  try {
    const params: Record<string, string | number | boolean> = { page: keywordPage.value, size: keywordSize }
    if (keywordFilters.q) params.q = keywordFilters.q
    if (keywordFilters.category) params.category = keywordFilters.category
    if (keywordFilters.type) params.type = keywordFilters.type
    if (keywordFilters.enabled) params.is_enabled = keywordFilters.enabled === 'true'
    const [list, categories] = await Promise.all([
      api.get('/foreign/keywords', { params }),
      api.get('/foreign/keywords/categories'),
    ])
    keywords.value = list.data.items || []
    keywordTotal.value = list.data.total || 0
    keywordCategories.value = categories.data.items || []
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '外网关键词加载失败')
  } finally { loading.value = false }
}
async function loadOpinions() {
  loading.value = true
  try {
    const params: Record<string, string | number> = { page: opinionPage.value, size: opinionSize, risk_source: riskSource.value }
    if (opinionFilters.q) params.q = opinionFilters.q
    if (opinionFilters.source) params.source = opinionFilters.source
    if (opinionFilters.keyword) params.keyword = opinionFilters.keyword
    if (opinionFilters.date_from) params.date_from = opinionFilters.date_from
    if (opinionFilters.date_to) params.date_to = opinionFilters.date_to
    if (riskFilters.language) params.language = riskFilters.language
    if (riskFilters.risk_level) params.risk_level = riskFilters.risk_level
    if (riskFilters.analysis_status) params.analysis_status = riskFilters.analysis_status
    const [list, sourceList] = await Promise.all([
      api.get('/foreign/opinions', { params }),
      api.get('/foreign/opinions/sources'),
    ])
    opinions.value = list.data.items
    opinionTotal.value = list.data.total
    opinionSources.value = sourceList.data
  } finally { loading.value = false }
}
async function loadRisk() {
  loading.value = true
  try {
    const base: Record<string, string | number> = { size: riskSize }
    if (riskFilters.q) base.q = riskFilters.q
    if (riskFilters.source) base.source = riskFilters.source
    if (riskFilters.language) base.language = riskFilters.language
    if (riskFilters.sentiment) base.sentiment = riskFilters.sentiment
    if (riskFilters.risk_level) base.risk_level = riskFilters.risk_level
    if (riskFilters.analysis_status) base.analysis_status = riskFilters.analysis_status
    if (riskFilters.date_from) base.date_from = riskFilters.date_from
    if (riskFilters.date_to) base.date_to = riskFilters.date_to
    const [first, sourceList] = await Promise.all([
      api.get('/foreign/risk', { params: { ...base, page: 1 } }),
      api.get('/foreign/opinions/sources').catch(() => ({ data: [] })),
    ])
    const total = first.data.total || 0
    let items: RiskResult[] = first.data.items || []
    const pages = Math.min(Math.ceil(total / riskSize), riskMaxPages)
    if (pages > 1) {
      const rest = await Promise.all(
        Array.from({ length: pages - 1 }, (_, index) =>
          api.get('/foreign/risk', { params: { ...base, page: index + 2 } }).catch(() => ({ data: { items: [] } })),
        ),
      )
      for (const response of rest) items = items.concat((response as any).data.items || [])
    }
    risks.value = items
    riskTotal.value = total
    riskPage.value = 1
    if (Array.isArray((sourceList as any).data) && (sourceList as any).data.length) {
      opinionSources.value = (sourceList as any).data
    }
  } catch (err: any) {
    risks.value = []
    riskTotal.value = 0
    ElMessage.error(err?.response?.data?.detail || '外网风险研判数据加载失败')
  } finally { loading.value = false }
}
async function loadRuns() {
  loading.value = true
  try { runs.value = (await api.get('/foreign/collection-runs', { params: { size: 100 } })).data.items } finally { loading.value = false }
}
async function loadEvents() {
  loading.value = true
  eventLoadError.value = null
  try {
    const [candidateResponse, eventResponse, runResponse, autoStatus] = await Promise.all([
      api.get('/foreign/events/candidates', { params: { size: 100, status: 'candidate' } }),
      api.get('/foreign/events', { params: { size: 100 } }),
      api.get('/foreign/event-runs', { params: { size: 20, status: 'failed' } }),
      api.get('/foreign/events/auto-aggregate/status'),
    ])
    eventCandidates.value = candidateResponse.data.items
    foreignEvents.value = eventResponse.data.items
    eventRunFailures.value = runResponse.data.items
    eventAutoStatus.value = autoStatus.data
  } catch (err: any) {
    eventLoadError.value = err?.response?.data?.detail || '请求失败，请稍后重试'
    eventCandidates.value = []
    foreignEvents.value = []
    eventRunFailures.value = []
  } finally { loading.value = false }
}
async function rebuildEvents() {
  if (rebuildingEvents.value) return
  rebuildingEvents.value = true
  try {
    await api.post('/foreign/events/rebuild', { dry_run: true })
    ElMessage.success('外网事件候选 Dry-Run 已完成')
    await loadEvents()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '外网事件候选重建失败')
  } finally { rebuildingEvents.value = false }
}
async function confirmCandidate(row: EventCandidate) {
  const key = `candidate-confirm-${row.id}`
  if (eventActionKey.value) return
  eventActionKey.value = key
  try {
    await api.post(`/foreign/events/candidates/${row.id}/confirm`, { reason: 'Foreign workspace manual confirmation', request_id: operationRequestId(`candidate-confirm-${row.id}`) })
    ElMessage.success('外网事件候选已确认')
    await loadEvents()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '确认外网事件候选失败')
  } finally { eventActionKey.value = null }
}
async function rejectCandidate(row: EventCandidate) {
  const key = `candidate-reject-${row.id}`
  if (eventActionKey.value) return
  eventActionKey.value = key
  try {
    await api.post(`/foreign/events/candidates/${row.id}/reject`, { reason: 'Foreign workspace manual rejection', request_id: operationRequestId(`candidate-reject-${row.id}`) })
    ElMessage.success('外网事件候选已拒绝')
    await loadEvents()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '拒绝外网事件候选失败')
  } finally { eventActionKey.value = null }
}
async function loadEventDetail(id: number) {
  if (selectedForeignEvent.value?.id === id && selectedForeignEvent.value.opinions) return
  if (eventDetailLoadingId.value) return
  eventDetailLoadingId.value = id
  try {
    selectedForeignEvent.value = (await api.get(`/foreign/events/${id}`)).data
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '外网事件详情加载失败')
  } finally { eventDetailLoadingId.value = null }
}
async function archiveEvent(row: ForeignEvent) {
  if (eventActionKey.value) return
  eventActionKey.value = `event-archive-${row.id}`
  try {
    await api.post(`/foreign/events/${row.id}/status`, { status: 'archived', reason: 'Foreign workspace archive', request_id: operationRequestId(`event-archive-${row.id}`) })
    ElMessage.success('外网事件已归档')
    await loadEvents()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '外网事件归档失败')
  } finally { eventActionKey.value = null }
}
async function closeEvent(row: ForeignEvent) {
  if (!canChangeEventStatus || eventActionKey.value) return
  eventActionKey.value = `event-close-${row.id}`
  try {
    const prompt = await ElMessageBox.prompt('请输入关闭原因', '关闭外网事件', { inputType: 'textarea', inputValidator: (value: string) => value.trim() ? true : '原因不能为空' })
    await api.post(`/foreign/events/${row.id}/close`, { reason: prompt.value, request_id: operationRequestId(`event-close-${row.id}`) })
    ElMessage.success('外网事件已关闭')
    await loadEvents()
  } catch (err: any) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(err?.response?.data?.detail || '关闭外网事件失败')
  } finally { eventActionKey.value = null }
}
async function mergeEvent(row: ForeignEvent) {
  if (!canMergeEvents || eventActionKey.value) return
  eventActionKey.value = `event-merge-${row.id}`
  try {
    const prompt = await ElMessageBox.prompt('请输入目标外网事件 ID', '合并外网事件', { inputType: 'number', inputValidator: (value: string) => /^\d+$/.test(value) && Number(value) !== row.id ? true : '请输入不同的有效事件 ID' })
    await api.post(`/foreign/events/${row.id}/merge`, { target_event_id: Number(prompt.value), reason: 'Foreign workspace manual merge', request_id: operationRequestId(`event-merge-${row.id}`) })
    ElMessage.success('外网事件已合并')
    selectedForeignEvent.value = null
    await loadEvents()
  } catch (err: any) { if (err === 'cancel' || err === 'close') return; ElMessage.error(err?.response?.data?.detail || '外网事件合并失败') } finally { eventActionKey.value = null }
}
async function splitEvent(row: ForeignEvent) {
  if (!canSplitEvents || !row.opinions?.length || eventActionKey.value) return
  eventActionKey.value = `event-split-${row.id}`
  try {
    const prompt = await ElMessageBox.prompt('请输入要拆出的文章 ID，多个 ID 用逗号分隔', '拆分外网事件', { inputValidator: (value: string) => value.split(',').every(item => /^\s*\d+\s*$/.test(item)) ? true : '请输入逗号分隔的文章 ID' })
    const opinion_ids = prompt.value.split(',').map(item => Number(item.trim())).filter(Boolean)
    await api.post(`/foreign/events/${row.id}/split`, { opinion_ids, reason: 'Foreign workspace manual split', request_id: operationRequestId(`event-split-${row.id}`) })
    ElMessage.success('外网事件已拆分')
    selectedForeignEvent.value = null
    await loadEvents()
  } catch (err: any) { if (err === 'cancel' || err === 'close') return; ElMessage.error(err?.response?.data?.detail || '外网事件拆分失败') } finally { eventActionKey.value = null }
}
async function createKeyword() {
  if (keywordSaving.value) return
  const word = keywordDraft.word.trim()
  if (!word) { ElMessage.warning('请输入关键词'); return }
  keywordSaving.value = true
  try {
    const payload = { word, category: keywordDraft.category.trim() || 'general', type: keywordDraft.type, weight: keywordDraft.weight, severity_weight: 0, source: editingKeywordId.value ? undefined : 'custom', is_enabled: true }
    if (editingKeywordId.value) {
      await api.patch(`/foreign/keywords/${editingKeywordId.value}`, payload)
      ElMessage.success('外网关键词已更新')
    } else {
      await api.post('/foreign/keywords', payload)
      ElMessage.success('外网关键词已新增')
    }
    editingKeywordId.value = null
    keywordDraft.word = ''
    await loadKeywords()
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '外网关键词保存失败') } finally { keywordSaving.value = false }
}
async function toggleKeyword(row: Keyword) {
  if (keywordSaving.value) return
  keywordSaving.value = true
  try { await api.patch(`/foreign/keywords/${row.id}`, { is_enabled: !row.is_enabled }); await loadKeywords() } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '外网关键词更新失败') } finally { keywordSaving.value = false }
}
async function removeKeyword(id: number) {
  try {
    await ElMessageBox.confirm('确认删除这个外网关键词？', '删除关键词', { type: 'warning' })
    await api.delete(`/foreign/keywords/${id}`)
    await loadKeywords()
    ElMessage.success('外网关键词已删除')
  } catch (err: any) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(err?.response?.data?.detail || '外网关键词删除失败')
  }
}
function editKeyword(row: Keyword) {
  editingKeywordId.value = row.id
  keywordDraft.word = row.word
  keywordDraft.category = row.category
  keywordDraft.type = row.type || 'monitoring'
  keywordDraft.weight = row.weight ?? 10
}
async function bulkToggleKeywords(isEnabled: boolean) {
  if (keywordSaving.value || !keywords.value.length) return
  keywordSaving.value = true
  try { await api.post('/foreign/keywords/bulk-status', { keyword_ids: keywords.value.map(row => row.id), is_enabled: isEnabled }); await loadKeywords(); ElMessage.success('外网关键词状态已批量更新') } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '批量更新失败') } finally { keywordSaving.value = false }
}
async function openOpinion(id: number) {
  detailId.value = id
  detailVisible.value = true
}
// AUDIT-008：外网告警标题可点击，按关联对象类型打开对应详情（文章→详情弹窗；事件→事件标签页内联详情）
function openAlertTarget(row: ForeignAlert) {
  if (row.foreign_opinion_id) {
    openOpinion(row.foreign_opinion_id)
  } else if (row.foreign_event_id) {
    activeTab.value = 'events'
    loadEventDetail(row.foreign_event_id)
  }
}
async function analyzeRisk(id: number) {
  if (!canAnalyzeRisk) {
    ElMessage.warning('当前账号没有外网规则分析权限')
    return
  }
  try {
    await api.post(`/foreign/risk/${id}/analyze`, {})
    ElMessage.success('外网规则分析完成')
    await loadRisk()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '外网规则分析失败')
  }
}
async function collectNow() {
  if (collecting.value) return
  collecting.value = true
  try {
    const { data } = await api.post('/foreign/collect', { source_ids: selectedSourceIds.value })
    const result = await pollTask(data.task_id)
    if (result.status === 'success') { ElMessage.success(`外网采集完成：新增 ${result.result?.created || 0} 条，已自动规则研判 ${result.result?.analyzed || 0} 条`); await loadOpinions(); await loadRuns(); await loadRisk() }
    else ElMessage.error(result.error || '外网采集失败')
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || err?.message || '外网采集失败') } finally { collecting.value = false }
}
async function collectAll() {
  try {
    await ElMessageBox.confirm(
      'This runs every enabled foreign source. Continue?',
      'Confirm full foreign collection',
      { type: 'warning', confirmButtonText: 'Collect all', cancelButtonText: 'Cancel' },
    )
  } catch (err) {
    if (err === 'cancel' || err === 'close') return
    throw err
  }
  if (collecting.value) return
  collecting.value = true
  try {
    const { data } = await api.post('/foreign/collect', { all_sources: true })
    const result = await pollTask(data.task_id)
    if (result.status === 'success') { ElMessage.success(`Full collection complete: ${result.result?.created || 0} new articles, ${result.result?.analyzed || 0} auto-analyzed`); await loadOpinions(); await loadRuns(); await loadRisk() }
    else ElMessage.error(result.error || 'Foreign collection failed')
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || err?.message || 'Foreign collection failed') } finally { collecting.value = false }
}
watch(
  () => route.query.tab,
  (value) => {
    // 旧外网页签（外网告警 / 告警规则）已整合进统一预警中心 /alerts。
    // 直接访问旧地址时重定向过去，保持书签/历史可用。
    const tab = value as string | undefined
    if (tab === 'alerts' || tab === 'alertRules') {
      router.replace({ path: '/alerts', query: { tab: tab === 'alerts' ? 'records' : 'rules', scope: 'foreign' } })
      return
    }
    const normalizedTab = normalizeTab(tab)
    activeTab.value = normalizedTab
    loadTab(normalizedTab)
  },
  { immediate: true },
)
onMounted(loadApprovedSources)
</script>

<style scoped>
.foreign-page { min-width: 0; }
.workspace-head { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; margin-bottom: 20px; }
.collection-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.source-scope-label { color: #6e6e73; font-size: 12px; align-self: center; }
.source-picker { position: relative; align-self: center; font-size: 12px; }
.source-picker summary { cursor: pointer; color: #0071e3; }
.source-picker-menu { position: absolute; z-index: 20; right: 0; top: 24px; min-width: 240px; max-height: 240px; overflow: auto; padding: 10px; background: #fff; border: 1px solid #e8e8ed; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
.source-picker-menu label { display: block; padding: 5px 2px; white-space: nowrap; }
.schedule-status { display:flex; flex-wrap:wrap; gap:12px; align-items:center; padding:10px 12px; margin-bottom:14px; border:1px solid #cfe8d4; background:#f3fbf4; color:#276738; font-size:13px; }
.schedule-status.disabled { border-color:#e5e7eb; background:#f7f7f8; color:#6e6e73; }
.schedule-status .error-text { color:#c45656; flex-basis:100%; }
.workspace-head h2 { margin: 0 0 6px; font-size: 24px; color: #1d1d1f; }
.workspace-head p, .source-note, .muted { margin: 0; color: #86868b; font-size: 13px; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid #e8e8ed; }
.tab { border: 0; background: transparent; padding: 10px 16px; color: #6e6e73; cursor: pointer; border-bottom: 2px solid transparent; }
.tab.active { color: #0071e3; border-bottom-color: #0071e3; }
.subtabs { display: flex; gap: 8px; margin: -4px 0 14px; border-bottom: 1px solid #e8e8ed; }
.subtabs .tab { padding: 8px 12px; }
.panel { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 8px 24px rgba(0,0,0,.05); }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; align-items: center; }
.visualization-panel { min-height: 280px; }
.visualization-content { display: grid; gap: 18px; }
.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(130px, 1fr)); gap: 12px; }
.metric-card, .data-section { border: 1px solid #e8e8ed; border-radius: 8px; padding: 14px; background: #fbfbfc; }
.metric-card { display: grid; gap: 6px; min-height: 92px; }
.metric-card span, .metric-card small { color: #6e6e73; font-size: 12px; }
.metric-card strong { color: #1d1d1f; font-size: 24px; }
.visualization-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.data-section h3 { margin: 0 0 10px; font-size: 14px; color: #1d1d1f; }
.distribution-row { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid #eeeeef; font-size: 13px; }
.distribution-row:last-child { border-bottom: 0; }
.distribution-row small { display: block; color: #86868b; font-size: 11px; }
.visualization-meta, .scope-badge, .source-management-note { color: #6e6e73; font-size: 12px; }
.scope-badge { padding: 4px 8px; border: 1px solid #d8e8f8; border-radius: 999px; color: #1769aa; background: #f3f9ff; }
.stale-badge { padding: 4px 8px; border: 1px solid #f0c36d; border-radius: 999px; color: #8a5a00; background: #fff8e6; }
.source-management-note { border-top: 1px solid #e8e8ed; margin-top: 18px; padding-top: 14px; }
@media (max-width: 900px) { .metric-grid { grid-template-columns: repeat(2, minmax(130px, 1fr)); } .visualization-columns { grid-template-columns: 1fr; } }
.input { height: 38px; border: 1px solid #d2d2d7; border-radius: 8px; padding: 0 11px; min-width: 190px; color: #1d1d1f; background: #fff; }
.btn { border: 0; border-radius: 8px; padding: 9px 15px; cursor: pointer; font-size: 13px; }
.btn-primary { color: #fff; background: #0071e3; }.btn-secondary { color: #1d1d1f; background: #f0f0f3; }
.btn:disabled { opacity: .5; cursor: default; }
.table-wrap { overflow-x: auto; } table { width: 100%; border-collapse: collapse; min-width: 720px; font-size: 13px; }
th, td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #e8e8ed; vertical-align: top; } th { color: #86868b; font-weight: 600; }
tbody tr:hover { background: #fafafc; cursor: pointer; }.title-cell { min-width: 280px; font-weight: 600; }
.tag { display: inline-block; color: #0071e3; background: #e8f1fd; border-radius: 999px; padding: 3px 7px; margin: 0 4px 3px 0; }
.status, .status-toggle { display: inline-block; border: 0; border-radius: 999px; padding: 4px 9px; color: #86868b; background: #f0f0f3; }.status.on, .status-toggle.on { color: #1a8e3c; background: #eafaf0; }.status.failed { color: #b42318; background: #fef3f2; }
.status-toggle { cursor: pointer; }.link-btn { border: 0; background: transparent; color: #0071e3; cursor: pointer; margin-right: 10px; }.link-btn.danger { color: #ff3b30; }
.feed { max-width: 420px; overflow-wrap: anywhere; color: #515154; }.proxy-mark { color: #1a8e3c; margin-left: 8px; }.error-cell { color: #ff3b30; max-width: 240px; }.date-input { min-width: 145px; }
.empty { text-align: center; color: #86868b; padding: 30px; }.pager { display: flex; justify-content: flex-end; align-items: center; gap: 10px; margin-top: 14px; color: #6e6e73; font-size: 13px; }
.detail-mask { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: grid; place-items: center; padding: 20px; z-index: 20; }.detail { position: relative; width: min(760px, 100%); max-height: 80vh; overflow: auto; background: #fff; border-radius: 12px; padding: 24px; }.detail h3 { margin: 0 34px 10px 0; color: #1d1d1f; }.detail-meta { color: #86868b; font-size: 13px; }.detail-text { white-space: pre-wrap; line-height: 1.8; color: #2b2b2e; }.close { position: absolute; right: 14px; top: 12px; border: 0; background: #f0f0f3; border-radius: 50%; width: 28px; height: 28px; cursor: pointer; }.original { color: #0071e3; }
.title-link { padding: 0; font-weight: 600; text-align: left; }
.alert-dialog, .history-dialog, .rule-dialog { width: min(820px, 100%); max-height: 86vh; }
.rule-dialog label { display: grid; gap: 6px; margin: 12px 0; color: #424245; font-size: 13px; }
.rule-preview { margin-top: 14px; padding: 12px; background: #f5f5f7; border-radius: 8px; }
.rule-preview pre { margin: 8px 0 0; white-space: pre-wrap; font-size: 12px; }
.event-detail { margin-top: 18px; border-top: 1px solid #e8e8ed; padding-top: 16px; }
.event-detail-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.event-detail h3 { margin: 0; color: #1d1d1f; }
.event-metrics { display: flex; flex-wrap: wrap; gap: 12px 20px; margin: 12px 0; color: #424245; font-size: 13px; }
.event-failures { margin: 12px 0; padding: 12px; border: 1px solid #f3c7c2; background: #fff8f7; color: #5c1b16; }
.event-failure-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; font-size: 13px; }
.error-state { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 12px 0; padding: 12px; border: 1px solid #f3c7c2; background: #fff8f7; color: #5c1b16; }
.alert-scope-note { margin: 10px 0 14px; padding: 10px 12px; border: 1px solid #d9e7f7; background: #f5f9ff; color: #36536f; font-size: 13px; }
.alert-failures { margin: 12px 0; padding: 12px; border: 1px solid #f3c7c2; background: #fff8f7; color: #5c1b16; }
.alert-failure-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; font-size: 13px; }
.alert-detail { margin-top: 18px; border-top: 1px solid #e8e8ed; padding-top: 16px; }
.alert-action-history { display: grid; gap: 8px; margin-top: 12px; }
.alert-action-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 10px 0; border-bottom: 1px solid #f0f0f3; }
.event-opinion { display: grid; gap: 4px; padding: 10px 0; border-bottom: 1px solid #f0f0f3; }
/* ===== 外网 Dashboard：苹果风卡片（对齐驾驶舱视觉） ===== */
.tabs { display: flex; align-items: center; gap: 0; margin-bottom: 18px; border-bottom: 1px solid #e8e8ed; flex-wrap: wrap; }
.tab { border: 0; background: transparent; padding: 12px 20px; color: #909399; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; font-size: 14px; font-weight: 500; transition: color .15s ease, border-color .15s ease; }
.tab:hover { color: #606266; }
.tab.active { color: var(--el-color-primary, #409eff); border-bottom-color: var(--el-color-primary, #409eff); font-weight: 600; }
.tab-actions { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.source-scope-label { font-size: 13px; color: #86868b; }
.btn-sm { padding: 6px 12px; font-size: 13px; }

.fw-dash-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; margin-bottom: 18px; }
.fw-dash-title { margin: 0 0 4px; font-size: 20px; font-weight: 600; color: #1d1d1f; letter-spacing: -0.01em; }
.fw-dash { display: grid; gap: 16px; }
.fw-kpi-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.fw-kpi { display: grid; gap: 6px; align-content: start; padding: 16px 18px; background: #fff; border: 1px solid #e8e8ed; border-radius: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.fw-kpi-label { font-size: 12.5px; font-weight: 600; color: #86868b; }
.fw-kpi-value { font-size: 28px; font-weight: 700; color: #1d1d1f; line-height: 1.15; font-variant-numeric: tabular-nums; }
.fw-kpi small { font-size: 12px; color: #86868b; }
.fw-dash-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; align-items: stretch; }
.fw-dash-grid > .fw-col-1 { grid-column: 1; }
.fw-dash-grid > .fw-col-2 { grid-column: 2; }
.fw-card { padding: 16px 18px; background: #fff; border: 1px solid #e8e8ed; border-radius: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); min-width: 0; }
.fw-card h3 { margin: 0 0 10px; font-size: 15px; font-weight: 600; color: #1d1d1f; }
.fw-card .empty { margin: 6px 0 0; color: #86868b; font-size: 13px; }
.fw-card-wide { grid-column: 1 / -1; }
.fw-card .table-wrap table { min-width: 560px; }
.fw-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.fw-card-head h3 { margin: 0; }
.fw-chart { width: 100%; height: 260px; }
.fw-chart-tall { height: 300px; }
.fw-card-alert { display: flex; flex-direction: column; }
.fw-alert-feed { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.fw-alert-summary { display: flex; gap: 16px; margin-bottom: 8px; font-size: 12px; color: #86868b; }
.fw-alert-sum { display: inline-flex; align-items: center; gap: 6px; }
.fw-sum-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.fw-sum-dot.is-amber { background: #ff9f0a; }
.fw-sum-dot.is-teal { background: #34c759; }
.fw-alert-viewport { position: relative; flex: 1; min-height: 0; overflow: hidden; }
.fw-alert-track { display: flex; flex-direction: column; gap: 8px; }
.fw-alert-track.scrolling { animation: fw-alert-scroll linear infinite; }
.fw-alert-track:hover { animation-play-state: paused; }
@keyframes fw-alert-scroll { from { transform: translateY(0); } to { transform: translateY(-50%); } }
.fw-alert-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.fw-alert-row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid #eef0f2; border-radius: 12px; background: #fafbfc; cursor: pointer; transition: background .15s ease; }
.fw-alert-row:hover { background: #f2f4f7; }
.fw-alert-main { flex: 1; min-width: 0; }
.fw-alert-title { font-size: 13px; font-weight: 600; color: #1d1d1f; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fw-alert-meta { font-size: 11px; color: #86868b; margin-top: 2px; }
.fw-badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.fw-badge.is-rose { color: #ff3b30; background: #ffeceb; }
.fw-badge.is-amber { color: #8a5a00; background: #fff3da; }
.fw-badge.is-teal { color: #1a8e3c; background: #eafaf0; }
.fw-badge.is-cyan { color: #0071e3; background: #e8f1fd; }
.fw-mono { font-variant-numeric: tabular-nums; }
@media (prefers-reduced-motion: reduce) { .fw-alert-track.scrolling { animation: none; } }
.fw-legend { display: flex; flex-wrap: wrap; gap: 6px; }
.fw-legend-item { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border: 1px solid #e8e8ed; border-radius: 980px; background: #fff; color: #1d1d1f; font-size: 12px; cursor: pointer; transition: opacity .15s ease, background .15s ease; }
.fw-legend-item:hover { background: #f5f5f7; }
.fw-legend-item i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.fw-legend-item.off { opacity: .38; }
.alert-title { color: #1d1d1f; font-weight: 600; }
.alert-title-link { background: none; border: none; padding: 0; margin: 0; font: inherit; cursor: pointer; text-align: left; color: #1d1d1f; }
.alert-title-link:hover { color: #0071e3; text-decoration: underline; }
.alert-title-link:focus-visible { outline: 2px solid #0071e3; outline-offset: 2px; border-radius: 4px; }
.linked-cell { min-width: 180px; }
.fw-hotwords { display: flex; flex-wrap: wrap; gap: 8px; }
.fw-hotword { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 980px; background: #f5f5f7; color: #1d1d1f; font-size: 13px; font-weight: 500; }
.fw-hotword small { color: #0071e3; font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }
/* ===== 舆情+风险合并表：横向滚动窗 ===== */
.tbl-scroll { min-width: 0; overflow-x: auto; }
.tbl-scroll table { min-width: 1880px; }
.tbl-scroll th { white-space: nowrap; }
.tbl-scroll .title-cell { min-width: 260px; }
/* 当前有效风险来源徽标：系统规则 */
.src-tag { display: inline-block; font-size: 12px; padding: 1px 7px; border-radius: 999px; background: #eef1f5; color: #51585e; }
.src-tag.ai { background: #fdeede; color: #b05a00; font-weight: 600; }
/* 规则 / AI 双值单元格 */
.dual-cell { display: inline-flex; flex-direction: column; gap: 2px; align-items: flex-start; line-height: 1.4; }
.dual-cell .muted { font-size: 12px; }

@media (max-width: 1100px) { .fw-kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } .fw-dash-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 820px) { .fw-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .fw-dash-grid { grid-template-columns: 1fr; } .fw-dash-grid > .fw-col-1, .fw-dash-grid > .fw-col-2 { grid-column: 1; } }
@media (max-width: 700px) { .workspace-head { flex-direction: column; }.input { width: 100%; min-width: 0; } }
</style>
