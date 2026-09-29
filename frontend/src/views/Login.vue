<template>
  <div class="login-split">
    <!-- 左：编辑社论式大图（scrim 压字） -->
    <div class="login-visual photo-shade">
      <img :src="HERO_IMAGE" class="login-photo ken-burns" alt="TravelAI" />
      <div class="visual-copy">
        <div class="visual-eyebrow">Travel Atelier</div>
        <div class="visual-title font-display">让每一段旅程，<br /><em>都独一无二。</em></div>
        <div class="visual-sub">AI 旅行规划 · 真实预订落地</div>
      </div>
    </div>

    <!-- 右：表单 -->
    <div class="login-form-wrap">
      <div class="login-head">
        <div class="login-title font-display">欢迎回来</div>
        <div class="login-subtitle">
          {{ isLogin ? '登录你的账号，继续规划旅程' : '注册一个账号，开始规划旅行' }}
        </div>
      </div>

      <a-form
        :model="form"
        layout="vertical"
        :rules="rules"
        @submit="handleSubmit"
      >
        <a-form-item field="email" label="邮箱" :validate-trigger="['blur']">
          <a-input v-model="form.email" placeholder="请输入邮箱" allow-clear>
            <template #prefix><icon-email /></template>
          </a-input>
        </a-form-item>

        <a-form-item v-if="!isLogin" field="name" label="昵称（可选）">
          <a-input v-model="form.name" placeholder="请输入昵称" allow-clear>
            <template #prefix><icon-user /></template>
          </a-input>
        </a-form-item>

        <a-form-item field="password" label="密码" :validate-trigger="['blur']">
          <a-input-password
            v-model="form.password"
            placeholder="至少 6 位密码"
            allow-clear
          >
            <template #prefix><icon-lock /></template>
          </a-input-password>
        </a-form-item>

        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            long
            :loading="loading"
          >
            {{ isLogin ? '登录' : '注册' }}
          </a-button>
        </a-form-item>
      </a-form>

      <div class="login-switch">
        {{ isLogin ? '还没有账号？' : '已有账号？' }}
        <a-link @click="toggleMode">{{ isLogin ? '去注册' : '去登录' }}</a-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { HERO_IMAGE } from '@/data/imagery'
import { useRouter } from 'vue-router'
import {
  Message,
  type FieldRule,
  type ValidatedError,
} from '@arco-design/web-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const isLogin = ref(true)
const loading = ref(false)

const form = reactive({
  email: '',
  name: '',
  password: '',
})

const rules: Record<string, FieldRule | FieldRule[]> = {
  email: [
    { required: true, message: '请输入邮箱' },
    { type: 'email', message: '邮箱格式不正确' },
  ],
  password: [
    { required: true, message: '请输入密码' },
    { minLength: 6, message: '密码至少 6 位' },
  ],
}

const toggleMode = () => {
  isLogin.value = !isLogin.value
}

const handleSubmit = async ({
  errors,
}: {
  errors: Record<string, ValidatedError> | undefined
}) => {
  if (errors) return
  if (loading.value) return

  loading.value = true
  try {
    if (isLogin.value) {
      await auth.login({ username: form.email, password: form.password })
      Message.success('登录成功')
    } else {
      await auth.register({
        email: form.email,
        password: form.password,
        name: form.name || undefined,
      })
      Message.success('注册成功，已自动登录')
    }
    router.push('/')
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '操作失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-split {
  min-height: calc(100vh - 60px);
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.9fr);
  margin: 0 -28px -28px;
  overflow: hidden;
}
@media (max-width: 860px) {
  .login-split { grid-template-columns: 1fr; }
  .login-visual { display: none; }
  .login-form-wrap { padding: 48px 24px !important; }
}

.login-visual {
  position: relative;
  overflow: hidden;
}
.login-photo {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.login-visual::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(11,15,14,0.15) 0%, rgba(11,15,14,0.35) 40%, rgba(11,15,14,0.75) 100%);
}
.visual-copy {
  position: absolute;
  left: 8%; bottom: 12%;
  z-index: 2;
  color: #f4f1ea;
  max-width: 30rem;
}
.visual-eyebrow {
  font-size: 12px;
  letter-spacing: 0.4em;
  text-transform: uppercase;
  color: var(--brand-bright);
  margin-bottom: 14px;
}
.visual-title {
  font-size: clamp(30px, 4vw, 52px);
  line-height: 1.12;
  font-weight: 300;
  color: #f8f6f0;
}
.visual-title em { font-style: italic; color: var(--brand-bright); }
.visual-sub { margin-top: 16px; font-size: 13px; letter-spacing: 0.14em; color: rgba(248,246,240,0.7); text-transform: uppercase; }

.login-form-wrap {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 56px 12%;
  background: var(--bg);
}

.login-head { margin-bottom: 28px; }
.login-title { font-size: 34px; font-weight: 400; color: var(--ink); }
.login-subtitle { margin-top: 8px; font-size: 14px; color: var(--ink-faint); }

.login-switch { margin-top: 4px; text-align: center; font-size: 14px; color: var(--ink-faint); }
</style>