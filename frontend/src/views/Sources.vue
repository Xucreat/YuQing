<template>
  <div class="ds-page" v-loading="loading">
    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="filters">
        <el-select v-model="filterRegion" placeholder="全部区域" clearable class="f-select" @change="reload(true)">
          <el-option v-for="o in regionOptions" :key="o.code" :label="o.name" :value="o.code" />
        </el-select>
        <el-select v-model="filterEnabled" placeholder="启用状态" clearable class="f-select" @change="reload(true)">
          <el-option label="已启用" :value="true" />
          <el-option label="已停用" :value="false" />
        </el-select>
        <el-input v-model="filterQ" placeholder="搜索名称 / key" clearable class="f-input" @keyup.enter="reload(true)" @clear="reload(true)" />
        <button class="btn btn-ghost" @click="reload(true)">刷新</button>
      </div>
      <div class="toolbar-right">
        <span class="count-tip">共 {{ total }} 个数据源</span>
        <button v-if="isSuperuser" class="btn btn-ghost" @click="openBatchSchedule">统一采集频率设置</button>
        <button v-if="isSuperuser" class="btn btn-primary" @click="openCreate">+ 新建采集源</button>
      </div>
    </div>

    <!-- 批量操作栏（复用于关键词管理页的批量启用/停用交互与样式） -->
    <div class="batch-bar" v-if="isSuperuser">
      <span class="batch-info">已选 {{ selectedIds.length }} 项</span>
      <button class="btn btn-primary btn-sm" :disabled="selectedIds.length === 0" @click="batchToggle(true)">批量启用</button>
      <button class="btn btn-ghost btn-sm" :disabled="selectedIds.length === 0" @click="batchToggle(false)">批量停用</button>
      <button class="btn btn-ghost btn-sm" v-if="selectedIds.length" @click="selectedIds = []">取消选择</button>
    </div>

    <!-- 管理表格 -->
    <div class="card source-table-card">
      <table class="tbl">
        <thead>
          <tr>
            <th style="width:44px"><input type="checkbox" class="row-check" :checked="pageAllSelected" @change="togglePageAll" /></th>
            <th>名称</th>
            <th style="width:180px">区域</th>
            <th style="width:240px">关键词策略</th>
            <th style="width:200px">过滤策略</th>
            <th style="width:96px">启用</th>
            <th style="width:120px">优先级</th>
            <th style="width:170px">健康状态</th>
            <th style="width:110px">最近状态</th>
            <th style="width:130px">最近抓取 / 新增</th>
            <th style="width:132px">采集质量</th>
            <th style="width:170px">最近运行时间</th>
            <th style="width:96px">自动采集</th>
            <th style="width:120px">采集周期</th>
            <th style="width:160px">下一次采集</th>
            <th style="width:160px">最近采集</th>
            <th style="width:120px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sources" :key="s.id">
            <td><input type="checkbox" class="row-check" :checked="selectedIds.includes(s.id)" @change="toggleRow(s)" /></td>
            <td>
              <div class="ds-name">
                {{ s.name }}
                <span class="ck" :class="s.type === 'rss' ? 'ck-rss' : (s.collector_kind === 'external_browser' ? 'ck-ext' : (s.collector_kind === 'dedicated' ? 'ck-ded' : 'ck-gen'))">
                  {{ s.type === 'rss' ? 'RSS' : (s.collector_kind === 'external_browser' ? '聚合' : (s.collector_kind === 'dedicated' ? '专用型' : '通用型')) }}
                </span>
              </div>
              <div class="ds-key">{{ s.key }} · {{ s.type }}</div>
            </td>
            <td class="region-cell">
              <span v-if="s.scope_display === '全国'" class="pill pill-gray region-pill">全国</span>
              <span v-else class="pill pill-blue region-pill">{{ s.scope_display }}</span>
            </td>
            <td>
              <div class="keyword-policy">
                <span class="pill" :class="keywordModePill(s.keyword_mode)">
                  {{ keywordModeText(s.keyword_mode) }}
                </span>
                <div class="keyword-policy-desc">{{ s.keyword_description }}</div>
                <div class="keyword-policy-list" :title="(s.effective_keywords || []).join('、')">
                  {{ effectiveKeywordsText(s) }}
                </div>
              </div>
            </td>
            <td>
              <div class="filter-strategy-cell">
                <span class="pill" :class="filterStrategyPill(s.effective_filter_strategy)">{{ filterStrategyText(s.effective_filter_strategy) }}</span>
                <div class="filter-strategy-src">{{ filterStrategySourceText(s.effective_filter_strategy) }}</div>
              </div>
            </td>
            <td>
              <el-switch v-if="isSuperuser"
                :model-value="s.enabled"
                :loading="s._saving"
                @change="(v: any) => onToggle(s, v)"
              />
              <span v-else :class="s.enabled ? 'status-on' : 'status-off'">{{ s.enabled ? '已启用' : '已停用' }}</span>
            </td>
            <td>
              <el-input-number v-if="isSuperuser"
                :model-value="s.priority"
                :min="0"
                :max="999"
                size="small"
                controls-position="right"
                @change="(v: any) => onPriority(s, v)"
              />
                <span v-else>{{ s.priority }}</span>
            </td>
            <td>
              <template v-if="s.health_summary">
                <span class="pill" :class="healthPill(s.health_summary.health_status)">
                  {{ healthText(s.health_summary.health_status) }}
                </span>
                <div class="quality-hint">{{ s.health_summary.health_reason }}</div>
                <div v-if="s.health_summary.last_error_code" class="quality-hint">
                  {{ s.health_summary.last_error_code }} · 连续失败 {{ s.health_summary.consecutive_failures }} 次
                </div>
              </template>
              <span v-else class="muted">未知</span>
            </td>
            <td>
              <span v-if="s.latest_run_status" class="pill" :class="runPill(s.latest_run_status)">{{ runText(s.latest_run_status) }}</span>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <template v-if="qualityFor(s)">
                <span class="metric-number">{{ qualityFor(s)?.latest_fetched_raw ?? '—' }}</span>
                <span class="metric-divider">/</span>
                <span class="metric-number">{{ qualityFor(s)?.latest_created ?? '—' }}</span>
              </template>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <template v-if="qualityFor(s)">
                <span class="pill" :class="qualityPill(qualityFor(s)!.empty_fetch_risk)">
                  {{ qualityText(qualityFor(s)!.empty_fetch_risk) }}
                </span>
                <div v-if="qualityHint(qualityFor(s)!)" class="quality-hint">{{ qualityHint(qualityFor(s)!) }}</div>
              </template>
              <span v-else class="muted">暂无运行</span>
            </td>
            <td>
              <span v-if="s.latest_run_at">{{ formatTime(s.latest_run_at) }}</span>
              <span v-else class="muted">从未运行</span>
            </td>
            <td>
              <el-switch v-if="isSuperuser"
                :model-value="s.schedule_enabled"
                :loading="s._savingSchedule"
                @change="(v: any) => onScheduleEnabled(s, v)"
              />
              <span v-else>{{ s.schedule_enabled ? '自动' : '手动' }}</span>
            </td>
            <td>
              <span v-if="s.schedule_interval_minutes">{{ s.schedule_interval_minutes }} 分钟</span>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <span v-if="s.next_collect_time">{{ formatTime(s.next_collect_time) }}</span>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <span v-if="s.last_collect_time">{{ formatTime(s.last_collect_time) }}</span>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <button class="btn btn-mini" @click="openHistory(s)">查看历史</button>
              <button v-if="isSuperuser" class="btn btn-mini" @click="openConfig(s)">配置</button>
              <button v-if="isSuperuser" class="btn btn-mini" @click="openSchedule(s)">调度</button>
            </td>
          </tr>
          <tr v-if="!sources.length"><td colspan="17" class="empty-row">暂无数据源</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div class="pager" v-if="total > size">
      <Pager
        :total="total"
        :page-size="size"
        :current-page="page"
        @current-change="onPage"
      />
    </div>

    <!-- 查看历史弹窗（仅采集历史） -->
    <el-dialog
      v-model="historyVisible"
      :title="'采集历史 · ' + (currentSource?.name || '')"
      width="760px"
      align-center
      class="apple-dialog"
      modal-class="apple-modal"
    >
      <div v-loading="historyLoading">
        <div class="run-summary" v-if="history.length">
          <div class="run-stat">
            <span>原始候选</span>
            <b>{{ historySummary.fetched }}</b>
          </div>
          <div class="run-stat">
            <span>{{ commentStatsLabel }}</span>
            <b>{{ commentStatsValue(historySummary.commentsSkipped) }}</b>
          </div>
          <div class="run-stat">
            <span>准入过滤</span>
            <b>{{ historySummary.admissionFiltered }}</b>
          </div>
          <div class="run-stat">
            <span>最终形成舆情</span>
            <b>{{ historySummary.created }}</b>
          </div>
        </div>
        <div class="card table-card">
          <table class="tbl hist-tbl">
            <thead>
              <tr>
                <th style="width:170px">时间</th>
                <th>采集器</th>
                <th style="width:70px">抓取</th>
                <th style="width:92px">{{ commentStatsLabel }}</th>
                <th style="width:92px">准入过滤</th>
                <th style="width:70px">新增</th>
                <th style="width:70px">分析</th>
                <th style="width:80px">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in history" :key="r.id">
                <td>{{ formatTime(r.start_time) }}</td>
                <td>{{ r.collector_name }}</td>
                <td>{{ r.fetched_raw }}</td>
                <td>{{ commentStatsValue(r.comments_skipped) }}</td>
                <td>{{ r.admission_filtered ?? 0 }}</td>
                <td>{{ r.created }}</td>
                <td>{{ r.analyzed }}</td>
                <td><span class="pill" :class="runPill(r.status)">{{ runText(r.status) }}</span></td>
              </tr>
              <tr v-if="!history.length"><td colspan="8" class="empty-row">暂无采集记录</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <template #footer>
        <span class="dlg-foot">
          <button class="btn btn-ghost" @click="historyVisible = false">关闭</button>
        </span>
      </template>
    </el-dialog>

    <!-- 配置弹窗（过滤策略 + 高级 config_json） -->
    <el-dialog
      v-model="configVisible"
      :title="'配置 · ' + (currentSource?.name || '')"
      width="600px"
      align-center
      class="apple-dialog"
      modal-class="apple-modal"
    >
      <p class="dlg-sub">区域范围</p>
      <div class="cf-row">
        <label class="cf-label">区域（不选 = 全国）</label>
        <el-cascader
          v-model="scopeRegionDraft"
          :options="regionTreeOptions"
          :props="regionCascaderProps"
          :loading="regionCatalogLoading"
          :disabled="regionCatalogLoading"
          :show-all-levels="false"
          collapse-tags
          clearable
          filterable
          placeholder="不选 = 全国"
          class="cf-full"
        />
        <div class="cf-hint">可逐级选择省、市、县、乡镇/街道，选到任一级即可；保存后仍可修改。</div>
      </div>
      <div class="cf-divider"></div>
      <p class="dlg-sub">过滤策略（filter_mode / keyword_scope）</p>
      <div class="cf-row">
        <label class="cf-label">过滤模式 filter_mode</label>
        <el-select v-model="filterModeDraft" class="cf-full" @change="onConfigFilterModeChange">
          <el-option v-for="o in filterModeOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </div>
      <div class="cf-row">
        <label class="cf-label">关键词范围 keyword_scope</label>
        <el-select v-model="keywordScopeDraft" class="cf-full">
          <el-option
            v-for="o in keywordScopeOptions"
            :key="o.value"
            :label="o.label"
            :value="o.value"
            :disabled="scopeDisabledFor(filterModeDraft, o.value)"
          />
        </el-select>
      </div>
      <div class="cf-row">
        <label class="cf-label">单次抓取条数 max_items</label>
        <el-input-number v-model="maxItemsDraft" :min="1" :max="500" size="small" controls-position="right" />
      </div>
      <div class="cfg-hint">留空（默认）即按采集器内置上限；设置后单次最多抓取该条数。</div>
      <div v-if="illegalComboError(filterModeDraft, keywordScopeDraft)" class="cfg-err">
        {{ illegalComboError(filterModeDraft, keywordScopeDraft) }}
      </div>

      <!-- 生效策略预览（实时，基于当前下拉选择） -->
      <div class="strategy-preview">
        <div class="strategy-preview-title">当前生效策略预览</div>
        <div class="strategy-preview-row">
          <span class="pill" :class="draftStrategyPill()">{{ draftStrategyText() }}</span>
          <span class="strategy-preview-src">{{ draftStrategySource() }}</span>
        </div>
        <div class="strategy-preview-ks">关键词范围：{{ draftKeywordScopeText() }}</div>
      </div>

      <!-- 风险提示（仅提示，不阻止合法配置） -->
      <div v-if="filterModeDraft === 'topic_only'" class="cfg-warn">
        ⚠ 该策略将降低地域限定能力，可能扩大采集范围，请确认。
      </div>
      <div v-if="filterModeDraft === 'region_only'" class="cfg-info">
        该策略仅关注区域相关内容。
      </div>

      <div class="cf-divider"></div>

      <template v-if="currentSource && currentSource.type === 'rss'">
        <p class="dlg-sub">RSS 地址</p>
        <div class="feed-list">
          <div class="feed-item" v-for="(u, i) in feedListEdit" :key="i">
            <el-input v-model="feedListEdit[i]" placeholder="https://example.com/feed.xml" />
            <button class="btn btn-ghost btn-mini" type="button" :disabled="feedListEdit.length <= 1" @click="removeFeedEdit(i)">删除</button>
          </div>
        </div>
        <button class="btn btn-ghost btn-mini" type="button" @click="addFeedEdit">+ 添加地址</button>
      </template>

      <!-- bb-browser 聚合采集：平台选择（仅 external_browser） -->
      <template v-if="currentSource && currentSource.collector_kind === 'external_browser'">
        <div class="cf-divider"></div>
        <p class="dlg-sub">采集平台（bb-browser）</p>
        <div v-if="platformLoading" class="cf-hint">平台目录加载中…</div>
        <div v-else class="platform-grid">
          <label
            v-for="p in platformCatalog"
            :key="p.key"
            class="platform-item"
            :class="{ 'is-disabled': !isPlatformSelectable(p), 'is-checked': platformDraft.includes(p.key) }"
          >
            <input
              type="checkbox"
              :value="p.key"
              :checked="platformDraft.includes(p.key)"
              :disabled="!isPlatformSelectable(p)"
              @change="onPlatformToggle(p.key, $event)"
            />
            <span class="platform-name">{{ p.name }}</span>
            <span v-if="!isPlatformSelectable(p)" class="platform-tag tag-locked">{{ platformBlockReason(p) }}</span>
          </label>
        </div>
        <div v-if="platformError" class="cfg-err">{{ platformError }}</div>
        <div class="cf-hint">
          勾选 bb-browser 要采集的平台；同一平台不得与已启用的 MediaCrawler 数据源同时开启。未勾选任何平台将禁止保存。
        </div>
      </template>

      <template v-if="!(currentSource && currentSource.collector_kind === 'dedicated')">
        <p class="dlg-sub">高级配置（config_json）</p>
        <el-input
          v-model="configDraft"
          type="textarea"
          :rows="10"
          placeholder='如 {"keywords":"河北,石家庄"}'
        />
      </template>
      <div v-else-if="!(currentSource && currentSource.type === 'rss')" class="cfg-note">
        当前采集器为<strong>专用型</strong>，使用系统内置采集逻辑。除上方「过滤策略」外无需填写其他自定义配置；其余配置保持为空（<code>{}</code>）即可。
      </div>
      <template #footer>
        <span class="dlg-foot">
          <span v-if="configError" class="cfg-err">{{ configError }}</span>
          <button class="btn btn-ghost" @click="configVisible = false">关闭</button>
          <button
            class="btn btn-primary" :disabled="savingConfig" @click="saveConfig"
          >保存配置</button>
        </span>
      </template>
    </el-dialog>

    <!-- 新建采集源弹窗 -->
    <el-dialog
      v-model="createVisible"
      title="新建采集源"
      width="660px"
      align-center
      class="apple-dialog"
      modal-class="apple-modal"
    >
      <div class="create-form" v-loading="creating">
        <div class="cf-row">
          <label class="cf-label">名称 <span class="req">*</span></label>
          <el-input v-model="form.name" placeholder="如 石家庄市政府网" />
        </div>
        <div class="cf-row">
          <label class="cf-label">标识 key <span class="req">*</span></label>
          <el-input v-model="form.key" placeholder="如 shijiazhuang_gov（字母/数字/下划线，唯一）" />
        </div>
        <div class="cf-row">
          <label class="cf-label">类型</label>
          <el-select v-model="form.type" class="cf-full">
            <el-option label="通用网站（列表 → 详情）" value="generic_site" />
            <el-option label="新闻网站" value="news_site" />
            <el-option label="政府网站" value="gov_site" />
            <el-option label="搜索引擎" value="search" />
            <el-option label="RSS" value="rss" />
            <el-option label="bb-browser 聚合采集（百度/虎扑/头条/B站/YouTube）" value="external_browser" />
          </el-select>
        </div>
        <div class="cf-row">
          <label class="cf-label">区域（不选 = 全国）</label>
          <el-cascader
            v-model="form.scope_region_codes"
            :options="regionTreeOptions"
            :props="regionCascaderProps"
            :loading="regionCatalogLoading"
            :disabled="regionCatalogLoading"
            :show-all-levels="false"
            collapse-tags
            clearable
            filterable
            placeholder="不选 = 全国"
            class="cf-full"
          />
          <div class="cf-hint">可逐级选择省、市、县、乡镇/街道，选到任一级即可；支持多区域选择。</div>
        </div>
        <div class="cf-row cf-row-2">
          <div class="cf-col">
            <label class="cf-label">优先级</label>
            <el-input-number v-model="form.priority" :min="0" :max="999" size="small" controls-position="right" />
          </div>
          <div class="cf-col">
            <label class="cf-label">启用</label>
            <el-switch v-model="form.enabled" />
          </div>
        </div>
        <div class="cf-row" v-if="form.type === 'rss'">
          <label class="cf-label">RSS 地址 <span class="req">*</span></label>
          <div class="feed-list">
            <div class="feed-item" v-for="(u, i) in feedList" :key="i">
              <el-input v-model="feedList[i]" placeholder="https://example.com/feed.xml" />
              <button class="btn btn-ghost btn-mini" type="button" :disabled="feedList.length <= 1" @click="removeFeed(i)">删除</button>
            </div>
          </div>
          <button class="btn btn-ghost btn-mini" type="button" @click="addFeed">+ 添加地址</button>
          <div v-if="rssFeedError" class="cfg-err">{{ rssFeedError }}</div>
          <div class="cf-hint">填写一个或多个 RSS/Atom 地址（仅支持 http/https）。保存时会用真实抓取校验。</div>
        </div>
        <div class="cf-row" v-if="form.type === 'external_browser'">
          <label class="cf-label">调度模式</label>
          <el-switch v-model="form.schedule_enabled" active-text="自动" inactive-text="手动" />
          <div class="cf-hint">bb-browser 聚合采集默认「手动」。Phase 2 灰度期间必须保持手动（schedule_enabled=false），不得自动调度。</div>
        </div>
        <!-- 新建 bb-browser：平台选择 -->
        <div class="cf-row" v-if="form.type === 'external_browser'">
          <label class="cf-label">采集平台 <span class="req">*</span></label>
          <div v-if="platformLoading" class="cf-hint">平台目录加载中…</div>
          <div v-else class="platform-grid">
            <label
              v-for="p in platformCatalog"
              :key="p.key"
              class="platform-item"
              :class="{ 'is-disabled': !isPlatformSelectable(p), 'is-checked': platformDraft.includes(p.key) }"
            >
              <input
                type="checkbox"
                :value="p.key"
                :checked="platformDraft.includes(p.key)"
                :disabled="!isPlatformSelectable(p)"
                @change="onPlatformToggle(p.key, $event)"
              />
              <span class="platform-name">{{ p.name }}</span>
              <span v-if="!isPlatformSelectable(p)" class="platform-tag tag-locked">{{ platformBlockReason(p) }}</span>
            </label>
          </div>
          <div v-if="createConfigError && form.type === 'external_browser' && platformDraft.length === 0" class="cfg-err">{{ createConfigError }}</div>
          <div class="cf-hint">
            勾选 bb-browser 要采集的平台（也可在上方 config_json 中直接写 platforms 数组，二者保持一致即可）。同一平台不得与已启用的 MediaCrawler 数据源同时开启。
          </div>
        </div>
        <div class="cf-row" v-if="form.type !== 'rss'">
          <label class="cf-label">配置 config_json <span class="req">*</span></label>
          <el-input v-model="form.config_json" type="textarea" :rows="13" placeholder="JSON 配置" />
          <div v-if="createConfigError" class="cfg-err">{{ createConfigError }}</div>
          <div v-if="form.type === 'external_browser'" class="cf-hint">
            bb-browser 聚合采集：填写 config_json（JSON），至少含 <code>platforms</code>、<code>control_root</code>、<code>exchange_root</code>、<code>bb_browser_cli</code>；
            平台白名单仅允许 baidu/hupu/toutiao/bilibili/youtube，禁止 weibo/xiaohongshu/zhihu。保存时仅做结构校验，不会触发实时抓取。
          </div>
          <div v-else class="cf-hint">新建的数据源将使用<strong>通用型采集器（配置驱动）</strong>，需填写 config_json（至少含 list_urls）；保存时会用真实抓取校验：能取到正文才创建成功。</div>
        </div>
        <div class="cf-row">
          <label class="cf-label">过滤策略（可选）</label>
          <div class="filter-row">
            <el-select v-model="form.filter_mode" placeholder="过滤模式" class="cf-half" @change="onCreateFilterModeChange">
              <el-option v-for="o in filterModeOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-select v-model="form.keyword_scope" placeholder="关键词范围" class="cf-half">
              <el-option
                v-for="o in keywordScopeOptions"
                :key="o.value"
                :label="o.label"
                :value="o.value"
                :disabled="scopeDisabledFor(form.filter_mode, o.value)"
              />
            </el-select>
          </div>
          <div v-if="illegalComboError(form.filter_mode, form.keyword_scope)" class="cfg-err">
            {{ illegalComboError(form.filter_mode, form.keyword_scope) }}
          </div>
          <div class="cf-hint">留空（默认）即按采集器内置默认过滤策略；专用型源可在下拉中指定过滤模式与关键词范围。</div>
        <div class="cf-row">
          <label class="cf-label">单次抓取条数 max_items（可选）</label>
          <el-input-number v-model="form.max_items" :min="1" :max="500" size="small" controls-position="right" />
        </div>
        </div>
      </div>
      <template #footer>
        <span class="dlg-foot">
          <span v-if="testMsg" class="test-msg" :class="testOk ? 'ok' : 'bad'">{{ testMsg }}</span>
          <button class="btn btn-ghost" :disabled="testing" @click="testCreate">测试连接</button>
          <button class="btn btn-ghost" @click="createVisible = false">取消</button>
          <button class="btn btn-primary" :disabled="creating || testing" @click="submitCreate">保存</button>
        </span>
      </template>
    </el-dialog>

    <!-- 单源调度配置弹窗 -->
    <el-dialog
      v-model="scheduleVisible"
      :title="'采集调度 · ' + (currentSource?.name || '')"
      width="520px"
      align-center
      class="apple-dialog"
      modal-class="apple-modal"
    >
      <div class="schedule-form" v-loading="savingSchedule">
        <div class="cf-row">
          <label class="cf-label">自动采集</label>
          <el-switch v-model="scheduleDraft.schedule_enabled" />
        </div>
        <div class="cf-row">
          <label class="cf-label">采集周期（分钟）</label>
          <el-input-number v-model="scheduleDraft.schedule_interval_minutes" :min="5" :max="1440" size="small" controls-position="right" />
        </div>
        <div class="cf-hint">最小周期 5 分钟（与后端校验一致）。保存后立即按新周期参与调度。</div>
      </div>
      <template #footer>
        <span class="dlg-foot">
          <button class="btn btn-ghost" @click="scheduleVisible = false">取消</button>
          <button class="btn btn-primary" :disabled="savingSchedule" @click="saveSchedule">保存</button>
        </span>
      </template>
    </el-dialog>

    <!-- 批量调度设置弹窗 -->
    <el-dialog
      v-model="batchVisible"
      title="统一采集频率设置"
      width="520px"
      align-center
      class="apple-dialog"
      modal-class="apple-modal"
    >
      <div class="schedule-form" v-loading="batchSaving">
        <div class="cf-row">
          <label class="cf-label">范围</label>
          <el-select v-model="batchForm.scope" class="cf-full">
            <el-option label="全部数据源" value="all" />
            <el-option label="仅已启用" value="enabled_only" />
          </el-select>
        </div>
        <div class="cf-row">
          <label class="cf-label">自动采集</label>
          <el-switch v-model="batchForm.schedule_enabled" />
        </div>
        <div class="cf-row">
          <label class="cf-label">采集周期（分钟）</label>
          <el-input-number v-model="batchForm.interval_minutes" :min="5" :max="1440" size="small" controls-position="right" />
        </div>
      </div>
      <template #footer>
        <span class="dlg-foot">
          <span v-if="batchMessage" class="test-msg" :class="batchOk ? 'ok' : 'bad'">{{ batchMessage }}</span>
          <button class="btn btn-ghost" @click="batchVisible = false">取消</button>
          <button class="btn btn-primary" :disabled="batchSaving" @click="saveBatchSchedule">保存</button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { usePermission } from '@/composables/usePermission'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type {
  CollectorRunItem,
  DataSourceCreateRequest,
  DataSourceItem,
  DataSourceListResponse,
  DataSourceQualityItem,
  DataSourceQualityResponse,
  DataSourceScheduleBatchRequest,
  DataSourceScheduleBatchResponse,
  DataSourceScheduleSummary,
  DataSourceTestResult,
  RegionOption,
} from '@/types'

