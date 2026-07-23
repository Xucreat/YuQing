<template>
  <div class="login-screen">
    <div class="login-card">
      <div class="login-badge">YQ</div>
      <h1 class="login-title">大厂县公安互联网舆情监测研判平台</h1>
      <p class="login-sub">Internet Public Opinion Monitoring Platform</p>

      <div class="field">
        <label>用户名</label>
        <input
          v-model="form.username"
          class="input"
          type="text"
          placeholder="请输入用户名"
          autocomplete="username"
          @keyup.enter="handleLogin"
        />
      </div>
      <div class="field">
        <label>密码</label>
        <input
          v-model="form.password"
          class="input"
          type="password"
          placeholder="请输入密码"
          autocomplete="current-password"
          @keyup.enter="handleLogin"
        />
      </div>

      <button class="btn btn-primary login-btn" :disabled="loading" @click="handleLogin">
        {{ loading ? '登录中...' : '登 录' }}
      </button>

      <p class="login-hint">
        默认账号 <code>admin</code> / <code>admin123</code>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { useAuthStore } from '@/stores'
import type { LoginResult } from '@/types'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: 'admin123',
})

async function handleLogin() {
  if (!form.username.trim() || !form.password.trim()) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (loading.value) return
  loading.value = true
  try {
    const { data } = await api.post<LoginResult>('/login', {
      username: form.username,
      password: form.password,
    })
    authStore.setToken(data.access_token)
    authStore.setUsername(form.username)
    authStore.setRole(data.role || 'analyst')
    authStore.setPermissions(data.permissions || [])
    authStore.setIsSuperuser(!!data.is_superuser)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '登录失败，请检查用户名或密码'
    ElMessage.error(typeof msg === 'string' ? msg : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-screen {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(1200px 600px at 50% -10%, #eef4fb 0%, rgba(238, 244, 251, 0) 60%),
    #f5f5f7;
}
.login-card {
  width: 412px;
  max-width: 100%;
  background: #ffffff;
  border-radius: 22px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.18);
  padding: 44px 40px 40px;
  text-align: center;
}
.login-badge {
  width: 64px;
  height: 64px;
  margin: 0 auto 22px;
  border-radius: 18px;
  background: linear-gradient(135deg, #0071e3, #42a5f5);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 30px;
  font-weight: 700;
  box-shadow: 0 8px 24px rgba(0, 113, 227, 0.28);
}
.login-title {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 0;
  color: #1d1d1f;
}
.login-sub {
  font-size: 13px;
  color: #86868b;
  margin: 8px 0 28px;
  letter-spacing: 0.01em;
}
.field {
  text-align: left;
  margin-bottom: 16px;
}
.field label {
  display: block;
  font-size: 13px;
  color: #6e6e73;
  margin-bottom: 7px;
  font-weight: 500;
}
.input {
  width: 100%;
  height: 46px;
  padding: 0 15px;
  font-size: 15px;
  color: #1d1d1f;
  background: #fbfbfd;
  border: 1px solid #d2d2d7;
  border-radius: 14px;
  outline: none;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
  box-sizing: border-box;
}
.input:focus {
  border-color: #0071e3;
  background: #fff;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.12);
}
.login-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  margin-top: 8px;
  border: none;
  border-radius: 980px;
  background: #0071e3;
  color: #fff;
  font-weight: 500;
  cursor: pointer;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  transition: background-color 0.18s ease, transform 0.12s ease, opacity 0.18s ease;
}
.login-btn:hover {
  background: #0077ed;
}
.login-btn:disabled {
  opacity: 0.55;
  cursor: default;
}
.login-btn:active {
  transform: scale(0.98);
}
.login-hint {
  margin-top: 18px;
  font-size: 12.5px;
  color: #86868b;
}
.login-hint code {
  background: #e8e8ed;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 12px;
  font-family: "SF Mono", "Fira Code", "Fira Mono", Menlo, Consolas, monospace;
}
</style>
