<template>
  <div class="chat-page">
    <!-- 左侧历史会话侧边栏 -->
    <aside class="history-sidebar">
      <div class="sidebar-head">
        <a-button type="primary" long @click="createNewSession">
          <template #icon><icon-plus /></template>
          新建行程
        </a-button>
      </div>
      <div class="sidebar-list" ref="sidebarListRef">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === activeSessionId }"
          @click="selectSession(s)"
        >
          <div class="session-title">{{ sessionTitle(s) }}</div>
          <div class="session-sub">{{ sessionSub(s) }}</div>
          <a-popconfirm content="删除该会话？" position="left" @ok="deleteSession(s)" @click.stop>
            <button class="session-del" aria-label="删除该会话">
              <icon-delete />
            </button>
          </a-popconfirm>
        </div>
      </div>
    </aside>

    <!-- 主聊天区 -->
    <main class="chat-main">
      <div class="ai-chat-page">
    <!-- 页面头部（编辑社论式） -->
    <div class="page-header">
      <div class="eyebrow">Travel Atelier</div>
      <h1 class="font-display">智能旅行规划</h1>
      <p class="subtitle">告诉我你的旅行想法，AI 帮你规划完美行程</p>
    </div>

    <!-- 目的地灵感画廊（大图卡，点卡发起规划） -->
    <div class="inspiration" v-if="messages.length === 0">
      <div class="inspiration-head">
        <span class="eyebrow">Inspiration</span>
        <span class="inspiration-caption">点一张图，开始你的旅程</span>
      </div>
      <div class="inspiration-track">
        <button
          v-for="it in gallery"
          :key="it.key"
          class="inspiration-card group-zoom photo-shade"
          :style="{ backgroundImage: `url(${it.file})` }"
          @click="useInspiration(it)"
        >
          <span class="inspiration-tag">{{ it.tag }}</span>
          <span class="inspiration-name font-display">{{ it.name }}</span>
        </button>
      </div>
    </div>

    <!-- 快速模板 -->
    <div class="quick-templates" v-if="messages.length === 0">
      <h3 class="templates-title">试试这些</h3>
      <div class="template-list">
        <a-card
          v-for="template in templates"
          :key="template.title"
          :hoverable="true"
          class="template-card"
          @click="useTemplate(template)"
        >
          <template #cover>
            <div class="template-icon">{{ template.icon }}</div>
          </template>
          <div class="template-content">
            <div class="template-title">{{ template.title }}</div>
            <div class="template-desc">{{ template.desc }}</div>
          </div>
        </a-card>
      </div>
    </div>

    <!-- 聊天消息区域 -->
    <div class="chat-container" ref="chatContainer">
      <!-- :key 绑定活动会话：切换会话时重播 0.15s 淡入 -->
      <div class="message-list" :key="activeSessionId || 'no-session'">
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['message', msg.role]"
        >
          <div class="message-avatar">
            <avatar-user v-if="msg.role === 'user'" :size="36" />
            <avatar-ai v-else :size="36" />
          </div>
          <div class="message-content">
            <div class="message-header">
              <span class="sender-name">{{ msg.role === 'user' ? '你' : 'TravelAI' }}</span>
              <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
            </div>
            <div class="message-body">
              <!-- 用户消息 -->
              <div v-if="msg.role === 'user'" class="user-message">
                {{ msg.content }}
              </div>

              <!-- AI 消息 -->
              <div v-else class="ai-message">
                <!-- 流式输出中：先显示逐字文本，完成后才渲染结构化卡片 -->
                <template v-if="msg.streaming">
                  <div class="streaming-text">{{ msg.content }}<span class="streaming-caret">▍</span></div>
                </template>
                <template v-else>
                <!-- 天气信息 -->
                <div v-if="msg.weather_info" class="weather-card">
                  <div class="weather-header">
                    <icon-location />
                    <span>{{ msg.weather_info.city }} 天气预报</span>
                  </div>
                  <div class="weather-days">
                    <div
                      v-for="day in msg.weather_info.forecasts.slice(0, 5)"
                      :key="day.date"
                      class="weather-day"
                    >
                      <div class="day-name">{{ day.weekday }}</div>
                      <div class="day-icon">{{ day.icon }}</div>
                      <div class="day-weather">{{ day.weather }}</div>
                      <div class="day-temp">{{ day.temp_low }}° ~ {{ day.temp_high }}°</div>
                    </div>
                  </div>
                  <div class="weather-tips" v-if="msg.weather_info.tips">
                    💡 {{ msg.weather_info.tips }}
                  </div>
                </div>

                <!-- 行程内容 -->
                <div v-if="msg.itinerary" class="itinerary-preview">
                  <place-gallery :places="galleryPlaces(msg)" />
                  <div class="itinerary-header">
                    <icon-compass />
                    <span>为你生成了旅行规划</span>
                  </div>
                  <div class="itinerary-actions">
                    <a-button type="primary" @click="viewItinerary(msg)">
                      <template #icon><icon-save /></template>
                      查看完整行程
                    </a-button>
                    <a-button status="success" @click="saveItinerary(msg)">
                      <template #icon><icon-bookmark /></template>
                      保存为行程
                    </a-button>
                    <a-button @click="modifyItinerary">
                      <template #icon><icon-edit /></template>
                      修改行程
                    </a-button>
                  </div>
                </div>

                <!-- 可订酒店 -->
                <div v-if="msg.hotels?.length" :id="'hotels-' + msg.id" class="hotels-preview">
                  <div class="hotels-title">🛏️ 周边可订酒店</div>
                  <div v-for="h in msg.hotels" :key="h.name" class="hotel-row">
                    <span class="hotel-name-txt">{{ h.name }}<template v-if="h.starRating"> ★{{ h.starRating }}</template></span>
                    <span class="hotel-price-txt">{{ h.price || '' }}</span>
                    <a-button
                      v-if="h.bookingUrl"
                      size="mini"
                      tag="a"
                      :href="h.bookingUrl"
                      target="_blank"
                      type="primary"
                    >去预订</a-button>
                  </div>
                </div>

                <!-- 主动追问 -->
                <div v-if="msg.follow_up" class="follow-up">
                  <span>💬 {{ msg.follow_up }}</span>
                  <a-button v-if="msg.hotels?.length" size="small" type="text" status="success" @click="scrollToHotels(msg.id)">
                    查看可订酒店
                  </a-button>
                </div>

                <!-- 行程自查提示 -->
                <div v-if="msg.review_note" class="review-note">📋 {{ msg.review_note }}</div>

                <!-- 纯文本回复 -->
                <div class="markdown-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
                </template>
              </div>
            </div>

            <!-- 建议操作 -->
            <div v-if="msg.suggested_actions?.length && msg.role === 'assistant'" class="suggested-actions">
              <span class="action-label">你可以：</span>
              <a-tag
                v-for="action in msg.suggested_actions"
                :key="action"
                class="action-tag"
                @click="handleAction(action)"
              >
                {{ action }}
              </a-tag>
            </div>
          </div>
        </div>

        <!-- 加载状态 -->
        <div v-if="loading" class="message assistant loading">
          <div class="message-avatar">
            <avatar-ai :size="36" />
          </div>
          <div class="message-content">
            <a-typography-paragraph class="typing-indicator">
              <a-spin :size="14" /> {{ statusLabel || 'TravelAI 正在规划中...' }}
            </a-typography-paragraph>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <a-textarea
        v-model="inputMessage"
        placeholder="描述你的旅行计划... 例如：我想去日本东京，4月份，5天3人，预算2万"
        :auto-size="{ minRows: 2, maxRows: 5 }"
        @keydown="onTextareaKeydown"
      />
      <div class="input-actions">
        <a-button @click="clearHistory" :disabled="loading">
          <template #icon><icon-delete /></template>
          清空记录
        </a-button>
        <a-button v-if="loading" status="danger" @click="stopGeneration">
          <template #icon><icon-close-circle /></template>
          停止生成
        </a-button>
        <a-button type="primary" @click="handleSend" :disabled="!inputMessage.trim()">
          <template #icon><icon-send /></template>
          发送
        </a-button>
      </div>
    </div>

    <!-- 完整行程弹窗 -->
    <a-drawer
      :visible="itineraryVisible"
      title="🗺️ 完整行程规划"
      :width="680"
      :footer="false"
      @cancel="itineraryVisible = false"
    >
      <!-- 结构化时间线：行程已对象化为 days 时按天展示 -->
      <template v-if="activeItinerary?.days?.length">
        <div class="itinerary-timeline">
          <div
            v-for="d in activeItinerary.days"
            :key="d.day"
            class="timeline-day"
          >
            <div class="timeline-marker">
              <div class="timeline-day-num">{{ d.day }}</div>
            </div>
            <div class="timeline-body">
              <div class="timeline-day-title">
                第 {{ d.day }} 天 · {{ d.title }}
              </div>
              <div
                class="markdown-body timeline-day-text"
                v-html="renderMarkdown(d.text)"
              ></div>
              <place-gallery v-if="dayPlaces(d).length" :places="dayPlaces(d)" class="day-gallery" />
            </div>
          </div>
        </div>
      </template>
      <!-- 无结构化 days 时回退为纯 markdown -->
      <div
        v-else
        class="markdown-body"
        v-html="renderMarkdown(activeItinerary?.content || '')"
      ></div>
    </a-drawer>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import MarkdownIt from 'markdown-it'