interface RegionCatalogItem {
  code: string
  name: string
  level: string
  parent_code: string | null
}

interface RegionTreeOption {
  value: string
  label: string
  children?: RegionTreeOption[]
}

interface Row extends DataSourceItem {
  _saving?: boolean
  _savingSchedule?: boolean
  collector_kind?: 'generic' | 'dedicated' | 'external_browser'
}

// 平台可用性（GET /admin/data-sources/platforms/availability）
interface PlatformAvailability {
  key: string
  name: string
  collectors: string[]
  source_type: string
  python_normalized: boolean
  collect_type: string
  selectable_for_bb: boolean
  blocked_reason: string | null
  current_owner: { id: number; name: string } | null
}

const DEFAULT_CONFIG = JSON.stringify(
  {
    source_name: '',
    list_urls: ['https://example.gov.cn/list/'],
    link_rule: { href_contains: '.html', max_links: 20 },
    content_selectors: ['div.content', 'div.article'],
    keywords: '河北,石家庄',
    max_articles: 5,
    timeout: 10,
  },
  null,
  2,
)

// —— 过滤策略（filter_mode / keyword_scope）选项与联动规则（Phase DataSource-Filter-Config-3）——
const FILTER_MODE_DEFAULT_LABEL = '默认（不指定，按采集器默认）'
const KEYWORD_SCOPE_DEFAULT_LABEL = '默认（不指定，按采集器默认）'
const filterModeOptions = [
  { value: '', label: FILTER_MODE_DEFAULT_LABEL },
  { value: 'region_only', label: '仅地域' },
  { value: 'region_or_topic', label: '地域或主题' },
  { value: 'topic_only', label: '仅主题' },
]
const keywordScopeOptions = [
  { value: '', label: KEYWORD_SCOPE_DEFAULT_LABEL },
  { value: 'region', label: '地域词' },
  { value: 'region_topic', label: '地域+主题词' },
  { value: 'topic', label: '主题词' },
]

