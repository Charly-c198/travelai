<script setup lang="ts">
// 需求:「地点图鉴」照片墙。给一组地名拉 Unsplash 图,展示照片 + 地名。
// - 点击某张 → 灯箱放大预览(Teleport 到 body,支持方向键翻页 / Esc 关闭)。
// - 加载中显示骨架;某个地点无图跳过;全部无图/失败则整体隐藏(不影响父级)。
import { watch, ref, onMounted, onBeforeUnmount } from 'vue'
import { usePlaceImages, type PlaceItem } from '@/data/usePlaceImages'

const props = defineProps<{ places: PlaceItem[] }>()

const { images, loading, load } = usePlaceImages()

watch(
  () => props.places,
  (v) => {
    if (v && v.length) load(v)
    else load([])
  },
  { immediate: true }
)

// —— 灯箱预览 ——
const zoomIndex = ref<number | null>(null)
const openZoom = (i: number) => { zoomIndex.value = i }
const closeZoom = () => { zoomIndex.value = null }
const zoomPrev = () => {
  if (zoomIndex.value === null) return
  zoomIndex.value = images.value.length ? (zoomIndex.value - 1 + images.value.length) % images.value.length : null
}
const zoomNext = () => {
  if (zoomIndex.value === null) return
  zoomIndex.value = images.value.length ? (zoomIndex.value + 1) % images.value.length : null
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => { window.removeEventListener('keydown', onKey); document.body.style.overflow = '' })
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') closeZoom()
  else if (e.key === 'ArrowLeft') zoomPrev()
  else if (e.key === 'ArrowRight') zoomNext()
}
// 防止打开灯箱时背景滚动
watch(zoomIndex, (v) => {
  document.body.style.overflow = v !== null ? 'hidden' : ''
})
</script>

<template>
  <div v-if="images.length || loading" class="place-gallery">
    <!-- 加载骨架 -->
    <div v-if="loading && !images.length" v-for="i in Math.min(places.length || 1, 5)" :key="'skeleton-' + i" class="pg-item pg-skeleton" />
    <!-- 照片墙（可点击放大） -->
    <button
      v-for="(p, i) in images"
      :key="p.url"
      type="button"
      class="pg-item photo-shade"
      @click="openZoom(i)"
    >
      <img :src="p.url" :alt="p.name" loading="lazy" />
      <span class="pg-caption">{{ p.name }}</span>
      <span v-if="p.credit" class="pg-credit">Photo · {{ p.credit }}</span>
    </button>
  </div>

  <!-- 灯箱预览 -->
  <Teleport to="body">
    <Transition name="pg-fade">
      <div v-if="zoomIndex !== null && images[zoomIndex]" class="pg-lightbox" @click.self="closeZoom">
        <button type="button" class="pg-close" aria-label="关闭" @click="closeZoom">✕</button>
        <button type="button" class="pg-nav pg-prev" aria-label="上一张" @click="zoomPrev">‹</button>
        <button type="button" class="pg-nav pg-next" aria-label="下一张" @click="zoomNext">›</button>
        <figure class="pg-stage" @click="zoomNext">
          <Transition name="pg-zoom" mode="out-in">
            <img :key="zoomIndex" :src="images[zoomIndex].url" :alt="images[zoomIndex].name" />
          </Transition>
          <figcaption>
            <strong>{{ images[zoomIndex].name }}</strong>
            <span v-if="images[zoomIndex].credit" class="pg-zoom-credit">Photo · {{ images[zoomIndex].credit }}</span>
          </figcaption>
        </figure>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.place-gallery {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 6px;
  scrollbar-width: thin;
}
.pg-item {
  position: relative;
  flex: 0 0 auto;
  width: 150px;
  height: 96px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--line);
  padding: 0;
  cursor: zoom-in;
}
.pg-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.pg-caption {
  position: absolute;
  left: 8px;
  bottom: 6px;
  z-index: 1;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.02em;
  text-shadow: 0 1px 3px rgba(11, 15, 14, 0.6);
  max-width: 92%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pg-credit {
  position: absolute;
  right: 6px;
  top: 6px;
  z-index: 1;
  font-size: 9px;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(11, 15, 14, 0.4);
  padding: 1px 6px;
  border-radius: 999px;
}
.pg-skeleton {
  background: linear-gradient(90deg, var(--bg-alt) 25%, var(--surface) 50%, var(--bg-alt) 75%);
  background-size: 200% 100%;
  animation: pg-shimmer 1.2s ease-in-out infinite;
}
@keyframes pg-shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* —— 灯箱 —— */
.pg-lightbox {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(6, 9, 8, 0.72);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}
.pg-stage {
  margin: 0;
  max-width: min(92vw, 1100px);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  cursor: zoom-in;
}
.pg-stage img {
  max-width: 100%;
  max-height: 72vh;
  object-fit: contain;
  border-radius: 12px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5);
}
.pg-stage figcaption {
  color: #fff;
  font-size: 15px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.pg-zoom-credit {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}
.pg-close {
  position: absolute;
  top: 18px;
  right: 18px;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}
.pg-close:hover { background: rgba(255, 255, 255, 0.26); }
.pg-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  font-size: 24px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  z-index: 1;
}
.pg-nav:hover { background: rgba(255, 255, 255, 0.26); }
.pg-prev { left: 20px; }
.pg-next { right: 20px; }

.pg-fade-enter-active, .pg-fade-leave-active { transition: opacity 0.2s ease; }
.pg-fade-enter-from, .pg-fade-leave-to { opacity: 0; }
.pg-zoom-enter-active, .pg-zoom-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.pg-zoom-enter-from, .pg-zoom-leave-to { opacity: 0; transform: scale(0.97); }
</style>