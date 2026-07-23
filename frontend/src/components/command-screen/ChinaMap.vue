<template>
  <div class="cs-map-wrap" :class="{ 'is-province': level === 'province' }">
    <div ref="mapEl" class="cs-map"></div>

    <!-- 国家级：仅加载提示 -->
    <div v-if="mapError" class="cs-map-msg">地图资源加载失败，仅影响地图展示</div>
    <div v-else-if="!mapReady" class="cs-map-msg">地图加载中…</div>

    <!-- 省级下钻：返回 + 摘要 -->
    <div v-if="level === 'province'" class="cs-map-overlay">
      <button class="cs-map-back" type="button" @click="backToCountry">
        ← 返回全国
      </button>
      <div v-if="children" class="cs-map-badge cs-mono">
        <template v-if="children.total > 0">已下钻 · {{ children.province }} · 共 {{ children.total }} 条</template>
        <template v-else>已下钻 · {{ children.province }} · 该省暂无细分数据</template>
      </div>
      <div v-else-if="loadingChildren" class="cs-map-badge">加载细分数据…</div>
    </div>

    <!-- 自动轮播控制：默认隐形（仅一个小圆点），可展开/收缩 -->
    <div class="cs-tour" :class="{ open: tourPanelOpen }">
      <button
        v-if="!tourPanelOpen"
        class="cs-tour-fab"
        type="button"
        title="自动轮播下钻"
        @click="tourPanelOpen = true"
      >
        <span class="cs-tour-fab-icon">▶</span>
      </button>
      <div v-else class="cs-tour-panel">
        <div class="cs-tour-head">
          <span>自动轮播下钻</span>
          <button class="cs-tour-x" type="button" title="收起" @click="tourPanelOpen = false">×</button>
        </div>

        <div class="cs-tour-ctrl">
          <button v-if="!tourActive" class="cs-tour-btn play" type="button" @click="startTour">▶ 开始</button>
          <template v-else>
            <button class="cs-tour-btn" type="button" @click="togglePause">
              {{ tourPaused ? '▶ 继续' : '⏸ 暂停' }}
            </button>
            <button class="cs-tour-btn stop" type="button" @click="stopTour">■ 停止</button>
          </template>
        </div>

        <div class="cs-tour-list">
          <span
            v-for="p in tourProvinces"
            :key="p"
            class="cs-tour-chip"
            :class="{ active: currentTourProvince === p }"
          >
            {{ p }}
            <button class="cs-tour-chip-x" type="button" title="移出轮播" @click="removeProvince(p)">×</button>
          </span>
          <select
            v-if="candidateProvinces.length"
            class="cs-tour-add"
            :value="''"
            @change="onAddProvince"
          >
            <option value="">+ 添加省份</option>
            <option v-for="p in candidateProvinces" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>

        <div v-if="tourActive" class="cs-tour-status cs-mono">
          {{ tourPaused ? '已暂停' : (currentTourProvince ? '轮播中 · ' + currentTourProvince : '轮播中') }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import { useEcharts, registerMapOnce } from '@/composables/useEcharts'
import { fetchRegionChildren } from '@/composables/useCommandScreen'
import type { RegionItem, RegionChildren } from '@/types'

/**
 * ChinaMap —— 中国省级 choropleth + 点击下钻到市级 + 自动轮播下钻(tour)。
 *
 * - 国家级：GeoJSON 来自本地静态资源 /geo/china-provinces.json（不依赖外网 CDN）。
 *   只消费后端已上卷好的省级 regions，前端不做任何市县→省映射。
 * - 下钻：点击省级区域 → 按该省 adcode 取「市级」GeoJSON（河北本地打包，其他省点击时
 *   按需联网从 DataV 拉取并缓存）→ 注册为 prov-{adcode} 地图 → 渲染市级着色 +
 *   悬浮 tooltip；顶部「返回全国」回到国家级。
 * - 市/县数据：通过 /api/dashboard/region-children 按省名拉取，市级已上卷（含所辖县），
 *   与市级 GeoJSON 按名称匹配着色。
 * - tour（自动轮播）：依次放大到轮播列表中的各省 → 逐个高亮该省市区并弹出 tooltip →
 *   回到全国 → 下一省，循环。轮播列表默认只含「有数据的省」（如河北），可在面板里增删。
 *   点击地图会立即停止轮播，回到手动模式。
 */
const props = defineProps<{ regions: RegionItem[] | null; days?: number }>()

const mapEl = ref<HTMLElement | null>(null)
const mapReady = ref(false)
const mapError = ref(false)
const { setOption, chart } = useEcharts(mapEl)

const CHINA_NAME = 'china'
type Level = 'country' | 'province'
const level = ref<Level>('country')
const provinceName = ref<string | null>(null)
const provinceAdcode = ref<number | null>(null)
const children = ref<RegionChildren | null>(null)
const loadingChildren = ref(false)

// 省名 → adcode 映射（从国家级 GeoJSON 的 properties 建立）
const chinaAdcodeMap = new Map<string, number>()
// 已加载的省级 GeoJSON 缓存：adcode -> geojson
const geoCache = new Map<number, object>()
// 全部省份名（用于轮播候选列表）
const allProvinceNames = ref<string[]>([])

// ---------------------------------------------------------------------------
// 自动轮播（tour）状态
// ---------------------------------------------------------------------------
const LS_KEY = 'cmd-tour-provinces'
const tourPanelOpen = ref(false)     // 面板是否展开（折叠态=仅小圆点）
const tourActive = ref(false)        // 是否正在轮播
const tourPaused = ref(false)        // 是否暂停
const tourProvinces = ref<string[]>([])   // 轮播省份列表（可编辑，持久化）
const currentTourProvince = ref<string | null>(null) // 当前轮播到的省（用于高亮）

let tourToken = 0                    // 自增令牌，用于中断在途的轮播
const sleepers = new Set<number>()   // 在途的 sleep 定时器，便于停止时清理
// 各环节停留时长（ms）
const DWELL = { province: 1600, city: 900, country: 1300 }

const candidateProvinces = computed(() =>
  allProvinceNames.value.filter((p) => !tourProvinces.value.includes(p)),
)

// 读取/保存轮播列表到 localStorage（桌面端 http 下可用；file:// 下静默降级）
function loadTourProvinces(): string[] | null {
  try {
    const v = localStorage.getItem(LS_KEY)
    return v ? (JSON.parse(v) as string[]) : null
  } catch {
    return null
  }
}
function saveTourProvinces() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(tourProvinces.value))
  } catch {
    /* 忽略：隐私模式/无 localStorage 时仅本次会话有效 */
  }
}

