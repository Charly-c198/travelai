import { post } from './index'
import type { TokenResponse } from '@/types'

export interface RegisterData {
  email: string
  password: string
  name?: string
}

export interface LoginData {
  username: string
  password: string
}

export const authApi = {
  register: (data: RegisterData) =>
    post<TokenResponse>('/api/v1/auth/register', data),

  login: (data: LoginData) =>
    post<TokenResponse>(
      '/api/v1/auth/token',
      new URLSearchParams({ username: data.username, password: data.password }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    ),
}