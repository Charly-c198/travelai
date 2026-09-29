import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type LoginData, type RegisterData } from '@/api/auth'
import type { User, TokenResponse } from '@/types'

const TOKEN_KEY = 'token'
const USER_KEY = 'user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref<User | null>(readUser())

  function readUser(): User | null {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
    } catch {
      return null
    }
  }

  const isAuthenticated = computed(() => !!token.value)

  function setAuth(data: TokenResponse) {
    token.value = data.access_token
    user.value = data.user ?? null
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user ?? null))
  }

  async function login(payload: LoginData) {
    const data = await authApi.login(payload)
    setAuth(data)
  }

  async function register(payload: RegisterData) {
    const data = await authApi.register(payload)
    setAuth(data)
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return { token, user, isAuthenticated, login, register, logout }
})