// 前端禁止的非法组合（与后端 validate_data_source_config 保持一致）
function scopeDisabledFor(mode: string, scope: string): boolean {
  if (mode === 'region_only' && scope === 'topic') return true
  if (mode === 'topic_only' && scope === 'region') return true
  return false
}

function illegalComboError(mode: string, scope: string): string | null {
  if (mode === 'region_only' && scope === 'topic') {
    return 'region_only 不允许与 keyword_scope=主题词(topic) 组合'
  }
  if (mode === 'topic_only' && scope === 'region') {
    return 'topic_only 不允许与 keyword_scope=地域词(region) 组合'
  }
  return null
}

// —— Phase DataSource-Filter-Config-4：生效策略展示辅助函数 ——
function filterStrategyText(efs: any): string {
  if (!efs || !efs.effective_filter_mode) return '不适用'
  const fm: Record<string, string> = { region_only: '仅地域', region_or_topic: '地域或主题', topic_only: '仅主题' }
  const m = fm[efs.effective_filter_mode] || efs.effective_filter_mode
  const src = efs.source === 'config' ? '管理员配置' : (efs.source === 'not_applicable' ? '不适用' : '默认')
  return m + '（' + src + '）'
}
function filterStrategyPill(efs: any): string {
  if (!efs || efs.source === 'not_applicable') return 'pill-gray'
  return efs.source === 'config' ? 'pill-green' : 'pill-blue'
}
function filterStrategySourceText(efs: any): string {
  if (!efs) return ''
  if (efs.source === 'not_applicable') return '采集器内置策略（不适用过滤配置）'
  const ks: Record<string, string> = { region: '地域词', region_topic: '地域+主题词', topic: '主题词' }
  const k = efs.effective_keyword_scope ? (ks[efs.effective_keyword_scope] || efs.effective_keyword_scope) : ''
  return '关键词范围：' + (k || '（未指定）')
}
// 配置弹窗：基于当前下拉草稿的实时预览
function draftStrategyText(): string {
  const fm = filterModeDraft.value
  const map: Record<string, string> = { region_only: '仅地域', region_or_topic: '地域或主题', topic_only: '仅主题' }
  return map[fm] || '默认（未指定）'
}
function draftStrategySource(): string {
  const fm = filterModeDraft.value
  const ks = keywordScopeDraft.value
  return (!fm && !ks) ? '沿用采集器默认' : '管理员配置（保存后生效）'
}
function draftKeywordScopeText(): string {
  const ks = keywordScopeDraft.value
  const map: Record<string, string> = { region: '地域词', region_topic: '地域+主题词', topic: '主题词' }
  return ks ? (map[ks] || ks) : '（未指定，沿用默认）'
}
function draftStrategyPill(): string {
  const fm = filterModeDraft.value
  const ks = keywordScopeDraft.value
  return (!fm && !ks) ? 'pill-blue' : 'pill-green'
}

