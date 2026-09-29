/**
 * 行程分享 API
 */
import { get, post } from './index'
import type { Trip } from '@/types'

export const shareApi = {
  // 生成本人行程的公开分享链接（返回 token + 相对路径 /s/{token}）
  shareTrip: (id: string) => post<{ token: string; url: string }>(`/api/v1/trips/${id}/share`),
  // 公开查看分享的行程（无需登录）
  getShared: (token: string) => get<Trip>(`/api/v1/s/${token}`),
}