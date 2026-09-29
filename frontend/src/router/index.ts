import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/Home.vue'),
      meta: { title: '首页' },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/Profile.vue'),
      meta: { title: '个人中心' },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { title: '数据看板' },
    },
    {
      path: '/my-trips',
      name: 'my-trips',
      component: () => import('@/views/MyTrips.vue'),
      meta: { title: '我的行程' },
    },
    {
      path: '/s/:token',
      name: 'shared-trip',
      component: () => import('@/views/SharedTrip.vue'),
      meta: { public: true, title: '分享的行程' },
    },
    {
      path: '/trip-detail',
      name: 'trip-detail',
      component: () => import('@/views/TripDetail.vue'),
      meta: { title: '行程详情' },
    },
    {
      // 占位：页面内容后续实现
      path: '/trip-create',
      name: 'trip-create',
      component: () => import('@/views/TripCreate.vue'),
      meta: { title: '创建行程' },
    },
    {
      // 占位：页面内容后续实现
      path: '/trip-plan',
      name: 'trip-plan',
      component: () => import('@/views/TripPlan.vue'),
      meta: { title: '行程规划' },
    },
  ],
})

// 登录守卫：除公开页外均需登录
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'home' }
  }
  return true
})

router.afterEach((to) => {
  const title = (to.meta?.title as string) || 'TravelAI'
  document.title = `${title} - TravelAI`
})

export default router