import { agentApi } from '../api/agent'
import { tripApi } from '@/api/trips'
import { useTripStore } from '@/stores/trip'
import { useChatStore, type ChatSession, type SessionMessage } from '@/stores/chat'
import type { Trip } from '@/types'
import { GALLERY, type Curation } from '@/data/imagery'
import AvatarAI from '@/components/AvatarAI.vue'
import AvatarUser from '@/components/AvatarUser.vue'
import PlaceGallery from '@/components/PlaceGallery.vue'
import type { PlaceItem } from '@/data/usePlaceImages'
import { buildPlaceGallery } from '@/data/placeGallery'

const gallery = GALLERY

const router = useRouter()

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const store = useTripStore()
// —— 对话会话状态放进 Pinia store：跨路由切换存活，避免切页丢流式内容 ——
const chat = useChatStore()
const sessions = computed(() => chat.sessions)
const activeSessionId = computed({
  get: () => chat.activeSessionId,
  set: (v) => {
    chat.activeSessionId = v
  },
})
const messages = computed(() => chat.messages)
const abortController = computed({
  get: () => chat.abortController,
  set: (v) => {
    chat.abortController = v
  },
})
const sidebarListRef = ref<HTMLElement>()

const inputMessage = ref('')
const loading = ref(false)
const statusLabel = ref('')
const chatContainer = ref<HTMLElement>()

