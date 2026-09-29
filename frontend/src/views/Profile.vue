<template>
  <div class="profile-page">
    <div class="profile-header">
      <h1>👤 个人中心</h1>
      <p class="subtitle">管理你的账号信息</p>
    </div>

    <a-card class="profile-card" v-if="auth.user">
      <div class="profile-body">
        <a-avatar :size="64" class="profile-avatar">
          <icon-user />
        </a-avatar>
        <div class="profile-info">
          <div class="profile-name">{{ auth.user.name || '未设置昵称' }}</div>
          <div class="profile-email">{{ auth.user.email }}</div>
          <div class="profile-meta" v-if="auth.user.created_at">
            注册时间：{{ formatDate(auth.user.created_at) }}
          </div>
        </div>
      </div>

      <a-divider />

      <div class="profile-actions">
        <a-button @click="router.push('/')">
          <template #icon><icon-home /></template>
          返回首页
        </a-button>
        <a-button type="primary" status="danger" @click="handleLogout">
          <template #icon><icon-poweroff /></template>
          退出登录
        </a-button>
      </div>
    </a-card>

    <a-empty v-else description="暂无用户信息" />
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

const handleLogout = () => {
  Message.success('已退出登录')
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.profile-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 16px 0;
}

.profile-header {
  margin-bottom: 20px;
}

.profile-header h1 {
  font-size: 24px;
  margin-bottom: 4px;
}

.subtitle {
  color: #86909c;
  font-size: 14px;
}

.profile-body {
  display: flex;
  align-items: center;
  gap: 20px;
}

.profile-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  font-size: 28px;
}

.profile-name {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.profile-email {
  color: #86909c;
  margin-bottom: 4px;
}

.profile-meta {
  color: #86909c;
  font-size: 13px;
}

.profile-actions {
  display: flex;
  gap: 12px;
}
</style>