/** 首次用「有数据的省」初始化轮播列表（用户未自定义时）。 */
function initTourProvinces() {
  if (tourProvinces.value.length > 0) return
  const saved = loadTourProvinces()
  if (saved && saved.length) {
    tourProvinces.value = saved
    return
  }
  const dataProvinces = (props.regions ?? [])
    .filter((r) => (r.count ?? 0) > 0)
    .map((r) => r.region_name)
  if (dataProvinces.length) tourProvinces.value = dataProvinces
}

function addProvince(name: string) {
  if (!name) return
  if (!tourProvinces.value.includes(name)) {
    tourProvinces.value = [...tourProvinces.value, name]
    saveTourProvinces()
  }
}
function removeProvince(name: string) {
  tourProvinces.value = tourProvinces.value.filter((p) => p !== name)
  saveTourProvinces()
}
function onAddProvince(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  if (v) addProvince(v)
}

// 可被令牌中断的 sleep
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    const id = window.setTimeout(() => {
      sleepers.delete(id)
      resolve()
    }, ms)
    sleepers.add(id)
  })
}
function clearSleepers() {
  sleepers.forEach((id) => clearTimeout(id))
  sleepers.clear()
}
// 暂停时挂起，直到恢复
function waitWhilePaused(): Promise<void> {
  return new Promise((resolve) => {
    const check = () => {
      if (!tourPaused.value) return resolve()
      window.setTimeout(check, 200)
    }
    check()
  })
}

// 逐个高亮市区 + tooltip
function dispatchHighlight(i: number) {
  chart.value?.dispatchAction({ type: 'downplay', seriesIndex: 0 })
  chart.value?.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: i })
  chart.value?.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: i })
}
function dispatchDownplayAll() {
  chart.value?.dispatchAction({ type: 'downplay', seriesIndex: 0 })
  chart.value?.dispatchAction({ type: 'hideTip' })
}

/** 预取轮播省份的 GeoJSON，避免轮播到时才联网卡顿。 */
async function prefetchTourGeo(list: string[]) {
  await Promise.all(
    list.map(async (name) => {
      const ad = chinaAdcodeMap.get(name)
      if (ad != null) {
        try {
          await loadProvinceGeo(ad)
        } catch {
          /* 忽略个别省份拉取失败 */
        }
      }
    }),
  )
}

