/**
 * 行程 Pinia store：列表 / 加载 / 删除
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { tripApi } from '@/api/trips'
import type { Trip } from '@/types'

export const useTripStore = defineStore('trip', () => {
  const trips = ref<Trip[]>([])
  const total = ref(0)
  const loading = ref(false)

  async function fetchTrips(page = 1, pageSize = 20): Promise<TripList> {
    loading.value = true
    try {
      const res = await tripApi.list({ page, page_size: pageSize })
      trips.value = res.items
      total.value = res.total
      return res
    } finally {
      loading.value = false
    }
  }

  async function removeTrip(id: string) {
    await tripApi.remove(id)
    trips.value = trips.value.filter((t) => t.id !== id)
    total.value = Math.max(0, total.value - 1)
  }

  return { trips, total, loading, fetchTrips, removeTrip }
})

// 便于 store 外复用列表响应类型
export interface TripList {
  items: Trip[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}