<template>
  <div class="login-wrapper">
    <el-card class="login-card" shadow="always">
      <div class="login-header">
        <h1 class="platform-name">大厂县公安互联网舆情监测研判平台</h1>
        <p class="platform-sub">Internet Public Opinion Monitoring Platform</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            clearable
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            class="login-btn"
            :loading="loading"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import api from '@/api'
import { useAuthStore } from '@/stores'
import type { LoginResult } from '@/types'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

// 默认填充 admin / admin123
const form = reactive({
  username: 'admin',
  password: 'admin123',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  // 防重复点击
  if (loading.value) return
  loading.value = true
  try {
    // 登录是全站唯一公开接口，无需 Bearer token
    const { data } = await api.post<LoginResult>('/login', {
      username: form.username,
      password: form.password,
    })
    authStore.setToken(data.access_token)
    authStore.setUsername(form.username)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (err: any) {
    const msg =
      err?.response?.data?.detail || err?.message || '登录失败，请检查用户名或密码'
    ElMessage.error(typeof msg === 'string' ? msg : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f0f2f5;
}
.login-card {
  width: 420px;
  padding: 10px 20px 0;
}
.login-header {
  text-align: center;
  margin-bottom: 24px;
}
.platform-name {
  font-size: 20px;
  font-weight: 700;
  color: #1f2d3d;
  margin: 8px 0 4px;
  line-height: 1.4;
}
.platform-sub {
  font-size: 12px;
  color: #909399;
  margin: 0;
}
.login-btn {
  width: 100%;
}
</style>