const loading = ref(false)
const { isSuperuser } = usePermission()
const sources = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const regionOptions = ref<RegionOption[]>([])
const regionTreeOptions = ref<RegionTreeOption[]>([])
const regionCatalogLoading = ref(false)
const regionCascaderProps = {
  multiple: true,
  checkStrictly: true,
  emitPath: false,
  value: 'value',
  label: 'label',
  children: 'children',
}
const filterRegion = ref<string>('')
const filterEnabled = ref<boolean | ''>('')
const filterQ = ref('')
const qualityBySourceId = ref<Record<number, DataSourceQualityItem>>({})

// 批量启用/停用：行选择状态（复用关键词管理页交互）
const selectedIds = ref<number[]>([])
const pageAllSelected = computed(
  () => sources.value.length > 0 && sources.value.every((s) => selectedIds.value.includes(s.id)),
)
function toggleRow(s: Row) {
  const i = selectedIds.value.indexOf(s.id)
  if (i >= 0) selectedIds.value.splice(i, 1)
  else selectedIds.value.push(s.id)
}
function togglePageAll(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  if (checked) {
    for (const s of sources.value) if (!selectedIds.value.includes(s.id)) selectedIds.value.push(s.id)
  } else {
    const pageIds = new Set(sources.value.map((s) => s.id))
    selectedIds.value = selectedIds.value.filter((id) => !pageIds.has(id))
  }
}
async function batchToggle(enabled: boolean) {
  if (selectedIds.value.length === 0) return
  try {
    const { data } = await api.post<{ affected_count: number; skipped: number }>(
      '/admin/data-sources/batch-toggle',
      { ids: selectedIds.value, enabled },
    )
    ElMessage.success(enabled ? `已批量启用 ${data.affected_count} 个` : `已批量停用 ${data.affected_count} 个`)
    selectedIds.value = []
    reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '批量操作失败')
  }
}

const historyVisible = ref(false)
const configVisible = ref(false)
const currentSource = ref<Row | null>(null)
const history = ref<CollectorRunItem[]>([])
const historyLoading = ref(false)
const configDraft = ref('')
const configError = ref('')
const savingConfig = ref(false)
const scopeRegionDraft = ref<string[]>([])
// 过滤策略下拉草稿（配置弹窗）
const filterModeDraft = ref('')
const keywordScopeDraft = ref('')
const maxItemsDraft = ref(null)

// —— bb-browser 平台选择（Phase：灵活选择平台）——
const platformCatalog = ref<PlatformAvailability[]>([])
const platformDraft = ref<string[]>([])
const platformLoading = ref(false)
const platformError = ref('')

async function loadPlatformAvailability() {
  platformLoading.value = true
  try {
    const { data } = await api.get<{ platforms: PlatformAvailability[] }>(
      '/admin/data-sources/platforms/availability',
    )
    platformCatalog.value = data?.platforms || []
  } catch {
    platformCatalog.value = []
  } finally {
    platformLoading.value = false
  }
}

// 仅当平台可选且未被其它已启用源占用时，才允许勾选
function isPlatformSelectable(p: PlatformAvailability): boolean {
  if (!p.selectable_for_bb) return false
  if (p.current_owner && currentSource.value && p.current_owner.id !== currentSource.value.id) {
    return false
  }
  return true
}

function platformBlockReason(p: PlatformAvailability): string {
  if (p.current_owner && currentSource.value && p.current_owner.id !== currentSource.value.id) {
    return `已被「${p.current_owner.name}」占用`
  }
  return p.blocked_reason || '当前不可选择'
}

