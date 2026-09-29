<template>
  <div class="my-trips-page">
    <div class="page-header">
      <h1>🧳 我的行程</h1>
      <a-button type="primary" @click="router.push('/trip-create')">
        <template #icon><icon-plus /></template>
        创建新行程
      </a-button>
    </div>

    <a-spin :loading="store.loading" style="width: 100%">
      <!-- 空状态 -->
      <a-empty v-if="!store.loading && store.trips.length === 0" description="还没有行程，去创建一份吧">
        <template #image><span style="font-size: 56px">🗺️</span></template>
        <a-button type="primary" @click="router.push('/trip-create')">创建行程</a-button>
      </a-empty>

      <!-- 行程卡片列表 -->
      <div v-else class="trip-list">
        <a-card
          v-for="trip in store.trips"
          :key="trip.id"
          class="trip-card"
          :hoverable="true"
        >
          <div class="trip-card-body">
            <div class="trip-cover photo-shade" @click="openDetail(trip)">
              <city-image :city="trip.destination" />
              <span class="trip-city font-display">{{ trip.destination }}</span>
            </div>
            <div class="trip-main" @click="openDetail(trip)">
              <div class="trip-title">{{ trip.title }}</div>
              <div class="trip-desc">{{ tripDesc(trip) }}</div>
              <div class="trip-meta">
                <span><icon-location /> {{ trip.destination }}</span>
                <span><icon-calendar /> {{ trip.start_date }} ~ {{ trip.end_date }}</span>
                <span><icon-user-group /> {{ trip.travelers }} 人</span>
                <span v-if="trip.budget"><icon-tag /> ¥{{ trip.budget.toLocaleString() }}</span>
              </div>
            </div>
            <div class="trip-actions">
              <a-button size="small" @click="openDetail(trip)">查看</a-button>
              <a-popconfirm
                content="确定删除该行程吗？"
                @ok="onDelete(trip)"
              >
                <a-button size="small" status="danger">删除</a-button>
              </a-popconfirm>
            </div>
          </div>
        </a-card>
      </div>
    </a-spin>

    <!-- 行程详情抽屉 -->
    <a-drawer
      :visible="detailVisible"
      :title="activeTrip?.title || '行程详情'"
      :width="680"
      :footer="false"
      @cancel="detailVisible = false"
    >
      <div v-if="activeTrip" class="detail-banner photo-shade">
        <city-image :city="activeTrip.destination" credit />
        <div class="banner-copy">
          <div class="detail-title font-display">{{ activeTrip.destination }}</div>
          <div class="detail-meta">{{ activeTrip.start_date }} ~ {{ activeTrip.end_date }}</div>
          <div class="detail-actions">
            <a-button size="small" status="success" @click="share">
              <template #icon><icon-share-alt /></template>分享
            </a-button>
            <a-button size="small" @click="copyMd">
              <template #icon><icon-copy /></template>复制 Markdown
            </a-button>
            <a-button size="small" @click="exportPdf">
              <template #icon><icon-file-pdf /></template>导出 PDF
            </a-button>
          </div>
        </div>
      </div>

      <div v-if="activeTrip && !activeTrip.generated_plan?.content" class="no-plan">
        <p class="no-plan-tip">这个行程还没有 AI 规划内容</p>
        <a-button type="primary" status="warning" :loading="generating" @click="generatePlan">
          ✨ 一键生成 AI 计划
        </a-button>
      </div>

      <template v-if="activeTrip?.generated_plan?.days?.length">
        <div class="plan-timeline">
          <div v-for="d in activeTrip.generated_plan.days" :key="d.day" class="timeline-day">
            <div class="timeline-marker"><div class="day-num">{{ d.day }}</div></div>
            <div class="timeline-body">
              <div class="timeline-title">第 {{ d.day }} 天 · {{ d.title }}</div>
              <div class="markdown-body" v-html="renderMarkdown(d.text)"></div>
            </div>
          </div>
        </div>
      </template>
      <div
        v-else
        class="markdown-body"
        v-html="renderMarkdown(activeTrip?.generated_plan?.content || '暂无行程内容')"
      ></div>

      <div v-if="activeTrip" class="detail-gallery">
        <div class="map-title">🖼️ 目的地图鉴</div>
        <place-gallery :places="detailPlaces(activeTrip)" />
      </div>

      <div v-if="activeTrip" class="detail-map">
        <div class="map-title">📍 景点 & 🏨 酒店地图</div>
        <trip-map
          :spots="activeTrip?.generated_plan?.spots || []"
          :hotels="hotels"
          :city="activeTrip?.destination || ''"
        />
      </div>

      <div class="detail-hotels">
        <div class="map-title">🛏️ 周边可订酒店</div>
        <a-spin :loading="hotelsLoading" style="width: 100%">
          <a-empty v-if="!hotelsLoading && hotels.length === 0" description="暂无该地可订酒店" />
          <div v-else class="hotel-list">
            <div v-for="h in hotels" :key="h.hotelId" class="hotel-item">
              <div class="hotel-info">
                <div class="hotel-name">
                  {{ h.name }}
                  <template v-if="h.starRating"><span class="star">★{{ h.starRating }}</span></template>
                </div>
                <div class="hotel-price">{{ h.price?.message || '' }}</div>
              </div>
              <a-button size="small" type="primary" @click="openBooking(h)">去预订</a-button>
            </div>
          </div>
        </a-spin>
      </div>
    <div class="detail-hotels">
        <div class="map-title">🛏️ 周边可订酒店</div>
        <a-spin :loading="hotelsLoading" style="width: 100%">
          <a-empty v-if="!hotelsLoading && hotels.length === 0" description="暂无该地可订酒店" />
          <div v-else class="hotel-list">
            <div v-for="h in hotels" :key="h.hotelId" class="hotel-item">
              <div class="hotel-info">
                <div class="hotel-name">
                  {{ h.name }}
                  <template v-if="h.starRating"><span class="star">★{{ h.starRating }}</span></template>
                </div>
                <div class="hotel-price">{{ h.price?.message || '' }}</div>
              </div>
              <a-button size="small" type="primary" @click="openBooking(h)">去预订</a-button>
            </div>
          </div>
        </a-spin>
      </div>

      <div class="detail-hotels">
        <div class="map-title">✈️ 机票（预订入口）</div>
        <a-spin :loading="flightsLoading" style="width: 100%">
          <a-empty v-if="!flightsLoading && !singleFlight && !returnFlight" description="暂无该路线购票入口" />
          <div v-else class="flight-list">
            <div v-if="singleFlight" class="hotel-item">
              <div class="hotel-info">
                <div class="hotel-name">去程 · {{ singleFlight.from }} → {{ singleFlight.to }}</div>
                <div class="hotel-price">{{ singleFlight.date }} · 查看当日航班 & 价格</div>
              </div>
              <a-button size="small" type="primary" @click="openFlight(singleFlight, 'departure')">去购票</a-button>
            </div>
            <div v-if="returnFlight" class="hotel-item">
              <div class="hotel-info">
                <div class="hotel-name">返程 · {{ returnFlight.from }} → {{ returnFlight.to }}</div>
                <div class="hotel-price">{{ returnFlight.date }} · 查看当日航班 & 价格</div>
              </div>
              <a-button size="small" type="primary" @click="openFlight(returnFlight, 'return')">去购票</a-button>
            </div>
          </div>
        </a-spin>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import MarkdownIt from 'markdown-it'
