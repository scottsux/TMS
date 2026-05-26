<template>
  <div class="login-page">
    <section class="login-card">
      <div class="login-head">
        <h1 class="login-title">登录</h1>
        <p class="login-subtitle">使用后端真实账号登录，服务端会校验密码和角色权限。</p>
      </div>

      <div class="login-form">
        <div>
          <label class="field-label">邮箱</label>
          <input v-model.trim="email" class="input" type="email" placeholder="例如 customer@example.com" />
        </div>
        <div>
          <label class="field-label">密码</label>
          <input v-model="password" class="input" type="password" placeholder="输入密码" />
        </div>
        <div class="login-hint">
          <div>客户：`customer@example.com` / `demo123`</div>
          <div>员工：`staff@example.com` / `demo123`</div>
          <div>操作员：`operator@example.com` / `demo123`</div>
        </div>
        <button class="btn btn-primary login-submit" @click="doLogin" :disabled="!email || !password || loading">
          {{ loading ? '登录中...' : '进入系统' }}
        </button>
        <div v-if="msg" class="login-error">{{ msg }}</div>
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
const email = ref('customer@example.com')
const password = ref('demo123')
const loading = ref(false)
const msg = ref('')

async function doLogin() {
  msg.value = ''
  try {
    loading.value = true
    await auth.login({ email: email.value, password: password.value })
    try {
      sessionStorage.setItem('first_visit_done', '1')
    } catch {}
    router.replace('/')
  } catch (error) {
    msg.value = `登录失败：${error?.message || '未知错误'}`
  } finally {
    loading.value = false
  }
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

.login-hint {
  font-size: 12px;
  color: var(--text-muted);
  display: grid;
  gap: 4px;
}

.login-error {
  font-size: 12px;
  color: var(--danger);
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
