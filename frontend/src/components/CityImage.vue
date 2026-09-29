<script setup lang="ts">
// 目的地配图：本地策展图立即显示，Unsplash 远程图就绪后无缝升级。
// 额外支持字幕（用于横幅类），点 cover 的点击事件由父级 .cover 的 click 处理。
import { useCityImage } from '@/data/remoteImages'

const props = defineProps<{ city: string; credit?: boolean }>()
const { src, credit } = useCityImage(props.city)
</script>

<template>
  <span class="city-image">
    <img :src="src" :alt="city" loading="lazy" />
    <span v-if="credit && credit" class="img-credit">Photo · {{ credit }}</span>
  </span>
</template>

<style scoped>
.city-image { position: relative; display: block; width: 100%; height: 100%; overflow: hidden; }
.city-image img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 1.4s cubic-bezier(.2,.7,.2,1); }
.img-credit { position: absolute; right: 8px; bottom: 6px; z-index: 3; font-size: 10px; letter-spacing: 0.04em; color: rgba(255,255,255,0.7); background: rgba(11,15,14,0.35); padding: 1px 6px; border-radius: 999px; }
</style>