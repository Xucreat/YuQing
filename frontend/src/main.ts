import { createApp } from "vue"
import { createPinia } from "pinia"
import ElementPlus from "element-plus"
import "element-plus/dist/index.css"
import Pager from "./components/Pager.vue"
import "./styles/theme.css"
import "./styles/page-nav.css"

import App from "./App.vue"
import router from "./router"
import { fetchMe } from "./api"
import { useAuthStore } from "./stores"

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus)
app.component("Pager", Pager)

// —— 权限生效机制（RBAC 收口）——
// 登录态下的权限此前只在「登录时」写入 localStorage，管理员改完角色权限后，
// 已登录用户必须退出重登才能生效。这里在应用启动时（存在 token 才请求）
// 拉一次 GET /api/auth/me 覆盖本地缓存，实现「刷新页面即生效」。
// - 挂载前 await，避免路由守卫用到过期权限导致误放行/误拦截；
// - 失败静默（401 已由 axios 拦截器统一登出），不阻塞应用启动。
async function bootstrap() {
  if (localStorage.getItem("token")) {
    const me = await fetchMe()
    if (me) {
      const auth = useAuthStore(pinia)
      auth.setRole(me.role || "")
      auth.setPermissions(me.permissions || [])
      auth.setIsSuperuser(!!me.is_superuser)
      if (me.username) auth.setUsername(me.username)
    }
  }
  app.mount("#app")
}

void bootstrap()
