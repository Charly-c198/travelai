<template>
  <div class="dashboard-page">
    <div class="page-header">
      <h1>📊 商业仪表盘</h1>
      <a-select v-model="days" :style="{ width: 120 }" @change="load">
        <a-option :value="7">近 7 天</a-option>
        <a-option :value="30">近 30 天</a-option>
      </a-select>
    </div>

    <a-spin :loading="loading" style="width: 100%">
      <!-- 今日额度 -->
      <a-card v-if="data" class="section-card">
        <template #title>🔋 今日生成额度（{{ data?.quota.plan }}）</template>
        <div class="quota-row">
          <a-progress
            type="line"
            :percent="Math.min(100, Math.round(((data?.quota.used ?? 0) / (data?.quota.limit || 1)) * 100))"
            :format="() => `${data?.quota.used ?? 0} / ${data?.quota.limit ?? 0}`"
            style="flex: 1"
          />
          <span class="quota-remaining">剩余 {{ data?.quota.remaining }} 次</span>
        </div>
      </a-card>

      <!-- 核心指标卡 -->
      <div class="metric-grid">
        <a-card class="metric-card">
          <div class="metric-label">LLM 调用次数</div>
          <div class="metric-value">{{ data?.generation.count ?? '-' }}</div>
        </a-card>
        <a-card class="metric-card">
          <div class="metric-label">总成本（估算）</div>
          <div class="metric-value">¥{{ fmtCost(data?.generation.total_cost) }}</div>
          <div class="metric-sub">单会话均 ¥{{ fmtCost(data?.generation.avg_cost) }}</div>
        </a-card>
        <a-card class="metric-card">
          <div class="metric-label">总 Token</div>
          <div class="metric-value">{{ fmtNum((data?.generation.prompt_tokens ?? 0) + (data?.generation.completion_tokens ?? 0)) }}</div>
          <div class="metric-sub">输入 {{ fmtNum(data?.generation.prompt_tokens) }} / 输出 {{ fmtNum(data?.generation.completion_tokens) }}</div>
        </a-card>
        <a-card class="metric-card">
          <div class="metric-label">首字段延迟</div>
          <div class="metric-value">{{ fmtMs(data?.generation.first_token_p50) }}</div>
          <div class="metric-sub">P95 {{ fmtMs(data?.generation.first_token_p95) }}</div>
        </a-card>
      </div>

      <!-- 图表行 -->
      <div class="chart-grid">
        <a-card class="chart-card">
          <template #title>📈 每日生成 & 成本</template>
          <div ref="dailyChartRef" class="chart" />
        </a-card>
        <a-card class="chart-card">
          <template #title>🛒 CPS 转化漏斗</template>
          <div ref="funnelChartRef" class="chart" />
          <div class="funnel-note">
            曝光 {{ data?.cps.trip_view ?? 0 }} → 点击 {{ data?.cps.booking_click ?? 0 }} → 预订 {{ data?.cps.booking_success ?? 0 }}
            <span v-if="data?.cps.click_rate != null">· 点击率 {{ (data.cps.click_rate * 100).toFixed(1) }}%</span>
            <span v-if="data?.cps.conversion != null">· 转化率 {{ (data.cps.conversion * 100).toFixed(2) }}%</span>
          </div>
        </a-card>
      </div>

      <a-alert type="warning">
        Token 与成本为按字符数 × 系数的估算值（单价可在后端 config.py 校准），用于复盘单会话净贡献，非计费依据。
      </a-alert>
    </a-spin>

    <a-empty v-if="!loading && !data" description="暂无数据" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { dashboardApi, type DashboardSummary } from '@/api/dashboard'

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
])

const loading = ref(false)
const days = ref(7)
const data = ref<DashboardSummary | null>(null)
const dailyChartRef = ref<HTMLElement>()
const funnelChartRef = ref<HTMLElement>()
let dailyChart: echarts.ECharts | null = null
let funnelChart: echarts.ECharts | null = null

const fmtNum = (n?: number) => (n ?? 0).toLocaleString('zh-CN')
const fmtCost = (n?: number) => (n ?? 0).toFixed(4)
const fmtMs = (n?: number | null) => (n == null ? '-' : `${n} ms`)

const load = async () => {
  loading.value = true
  try {
    data.value = await dashboardApi.summary(days.value)
    await nextTick()
    renderCharts()
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

const renderCharts = () => {
  if (!data.value) return
  const g = data.value.generation

  // 每日生成&成本：柱=次数，线=成本
  if (dailyChartRef.value) {
    dailyChart = dailyChart || echarts.init(dailyChartRef.value)
    dailyChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['生成次数', '成本(元)'] },
      grid: { left: 48, right: 48, top: 40, bottom: 30 },
      xAxis: {
        type: 'category',
        data: g.per_day.map((d) => d.date.slice(5)),
      },
      yAxis: [
        { type: 'value', name: '次数', minInterval: 1 },
        { type: 'value', name: '成本', min: 0 },
      ],
      series: [
        {
          name: '生成次数',
          type: 'bar',
          data: g.per_day.map((d) => d.count),
          itemStyle: { color: '#165dff' },
        },
        {
          name: '成本(元)',
          type: 'line',
          yAxisIndex: 1,
          data: g.per_day.map((d) => Number(d.cost.toFixed(4))),
          itemStyle: { color: '#f79a3b' },
        },
      ],
    })
  }

  // CPS 漏斗：横向条形
  if (funnelChartRef.value) {
    funnelChart = funnelChart || echarts.init(funnelChartRef.value)
    const c = data.value.cps
    const items = [
      { name: '行程曝光', value: c.trip_view },
      { name: '预订点击', value: c.booking_click },
      { name: '预订成功', value: c.booking_success },
    ]
    funnelChart.setOption({
      tooltip: { trigger: 'item' },
      grid: { left: 90, right: 40, top: 20, bottom: 30 },
      xAxis: { type: 'value', minInterval: 1 },
      yAxis: { type: 'category', data: items.map((i) => i.name) },
      series: [
        {
          type: 'bar',
          data: items.map((i) => i.value),
          label: { show: true, position: 'right' },
          itemStyle: {
            color: (p: any) => ['#165dff', '#f7ba1e', '#00b42a'][p.dataIndex] || '#165dff',
          },
        },
      ],
    })
  }
}

const onResize = () => {
  dailyChart?.resize()
  funnelChart?.resize()
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  dailyChart?.dispose()
  funnelChart?.dispose()
  dailyChart = null
  funnelChart = null
})
</script>

<style scoped>
.dashboard-page { max-width: 1000px; margin: 0 auto; padding: 8px 16px 32px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.page-header h1 { font-size: 24px; margin: 0; }
.section-card { margin-bottom: 16px; }
.quota-row { display: flex; align-items: center; gap: 16px; }
.quota-remaining { color: var(--ink-soft); font-size: 13px; white-space: nowrap; }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.metric-card { border-radius: 10px; }
.metric-label { font-size: 13px; color: var(--ink-soft); margin-bottom: 6px; }
.metric-value { font-size: 24px; font-weight: 700; color: var(--ink); }
.metric-sub { font-size: 12px; color: var(--ink-soft); margin-top: 4px; }
.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart-card { border-radius: 10px; }
.chart { height: 280px; }
.funnel-note { font-size: 13px; color: var(--ink-soft); padding-top: 8px; border-top: 1px dashed var(--line); }
@media (max-width: 760px) {
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
  .chart-grid { grid-template-columns: 1fr; }
}
</style>
