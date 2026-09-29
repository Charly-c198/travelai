/**
 * 行程 CRUD API
 */
import { get, post, put, del } from './index'
import type { Trip, TripList, Spot } from '@/types'

export interface TripCreateData {
  destination: string
  start_date: string
  end_date: string
  budget?: number
  travelers?: number
  status?: string
  title?: string
  requirements?: Record<string, unknown>
  generated_plan?: Trip['generated_plan']
}

export interface TripUpdateData {
  title?: string
  destination?: string
  start_date?: string
  end_date?: string
  budget?: number
  travelers?: number
  status?: string
  requirements?: Record<string, unknown>
  generated_plan?: Trip['generated_plan']
}

export const tripApi = {
  create: (data: TripCreateData) => post<Trip>('/api/v1/trips', data),
  list: (params?: { page?: number; page_size?: number }) =>
    get<TripList>('/api/v1/trips', { params }),
  get: (id: string) => get<Trip>(`/api/v1/trips/${id}`),
  update: (id: string, data: TripUpdateData) =>
    put<Trip>(`/api/v1/trips/${id}`, data),
  remove: (id: string) => del(`/api/v1/trips/${id}`),
  // 为暂无 AI 计划的行程一键生成计划（同步，约 1 分钟）
  generate: (id: string) => post<Trip>(`/api/v1/trips/${id}/generate`),
}

export const spotApi = {
  list: (params?: { city?: string; category?: string; keyword?: string; limit?: number }) =>
    get<Spot[]>('/api/v1/spots', { params }),
}