function onPlatformToggle(key: string, ev: Event) {
  const checked = (ev.target as HTMLInputElement).checked
  const i = platformDraft.value.indexOf(key)
  if (checked && i < 0) platformDraft.value.push(key)
  if (!checked && i >= 0) platformDraft.value.splice(i, 1)
}

// —— 调度配置（单源 + 批量）——
const scheduleVisible = ref(false)
const savingSchedule = ref(false)
const scheduleDraft = reactive({ schedule_enabled: true, schedule_interval_minutes: 30 })
const batchVisible = ref(false)
const batchSaving = ref(false)
const batchMessage = ref('')
const batchOk = ref(false)
const batchForm = reactive({
  scope: 'enabled_only' as 'all' | 'enabled_only',
  schedule_enabled: true,
  interval_minutes: 30,
})

function supportsCommentStats(source: Row | null): boolean {
  if (!source) return false
  const identity = [source.key, source.type, source.name]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return source.key === 'weibo_octopus' || identity.includes('weibo') || identity.includes('微博')
}

const commentStatsApplicable = computed(() => supportsCommentStats(currentSource.value))
const commentStatsLabel = computed(() => commentStatsApplicable.value ? '评论跳过' : '评论处理')

function commentStatsValue(value?: number | null): number | string {
  return commentStatsApplicable.value ? (value ?? 0) : '不适用'
}

const historySummary = computed(() => history.value.reduce(
  (acc, r) => {
    acc.fetched += r.fetched_raw || 0
    acc.commentsSkipped += r.comments_skipped || 0
    acc.admissionFiltered += r.admission_filtered || 0
    acc.created += r.created || 0
    return acc
  },
  { fetched: 0, commentsSkipped: 0, admissionFiltered: 0, created: 0 },
))

// —— 新建采集源 ——
const createVisible = ref(false)
const creating = ref(false)
const testing = ref(false)
const testMsg = ref('')
const testOk = ref(false)
const createConfigError = ref('')
// 通用 RSS 数据源：feeds 地址列表（创建 / 编辑共用结构）
const feedList = ref<string[]>([''])
const feedListEdit = ref<string[]>([''])
const rssFeedError = ref('')
const form = reactive({
  name: '',
  key: '',
  type: 'generic_site',
  scope_region_codes: [] as string[],
  priority: 50,
  enabled: true,
  schedule_enabled: false,
  config_json: DEFAULT_CONFIG,
  filter_mode: '' as string,
  keyword_scope: '' as string,
  max_items: null,
})

function runPill(s: string): string {
  const m: Record<string, string> = {
    running: 'pill-green', success: 'pill-green', partial: 'pill-orange',
    failed: 'pill-red', error: 'pill-red', unknown: 'pill-gray',
  }
  return m[s] || 'pill-gray'
}
function runText(s: string): string {
  const m: Record<string, string> = {
    running: '运行中', success: '成功', partial: '部分成功',
    failed: '失败', error: '异常', unknown: '未知',
  }
  return m[s] || s
}
function formatTime(t: string | null): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

function qualityFor(source: Row): DataSourceQualityItem | undefined {
  return qualityBySourceId.value[source.id]
}

function qualityPill(risk: DataSourceQualityItem['empty_fetch_risk']): string {
  const m: Record<DataSourceQualityItem['empty_fetch_risk'], string> = {
    normal: 'pill-green', warning: 'pill-orange', high: 'pill-red', unknown: 'pill-gray',
  }
  return m[risk]
}

function qualityText(risk: DataSourceQualityItem['empty_fetch_risk']): string {
  const m: Record<DataSourceQualityItem['empty_fetch_risk'], string> = {
    normal: '正常', warning: '空抓取', high: '高风险', unknown: '未运行',
  }
  return m[risk]
}

function qualityHint(item: DataSourceQualityItem): string {
  if (item.consecutive_failed_count > 0) return `连续失败 ${item.consecutive_failed_count}`
  if (item.consecutive_empty_fetch_count > 0) return `连续空抓取 ${item.consecutive_empty_fetch_count}`
  return ''
}

function healthPill(status: string): string {
  return ({ healthy: 'pill-green', degraded: 'pill-orange', unhealthy: 'pill-red', paused: 'pill-gray', unknown: 'pill-gray' } as Record<string, string>)[status] || 'pill-gray'
}

function healthText(status: string): string {
  return ({ healthy: '正常', degraded: '降级', unhealthy: '异常', paused: '已停用', unknown: '未知' } as Record<string, string>)[status] || status
}

function keywordModeText(mode: Row['keyword_mode']): string {
  const map: Record<Row['keyword_mode'], string> = {
    global_region: '全局地域词',
    source_keywords: '数据源独立词',
    no_filter: '全量放行',
    full_collection: '全量采集',
    unknown: '待确认',
  }
  return map[mode] || '待确认'
}

function keywordModePill(mode: Row['keyword_mode']): string {
  const map: Record<Row['keyword_mode'], string> = {
    global_region: 'pill-blue',
    source_keywords: 'pill-green',
    no_filter: 'pill-orange',
    full_collection: 'pill-gray',
    unknown: 'pill-orange',
  }
  return map[mode] || 'pill-gray'
}

function effectiveKeywordsText(source: Row): string {
  const keywords = source.effective_keywords || []
  if (keywords.length) return keywords.join('、')
  return source.keyword_mode === 'no_filter' || source.keyword_mode === 'full_collection'
    ? '不适用'
    : '当前无有效关键词'
}

async function reload(resetPage = false) {
  if (resetPage) page.value = 1
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: size.value, is_foreign: false }
    if (filterRegion.value) params.region_code = filterRegion.value
    if (filterEnabled.value !== '') params.enabled = filterEnabled.value
    if (filterQ.value) params.q = filterQ.value
    const [sourceResponse, qualityResponse] = await Promise.all([
      api.get<DataSourceListResponse>('/admin/data-sources', { params }),
      api.get<DataSourceQualityResponse>('/admin/data-sources/quality', { params: { days: 7 } }),
    ])
    const data = sourceResponse.data
    sources.value = data.items || []
    total.value = data.total || 0
    if (data.region_options) regionOptions.value = data.region_options
    qualityBySourceId.value = Object.fromEntries(
      (qualityResponse.data.items || []).map(item => [item.data_source_id, item]),
    )
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载数据源失败')
  } finally {
    loading.value = false
  }
}

function parseScopeCodes(raw: string | null | undefined): string[] {
  return (raw || '')
    .split(',')
    .map(code => code.trim())
    .filter(Boolean)
}

