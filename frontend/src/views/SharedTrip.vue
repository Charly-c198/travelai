<template>
  <div class="shared-trip-page">
    <a-spin :loading="loading">
      <template v-if="trip">
        <div class="head">
          <div class="badge">公开分享</div>
          <h1>{{ trip.title }}</h1>
          <div class="meta">
            <span><icon-location /> {{ trip.destination }}</span>
            <span v-if="trip.start_date">{{ trip.start_date }} ~ {{ trip.end_date }}</span>
            <span v-if="trip.budget"><icon-tag /> ¥{{ trip.budget.toLocaleString() }}</span>
          </div>
        </div>

        <template v-if="trip.generated_plan?.days?.length">
          <div class="timeline">
            <div v-for="d in trip.generated_plan.days" :key="d.day" class="timeline-day">
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
          v-html="renderMarkdown(trip.generated_plan?.content || '暂无行程内容')"
        ></div>
      </template>

      <a-result v-else-if="!loading" status="404" title="分享不存在或已失效">
        <template #subtitle><span>该分享链接可能已被删除</span></template>
      </a-result>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import { shareApi } from '@/api/share'
import type { Trip } from '@/types'

const route = useRoute()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const renderMarkdown = (c: string) => md.render(c || '')

const loading = ref(true)
const trip = ref<Trip | null>(null)

onMounted(async () => {
  const token = String(route.params.token || '')
  try {
    trip.value = await shareApi.getShared(token)
  } catch {
    trip.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.shared-trip-page { max-width: 760px; margin: 0 auto; padding: 24px 20px 48px; }
.head { margin-bottom: 24px; }
.badge { display: inline-block; font-size: 12px; color: #fff; background: #165dff; border-radius: 4px; padding: 2px 8px; margin-bottom: 10px; }
h1 { font-size: 26px; margin: 0 0 8px; }
.meta { display: flex; flex-wrap: wrap; gap: 16px; color: #86909c; font-size: 14px; }
.timeline { display: flex; flex-direction: column; gap: 18px; }
.timeline-day { display: flex; gap: 12px; }
.timeline-marker { position: relative; display: flex; flex-direction: column; align-items: center; flex-shrink: 0; }
.day-num { width: 26px; height: 26px; border-radius: 50%; background: #165dff; color: #fff; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: center; z-index: 1; }
.timeline-marker::after { content: ''; position: absolute; top: 34px; bottom: -20px; width: 2px; background: #e5e6eb; }
.timeline-day:last-child .timeline-marker::after { display: none; }
.timeline-body { flex: 1; min-width: 0; }
.timeline-title { font-size: 15px; font-weight: 600; color: #1d2129; margin-bottom: 6px; }
.timeline-body :deep(.markdown-body) { background: #f7f8fa; border-radius: 8px; padding: 10px 14px; }
</style>