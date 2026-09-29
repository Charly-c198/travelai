/**
 * 酒店查询 API（RollingGo 真实可订房）
 */
import { get } from './index'

export interface RollingHotel {
  hotelId?: number
  name?: string
  address?: string
  latitude?: number
  longitude?: number
  starRating?: number
  price?: { message?: string }
  bookingUrl?: string
}

export const hotelsApi = {
  search: (place: string, size = 8) =>
    get<{ success?: boolean; hotels: RollingHotel[] }>('/api/v1/hotels', {
      params: { place, size },
    }),
}