async function startTour() {
  const list = [...tourProvinces.value]
  if (!list.length) return
  tourActive.value = true
  tourPaused.value = false
  tourPanelOpen.value = true
  const token = ++tourToken
  await prefetchTourGeo(list)
  if (tourToken !== token) return
  if (level.value === 'province') backToCountry()
  while (tourToken === token) {
    for (const prov of list) {
      if (tourToken !== token) return
      if (tourPaused.value) await waitWhilePaused()
      if (tourToken !== token) return
      await drillTo(prov) // 放大下钻到该省（含 GeoJSON 加载 + 市级数据）
      if (tourToken !== token) return
      currentTourProvince.value = prov
      if (level.value === 'province') {
        await sleep(DWELL.province)
        if (tourToken !== token) return
        const cities = children.value?.cities ?? []
        for (let i = 0; i < cities.length; i++) {
          if (tourToken !== token) return
          if (tourPaused.value) await waitWhilePaused()
          if (tourToken !== token) return
          dispatchHighlight(i) // 依次高亮每个市区
          await sleep(DWELL.city)
        }
        dispatchDownplayAll()
      }
      currentTourProvince.value = null
      backToCountry() // 回到全国，再放下一个省
      await sleep(DWELL.country)
    }
    // 一轮结束（已回到全国），while 循环继续下一轮
  }
}

function stopTour() {
  tourToken++
  clearSleepers()
  tourActive.value = false
  tourPaused.value = false
  currentTourProvince.value = null
  dispatchDownplayAll()
  if (level.value === 'province') backToCountry()
}
function togglePause() {
  if (!tourActive.value) return
  tourPaused.value = !tourPaused.value
}

// ---------------------------------------------------------------------------
// 地图渲染
// ---------------------------------------------------------------------------
function renderCountry() {
  if (!mapReady.value) return
  const data = (props.regions ?? []).map((r) => ({ name: r.region_name, value: r.count }))
  const max = data.reduce((m, d) => Math.max(m, d.value), 0) || 1
  const option: EChartsOption = baseOption(max, data)
  setOption(option, { notMerge: true })
}

function renderProvince() {
  if (provinceAdcode.value == null || !geoCache.has(provinceAdcode.value)) return
  const data = (children.value?.cities ?? []).map((c) => ({ name: c.name, value: c.count }))
  const max = data.reduce((m, d) => Math.max(m, d.value), 0) || 1
  const option: EChartsOption = baseOption(max, data, /*roam*/ true)
  setOption(option, { notMerge: true })
}

/** 国家级与省级共用的 option 骨架；roam 仅在省级开启（可缩放/平移） */
function baseOption(max: number, data: { name: string; value: number }[], roam = false): EChartsOption {
  const mapName = level.value === 'province' && provinceAdcode.value != null
    ? `prov-${provinceAdcode.value}`
    : CHINA_NAME
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(10,17,32,0.92)',
      borderColor: 'rgba(34,211,238,0.35)',
      textStyle: { color: '#eaf6ff' },
      formatter: (p: any) => {
        const v = p.value ?? 0
        const suffix = level.value === 'province' ? '（含所辖县）' : ''
        return `${p.name}${suffix}<br/>舆情数量：${v}`
      },
    },
    visualMap: {
      min: 0,
      max,
      left: 12,
      bottom: 12,
      calculable: true,
      inRange: { color: ['#0e2233', '#0f6d80', '#22d3ee'] },
      textStyle: { color: '#a9c2da' },
    },
    series: [
      {
        type: 'map',
        map: mapName,
        roam,
        aspectScale: 0.78,
        data,
        label: { show: false },
        itemStyle: {
          areaColor: '#0c1a2b',
          borderColor: 'rgba(90,138,178,0.35)',
          borderWidth: 0.6,
        },
        emphasis: {
          label: { show: true, color: '#eaf6ff' },
          itemStyle: { areaColor: '#164863', borderColor: '#22d3ee' },
        },
      },
    ],
  }
}

async function loadProvinceGeo(adcode: number): Promise<object> {
  if (geoCache.has(adcode)) return geoCache.get(adcode)!
  // 1) 先尝试本地打包资源（如 frontend/public/geo/130000_full.json）
  try {
    const local = await fetch(`/geo/${adcode}_full.json`)
    if (local.ok) {
      const geo = await local.json()
      geoCache.set(adcode, geo)
      return geo
    }
  } catch {
    /* 本地无，下面联网 */
  }
  // 2) 按需联网从 DataV 拉取（与现有地图同源，仅在用户点击且本地缺失时触发）
  const res = await fetch(`https://geo.datav.aliyun.com/areas_v3/bound/${adcode}_full.json`)
  if (!res.ok) throw new Error(`province geo ${adcode} ${res.status}`)
  const geo = await res.json()
  geoCache.set(adcode, geo)
  return geo
}