import { useTripStore } from '@/stores/trip'
import { shareApi } from '@/api/share'
import { tripApi } from '@/api/trips'
import { hotelsApi, type RollingHotel } from '@/api/hotels'
import { flightsApi, type FlightOption } from '@/api/flights'
import { trackingApi } from '@/api/tracking'
import TripMap from '@/components/TripMap.vue'
import CityImage from '@/components/CityImage.vue'
import PlaceGallery from '@/components/PlaceGallery.vue'
import type { PlaceItem } from '@/data/usePlaceImages'
import { buildPlaceGallery } from '@/data/placeGallery'
import type { Trip } from '@/types'

const router = useRouter()
const store = useTripStore()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const renderMarkdown = (c: string) => md.render(c || '')

// 卡片地点说明：取 AI 计划正文首段非空文字，去 markdown 记号并截断
const tripDesc = (t: Trip): string => {
  const c = (t.generated_plan?.content || '').trim()
  if (c) {
    const first = c
      .split(/\n+/)
      .map((s) => s.trim())
      .find(Boolean)
    if (first) return first.replace(/^[\s#>*\-]+/, '').slice(0, 60)
  }
  return `${t.destination} · 沉浸式旅行计划`
}

// 详情"目的地图鉴"：统一走 buildPlaceGallery（城市可验证属于目的地才有独立照片）
const detailPlaces = (t: Trip): PlaceItem[] =>
  buildPlaceGallery(t.destination, t.generated_plan?.spots || [], 5)

const detailVisible = ref(false)
const activeTrip = ref<Trip | null>(null)
const hotels = ref<RollingHotel[]>([])
const hotelsLoading = ref(false)
const flightsLoading = ref(false)
const singleFlight = ref<FlightOption | null>(null)
const returnFlight = ref<FlightOption | null>(null)
const generating = ref(false)
// 生成版本号：生成成功 +1，让打开详情时发起的旧 GET 不再覆盖新生成的行程
const genRevision = ref(0)

// 一键用 AI 生成行程计划（针对暂无计划的行程）
const generatePlan = async () => {
  if (!activeTrip.value || generating.value) return
  generating.value = true
  try {
    const fresh = await tripApi.generate(activeTrip.value.id)
    genRevision.value++ // 让打开详情时的旧 GET 不再覆盖本结果
    activeTrip.value = fresh
    loadHotels(fresh.destination || '')
    loadFlights(fresh.destination || '', fresh.start_date || '', fresh.end_date || '')
    Message.success('AI 行程已生成')
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '生成失败，请稍后重试')
  } finally {
    generating.value = false
  }
}

const openDetail = async (trip: Trip) => {
  activeTrip.value = trip
  detailVisible.value = true
  loadHotels(trip.destination)
  loadFlights(trip.destination, trip.start_date || '', trip.end_date || '')
  // 埋点：行程曝光
  trackingApi.track('trip_view', { channel: 'trip_detail', trip_id: trip.id })
  // 拉取最新详情：后端会为含正文/天数的计划自动补全景点坐标，地图才能显示
  const rev = genRevision.value
  try {
    const fresh = await tripApi.get(trip.id)
    // 仅当期间没有触发"重新生成"时才应用，避免覆盖新生成的行程
    if (fresh && genRevision.value === rev) activeTrip.value = fresh
  } catch {
    /* 保留列表数据 */
  }
}

const loadHotels = async (place: string) => {
  hotels.value = []
  if (!place) return
  hotelsLoading.value = true
  try {
    const r = await hotelsApi.search(place, 6)
    hotels.value = r.hotels || []
  } catch {
    hotels.value = []
  } finally {
    hotelsLoading.value = false
  }
}

const openBooking = (h: RollingHotel) => {
  if (!h.bookingUrl) return
  // 埋点：预订点击（漏斗 曝光→点击）
  trackingApi.track('booking_click', {
    channel: 'rollinggo_hotel',
    trip_id: activeTrip.value?.id,
    meta: { url: h.bookingUrl },
  })
  window.open(h.bookingUrl, '_blank')
}

// 机票：按行程目的地+日期生成购票落地页深链（CPS，无实时价格）
const loadFlights = async (destination: string, start?: string, end?: string) => {
  singleFlight.value = null
  returnFlight.value = null
  if (!destination) return
  flightsLoading.value = true
  try {
    const r = await flightsApi.search({ to: destination, date: start || '', return_date: end || undefined })
    singleFlight.value = r.departure
    returnFlight.value = r.return || null
  } catch {
    singleFlight.value = null
    returnFlight.value = null
  } finally {
    flightsLoading.value = false
  }
}

const openFlight = (opt: FlightOption, leg: 'departure' | 'return') => {
  if (!opt.booking_url) return
  // 埋点：机票预订点击
  trackingApi.track('booking_click', {
    channel: 'flight_cps',
    trip_id: activeTrip.value?.id,
    meta: { url: opt.booking_url, leg, from: opt.from, to: opt.to, date: opt.date },
  })
  window.open(opt.booking_url, '_blank')
}

const onDelete = async (trip: Trip) => {
  try {
    await store.removeTrip(trip.id)
    Message.success('已删除')
  } catch (e) {
    Message.error('删除失败')
  }
}

// 复制 Markdown
const copyMd = async () => {
  const text = activeTrip.value?.generated_plan?.content || ''
  if (!text) return Message.warning('该行程无可复制的正文')
  try {
    await navigator.clipboard.writeText(text)
    Message.success('Markdown 已复制')
  } catch {
    Message.error('复制失败')
  }
}

// 导出 PDF（借助浏览器打印另存为 PDF）
const exportPdf = () => {
  const trip = activeTrip.value
  if (!trip) return
  const html = md.render(trip.generated_plan?.content || '暂无内容')
  const w = window.open('', '_blank')
  if (!w) {
    Message.error('浏览器阻止了弹窗，请允许后重试')
    return
  }
  w.document.write(
    `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${trip.title || '行程'}</title>` +
      `<style>body{font-family:sans-serif;max-width:720px;margin:24px auto;padding:0 16px;color:#222;line-height:1.8;word-break:break-word}h1,h2,h3{color:#111}li{margin:4px 0}@media print{body{margin:0}}</style></head>` +
      `<body><h1>${trip.title || ''}</h1><p style="color:#888">${trip.destination || ''} · ${trip.start_date || ''} ~ ${trip.end_date || ''}</p>${html}</body></html>`
  )
  w.document.close()
  w.focus()
  setTimeout(() => w.print(), 300)
}

// 生成/复制分享短链接
const share = async () => {
  if (!activeTrip.value) return
  try {
    const r = await shareApi.shareTrip(activeTrip.value.id)
    const url = `${window.location.origin}${r.url}`
    await navigator.clipboard.writeText(url)
    Message.success('分享链接已复制')
  } catch {
    Message.error('生成分享链接失败')
  }
}

onMounted(() => store.fetchTrips())
</script>

<style scoped>
.my-trips-page { max-width: 900px; margin: 0 auto; padding: 32px 16px 32px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.page-header h1 { font-size: 32px; margin: 0; font-weight: 300; color: var(--ink); }
.trip-list { display: flex; flex-direction: column; gap: 14px; }
.trip-card { border-radius: var(--radius-card); border: 1px solid var(--line); background: var(--surface); transition: transform .3s cubic-bezier(.2,.7,.2,1), box-shadow .3s; }
.trip-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-soft); }
.trip-card-body { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.trip-cover { position: relative; flex-shrink: 0; width: 132px; height: 92px; border-radius: 10px; overflow: hidden; cursor: pointer; }
.trip-cover img { width: 100%; height: 100%; object-fit: cover; transition: transform 1.4s cubic-bezier(.2,.7,.2,1); }
.trip-card:hover .trip-cover img { transform: scale(1.06); }
.trip-cover::after { content:''; position:absolute; inset:0; background: linear-gradient(180deg, rgba(11,15,14,0) 40%, rgba(11,15,14,0.62) 100%); border-radius: inherit; }
.trip-city { position: absolute; left: 10px; bottom: 8px; z-index: 1; color: #fff; font-size: 15px; font-weight: 400; }
.trip-main { flex: 1; cursor: pointer; }
.trip-title { font-size: 17px; font-weight: 400; color: var(--ink); margin-bottom: 6px; font-family: var(--font-display); }
.trip-desc { font-size: 12px; color: var(--ink-faint); line-height: 1.5; margin-bottom: 6px; }
.trip-meta { display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; color: var(--ink-faint); }
.trip-actions { display: flex; gap: 8px; flex-shrink: 0; }
.detail-head { margin-bottom: 16px; }
.detail-banner { position: relative; height: 168px; border-radius: 14px; overflow: hidden; margin-bottom: 18px; }
.detail-banner img { width: 100%; height: 100%; object-fit: cover; }
.detail-banner::after { content:''; position:absolute; inset:0; background: linear-gradient(180deg, rgba(11,15,14,0) 30%, rgba(11,15,14,0.72) 100%); }
.banner-copy { position: absolute; left: 16px; bottom: 14px; z-index: 1; color: #fff; }
.detail-actions { display: flex; gap: 8px; margin-top: 8px; }
.no-plan { padding: 32px 0; text-align: center; color: var(--ink-faint); border: 1px dashed var(--line); border-radius: 10px; background: var(--bg-alt); margin-bottom: 18px; }
.no-plan-tip { margin: 0 0 14px; font-size: 14px; }
.detail-title { font-size: 22px; font-weight: 400; color: #fff; font-family: var(--font-display); }
.detail-gallery { margin-top: 20px; }
.detail-gallery :deep(.place-gallery) { margin-top: 8px; }
.detail-map { margin-top: 20px; }
.detail-hotels { margin-top: 20px; }
.map-title { font-size: 15px; font-weight: 600; color: var(--ink); margin-bottom: 8px; }
.hotel-list { display: flex; flex-direction: column; gap: 8px; }
.hotel-item { display: flex; align-items: center; justify-content: space-between; gap: 10px; border: 1px solid #e5e6eb; border-radius: 8px; padding: 10px 12px; background: #fff; }
.hotel-name { font-size: 14px; font-weight: 600; color: #1d2129; }
.hotel-name .star { color: #f79a3b; margin-left: 5px; font-size: 13px; }
.hotel-price { font-size: 12px; color: #86909c; margin-top: 3px; }
.detail-meta { font-size: 13px; color: rgba(255,255,255,0.75); }
.plan-timeline { display: flex; flex-direction: column; gap: 18px; }
.timeline-day { display: flex; gap: 12px; }
.timeline-marker { position: relative; display: flex; flex-direction: column; align-items: center; flex-shrink: 0; }
.day-num { width: 26px; height: 26px; border-radius: 50%; background: #165dff; color: #fff; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: center; z-index: 1; }
.timeline-marker::after { content: ''; position: absolute; top: 34px; bottom: -20px; width: 2px; background: #e5e6eb; }
.timeline-day:last-child .timeline-marker::after { display: none; }
.timeline-body { flex: 1; min-width: 0; }
.timeline-title { font-size: 15px; font-weight: 500; color: var(--ink); margin-bottom: 6px; font-family: var(--font-display); }
.timeline-body :deep(.markdown-body) { background: var(--bg); border-radius: 8px; padding: 10px 14px; }
</style>