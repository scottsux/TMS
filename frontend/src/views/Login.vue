<template>
  <div class="login-page">
    <section class="login-card">
      <div class="login-head">
        <h1 class="login-title">登录</h1>
        <p class="login-subtitle">本页面为演示登录，仅设置本地角色与令牌。</p>
      </div>

      <div class="login-form">
        <div>
          <label class="field-label">角色</label>
          <select v-model="role" class="input">
            <option disabled value="">选择角色</option>
            <option value="customer">客户</option>
            <option value="staff">员工</option>
            <option value="operator">操作员</option>
          </select>
        </div>
        <button class="btn btn-primary login-submit" @click="doLogin" :disabled="!role">进入系统</button>
      </div>
    </section>
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
  try {
    sessionStorage.setItem('first_visit_done', '1')
  } catch {}
  router.replace('/')
}
</script>

<style scoped>
.login-page {
  min-height: calc(100svh - 120px);
  display: grid;
  place-items: center;
  padding: 32px 16px;
}

.login-card {
  width: min(460px, 100%);
  padding: 28px;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface);
}

.login-head {
  margin-bottom: 20px;
}

.login-title {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
  font-weight: 700;
  color: var(--text-h);
}

.login-subtitle {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-muted);
}

.login-form {
  display: grid;
  gap: 16px;
}

.login-submit {
  width: 100%;
  justify-content: center;
}

@media (max-width: 640px) {
  .login-page {
    padding: 20px 12px;
    min-height: calc(100svh - 92px);
  }

  .login-card {
    padding: 20px;
  }
}
</style>