// 完整行程弹窗状态
const itineraryVisible = ref(false)
const activeItinerary = ref<{
  content?: string
  spots_used?: string[]
  spots?: Array<{ name?: string; name_en?: string; city?: string }>
  days?: Array<{ day: number; title: string; text: string }>
} | null>(null)
const activeItineraryDest = ref('')

// 快速模板
const templates = [
  { icon: '🌸', title: '日本赏樱', desc: '4月初去日本东京，5天，2人，赏樱之旅' },
  { icon: '🏖️', title: '海岛度假', desc: '想去三亚，3天，亲子游，预算1万' },
  { icon: '🏔️', title: '云南自由行', desc: '丽江大理，7天，2人，休闲游' },
  { icon: '🇹🇭', title: '泰国泼水节', desc: '4月中旬去曼谷，4天，预算5000' },
]

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// —— 侧边栏会话 ——
const activeSession = computed(
  () => sessions.value.find((s) => s.id === activeSessionId.value) || null
)

// 空白的"新建行程"会话
const makeBlankSession = (): ChatSession => ({
  id: `new-${Date.now()}`,
  title: '新行程',
  destination: '',
  days: 0,
  created_at: new Date().toISOString(),
  messages: [],
})

// 由现有行程构建会话：主内容区渲染其完整规划
const tripToSession = (t: Trip): ChatSession => {
  const plan = t.generated_plan || {}
  const days = plan.days?.length || 0
  const messages: SessionMessage[] = []
  if (plan.content) {
    messages.push(
      {
        id: `u-${t.id}-req`,
        role: 'user',
        content: String((t.requirements as any)?.intent || '') || `帮我规划${t.destination}的行程`,
        timestamp: t.created_at || '',
      },
      {
        id: `a-${t.id}-plan`,
        role: 'assistant',
        content: plan.content,
        timestamp: t.created_at || '',
        streaming: false,
        itinerary: plan,
        destination: t.destination,
        start_date: t.start_date || null,
        end_date: t.end_date || null,
        follow_up: '要不要顺便看看周边可订酒店，或帮你调整行程？',
      }
    )
  }
  return {
    id: `trip-${t.id}`,
    tripId: t.id,
    title: t.title || `${t.destination}之旅`,
    destination: t.destination,
    days,
    created_at: t.created_at || '',
    budget: t.budget,
    messages,
  }
}