async function loadRegionCatalog() {
  if (regionTreeOptions.value.length || regionCatalogLoading.value) return
  regionCatalogLoading.value = true
  try {
    const { data } = await api.get<RegionCatalogItem[]>('/admin/data-sources/regions')
    const nodes = new Map<string, RegionTreeOption>()
    const roots: RegionTreeOption[] = []
    for (const item of data || []) {
      nodes.set(item.code, { value: item.code, label: item.name })
    }
    for (const item of data || []) {
      const node = nodes.get(item.code)
      if (!node) continue
      if (item.parent_code && nodes.has(item.parent_code)) {
        const parent = nodes.get(item.parent_code)!
        if (!parent.children) parent.children = []
        parent.children.push(node)
      } else {
        roots.push(node)
      }
    }
    regionTreeOptions.value = roots
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载区域目录失败')
  } finally {
    regionCatalogLoading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  reload()
}

async function onToggle(row: Row, val: boolean) {
  const prev = row.enabled
  row.enabled = val
  row._saving = true
  try {
    await api.patch('/admin/data-sources/' + row.id, { enabled: val })
    ElMessage.success(val ? '已启用' : '已停用')
  } catch (e: any) {
    row.enabled = prev
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    row._saving = false
  }
}

async function onPriority(row: Row, val: number) {
  if (val == null || isNaN(val)) return
  const prev = row.priority
  row.priority = val // 乐观更新，即时响应界面
  try {
    await api.patch('/admin/data-sources/' + row.id, { priority: val })
    ElMessage.success('优先级已更新')
  } catch (e: any) {
    row.priority = prev // 失败回滚
    ElMessage.error(e?.response?.data?.detail || '更新失败')
  }
}

async function openHistory(row: Row) {
  currentSource.value = row
  historyVisible.value = true
  configError.value = ''
  historyLoading.value = true
  history.value = []
  try {
    const { data } = await api.get<{ items: CollectorRunItem[] }>(
      '/admin/data-sources/' + row.id + '/runs',
      { params: { page: 1, size: 20 } },
    )
    history.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

async function openConfig(row: Row) {
  currentSource.value = row
  configError.value = ''
  platformError.value = ''
  scopeRegionDraft.value = parseScopeCodes(row.scope_region_codes)
  loadRegionCatalog()
  // bb-browser 聚合采集：加载平台目录并回显已选平台
  if (row.collector_kind === 'external_browser') {
    await loadPlatformAvailability()
    let pcfg: any = {}
    try {
      const parsed = JSON.parse(row.config_json || '{}')
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) pcfg = parsed
    } catch {
      pcfg = {}
    }
    platformDraft.value = Array.isArray(pcfg.platforms)
      ? pcfg.platforms.filter((x: any) => typeof x === 'string')
      : []
  } else {
    platformDraft.value = []
  }
  // 从现有 config_json 解析 filter_mode / keyword_scope 填入下拉（缺省回退「默认」）
  let cfg: any = {}
  try {
    const parsed = JSON.parse(row.config_json || '{}')
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) cfg = parsed
  } catch {
    cfg = {}
  }
  filterModeDraft.value = typeof cfg.filter_mode === 'string' ? cfg.filter_mode : ''
  keywordScopeDraft.value = typeof cfg.keyword_scope === 'string' ? cfg.keyword_scope : ''
  maxItemsDraft.value = typeof cfg.max_items === 'number' ? cfg.max_items : null
  // RSS 源：回显 feeds 地址列表（编辑共用 feedListEdit）
  if (row.type === 'rss') {
    const feeds = Array.isArray(cfg.feeds)
      ? cfg.feeds.map((f: any) => (typeof f === 'string' ? f : (f && f.url ? f.url : ''))).filter(Boolean)
      : []
    feedListEdit.value = feeds.length ? feeds : ['']
  }
  // 通用型保留原始 config_json 供高级编辑；专用型仅由下拉驱动策略
  configDraft.value = row.config_json || '{}'
  configVisible.value = true
}

function onConfigFilterModeChange() {
  // 切换过滤模式后若当前关键词范围变为非法组合，自动清空关键词范围
  if (illegalComboError(filterModeDraft.value, keywordScopeDraft.value)) {
    keywordScopeDraft.value = ''
  }
}

function onCreateFilterModeChange() {
  if (illegalComboError(form.filter_mode, form.keyword_scope)) {
    form.keyword_scope = ''
  }
}

async function saveConfig() {
  if (!currentSource.value) return
  configError.value = ''
  const mode = filterModeDraft.value
  const scope = keywordScopeDraft.value
  const comboErr = illegalComboError(mode, scope)
  if (comboErr) {
    configError.value = comboErr
    return
  }
  // RSS 源：由 feedListEdit 构建 config_json（filters + max_items），不改变源类型
  if (currentSource.value.type === 'rss') {
    const e = validateRssFeedsEdit()
    if (e) {
      configError.value = e
      return
    }
    const payload = rssConfigFromFeeds(feedListEdit.value, mode, scope, maxItemsDraft.value, currentSource.value.name)
    savingConfig.value = true
    try {
      const { data } = await api.patch<DataSourceItem>('/admin/data-sources/' + currentSource.value.id, {
        config_json: payload,
        scope_region_codes: scopeRegionDraft.value.join(','),
      })
      Object.assign(currentSource.value, data)
      ElMessage.success('配置已保存')
      configVisible.value = false
    } catch (err: any) {
      ElMessage.error(err?.response?.data?.detail || '保存失败')
    } finally {
      savingConfig.value = false
    }
    return
  }
  const isDedicated = currentSource.value.collector_kind === 'dedicated'
  // 合并下拉策略键到 config_json：专用型保留原有其他键（如 collection_mode），通用型保留高级配置
  const raw = isDedicated ? (currentSource.value.config_json || '{}') : configDraft.value
  let cfg: any = {}
  try {
    const parsed = JSON.parse(raw || '{}')
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) cfg = parsed
  } catch {
    if (!isDedicated) {
      configError.value = 'config_json 不是合法 JSON'
      return
    }
  }
  if (mode) cfg.filter_mode = mode
  else delete cfg.filter_mode
  if (scope) cfg.keyword_scope = scope
  else delete cfg.keyword_scope
  if (maxItemsDraft.value != null && maxItemsDraft.value >= 1) cfg.max_items = maxItemsDraft.value
  else delete cfg.max_items
  // bb-browser 聚合采集：把勾选的平台写入 config_json.platforms（去重、保持顺序）
  if (currentSource.value && currentSource.value.collector_kind === 'external_browser') {
    if (platformDraft.value.length === 0) {
      configError.value = '请至少选择一个采集平台'
      return
    }
    cfg.platforms = [...new Set(platformDraft.value)]
  }
  const payload = JSON.stringify(cfg)
  savingConfig.value = true
  try {
    const { data } = await api.patch<DataSourceItem>('/admin/data-sources/' + currentSource.value.id, {
      config_json: payload,
      scope_region_codes: scopeRegionDraft.value.join(','),
    })
    Object.assign(currentSource.value, data)
    ElMessage.success('配置已保存')
    configVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    savingConfig.value = false
  }
}

async function onScheduleEnabled(row: Row, val: boolean) {
  const prev = row.schedule_enabled
  row.schedule_enabled = val
  row._savingSchedule = true
  try {
    await api.patch('/admin/data-sources/' + row.id, { schedule_enabled: val })
    ElMessage.success(val ? '已开启自动采集' : '已关闭自动采集')
  } catch (e: any) {
    row.schedule_enabled = prev
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    row._savingSchedule = false
  }
}

function openSchedule(row: Row) {
  currentSource.value = row
  scheduleDraft.schedule_enabled = !!row.schedule_enabled
  scheduleDraft.schedule_interval_minutes = row.schedule_interval_minutes ?? 30
  savingSchedule.value = false
  scheduleVisible.value = true
}

async function saveSchedule() {
  if (!currentSource.value) return
  savingSchedule.value = true
  try {
    await api.patch('/admin/data-sources/' + currentSource.value.id, {
      schedule_enabled: scheduleDraft.schedule_enabled,
      schedule_interval_minutes: scheduleDraft.schedule_interval_minutes,
    })
    const row = sources.value.find(r => r.id === currentSource.value!.id)
    if (row) {
      row.schedule_enabled = scheduleDraft.schedule_enabled
      row.schedule_interval_minutes = scheduleDraft.schedule_interval_minutes
    }
    ElMessage.success('调度配置已保存')
    scheduleVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    savingSchedule.value = false
  }
}

function openBatchSchedule() {
  batchMessage.value = ''
  batchOk.value = false
  batchVisible.value = true
}

async function saveBatchSchedule() {
  batchSaving.value = true
  batchMessage.value = ''
  try {
    const { data } = await api.post<DataSourceScheduleBatchResponse>(
      '/admin/data-sources/schedule/batch',
      {
        scope: batchForm.scope,
        schedule_enabled: batchForm.schedule_enabled,
        interval_minutes: batchForm.interval_minutes,
      },
    )
    batchOk.value = true
    batchMessage.value = `已更新 ${data.affected_count} 个数据源`
    ElMessage.success(`已更新 ${data.affected_count} 个数据源`)
    await reload()
  } catch (e: any) {
    batchOk.value = false
    batchMessage.value = e?.response?.data?.detail || '批量设置失败'
    ElMessage.error(e?.response?.data?.detail || '批量设置失败')
  } finally {
    batchSaving.value = false
  }
}

onMounted(reload)

function openCreate() {
  createConfigError.value = ''
  platformError.value = ''
  testMsg.value = ''
  testOk.value = false
  rssFeedError.value = ''
  feedList.value = ['']
  platformDraft.value = []
  if (form) form.max_items = null
  createVisible.value = true
  loadRegionCatalog()
}

// 新建弹窗：类型切到 external_browser 时加载平台目录
watch(
  () => form.type,
  (t) => {
    if (t === 'external_browser') {
      loadPlatformAvailability()
    } else {
      platformDraft.value = []
    }
  },
)

