import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ArcoVueIcon from '@arco-design/web-vue/es/icon'
// Message 是命令式 API：不参与模板解析，需手动引入其样式（其余组件由 unplugin 按需附带样式）
import '@arco-design/web-vue/es/message/style/css.js'
import './styles/theme.css'
import App from './App.vue'
import router from './router'

// 主题初始化：亮/暗跟随系统，Arco 走官方 dark 机制
function applyTheme() {
  const saved = localStorage.getItem('travelai-theme')
  const dark = saved ? saved === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches
  document.body.setAttribute('arco-theme', dark ? 'dark' : '')
  document.body.classList.toggle('theme-dark', dark)
}
applyTheme()

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ArcoVueIcon)

app.mount('#app')