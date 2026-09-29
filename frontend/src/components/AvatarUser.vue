<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ size?: number }>()
// 渐变 id 每实例唯一，避免页面上多个用户消息重复 id 导致引用错乱
const gid = `user-grad-${Math.random().toString(36).slice(2, 9)}`
</script>

<template>
  <svg
    :width="size || 40"
    :height="size || 40"
    viewBox="0 0 40 40"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="avatar-user"
    role="img"
    aria-label="用户头像"
  >
    <defs>
      <linearGradient :id="gid" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#eef7f3" />
        <stop offset="100%" stop-color="#cfe9df" />
      </linearGradient>
    </defs>
    <!-- 圆角徽章底 -->
    <rect x="1.5" y="1.5" width="37" height="37" rx="10.5" :fill="`url(#${gid})`" />
    <rect x="1.5" y="1.5" width="37" height="37" rx="10.5" stroke="#0b6b5c" stroke-opacity="0.14" />
    <!-- 人物剪影 -->
    <circle cx="20" cy="15.5" r="5.5" fill="#0b6b5c" opacity="0.85" />
    <path d="M12 30.5 C12 25.5 16 23.5 20 23.5 C24 23.5 28 25.5 28 30.5 Z" fill="#0b6b5c" opacity="0.85" />
  </svg>
</template>

<style scoped>
.avatar-user { display: block; flex-shrink: 0; }
</style>
