/**
 * 商业埋点 API（曝光→点击→预订 漏斗）
 */
import { post } from './index'

export const trackingApi = {
  // 记录事件；失败静默（不影响业务）
  track: (
    event: string,
    opts: { channel?: string; trip_id?: string; meta?: Record<string, unknown> } = {}
  ) =>
    post<{ ok: boolean }>('/api/v1/tracking', {
      event,
      channel: opts.channel || '',
      trip_id: opts.trip_id || null,
      meta: opts.meta || {},
    }).catch(() => null),
}