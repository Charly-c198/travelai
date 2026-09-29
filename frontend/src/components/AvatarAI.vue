<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ size?: number }>()
// 渐变 id 每实例唯一，避免页面上多个 AI 消息重复 id 导致引用错乱
const gid = `ai-grad-${Math.random().toString(36).slice(2, 9)}`
</script>

<template>
  <svg
    :width="size || 40"
    :height="size || 40"
    viewBox="0 0 40 40"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="avatar-ai"
    role="img"
    aria-label="TravelAI 助手"
  >
    <defs>
      <linearGradient :id="gid" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#0b6b5c" />
        <stop offset="100%" stop-color="#2bbf9b" />
      </linearGradient>
    </defs>
    <!-- 圆角徽章底 -->
    <rect x="1.5" y="1.5" width="37" height="37" rx="10.5" :fill="`url(#${gid})`" />
    <rect x="1.5" y="1.5" width="37" height="37" rx="10.5" stroke="rgba(255,255,255,0.22)" stroke-width="1" />
    <!-- 纸飞机（发送 / 出行寓意） -->
    <path d="M30.5 9.5 L23.15 30.5 L18.95 21.05 L9.5 16.85 Z" fill="#fff" opacity="0.95" />
    <path d="M30.5 9.5 L18.95 21.05 L9.5 16.85 Z" fill="rgba(255,255,255,0.3)" />
    <path d="M30.5 9.5 L18.95 21.05" stroke="rgba(255,255,255,0.5)" stroke-width="1" stroke-linecap="round" />
    <!-- AI 星光点缀 -->
    <path
      d="M10.5 7 L11.35 9.65 L14 10.5 L11.35 11.35 L10.5 14 L9.65 11.35 L7 10.5 L9.65 9.65 Z"
      fill="#9ef0db"
      opacity="0.9"
    />
  </svg>
</template>

<style scoped>
.avatar-ai { display: block; flex-shrink: 0; }
</style>