// 切换会话：主聊天区同步渲染该会话消息
const selectSession = (s: ChatSession) => {
  if (activeSessionId.value === s.id && messages.value === s.messages) return
  activeSessionId.value = s.id
  // messages 由 store 按 activeSessionId 自动派生，无需手动同步
  nextTick(() => scrollToBottom())
}

// 新建行程：顶部插入空白会话并选中，侧边栏自动滚回列表顶部
const createNewSession = () => {
  const s = makeBlankSession()
  sessions.value.unshift(s)
  selectSession(s)
  nextTick(() => {
    if (sidebarListRef.value) sidebarListRef.value.scrollTop = 0
  })
}

// 删除会话：行程会话同步删除后端行程；删除当前会话后切换到相邻会话，删光则新建空白会话
const deleteSession = async (s: ChatSession) => {
  const idx = sessions.value.findIndex((x) => x.id === s.id)
  if (idx === -1) return
  if (s.tripId) {
    try {
      await store.removeTrip(s.tripId)
    } catch {
      Message.error('删除行程失败')
      return
    }
  }
  sessions.value.splice(idx, 1)
  if (activeSessionId.value === s.id) {
    const next = sessions.value[idx] || sessions.value[idx - 1] || null
    if (next) selectSession(next)
    else createNewSession()
  }
  Message.success('已删除')
}

// 列表主标题：目的地 + 天数（新会话显示占位名）
const sessionTitle = (s: ChatSession): string => {
  if (!s.destination) return '新行程'
  return s.days > 0 ? `${s.destination} · ${s.days} 天` : s.destination
}

// 列表副标题：创建时间 + 预算摘要
const sessionSub = (s: ChatSession): string => {
  const parts: string[] = []
  if (s.created_at) {
    const d = new Date(s.created_at)
    if (!isNaN(d.getTime())) {
      const p = (n: number) => String(n).padStart(2, '0')
      parts.push(`${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`)
    }
  }
  if (s.budget) parts.push(`预算 ¥${s.budget.toLocaleString()}`)
  return parts.join(' · ')
}

const renderMarkdown = (content: string) => {
  // 用 markdown-it 渲染，去掉转义的前后空白行
  return md.render(content || '')
}

const useTemplate = (template: typeof templates[0]) => {
  inputMessage.value = template.desc
  handleSend()
}

// 灵感画廊：点卡直接把"去XX玩"填进对话框并发送
const useInspiration = (it: Curation) => {
  inputMessage.value = it.from || `去${it.name}旅行`
  handleSend()
}

