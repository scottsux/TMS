<template>
  <div class="container" style="container-type:inline-size;">
    <div class="card" style="max-width:480px; margin:40px auto; padding:20px;">
      <h1 class="mb-3" style="font-size:22px; font-weight:650;">登录</h1>
      <div class="grid gap-3">
        <select v-model="role" class="input">
          <option disabled value="">选择角色</option>
          <option value="customer">客户</option>
          <option value="staff">员工</option>
          <option value="operator">操作员</option>
        </select>
        <button class="btn btn-primary" @click="doLogin" :disabled="!role">进入</button>
      </div>
      <p class="mt-3" style="font-size:12px; opacity:.7;">本页面为演示登录，仅设置本地角色与令牌。</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const role = ref('')

function doLogin() {
  auth.login({ role: role.value })
  try { sessionStorage.setItem('first_visit_done', '1') } catch {}
  router.replace('/')
}
</script>
