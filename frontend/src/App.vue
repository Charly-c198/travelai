<template>
  <div class="app-shell">
    <!-- 顶部导航栏（frosted 玻璃 + 编辑社论式 wordmark） -->
    <header class="navbar">
      <div class="navbar-left">
        <router-link to="/" class="logo">🧳 Travel<span class="logo-italic">AI</span></router-link>
        <a-menu
          mode="horizontal"
          :selected-keys="[activeKey]"
          class="nav-menu"
          @menu-item-click="onMenuClick"
        >
          <a-menu-item key="/">首页</a-menu-item>
          <a-menu-item key="/my-trips">我的行程</a-menu-item>
          <a-menu-item key="/trip-create">创建行程</a-menu-item>
          <a-menu-item key="/dashboard">数据看板</a-menu-item>
        </a-menu>
      </div>

      <div class="navbar-right">
        <button class="theme-toggle" :title="isDark ? '切换到浅色' : '切换到深色'" @click="toggleTheme">
          <icon-moon v-if="!isDark" />
          <icon-sun v-else />
        </button>
        <template v-if="auth.isAuthenticated">
          <router-link to="/profile" class="user-entry">
            <avatar-user :size="32" />
            <span class="username">{{ displayName }}</span>
          </router-link>
          <a-button size="small" @click="handleLogout">退出登录</a-button>
        </template>
        <a-button v-else type="primary" size="small" @click="router.push('/login')">
          登录
        </a-button>
      </div>
    </header>

    <!-- 页面内容 -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AvatarUser from '@/components/AvatarUser.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// 顶部导航选中的 key 对应当前路由路径
const activeKey = computed(() => route.path === '/profile' ? '/profile' : route.path)

const isDark = ref(document.body.getAttribute('arco-theme') === 'dark')
function applyTheme() {
  document.body.setAttribute('arco-theme', isDark.value ? 'dark' : '')
  document.body.classList.toggle('theme-dark', isDark.value)
  localStorage.setItem('travelai-theme', isDark.value ? 'dark' : 'light')
}
function toggleTheme() {
  isDark.value = !isDark.value
  applyTheme()
}
onMounted(() => {
  isDark.value = document.body.getAttribute('arco-theme') === 'dark'
})

const displayName = computed(
  () => auth.user?.name || auth.user?.email || '用户'
)

const onMenuClick = (key: string) => {
  if (key !== route.path) {
    router.push(key)
  }
}

const handleLogout = () => {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

.navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  height: 60px;
  background: color-mix(in srgb, var(--bg) 78%, transparent);
  backdrop-filter: blur(14px) saturate(1.4);
  -webkit-backdrop-filter: blur(14px) saturate(1.4);
  border-bottom: 1px solid var(--line);
}

.navbar-left {
  display: flex;
  align-items: center;
  gap: 28px;
  min-width: 0;
}

.logo {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 400;
  color: var(--ink);
  text-decoration: none;
  letter-spacing: 0.01em;
  white-space: nowrap;
}
.logo-italic { font-style: italic; color: var(--brand); }

.nav-menu {
  background: transparent;
  min-width: 0;
}
.nav-menu :deep(.arco-menu-inner) { padding: 0; }
.nav-menu :deep(.arco-menu-item) {
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
}
.nav-menu :deep(.arco-menu-selected) { color: var(--brand); }

.navbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.theme-toggle {
  width: 34px; height: 34px;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
  transition: color .2s, border-color .2s, background .2s;
}
.theme-toggle:hover { color: var(--brand); border-color: var(--brand); }

.user-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-soft);
  text-decoration: none;
}

.username {
  font-size: 14px;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main-content {
  flex: 1;
  padding: 0 28px 28px;
}
@media (max-width: 720px) {
  .main-content { padding: 0 16px 24px; }
  .navbar { padding: 0 16px; }
  .nav-menu { display: none; }
}
</style>