// 对话框按键：Enter 发送、Shift+Enter 换行；中文输入法选词回车不触发发送
const onTextareaKeydown = (e: KeyboardEvent) => {
  if (e.isComposing || e.keyCode === 229) return
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

const handleSend = async () => {
  const content = inputMessage.value.trim()
  if (!content || loading.value) return

  // 兜底：无活动会话时先新建一个
  if (!activeSession.value) createNewSession()
  // 锁定目标会话的消息数组：即使流式过程中用户切换会话，回复仍写回原会话
  const target = messages.value

  // 用户消息
  target.push({
    id: `u-${Date.now()}`,
    role: 'user',
    content,
    timestamp: new Date().toISOString()
  })

  // AI 占位消息（流式填充）
  const aiId = `a-${Date.now()}`
  target.push({
    id: aiId,
    role: 'assistant',
    content: '',
    timestamp: new Date().toISOString(),
    streaming: true
  })

  inputMessage.value = ''
  loading.value = true
  statusLabel.value = '正在连接…'
  abortController.value = new AbortController()
  scrollToBottom()

  try {
    // 带上会话绑定的 trip_id：让"保存到我的行程"在已有行程上更新，否则新建
    const ctx = { trip_id: activeSession.value?.tripId || undefined }
    for await (const ev of agentApi.chatStream({ message: content, context: ctx }, abortController.value.signal)) {
      const aiMsg = target.find((m) => m.id === aiId)
      if (!aiMsg) break
      if (ev.type === 'token') {
        aiMsg.content += ev.payload.text
        scrollToBottom()
      } else if (ev.type === 'status') {
        statusLabel.value = ev.payload.label
        // 天数不符自动重生成：先清空已输出的内容，让后续 token 从新版本重填
        if (ev.payload.step === 'regenerate') {
          aiMsg.content = ''
          scrollToBottom()
        }
      } else if (ev.type === 'done') {
        aiMsg.streaming = false
        aiMsg.weather_info = ev.payload.weather_info
        aiMsg.itinerary = ev.payload.itinerary
        aiMsg.suggested_actions = ev.payload.suggested_actions
        aiMsg.destination = ev.payload.destination
        aiMsg.start_date = ev.payload.start_date
        aiMsg.end_date = ev.payload.end_date
        aiMsg.hotels = (ev.payload as any).hotels || []
        aiMsg.review_note = (ev.payload as any).review_note || ''
        aiMsg.follow_up = (ev.payload as any).follow_up || ''
        if (!aiMsg.content) aiMsg.content = ev.payload.message || ''
        // 对话内"保存到我的行程"成功：回填会话绑定，便于后续"保存"走更新
        const intent = ev.payload.intent
        const savedId = (ev.payload as any).saved_trip_id
        if (intent === 'save_trip' && savedId && activeSession.value) {
          // 回填会话绑定：后续再"保存到我的行程"会走更新而非重复新建
          activeSession.value.tripId = savedId
          if (ev.payload.destination) {
            activeSession.value.destination = ev.payload.destination
            activeSession.value.title = `${ev.payload.destination}之旅`
          }
          Message.success('已保存到「我的行程」')
        }
        statusLabel.value = ''
        scrollToBottom()
      } else if (ev.type === 'error') {
        aiMsg.streaming = false
        aiMsg.content = aiMsg.content || ev.payload.message || '出错了'
        statusLabel.value = ''
        scrollToBottom()
      }
    }
  } catch (error) {
    const aiMsg = target.find((m) => m.id === aiId)
    const isAbort = error instanceof DOMException && error.name === 'AbortError'
    if (aiMsg) {
      aiMsg.streaming = false
      if (!isAbort) aiMsg.content = aiMsg.content || '连接中断，请重试'
    }
    if (!isAbort) {
      Message.error(error instanceof Error ? error.message : '对话失败，请重试')
    }
    statusLabel.value = ''
  } finally {
    loading.value = false
    abortController.value = null
    scrollToBottom()
  }
}

const stopGeneration = () => {
  if (abortController.value) {
    abortController.value.abort()
    statusLabel.value = ''
  }
}

// 主动追问：滚动到该消息的周边可订酒店
const scrollToHotels = (msgId: string) => {
  const el = document.getElementById('hotels-' + msgId)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

const handleAction = (action: string) => {
  if (action.includes('修改')) {
    inputMessage.value = '帮我调整一下行程，我想...'
  } else if (action.includes('机票')) {
    // 跳转到机票预订
  } else if (action.includes('导出')) {
    Message.info('正在生成 PDF...')
  }
}

// 行程卡片"地点图鉴"：统一走 buildPlaceGallery（城市可验证属于目的地才有独立照片）
const galleryPlaces = (msg: any): PlaceItem[] =>
  buildPlaceGallery(msg?.destination, msg?.itinerary?.spots || [], 5)

const viewItinerary = (msg: any) => {
  activeItinerary.value = msg?.itinerary ?? null
  activeItineraryDest.value = msg?.destination || ''
  itineraryVisible.value = true
}

// 每天的地点照片：该天正文里出现的景点（最多 4 张），同样受城市校验约束
const dayPlaces = (day: any): PlaceItem[] => {
  const text = day?.text || ''
  const matched = (activeItinerary.value?.spots || []).filter((s) => text.includes(s?.name || ''))
  return buildPlaceGallery(activeItineraryDest.value, matched, 4)
}

const modifyItinerary = () => {
  inputMessage.value = '帮我调整一下行程，我想增加/减少景点，或者改变顺序'
}

// 把 AI 生成的行程一键存为「我的行程」
const saveItinerary = async (msg: any) => {
  const destination = msg?.destination || ''
  if (!destination) {
    Message.warning('暂未识别目的地，无法保存为行程')
    return
  }
  const daysCount = msg?.itinerary?.days?.length || 0
  let start = msg?.start_date
  let end = msg?.end_date
  // AI 未解析出具体日期时，退回"明天起 + 天数"作为占位（用户可在详情/后续编辑）
  if (!start || !end) {
    const s = new Date()
    s.setDate(s.getDate() + 1)
    const e = new Date(s)
    e.setDate(e.getDate() + Math.max(daysCount || 3, 1) - 1)
    const iso = (d: Date) =>
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    start = iso(s)
    end = iso(e)
  }
  const plan = msg?.itinerary || { content: msg?.content || '', days: undefined }
  try {
    // 该会话已关联行程：直接更新，避免重复创建
    if (activeSession.value?.tripId) {
      await tripApi.update(activeSession.value.tripId, {
        destination,
        start_date: start,
        end_date: end,
        title: `${destination}之旅`,
        generated_plan: plan,
      })
    } else {
      const created = await tripApi.create({
        destination,
        start_date: start,
        end_date: end,
        title: `${destination}之旅`,
        generated_plan: plan,
      })
      // 回填会话，让侧边栏条目同步目的地/天数/关联行程
      if (activeSession.value) {
        const s = activeSession.value
        s.tripId = created.id
        s.destination = destination
        s.days = daysCount
        s.title = `${destination}之旅`
      }
    }
    Message.success('已保存到「我的行程」')
    router.push('/my-trips')
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '保存失败，请重试')
  }
}

const clearHistory = async () => {
  try {
    await agentApi.clearHistory()
    // 清空当前会话消息（其他会话不受影响）；messages 由 store 派生，改会话数组即生效
    if (activeSession.value) activeSession.value.messages = []
    Message.success('已清空当前会话')
  } catch (error) {
    Message.error('清空失败')
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

onMounted(async () => {
  // 已在本次会话内挂载过（用户切页后重挂）：直接沿用 store 里的会话与流式内容，不再重建
  if (chat.hydrated) return
  chat.hydrated = true

  // 侧边栏历史会话：现有行程（后端已按创建时间倒序返回，最新置顶）
  try {
    await store.fetchTrips()
    chat.sessions = store.trips.map(tripToSession)
  } catch {
    /* 加载失败则侧边栏仅剩"新建"会话 */
  }
  // 顶部"新建"会话：载入后端对话历史，延续原首页单会话行为
  const fresh = makeBlankSession()
  sessions.value.unshift(fresh)
  try {
    const res = await agentApi.getHistory()
    fresh.messages = res.messages as SessionMessage[]
  } catch {
    /* 无历史，保持空白 */
  }
  activeSessionId.value = fresh.id
  // messages 由 store 按 activeSessionId 自动派生
  scrollToBottom()
})
</script>

<style scoped>
/* ——— 整体布局：左侧历史会话侧边栏 + 主聊天区 —— */
.chat-page {
  display: flex;
  align-items: stretch;
  height: calc(100vh - 60px); /* 与导航栏底部对齐，铺满剩余视口 */
  margin: 0 -28px -28px;      /* 抵消 main-content 内边距，让侧边栏贴齐视口边缘 */
}

.history-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--line);
  overflow: hidden;
}

.sidebar-head {
  padding: 20px 16px 14px;
  border-bottom: 1px solid var(--line);
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px 20px;
}

.session-item {
  position: relative;
  padding: 10px 12px 10px 16px;
  border-radius: 8px;
  cursor: pointer;
  background: transparent;
  transition: background-color 0.2s ease;
}
.session-item:hover {
  background: rgba(128, 138, 132, 0.12);
}
.session-item.active {
  background: var(--brand-soft);
}
.session-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 999px;
  background: var(--brand);
}
.session-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.2s ease;
}
.session-item.active .session-title {
  color: var(--ink);
}
.session-sub {
  margin-top: 3px;
  font-size: 12px;
  color: var(--ink-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-del {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-faint);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s ease, color 0.2s ease, background-color 0.2s ease;
}
.session-item:hover .session-del {
  opacity: 1;
}
.session-del:hover {
  color: #f53f3f;
  background: rgba(245, 63, 63, 0.12);
}

.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  justify-content: center;
}

