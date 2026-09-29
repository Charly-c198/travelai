<template>
  <div class="trip-detail-page">
    <!-- 行程概览 -->
    <a-card class="trip-overview">
      <div class="overview-header">
        <div class="trip-info">
          <h1>{{ trip.title }}</h1>
          <div class="trip-meta">
            <span><icon-location /> {{ trip.destination }}</span>
            <span><icon-calendar /> {{ formatDate(trip.start_date) }} - {{ formatDate(trip.end_date) }}</span>
            <span><icon-user-group /> {{ trip.travelers }} 人</span>
            <span><icon-tag /> ¥{{ trip.budget?.toLocaleString() }}</span>
          </div>
        </div>
        <div class="trip-actions">
          <a-button type="primary" @click="exportPDF">
            <template #icon><icon-download /></template>
            导出 PDF
          </a-button>
          <a-button @click="shareTrip">
            <template #icon><icon-share-alt /></template>
            分享
          </a-button>
          <a-button @click="editTrip">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
        </div>
      </div>
    </a-card>

    <!-- 地图视图 -->
    <a-card title="📍 行程地图" class="map-card">
      <div ref="mapContainer" class="map-container"></div>
    </a-card>

    <!-- 每日行程 -->
    <div class="itinerary-days">
      <a-card
        v-for="day in itineraryDays"
        :key="day.id"
        class="day-card"
      >
        <template #title>
          <div class="day-header">
            <div class="day-number">Day {{ day.day_number }}</div>
            <div class="day-date">{{ formatDate(day.date) }} · {{ day.theme }}</div>
          </div>
        </template>

        <!-- 天气信息 -->
        <div v-if="day.weather_info" class="day-weather">
          <span>{{ day.weather_info.icon }} {{ day.weather_info.weather }}</span>
          <span>{{ day.weather_info.temp_low }}°C ~ {{ day.weather_info.temp_high }}°C</span>
        </div>

        <!-- 景点列表 -->
        <a-timeline>
          <a-timeline-item
            v-for="(spot, index) in day.spots"
            :key="spot.id"
            :color="getSpotColor(index)"
          >
            <div class="spot-item">
              <div class="spot-time">
                {{ spot.start_time }} - {{ spot.end_time }}
              </div>
              <div class="spot-info">
                <div class="spot-name">{{ spot.name }}</div>
                <div class="spot-meta">
                  <span>{{ spot.category }}</span>
                  <span>游览约 {{ spot.duration_minutes }} 分钟</span>
                  <span>¥{{ spot.estimated_cost }}</span>
                </div>
                <div class="spot-notes" v-if="spot.notes">
                  {{ spot.notes }}
                </div>
              </div>
              <div v-if="spot.transport_to_next" class="transport-info">
                <icon-arrow-right /> {{ spot.transport_to_next }}
              </div>
            </div>
          </a-timeline-item>
        </a-timeline>

        <div class="day-summary">
          <strong>今日总结：</strong> {{ day.summary }}
        </div>
      </a-card>
    </div>

    <!-- 预订推荐 -->
    <a-card title="✈️ 预订推荐" class="booking-card">
      <a-tabs>
        <a-tab-pane key="flights" title="机票">
          <a-list :data="flights" :loading="loadingFlights">
            <template #item="{ item }">
              <a-list-item>
                <div class="flight-item">
                  <div class="flight-time">
                    <strong>{{ item.departure_time }}</strong>
                    <div class="flight-arrow">→</div>
                    <strong>{{ item.arrival_time }}</strong>
                  </div>
                  <div class="flight-info">
                    <div>{{ item.airline }} {{ item.flight_no }}</div>
                    <div class="flight-price">¥{{ item.price }}</div>
                  </div>
                  <a-button type="primary" size="small">预订</a-button>
                </div>
              </a-list-item>
            </template>
          </a-list>
        </a-tab-pane>
        <a-tab-pane key="hotels" title="酒店">
          <a-list :data="hotels" :loading="loadingHotels">
            <template #item="{ item }">
              <a-list-item>
                <div class="hotel-item">
                  <div class="hotel-info">
                    <div class="hotel-name">{{ item.name }}</div>
                    <div class="hotel-location">{{ item.location }}</div>
                    <div class="hotel-rating">⭐ {{ item.rating }} ({{ item.review_count }}条评价)</div>
                  </div>
                  <div class="hotel-price">¥{{ item.price }}/晚</div>
                  <a-button type="primary" size="small">预订</a-button>
                </div>
              </a-list-item>
            </template>
          </a-list>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
