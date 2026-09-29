<template>
  <div class="placeholder-page">
    <a-empty description="行程规划功能开发中，敬请期待">
      <template #image>
        <span style="font-size: 56px">🗺️</span>
      </template>
      <a-button type="primary" @click="$router.push('/')">返回首页</a-button>
    </a-empty>
  </div>
</template>

<script setup lang="ts">
// 占位页：行程规划功能后续实现
</script>

<style scoped>
.placeholder-page {
  min-height: calc(100vh - 96px);
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>