.ai-chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  max-width: 900px;
  padding: 0 16px;
}

.page-header {
  text-align: center;
  padding: 40px 0 8px;
}

.page-header h1 {
  font-size: 40px;
  margin: 6px 0 10px;
  font-weight: 300;
  letter-spacing: -0.01em;
  color: var(--ink);
}

.subtitle {
  color: var(--ink-soft);
  font-size: 15px;
  font-weight: 300;
}

/* ——— 灵感画廊 —— */
.inspiration { margin: 6px 0 4px; }
.inspiration-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; }
.inspiration-caption { font-size: 12px; color: var(--ink-faint); }
.inspiration-track {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  padding-bottom: 8px;
  scrollbar-width: thin;
}
.inspiration-card {
  position: relative;
  flex: 0 0 auto;
  width: 210px;
  height: 150px;
  border: none;
  border-radius: 14px;
  cursor: pointer;
  background-size: cover;
  background-position: center;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: flex-start;
  padding: 14px;
  text-align: left;
  color: #fff;
}
.inspiration-card::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(11,15,14,0) 40%, rgba(11,15,14,0.6) 100%);
}
.inspiration-card > span { position: relative; z-index: 1; }
.inspiration-tag {
  align-self: flex-end;
  font-size: 11px; letter-spacing: 0.08em;
  background: rgba(255,255,255,0.16); backdrop-filter: blur(6px);
  padding: 2px 8px; border-radius: 999px;
  color: #fff;
}
.inspiration-name { font-size: 18px; font-weight: 400; margin-top: 6px; }
.inspiration-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-soft); transition: transform .3s cubic-bezier(.2,.7,.2,1); }