// echarts 按需引入:只用散点 + tooltip + 网格 + Canvas 渲染器,避免整库打包
import * as echarts from 'echarts/core'
import { ScatterChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([ScatterChart, TooltipComponent, GridComponent, CanvasRenderer])

interface DaySpot {
  id: string
  name: string
  start_time: string
  end_time: string
  duration_minutes: number
  estimated_cost: number
  category: string
  notes?: string
  transport_to_next?: string
}

interface ItineraryDay {
  id: string
  day_number: number
  date: string
  theme: string
  summary: string
  weather_info: { weather: string; icon: string; temp_low: number; temp_high: number }
  spots: DaySpot[]
}

const mapContainer = ref<HTMLElement>()
const loadingFlights = ref(false)
const loadingHotels = ref(false)

const trip = ref({
  id: '',
  title: '东京5日游',
  destination: '日本东京',
  start_date: '2024-04-01',
  end_date: '2024-04-05',
  travelers: 2,
  budget: 20000
})

const itineraryDays = ref<ItineraryDay[]>([
  {
    id: '1',
    day_number: 1,
    date: '2024-04-01',
    theme: '初到东京',
    summary: '抵达东京，入住酒店，适应环境，游览浅草寺',
    weather_info: { weather: '晴', icon: '☀️', temp_low: 15, temp_high: 25 },
    spots: [
      { id: '1', name: '浅草寺', start_time: '14:00', end_time: '16:00', duration_minutes: 120, estimated_cost: 0, category: '寺庙', notes: '必去景点，可求签' },
      { id: '2', name: '仲见世商店街', start_time: '16:30', end_time: '18:00', duration_minutes: 90, estimated_cost: 2000, category: '购物', transport_to_next: '步行 10 分钟' },
    ]
  },
  {
    id: '2',
    day_number: 2,
    date: '2024-04-02',
    theme: '文化探访',
    summary: '游览上野公园、东京国立博物馆，感受日本文化',
    weather_info: { weather: '多云', icon: '⛅', temp_low: 14, temp_high: 23 },
    spots: [
      { id: '3', name: '上野恩赐公园', start_time: '09:00', end_time: '11:00', duration_minutes: 120, estimated_cost: 0, category: '公园' },
      { id: '4', name: '东京国立博物馆', start_time: '11:30', end_time: '15:00', duration_minutes: 210, estimated_cost: 1000, category: '博物馆' },
    ]
  }
])

const flights = ref([
  { departure_time: '08:00', arrival_time: '12:00', airline: '国航', flight_no: 'CA181', price: 2580 },
  { departure_time: '14:00', arrival_time: '18:00', airline: '日航', flight_no: 'JL781', price: 3200 },
])

const hotels = ref([
  { name: '东京王子大饭店', location: '港区', rating: 4.7, review_count: 5000, price: 1200 },
  { name: '新宿格拉斯丽酒店', location: '新宿', rating: 4.5, review_count: 8000, price: 800 },
])

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })
}

const getSpotColor = (index: number) => {
  const colors = ['blue', 'green', 'orange', 'purple', 'cyan']
  return colors[index % colors.length]
}

const initMap = () => {
  if (!mapContainer.value) return

  const map = echarts.init(mapContainer.value)

  // 注意：在未注册对应 GeoJSON 时，echarts 的 type:'map' 只会在控制台报 "Map xx not exists" 而非抛错，
  // try/catch 拦不住，还会让图表陷入异常态。因此本地没有 japan 地理数据前，直接用散点占位；
  // 待 Phase 3 接入高德/GeoJSON 后，再在这里按 data 渲染真实地图。
  map.setOption({
    tooltip: { trigger: 'item' },
    xAxis: { type: 'value', show: false, min: 0, max: 4 },
    yAxis: { type: 'value', show: false, min: 0, max: 4 },
    series: [{
      type: 'scatter',
      data: [[1, 1], [2, 0.5], [1.5, 2.5], [2.5, 2]],
      symbolSize: 16,
      itemStyle: { color: '#165dff' }
    }]
  })
}

const exportPDF = () => {
  Message.info('正在生成 PDF，请稍候...')
}

const shareTrip = () => {
  Message.success('分享链接已复制到剪贴板')
}

const editTrip = () => {
  Message.info('跳转到编辑页面')
}

onMounted(() => {
  initMap()
})
</script>

<style scoped>
.trip-detail-page {
  padding-bottom: 24px;
}

.trip-overview {
  margin-bottom: 16px;
}

.overview-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.trip-info h1 {
  font-size: 24px;
  margin-bottom: 8px;
}

.trip-meta {
  display: flex;
  gap: 24px;
  color: #86909c;
}

.trip-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.trip-actions {
  display: flex;
  gap: 8px;
}

.map-card {
  margin-bottom: 16px;
}

.map-container {
  width: 100%;
  height: 400px;
}

.day-card {
  margin-bottom: 16px;
}

.day-header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.day-number {
  background: #165dff;
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
}

.day-weather {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  color: #4a5a6a;
}

.spot-item {
  padding: 8px 0;
}

.spot-time {
  font-weight: 600;
  color: #165dff;
  margin-bottom: 4px;
}

.spot-name {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.spot-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #86909c;
}

.spot-notes {
  margin-top: 4px;
  font-size: 13px;
  color: #4a5a6a;
}

.transport-info {
  margin-top: 8px;
  padding: 8px;
  background: #f2f3f5;
  border-radius: 8px;
  font-size: 12px;
  color: #86909c;
  display: flex;
  align-items: center;
  gap: 4px;
}

.day-summary {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #e5e6eb;
  font-size: 14px;
  color: #4a5a6a;
}

.booking-card {
  margin-top: 16px;
}

.flight-item, .hotel-item {
  display: flex;
  align-items: center;
  gap: 24px;
  width: 100%;
}

.flight-time {
  display: flex;
  align-items: center;
  gap: 8px;
}

.flight-arrow {
  color: #165dff;
  font-size: 20px;
}

.flight-info, .hotel-info {
  flex: 1;
}

.flight-price, .hotel-price {
  font-size: 18px;
  font-weight: 600;
  color: #ff4d4f;
}

.hotel-name {
  font-weight: 600;
}

.hotel-location {
  font-size: 12px;
  color: #86909c;
}

.hotel-rating {
  font-size: 12px;
  color: #86909c;
}
</style>
