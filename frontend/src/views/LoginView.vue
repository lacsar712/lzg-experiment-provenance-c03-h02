<template>
  <div class="page" style="max-width: 420px; padding-top: 72px">
    <div class="card">
      <h1 style="margin-top: 0">登录</h1>
      <p class="muted">科学实验运行溯源工作台（CQRS + Event Sourcing）</p>
      <n-form @submit.prevent="onSubmit">
        <n-form-item label="用户名">
          <n-input v-model:value="username" placeholder="researcher / auditor" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input
            v-model:value="password"
            type="password"
            show-password-on="click"
            placeholder="密码"
            @keyup.enter="onSubmit"
          />
        </n-form-item>
        <n-button type="primary" block :loading="loading" @click="onSubmit">登录</n-button>
      </n-form>
      <p class="muted" style="margin-top: 16px; font-size: 13px">
        演示账号：researcher / lab123456（可写）；auditor / audit123456（只读）
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { login } from '../api/client'
import { useAuthStore } from '../stores/auth'

const username = ref('researcher')
const password = ref('lab123456')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const message = useMessage()

async function onSubmit() {
  loading.value = true
  try {
    const data = await login(username.value.trim(), password.value)
    auth.setSession(data)
    message.success('登录成功')
    router.replace(route.query.redirect || '/runs')
  } catch (e) {
    message.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>