// —— 通用 RSS feeds 辅助（创建 / 编辑共用）——
function addFeed() {
  feedList.value.push('')
}
function removeFeed(i: number) {
  if (feedList.value.length > 1) feedList.value.splice(i, 1)
}
function addFeedEdit() {
  feedListEdit.value.push('')
}
function removeFeedEdit(i: number) {
  if (feedListEdit.value.length > 1) feedListEdit.value.splice(i, 1)
}
function _collectRssUrls(list: string[]): string[] {
  return (list || []).map(u => (u || '').trim()).filter(Boolean)
}
function validateRssFeeds(): string | null {
  const urls = _collectRssUrls(feedList.value)
  if (!urls.length) return '请至少填写一个 RSS 地址'
  for (const u of urls) {
    const lower = u.toLowerCase()
    if (!lower.startsWith('http://') && !lower.startsWith('https://')) {
      return 'RSS 地址仅支持 http/https：' + u
    }
    try {
      const host = new URL(u).hostname.toLowerCase()
      if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0' || host === '::1') {
        return 'RSS 地址不能是本地地址：' + u
      }
    } catch {
      return 'RSS 地址格式不合法：' + u
    }
  }
  return null
}
function validateRssFeedsEdit(): string | null {
  const urls = _collectRssUrls(feedListEdit.value)
  if (!urls.length) return '请至少填写一个 RSS 地址'
  for (const u of urls) {
    const lower = u.toLowerCase()
    if (!lower.startsWith('http://') && !lower.startsWith('https://')) {
      return 'RSS 地址仅支持 http/https：' + u
    }
    try {
      const host = new URL(u).hostname.toLowerCase()
      if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0' || host === '::1') {
        return 'RSS 地址不能是本地地址：' + u
      }
    } catch {
      return 'RSS 地址格式不合法：' + u
    }
  }
  return null
}
function rssConfigFromFeeds(list: string[], mode: string, scope: string, maxItems: number | null, name?: string): string {
  const feeds = _collectRssUrls(list).map(u => ({ url: u }))
  const cfg: any = { feeds }
  // source_name 与数据源显示名一致，使 collector_runs.collector_name 与
  // opinions.source 使用正确的来源名（缺失会导致所有 RSS 源共用 "rss" 一个名字）。
  if (name && name.trim()) cfg.source_name = name.trim()
  if (mode) cfg.filter_mode = mode
  if (scope) cfg.keyword_scope = scope
  if (maxItems != null && maxItems >= 1) cfg.max_items = maxItems
  return JSON.stringify(cfg)
}


function buildPayload(): DataSourceCreateRequest {
  // RSS 类型：由 feeds 列表构建 config_json，不依赖通用型文本域
  if (form.type === 'rss') {
    return {
      name: form.name.trim(),
      key: form.key.trim(),
      type: form.type,
      scope_region_codes: (form.scope_region_codes || []).join(','),
      priority: form.priority,
      enabled: form.enabled,
      config_json: rssConfigFromFeeds(feedList.value, form.filter_mode, form.keyword_scope, form.max_items, form.name.trim()),
    }
  }
  // source_name 缺失时回退为名称，保证「查看历史」按 name 关联能命中
  const cfgObj = JSON.parse(form.config_json || '{}')
  if (!cfgObj.source_name) cfgObj.source_name = form.name.trim()
  // 合并过滤策略下拉（仅当用户显式选择时写入；留空则删除，避免改变采集器默认）
  if (form.filter_mode) cfgObj.filter_mode = form.filter_mode
  else delete cfgObj.filter_mode
  if (form.keyword_scope) cfgObj.keyword_scope = form.keyword_scope
  else delete cfgObj.keyword_scope
  if (form.max_items != null && form.max_items >= 1) cfgObj.max_items = form.max_items
  else delete cfgObj.max_items
  // bb-browser 聚合采集：把勾选的平台写入 config_json.platforms
  if (form.type === 'external_browser') {
    cfgObj.platforms = [...new Set(platformDraft.value)]
  }
  const payload: DataSourceCreateRequest = {
    name: form.name.trim(),
    key: form.key.trim(),
    type: form.type,
    scope_region_codes: (form.scope_region_codes || []).join(','),
    priority: form.priority,
    enabled: form.enabled,
    config_json: JSON.stringify(cfgObj),
  }
  if (form.type === 'external_browser') {
    payload.schedule_enabled = form.schedule_enabled
  }
  return payload
}

async function testCreate() {
  let ok = false
  const comboErr = illegalComboError(form.filter_mode, form.keyword_scope)
  if (comboErr) {
    createConfigError.value = comboErr
    return
  }
  if (form.type === 'rss') {
    const e = validateRssFeeds()
    if (e) {
      rssFeedError.value = e
      return
    }
    rssFeedError.value = ''
  } else {
    try {
      JSON.parse(form.config_json || '{}')
    } catch {
      createConfigError.value = 'config_json 不是合法 JSON'
      return
    }
    createConfigError.value = ''
  }
  // bb-browser 聚合采集：必须至少选择一个平台
  if (form.type === 'external_browser' && platformDraft.value.length === 0) {
    createConfigError.value = '请至少选择一个采集平台'
    return
  }
  testing.value = true
  testMsg.value = ''
  try {
    const { data } = await api.post<DataSourceTestResult>('/admin/data-sources/test', buildPayload())
    ok = !!data.ok
    testOk.value = ok
    if (ok) {
      const t = data.test
      if (form.type === 'rss') {
        testMsg.value = `测试通过：RSS 实时抓取命中 ${t?.count ?? 0} 条（${t?.feeds ?? 0} 个 feed 可用）`
      } else {
        testMsg.value =
          `测试通过：列表页获取到 ${t?.fetched_links ?? 0} 个链接` +
          (t?.sample_content_len ? `，示例详情页正文 ${t.sample_content_len} 字` : '')
      }
    } else {
      testMsg.value = '测试未通过：' + (data.error || '未知原因')
    }
  } catch (e: any) {
    testOk.value = false
    testMsg.value = '测试失败：' + (e?.response?.data?.detail || e?.message || '请求异常')
  } finally {
    testing.value = false
  }
}