.quick-templates {
  margin-bottom: 24px;
}

.quick-templates h3,
.templates-title {
  font-size: 12px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--brand);
  margin-bottom: 14px;
  font-weight: 500;
}

.template-list {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.template-card {
  cursor: pointer;
  transition: transform 0.3s cubic-bezier(0.2, 0.7, 0.2, 1), box-shadow 0.3s;
  border: 1px solid var(--line);
  background: var(--surface);
  overflow: hidden;
}
.template-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-soft);
}

.template-icon {
  font-size: 44px;
  text-align: center;
  padding: 26px 0;
  background:
    linear-gradient(180deg, rgba(11,107,92,0.08), rgba(11,107,92,0) 70%),
    var(--bg-alt);
}
.template-title { font-weight: 500; color: var(--ink); font-family: var(--font-display); }
.template-desc { font-size: 12px; color: var(--ink-faint); }

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  /* 切换会话淡入 */
  animation: session-fade-in 0.15s ease-out;
}
@keyframes session-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 滚动条：侧边栏与聊天区统一 */
.chat-container::-webkit-scrollbar,
.history-sidebar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.chat-container::-webkit-scrollbar-thumb,
.history-sidebar::-webkit-scrollbar-thumb {
  background: var(--line-strong);
  border-radius: 999px;
}
.chat-container::-webkit-scrollbar-track,
.history-sidebar::-webkit-scrollbar-track {
  background: transparent;
}

.message {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.message-content {
  max-width: 75%;
}

.message.user .message-content {
  align-items: flex-end;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}

.message.user .message-header {
  flex-direction: row-reverse;
}

.sender-name {
  font-weight: 600;
}

.message-time {
  color: #86909c;
}

.user-message {
  background: var(--brand);
  color: #fff;
  padding: 12px 16px;
  border-radius: 16px 16px 4px 16px;
}

.ai-message {
  background: var(--surface);
  border: 1px solid var(--line);
  padding: 16px;
  border-radius: 16px 16px 16px 4px;
}

.weather-card {
  background: linear-gradient(135deg, #0b6b5c 0%, #0b3f38 100%);
  color: #fff;
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 16px;
}

.weather-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
}

.weather-days {
  display: flex;
  gap: 8px;
}

.weather-day {
  text-align: center;
  flex: 1;
}

.day-icon {
  font-size: 24px;
  margin: 4px 0;
}

.day-weather {
  font-size: 12px;
  opacity: 0.9;
}

.day-temp {
  font-size: 11px;
  opacity: 0.8;
}

.weather-tips {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  font-size: 13px;
}

.itinerary-preview {
  background: var(--bg);
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 16px;
  border: 1px solid var(--line);
}
.itinerary-preview :deep(.place-gallery) {
  margin-bottom: 4px;
}

.itinerary-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--brand);
  font-weight: 600;
  margin-bottom: 12px;
}

