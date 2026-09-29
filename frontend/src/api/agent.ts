/**
 * Agent 对话 API
 */
import { get, post, del } from './index'

export interface AgentMessageRequest {
  message: string
  context?: Record<string, any>
}

export interface AgentMessageResponse {
  message: string
  intent?: string
  destination?: string
  start_date?: string | null
  end_date?: string | null
  suggested_actions: string[]
  /** 对话内"保存到我的行程"成功时返回的 trip id（前端回填会话绑定） */
  saved_trip_id?: string | null
  itinerary?: {
    content: string
    days?: Array<{ day: number; title: string; text: string }>
    spots_used: string[]
  }
  hotels?: Array<{
    name?: string
    starRating?: number
    price?: string
    bookingUrl?: string
  }>
  review_note?: string
  follow_up?: string
  weather_info?: {
    city: string
    forecasts: Array<{
      date: string
      weekday: string
      weather: string
      icon: string
      temp_high: number
      temp_low: number
    }>
    tips: string
  }
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: Record<string, any>
}

export const agentApi = {
  /**
   * 发送消息给 Agent
   */
  chat: (data: AgentMessageRequest) => {
    return post<AgentMessageResponse>('/api/v1/agent/chat', data)
  },

  /**
   * 流式发送消息给 Agent（SSE）：返回事件生成器
   * 事件: status / token / done / error
   * signal: 传入 AbortSignal 可中断生成（"停止"按钮）
   */
  chatStream: async function* (
    data: AgentMessageRequest,
    signal?: AbortSignal
  ): AsyncGenerator<AgentStreamEvent, void, unknown> {
    const token = localStorage.getItem('token') || ''
    const res = await fetch('/api/v1/agent/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
      ...(signal ? { signal } : {}),
    })
    if (!res.ok || !res.body) {
      throw new Error(`流式请求失败: HTTP ${res.status}`)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''
    // 处理 SSE：按双换行切分事件块，取 data: 行
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const block = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        const dataLine = block.split('\n').find((l) => l.startsWith('data:'))
        if (dataLine) {
          try {
            const ev = JSON.parse(dataLine.slice(5).trim()) as AgentStreamEvent
            yield ev
          } catch {
            // 忽略无法解析的行
          }
        }
      }
    }
  },

  /**
   * 获取对话历史
   */
  getHistory: (params?: { limit?: number; offset?: number }) => {
    return get<{
      messages: ChatMessage[]
      total: number
      has_more: boolean
    }>('/api/v1/agent/history', { params })
  },

  /**
   * 清除对话历史
   */
  clearHistory: () => {
    return del('/api/v1/agent/history')
  },
}

/** 流式对话事件类型 */
export type AgentStreamEvent =
  | { type: 'status'; payload: { step: string; label: string } }
  | { type: 'token'; payload: { text: string } }
  | {
      type: 'done'
      payload: Omit<AgentMessageResponse, 'message'> & { message: string }
    }
  | { type: 'error'; payload: { message: string } }

