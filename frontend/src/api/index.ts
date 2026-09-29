import axios, { type AxiosRequestConfig } from 'axios'

/**
 * 统一的 axios 请求封装
 * - 自动附加 Bearer token
 * - 统一返回 data
 * - 401 时清除登录态并跳转登录页
 */
export const request = axios.create({
  baseURL: '',
  timeout: 300000, // 后端 LLM 生成较慢，给足超时
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// 帮助 TS 识别拦截器已返回 data
export const get = <T>(url: string, config?: AxiosRequestConfig) =>
  request.get(url, config) as unknown as Promise<T>

export const post = <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
  request.post(url, data, config) as unknown as Promise<T>

export const put = <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
  request.put(url, data, config) as unknown as Promise<T>

export const del = <T>(url: string, config?: AxiosRequestConfig) =>
  request.delete(url, config) as unknown as Promise<T>

export default request