/**
 * 机票 CPS（方案A）API：返回预订落地页深链
 */
import { get } from './index'

export interface FlightOption {
  from: string
  to: string
  date: string
  booking_url: string
}

export interface FlightPlan {
  success: boolean
  from: string
  to: string
  departure: FlightOption | null
  return: FlightOption | null
}

export const flightsApi = {
  search: (params: { to: string; date: string; from?: string; return_date?: string }) =>
    get<FlightPlan>('/api/v1/flights', { params }),
}