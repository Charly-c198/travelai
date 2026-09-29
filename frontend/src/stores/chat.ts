// 对话会话状态（Pinia store）。
// 作用：把会话列表 / 当前会话 / 流式 AbortController 提到组件外，使其**跨路由存活**——
// 用户在 AI 流式输出时切到别的页面再切回来，Home.vue 会重挂，但 store 里的
// messages（含流式已经生成的部分）不会丢失，切回来能继续看到 AI 输出。
import { defineStore } from 'pinia'
import type { ChatMessage } from '@/api/agent'

export type SessionMessage = ChatMessage & {
  weather_info?: any
  itinerary?: any
  suggested_actions?: string[]
  streaming?: boolean
  destination?: string
  start_date?: string | null
  end_date?: string | null
  hotels?: Array<{ name?: string; starRating?: number; price?: string; bookingUrl?: string }>
  review_note?: string
  follow_up?: string
}

export interface ChatSession {
  id: string
  tripId?: string
  title: string
  destination: string
  days: number
  created_at: string
  budget?: number
  messages: SessionMessage[]
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: [] as ChatSession[],
    activeSessionId: null as string | null,
    // 流式 AbortController 放这里：跨组件实例也能让“停止生成”生效
    abortController: null as AbortController | null,
    // 是否已完成首屏加载（拉行程 + 历史）；重挂时不重复重建，保住流式内容
    hydrated: false,
  }),
  getters: {
    activeSession: (s): ChatSession | null =>
      s.sessions.find((x) => x.id === s.activeSessionId) || null,
    messages: (s): SessionMessage[] =>
      s.sessions.find((x) => x.id === s.activeSessionId)?.messages ?? [],
  },
})