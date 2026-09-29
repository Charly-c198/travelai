export interface User {
  id: string
  email: string
  name?: string | null
  created_at?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user?: User | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: Record<string, unknown>
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
    tips?: string
  }
  itinerary?: {
    content: string
    spots_used: string[]
  } | null
  suggested_actions?: string[]
}

export interface Trip {
  id: string
  user_id: string
  title: string
  destination: string
  start_date: string
  end_date: string
  budget: number
  travelers: number
  status: string
  requirements?: Record<string, unknown> | null
  generated_plan?: {
    content?: string
    days?: Array<{ day: number; title: string; text: string }>
    spots_used?: string[]
    spots?: Array<{
      name?: string
      name_en?: string
      city?: string
      latitude?: number | null
      longitude?: number | null
    }>
  } | null
  created_at?: string
  updated_at?: string
}

export interface TripList {
  items: Trip[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface Spot {
  id: string
  name: string
  city: string
  category?: string | null
  address?: string | null
  latitude?: number | null
  longitude?: number | null
  rating: number
  description?: string | null
  recommend_duration?: number
  tags?: string[]
}