async function submitCreate() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  if (!form.key.trim()) {
    ElMessage.warning('请填写标识 key')
    return
  }
  const comboErr = illegalComboError(form.filter_mode, form.keyword_scope)
  if (comboErr) {
    createConfigError.value = comboErr
    return
  }
  if (form.type === 'rss') {
    const e = validateRssFeeds()
    if (e) {
      rssFeedError.value = e
      return
    }
    rssFeedError.value = ''
  } else {
    try {
      JSON.parse(form.config_json || '{}')
    } catch {
      createConfigError.value = 'config_json 不是合法 JSON'
      return
    }
    createConfigError.value = ''
  }
  // bb-browser 聚合采集：必须至少选择一个平台
  if (form.type === 'external_browser' && platformDraft.value.length === 0) {
    createConfigError.value = '请至少选择一个采集平台'
    return
  }
  creating.value = true
  try {
    const { data } = await api.post<DataSourceItem & { test?: any }>('/admin/data-sources', buildPayload())
    const t = data.test || {}
    if (form.type === 'rss') {
      ElMessage.success(`添加成功，RSS 实时抓取通过（命中 ${t.count ?? 0} 条）`)
    } else {
      ElMessage.success(`添加成功，测试抓取通过（列表页获取到 ${t.fetched_links ?? 0} 个链接）`)
    }
    createVisible.value = false
    Object.assign(form, {
      name: '', key: '', type: 'generic_site',
      scope_region_codes: [], priority: 50, enabled: true, config_json: DEFAULT_CONFIG,
      filter_mode: '', keyword_scope: '',
    })
    feedList.value = ['']
    reload()
  } catch (e: any) {
    // 后端真实抓取校验失败 / 参数错误 / key 重复：返回失败提示，不关闭弹窗
    ElMessage.error(e?.response?.data?.detail || '添加失败')
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.ds-page { min-height: 100%; }
.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 18px; gap: 12px; flex-wrap: wrap;
}
.filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.f-select { width: 160px; }
.f-input { width: 200px; }
.count-tip { font-size: 13px; color: #86868b; }

.card {
  background: #fff; border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 12px 32px rgba(0,0,0,.05);
  padding: 6px 6px 14px; overflow: hidden;
}
table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
.source-table-card {
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  box-sizing: border-box;
  -webkit-overflow-scrolling: touch;
}
.source-table-card .tbl { width: max-content; min-width: 100%; }
table.tbl thead th {
  text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b;
  padding: 14px 18px; border-bottom: 1px solid #e8e8ed;
}
table.tbl tbody td { padding: 13px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; vertical-align: middle; }
table.tbl tbody tr:last-child td { border-bottom: none; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }

.ds-name { font-size: 14px; font-weight: 600; color: #1d1d1f; }
.ds-key { font-size: 12px; color: #86868b; margin-top: 2px; }

.pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; border-radius: 980px; font-size: 12px; font-weight: 500;
}
.pill-blue { background: rgba(0,122,255,0.1); color: #007aff; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.region-cell { white-space: nowrap; }
.region-pill { white-space: nowrap; }
.muted { color: #b0b0b5; }
.metric-number { font-variant-numeric: tabular-nums; font-weight: 600; }
.metric-divider { color: #86868b; margin: 0 4px; }
.quality-hint { font-size: 12px; color: #86868b; margin-top: 4px; white-space: nowrap; }
.keyword-policy { min-width: 180px; max-width: 240px; }
.keyword-policy-desc { color: #6e6e73; font-size: 12px; line-height: 1.45; margin-top: 4px; }
.keyword-policy-list { color: #1d1d1f; font-size: 12px; line-height: 1.45; margin-top: 2px; overflow-wrap: anywhere; }

.pager { display: flex; justify-content: flex-end; margin-top: 16px; }

.btn {
  display: inline-flex; align-items: center; justify-content: center;
  border: none; border-radius: 980px; padding: 8px 16px; font-size: 14px;
  font-weight: 500; cursor: pointer; transition: background-color .18s, opacity .18s;
}
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover { background: #0077ed; }
.btn-primary:disabled { opacity: .55; cursor: default; }
.btn-ghost { background: #f5f5f7; color: #1d1d1f; }
.btn-ghost:hover { background: #e8e8ed; }
.btn-mini { background: transparent; color: #0071e3; padding: 4px 10px; font-size: 13px; }
.btn-mini:hover { background: #e8f1fd; }
.btn-sm { padding: 6px 14px; font-size: 13px; }

/* 批量操作栏（复用关键词管理页样式） */
.batch-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.batch-info { font-size: 13px; color: #86868b; }
.row-check { width: 16px; height: 16px; cursor: pointer; accent-color: #0071e3; }

.dlg-sub { font-size: 15px; font-weight: 600; margin: 0 0 10px; color: #1d1d1f; }
.run-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.run-stat {
  min-height: 58px;
  padding: 10px 12px;
  border: 1px solid #e8e8ed;
  border-radius: 12px;
  background: #fafafc;
  box-sizing: border-box;
}
.run-stat span { display: block; font-size: 12px; color: #86868b; margin-bottom: 4px; }
.run-stat b { font-size: 20px; color: #1d1d1f; font-variant-numeric: tabular-nums; }
.table-card {
  padding: 0 6px 14px;     /* 去掉顶部内边距，避免吸顶表头与窗口顶之间出现空隙 */
  max-height: 56vh;        /* 内容过长时弹窗内出现纵向滚动窗 */
  overflow: auto;
  background: #fff;        /* 任何亚像素缝隙显示白色而非底下滚动内容 */
}
/* 苹果风细滚动条 */
.table-card::-webkit-scrollbar { width: 8px; height: 8px; }
.table-card::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 8px; }
.table-card::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.32); }
.table-card::-webkit-scrollbar-track { background: transparent; }
.hist-tbl td, .hist-tbl th { white-space: nowrap; }
.hist-tbl thead th {
  position: sticky; top: 0; z-index: 2;
  background: #fff;        /* 不透明背景，滚动内容不会从表头下方透出 */
  border-bottom: 1px solid #e8e8ed;  /* 实线分隔，避免阴影抗锯齿造成的缝隙 */
}
.hist-tbl td { padding: 12px 18px; }
.dlg-foot { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
@media (max-width: 600px) {
  .f-select, .f-input { width: 100%; }
}
.cfg-err { color: #ff3b30; font-size: 12.5px; margin-right: auto; }

/* 工具栏右侧：计数 + 新建按钮 */
.toolbar-right { display: flex; align-items: center; gap: 14px; }
/* 新建采集源表单 */
.create-form { display: flex; flex-direction: column; gap: 16px; }
.cf-row { display: flex; flex-direction: column; gap: 6px; }
.cf-row-2 { flex-direction: row; gap: 28px; }
.cf-col { display: flex; flex-direction: column; gap: 6px; }
.cf-label { font-size: 13px; font-weight: 500; color: #1d1d1f; }
.cf-label .req { color: #ff3b30; }
.cf-full { width: 100%; }
.cf-divider { height: 1px; background: #e8e8ed; margin: 18px 0; border: none; }
.filter-row { display: flex; gap: 12px; }
.cf-half { flex: 1; }
.cf-hint { font-size: 12px; color: #86868b; }
.test-msg { font-size: 12.5px; margin-right: auto; }
.test-msg.ok { color: #1a8e3c; }
.test-msg.bad { color: #ff3b30; }

/* 专用型/通用型 类型徽标（列表名称旁） */
.ck {
  display: inline-flex; align-items: center; margin-left: 8px;
  padding: 2px 9px; border-radius: 980px; font-size: 11.5px; font-weight: 500;
  vertical-align: middle;
}
.ck-gen { background: rgba(0,122,255,0.1); color: #007aff; }
.ck-ded { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.ck-rss { background: rgba(175,82,222,0.12); color: #af52de; }
.ck-ext { background: rgba(255,149,0,0.12); color: #c2700a; }

/* RSS feeds 编辑列表 */
.feed-list { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.feed-item { display: flex; align-items: center; gap: 8px; }
.feed-item .el-input { flex: 1; }

/* 专用型配置弹窗：只读提示 */
.cfg-note {
  font-size: 13px; line-height: 1.6; color: #1d1d1f;
  background: #f5f5f7; border: 1px solid #e8e8ed; border-radius: 12px;
  padding: 14px 16px; margin-bottom: 6px;
}
.cfg-note code {
  background: #e8e8ed; padding: 1px 6px; border-radius: 6px; font-size: 12.5px;
}
.status-on { color: #52c41a; font-weight: 500; }
.status-off { color: #ff4d4f; font-weight: 500; }

/* bb-browser 平台选择网格 */
.platform-grid {
  display: flex; flex-wrap: wrap; gap: 10px; width: 100%;
}
.platform-item {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px; border: 1px solid #e5e5ea; border-radius: 12px;
  background: #fff; cursor: pointer; font-size: 13px; user-select: none;
  transition: border-color .15s, background .15s;
}
.platform-item.is-checked {
  border-color: #0071e3; background: #f0f7ff;
}
.platform-item.is-disabled {
  cursor: not-allowed; opacity: .55; background: #f5f5f7;
}
.platform-item input { margin: 0; }
.platform-name { font-weight: 500; color: #1d1d1f; }
.platform-tag {
  font-size: 11px; padding: 1px 7px; border-radius: 999px; line-height: 1.6;
}
.tag-locked { background: #fdecec; color: #c0392b; }
</style>

<style>
/* 苹果风弹窗：仅作用于带 apple-dialog 类的 el-dialog（被 teleport 到 body，需全局样式） */
.apple-dialog {
  border-radius: 22px;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.22), 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  background: #fff;
}
.apple-dialog .el-dialog__header {
  padding: 22px 26px 10px;
  margin-right: 0;
}
.apple-dialog .el-dialog__title {
  font-size: 17px;
  font-weight: 600;
  color: #1d1d1f;
  letter-spacing: 0.2px;
}
.apple-dialog .el-dialog__headerbtn {
  top: 20px;
  right: 20px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  transition: background-color 0.18s;
}
.apple-dialog .el-dialog__headerbtn:hover {
  background: #f0f0f3;
}
.apple-dialog .el-dialog__headerbtn .el-dialog__close {
  color: #86868b;
  font-size: 18px;
  font-weight: 400;
}
.apple-dialog .el-dialog__headerbtn:hover .el-dialog__close {
  color: #1d1d1f;
}
.apple-dialog .el-dialog__body {
  padding: 4px 26px 10px;
  color: #1d1d1f;
  font-size: 14px;
}
.apple-dialog .el-dialog__footer {
  padding: 14px 26px 22px;
}

/* 背景遮罩毛玻璃 */
.apple-modal {
  background: rgba(0, 0, 0, 0.34);
  backdrop-filter: saturate(160%) blur(8px);
  -webkit-backdrop-filter: saturate(160%) blur(8px);
}

/* Phase DataSource-Filter-Config-4：过滤策略展示 */
.filter-strategy-cell { display: flex; flex-direction: column; gap: 4px; }
.filter-strategy-src { font-size: 12px; color: #86868b; line-height: 1.4; }
.strategy-preview {
  margin: 4px 0 2px;
  padding: 10px 12px;
  border: 1px solid #e5e5ea;
  border-radius: 10px;
  background: #fafafa;
}
.strategy-preview-title { font-size: 12px; color: #86868b; margin-bottom: 6px; }
.strategy-preview-row { display: flex; align-items: center; gap: 8px; }
.strategy-preview-src { font-size: 12px; color: #86868b; }
.strategy-preview-ks { font-size: 12px; color: #515154; margin-top: 4px; }
/* 限定在 apple-dialog 内：本块为非 scoped 全局样式，
   裸 .pill-green 会泄漏并污染 EventDetail 等使用同名类的页面 */
.apple-dialog .pill-green { background: #e7f7ed; color: #1a8a4f; }
.cfg-warn {
  margin-top: 6px; padding: 8px 10px; border-radius: 8px;
  background: #fff7ed; border: 1px solid #fed7aa; color: #c2410c; font-size: 12px;
}
.cfg-info {
  margin-top: 6px; padding: 8px 10px; border-radius: 8px;
  background: #f0f9ff; border: 1px solid #bae6fd; color: #0369a1; font-size: 12px;
}
</style>
