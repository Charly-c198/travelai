<template>
  <div class="trip-map">
    <div ref="mapRef" class="map-container"></div>
    <div v-if="loadState === 'missing-key'" class="map-note">未配置高德地图 key，无法显示地图</div>
    <div v-else-if="loadState === 'error'" class="map-note">地图加载失败</div>
    <div v-else-if="loadState === 'ready' && (spots || []).length === 0 && !city" class="map-note">暂无带坐标的景点</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount, computed } from 'vue'

interface MapSpot {
  name?: string
  city?: string
  latitude?: number | null
  longitude?: number | null
}

const props = defineProps<{ spots: MapSpot[]; hotels?: MapSpot[]; city?: string }>()
const mapRef = ref<HTMLElement>()
const loadState = ref<'loading' | 'ready' | 'error' | 'missing-key'>('loading')

const AMAP_KEY = (import.meta.env.VITE_AMAP_JS_KEY as string) || ''

let map: any = null
let markers: any[] = []
let amapScript: HTMLScriptElement | null = null

const valid = computed(() => (props.spots || []).filter((s) => s.latitude && s.longitude))
const validHotels = computed(() => (props.hotels || []).filter((h) => (h as any).latitude && (h as any).longitude))

function loadAMap(): Promise<any> {
  return new Promise((resolve, reject) => {
    if ((window as any).AMap) return resolve((window as any).AMap)
    if (!AMAP_KEY) { loadState.value = 'missing-key'; return reject(new Error('no key')) }
    const script = document.createElement('script')
    // 显式声明插件，保证 AMap.Geocoder 一定可用（否则地理编码会报错并可能破坏渲染树）
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}&plugin=AMap.Geocoder`
    script.onload = () => resolve((window as any).AMap)
    script.onerror = () => { loadState.value = 'error'; reject(new Error('amap load fail')) }
    amapScript = script
    document.head.appendChild(script)
  })
}

function makeMarker(pos: any, name: string, color: string) {
  const AMap = (window as any).AMap
  // 纯 CSS 图钉 + 名字气泡全部塞进 content（真实 DOM 节点，textContent 无注入）：
  // 不依赖 AMap 默认图标图片 / emoji 字体 / label 渲染，杜绝"空白占位框/名字不显示"。
  const wrap = document.createElement('div')
  wrap.style.cssText = 'position:relative'
  const pin = document.createElement('div')
  pin.style.cssText =
    `position:relative;width:20px;height:20px;background:${color};` +
    'border:2px solid #fff;border-radius:50% 50% 50% 0;transform:rotate(-45deg);' +
    'box-shadow:0 2px 6px rgba(11,15,14,.35)'
  const dot = document.createElement('div')
  dot.style.cssText = 'position:absolute;left:5px;top:5px;width:6px;height:6px;background:#fff;border-radius:50%'
  pin.appendChild(dot)
  if (name) {
    const bubble = document.createElement('div')
    bubble.style.cssText =
      'position:absolute;bottom:24px;left:50%;transform:translateX(-50%);' +
      'white-space:nowrap;font-size:12px;color:#333;background:#fff;' +
      'border:1px solid #e5e6eb;border-radius:4px;padding:1px 6px;' +
      'box-shadow:0 1px 4px rgba(11,15,14,.15)'
    bubble.textContent = name // textContent：酒店/景点名来自外部，杜绝 XSS
    wrap.appendChild(bubble)
  }
  wrap.appendChild(pin)
  return new AMap.Marker({
    position: pos,
    title: name || '',
    anchor: 'bottom-center',
    content: wrap,
  })
}

function renderMap() {
  if (!mapRef.value || loadState.value !== 'ready') return
  const AMap = (window as any).AMap
  try {
    // 若已存在，清空重绘
    if (map) { map.destroy(); map = null }
  map = new AMap.Map(mapRef.value, { zoom: 9, resizeEnable: true })
  markers.forEach((m) => m && m.setMap && m.setMap(null))
  markers = []

  const spotList = valid.value
  const hotelList = validHotels.value

  // 无任何坐标点：若给了目的地城市，把地图居中到该城市，避免一片空白
  if (spotList.length === 0 && hotelList.length === 0) {
    const cityName = props.city || ''
    if (cityName) {
      try {
        // 高德 Geocoder 需先懒加载插件，否则 AMap.Geocoder 不存在会抛错把渲染树弄坏
        AMap.plugin(['AMap.Geocoder'], () => {
          try {
            const geocoder = new AMap.Geocoder({ city: '全国' })
            geocoder.getLocation(cityName, (status: any, result: any) => {
              if (status === 'complete' && result?.geocodes?.length) {
                const loc = result.geocodes[0].location
                map?.setCenter(loc)
                const m = makeMarker(loc, cityName, '#165dff')
                m.setMap(map)
                markers.push(m)
              }
            })
          } catch {
            /* 定位失败，保持空白 */
          }
        })
      } catch {
        /* 插件加载失败，保持空白 */
      }
    }
    return
  }

  const bounds = new AMap.Bounds(new AMap.LngLat(180, 90), new AMap.LngLat(-180, -90))
  const plotList = (list: MapSpot[], color: string) => {
    list.forEach((s) => {
      const pos = new AMap.LngLat(Number((s as any).longitude), Number((s as any).latitude))
      bounds.extend(pos)
      const marker = makeMarker(pos, s.name || '', color)
      marker.setMap(map)
      markers.push(marker)
    })
  }
  plotList(spotList, '#165dff')
  plotList(hotelList, '#e8653a')
  map.setFitView()
  } catch (e) { console.error('[TripMap] render 出错', e) }
}

onMounted(async () => {
  try {
    const AMap = await loadAMap()
    if (AMap) loadState.value = 'ready'
    renderMap()
  } catch {
    /* 已在 load 时置状态 */
  }
})

watch(() => props.spots, () => { if (loadState.value === 'ready') renderMap() }, { deep: true })

onBeforeUnmount(() => {
  if (map) map.destroy()
  if (amapScript) amapScript.remove()
})
</script>

<style scoped>
.trip-map { position: relative; }
.map-container { width: 100%; height: 320px; border-radius: 10px; background: #f2f3f5; }
.map-note { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #86909c; font-size: 13px; z-index: 1; background: #f7f8fa; }
</style>