async function drillTo(name: string) {
  const adcode = chinaAdcodeMap.get(name)
  if (adcode == null) return
  provinceName.value = name
  provinceAdcode.value = adcode
  loadingChildren.value = true
  children.value = null
  try {
    const geo = await loadProvinceGeo(adcode)
    registerMapOnce(`prov-${adcode}`, geo)
    level.value = 'province'
    // 取市/县分布（市级已上卷，可与市级 GeoJSON 按名称匹配）
    try {
      const data = await fetchRegionChildren(name, props.days ?? 7)
      children.value = data
    } catch (e: any) {
      // 该省在库中暂无细分数据（如除河北外的其他省份）：仍展示地图轮廓，提示暂无数据
      if (e?.response?.status === 404) {
        children.value = { province: name, province_code: String(adcode), total: 0, cities: [], raw: [] }
      } else {
        throw e
      }
    }
    loadingChildren.value = false
    renderProvince()
  } catch (e) {
    loadingChildren.value = false
    console.error('[ChinaMap] 省级下钻失败：', e)
    // 失败回退到国家级，避免卡在半下钻状态
    backToCountry()
  }
}

function backToCountry() {
  level.value = 'country'
  provinceName.value = null
  provinceAdcode.value = null
  children.value = null
  renderCountry()
}

function onMapClick(params: any) {
  // 仅在国家级、点击到具体省区时触发下钻
  if (level.value !== 'country') return
  if (params?.componentType === 'series' && params.name) {
    if (tourActive.value) stopTour() // 手动点击即退出轮播
    void drillTo(params.name)
  }
}

onMounted(async () => {
  // useEcharts 已在自身 onMounted 完成 init，这里绑定点击下钻
  chart.value?.on('click', onMapClick)
  try {
    const res = await fetch('/geo/china-provinces.json')
    if (!res.ok) throw new Error(`geojson ${res.status}`)
    const geo = await res.json()
    // 建立 省名 → adcode 映射，供点击下钻时取对应市级边界
    for (const f of geo.features ?? []) {
      const p = f?.properties
      if (p?.name != null && p?.adcode != null) chinaAdcodeMap.set(p.name, p.adcode)
    }
    allProvinceNames.value = [...chinaAdcodeMap.keys()]
    registerMapOnce(CHINA_NAME, geo)
    mapReady.value = true
    renderCountry()
    // 地图与省名就绪后再初始化轮播列表（默认=有数据的省）
    initTourProvinces()
  } catch (e) {
    mapError.value = true
    console.error('[ChinaMap] 加载省级 GeoJSON 失败：', e)
  }
})

onUnmounted(() => {
  // 组件卸载：中断在途轮播，避免定时器泄漏
  tourToken++
  clearSleepers()
})

// 国家级数据到位/更新时重绘
watch(() => props.regions, renderCountry, { deep: true })
// days 变化且正处于下钻态时，重新拉取细分数据
watch(() => props.days, () => {
  if (level.value === 'province' && provinceName.value) {
    loadingChildren.value = true
    fetchRegionChildren(provinceName.value, props.days ?? 7)
      .then((d) => { children.value = d; loadingChildren.value = false; renderProvince() })
      .catch(() => { loadingChildren.value = false })
  }
})
// 省级 regions 首次/后续到达时，若用户尚未自定义轮播列表则补全（有数据的省）
watch(() => props.regions, initTourProvinces, { deep: true })
</script>

