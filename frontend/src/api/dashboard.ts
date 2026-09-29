/**
 * 商业仪表盘 API
 */
import { get } from './index'

export interface GenerationDay {
  date: string
  count: number
  cost: number
  tokens: number
}

export interface GenerationStats {
  count: number
  first_token_p50: number | null
  first_token_p95: number | null
  total_p50: number | null
  total_p95: number | null
  prompt_tokens: number
  completion_tokens: number
  total_cost: number
  avg_cost: number
  per_day: GenerationDay[]
}

export interface CpsFunnel {
  trip_view: number
  booking_click: number
  booking_success: number
  click_rate: number | null
  conversion: number | null
}

export interface QuotaUsage {
  user_id: string
  date: string
  plan: string
  used: number
  limit: number
  remaining: number
}

export interface DashboardSummary {
  days: number
  generation: GenerationStats
  cps: CpsFunnel
  quota: QuotaUsage
}

export const dashboardApi = {
  summary: (days = 7) =>
    get<DashboardSummary>('/api/v1/dashboard/summary', { params: { days } }),
}
