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
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import { useEcharts, registerMapOnce } from '@/composables/useEcharts'
import { fetchRegionChildren } from '@/composables/useCommandScreen'
import type { RegionItem, RegionChildren } from '@/types'

/**
 * ChinaMap —— 中国省级 choropleth + 点击下钻到市级。
 *
 * - 国家级：GeoJSON 来自本地静态资源 /geo/china-provinces.json（不依赖外网 CDN）。
 *   只消费后端已上卷好的省级 regions，前端不做任何市县→省映射。
 * - 下钻：点击省级区域 → 按该省 adcode 取「市级」GeoJSON（河北本地打包，其他省点击时
 *   按需联网从 DataV 拉取并缓存）→ 注册为 prov-{adcode} 地图 → 渲染市级着色 +
 *   悬浮 tooltip；顶部「返回全国」回到国家级。
 * - 市/县数据：通过 /api/dashboard/region-children 按省名拉取，市级已上卷（含所辖县），
 *   与市级 GeoJSON 按名称匹配着色。
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
  } catch { /* 本地无，下面联网 */ }
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
    registerMapOnce(CHINA_NAME, geo)
    mapReady.value = true
    renderCountry()
  } catch (e) {
    mapError.value = true
    console.error('[ChinaMap] 加载省级 GeoJSON 失败：', e)
  }
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
</script>

<style scoped>
.cs-map-wrap { position: relative; width: 100%; height: 100%; min-height: 0; }
.cs-map { width: 100%; height: 100%; transition: opacity 0.25s ease; }
.cs-map-wrap.is-province .cs-map { opacity: 1; }
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
</style>