<style scoped>
.cs-map-wrap { position: relative; width: 100%; height: 100%; min-height: 0; }
.cs-map { width: 100%; height: 100%; transition: opacity 0.25s ease; }
.cs-map-wrap.is-province .cs-map { opacity: 1; }
/* 下钻时的「推近」放大动画（轮播与手动下钻通用） */
.cs-map-wrap.is-province .cs-map { animation: cs-tour-zoom 0.55s cubic-bezier(0.22, 0.61, 0.36, 1); }
@keyframes cs-tour-zoom {
  from { transform: scale(1.08); opacity: 0.35; }
  to { transform: scale(1); opacity: 1; }
}
.cs-map-msg {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  color: var(--screen-ink-3); font-size: 13px; pointer-events: none;
}
.cs-map-overlay {
  position: absolute; top: 8px; left: 8px; right: 8px;
  display: flex; align-items: center; gap: 10px;
  pointer-events: none;
}
.cs-map-back {
  pointer-events: auto;
  font-size: 12px; font-weight: 600; color: #04121a;
  padding: 4px 12px; border: none; border-radius: 999px; cursor: pointer;
  background: var(--screen-primary); box-shadow: var(--screen-glow);
}
.cs-map-back:hover { filter: brightness(1.1); }
.cs-map-badge {
  font-size: 12px; color: var(--screen-ink-2);
  padding: 4px 10px; border-radius: 999px;
  background: rgba(10,17,32,0.6); border: 1px solid var(--screen-border);
}

/* ===== 自动轮播控制：默认隐形（仅右下角小圆点），可展开/收缩 ===== */
.cs-tour { position: absolute; right: 10px; bottom: 10px; z-index: 6; font-size: 12px; }
.cs-tour-fab {
  width: 30px; height: 30px; border-radius: 50%;
  border: 1px solid var(--screen-border);
  background: rgba(10,17,32,0.55); color: var(--screen-primary);
  cursor: pointer; opacity: 0.5; transition: opacity 0.2s, transform 0.2s;
  display: flex; align-items: center; justify-content: center; font-size: 11px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.35);
}
.cs-tour-fab:hover { opacity: 1; transform: scale(1.08); }
.cs-tour-panel {
  width: 226px; padding: 10px; border-radius: 12px;
  background: rgba(8,14,26,0.92); border: 1px solid var(--screen-border);
  box-shadow: 0 8px 28px rgba(0,0,0,0.45); backdrop-filter: blur(6px);
  animation: cs-panel-in 0.25s ease;
}
@keyframes cs-panel-in {
  from { opacity: 0; transform: translateY(8px) scale(0.96); }
  to { opacity: 1; transform: none; }
}
.cs-tour-head {
  display: flex; align-items: center; justify-content: space-between;
  color: var(--screen-ink-2); font-weight: 600; margin-bottom: 8px;
}
.cs-tour-x { background: none; border: none; color: var(--screen-ink-3); cursor: pointer; font-size: 15px; line-height: 1; }
.cs-tour-x:hover { color: var(--screen-ink-2); }
.cs-tour-ctrl { display: flex; gap: 6px; margin-bottom: 8px; }
.cs-tour-btn {
  flex: 1; font-size: 11px; padding: 5px 6px; border-radius: 8px;
  border: 1px solid var(--screen-border); background: rgba(34,211,238,0.08);
  color: var(--screen-ink-2); cursor: pointer; transition: filter 0.15s;
}
.cs-tour-btn.play { background: var(--screen-primary); color: #04121a; font-weight: 600; border-color: transparent; }
.cs-tour-btn.stop { background: rgba(244,63,94,0.12); color: #fca5b4; border-color: rgba(244,63,94,0.3); }
.cs-tour-btn:hover { filter: brightness(1.12); }
.cs-tour-list {
  display: flex; flex-wrap: wrap; gap: 5px; max-height: 132px; overflow: auto; margin-bottom: 6px;
}
.cs-tour-chip {
  display: inline-flex; align-items: center; gap: 3px; padding: 2px 6px;
  border-radius: 999px; font-size: 11px; color: var(--screen-ink-2);
  background: rgba(255,255,255,0.04); border: 1px solid var(--screen-border);
}
.cs-tour-chip.active { background: var(--screen-primary); color: #04121a; border-color: transparent; font-weight: 600; }
.cs-tour-chip-x { background: none; border: none; color: inherit; opacity: 0.6; cursor: pointer; font-size: 12px; line-height: 1; padding: 0; }
.cs-tour-chip-x:hover { opacity: 1; }
.cs-tour-add {
  flex-basis: 100%; margin-top: 2px; font-size: 11px;
  background: rgba(255,255,255,0.04); color: var(--screen-ink-2);
  border: 1px solid var(--screen-border); border-radius: 8px; padding: 3px 6px; cursor: pointer;
}
.cs-tour-status { font-size: 11px; color: var(--screen-primary); }

@media (prefers-reduced-motion: reduce) {
  .cs-map-wrap.is-province .cs-map { animation: none; }
  .cs-tour-panel { animation: none; }
}
</style>