.itinerary-actions {
  display: flex;
  gap: 8px;
}

.suggested-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.action-label {
  font-size: 12px;
  color: #86909c;
}

.action-tag {
  cursor: pointer;
}

.input-area {
  padding: 16px 0;
  border-top: 1px solid var(--line);
  background: transparent;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
}

.loading .ai-message {
  display: flex;
  align-items: center;
  gap: 8px;
}

.typing-indicator {
  margin: 0;
  color: var(--ink-soft);
}

/* 结构化行程时间线 */
.itinerary-timeline {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.timeline-day {
  display: flex;
  gap: 14px;
}

.timeline-marker {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.timeline-day-num {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--brand);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.timeline-marker::after {
  content: '';
  position: absolute;
  top: 34px;
  bottom: -22px;
  width: 2px;
  background: var(--line);
}

.timeline-day:last-child .timeline-marker::after {
  display: none;
}

.timeline-body {
  flex: 1;
  min-width: 0;
}

.timeline-day-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 6px;
  font-family: var(--font-display);
}

.timeline-day-text {
  background: var(--bg);
  border-radius: 8px;
  padding: 10px 14px;
}
.timeline-body :deep(.day-gallery) {
  margin-top: 10px;
}

/* 主动追问 */
.follow-up { margin-top: 10px; display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--brand); background: var(--brand-soft); padding: 6px 10px; border-radius: 6px; }

/* 行程自查 */
.review-note { margin-top: 10px; padding: 8px 12px; background: #fffbe6; border-radius: 6px; border: 1px solid #ffe58f; font-size: 13px; color: #ad6800; }

/* 可订酒店预览 */
.hotels-preview { margin-top: 12px; padding: 10px 14px; background: var(--bg); border-radius: 8px; border: 1px solid var(--line); }
.hotels-title { font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 8px; }
.hotel-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 6px 0; border-bottom: 1px dashed var(--line); }
.hotel-row:last-child { border-bottom: none; }
.hotel-name-txt { font-size: 13px; color: var(--ink-soft); flex: 1; }
.hotel-price-txt { font-size: 12px; color: var(--ink-faint); flex-shrink: 0; }

/* 流式输出文本 */
.streaming-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink-soft);
}

.streaming-caret {
  display: inline-block;
  width: 2px;
  height: 14px;
  margin-left: 2px;
  background: var(--brand);
  vertical-align: text-bottom;
  animation: stream-caret 1s steps(1) infinite;
}

@keyframes stream-caret {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.markdown-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink-soft);
  word-break: break-word;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  margin: 16px 0 8px;
  color: var(--ink);
  font-weight: 500;
}

.markdown-body h1 { font-size: 20px; }
.markdown-body h2 { font-size: 18px; }
.markdown-body h3 { font-size: 16px; }

.markdown-body p {
  margin: 8px 0;
}

.markdown-body ul,
.markdown-body ol {
  margin: 8px 0;
  padding-left: 22px;
}

.markdown-body li {
  margin: 4px 0;
}

.markdown-body strong {
  color: var(--ink);
  font-weight: 500;
}

.markdown-body em {
  font-style: italic;
}

.markdown-body code {
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-alt);
  font-family: inherit;
  word-break: break-word;
}

.markdown-body blockquote {
  margin: 8px 0;
  padding: 4px 12px;
  border-left: 3px solid var(--brand);
  background: var(--bg);
  color: var(--ink-soft);
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}

.markdown-body table th,
.markdown-body table td {
  border: 1px solid var(--line);
  padding: 6px 12px;
}

.markdown-body hr {
  border: none;
  border-top: 1px solid var(--line);
  margin: 16px 0;
}
</style>



