<template>
  <nav class="nav">
    <RouterLink v-for="item in items" :key="item.to" class="item" :to="item.to" active-class="active" exact>
      <span class="icon" v-html="item.icon" />
      <span>{{ item.label }}</span>
    </RouterLink>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '../stores/auth'
const { role } = storeToRefs(useAuthStore())

const allItems = [
  { to: '/', label: '仪表盘', roles: ['staff', 'operator', 'customer'], icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 13h7V4H4v9zm0 7h7v-5H4v5zm9 0h7V11h-7v9zm0-16v5h7V4h-7z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>' },
  { to: '/orders', label: '订单', roles: ['staff', 'operator', 'customer'], icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M7 4h10l3 4v11H4V8l3-4z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M4 8h16" stroke="currentColor" stroke-width="1.8"/></svg>' },
  { to: '/upload', label: '上传', roles: ['staff', 'customer'], icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 16V6m0 0-4 4m4-4 4 4M5 18v2h14v-2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>' },
  { to: '/tasks', label: '任务', roles: ['staff', 'operator'], icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>' },
  { to: '/billing', label: '结算', roles: ['staff'], icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 7h16v10H4z" stroke="currentColor" stroke-width="1.8"/><path d="M8 11h8M8 15h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>' },
  { to: '/exceptions', label: '异常', roles: ['staff', 'operator', 'customer'], icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 3 3.5 19h17L12 3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 9v4m0 3h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>' },
  { to: '/customers', label: '客户', roles: ['staff'], icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2M9.5 11A3.5 3.5 0 1 0 9.5 4a3.5 3.5 0 0 0 0 7zm8.5 10v-2a4 4 0 0 0-3-3.87M14 4.13a3.5 3.5 0 0 1 0 6.74" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>' },
  { to: '/parcels', label: '包裹', roles: ['staff', 'customer', 'operator'], icon: '<svg viewBox="0 0 24 24" fill="none"><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 12 4 7.5M12 12l8-4.5M12 12v9" stroke="currentColor" stroke-width="1.8"/></svg>' },
]

const items = computed(() => allItems.filter((item) => item.roles.includes(role.value)))
</script>

<style scoped>
.nav { display: grid; gap: 6px; }
.item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 8px; border: 1px solid transparent; color: var(--text); font-size: 14px; }
.item:hover { border-color: var(--border); background: var(--surface); color: var(--text-h); }
.icon { width: 18px; height: 18px; display: inline-flex; color: inherit; }
.icon :deep(svg) { width: 18px; height: 18px; }
.active { position: relative; background: var(--accent-soft); border-color: transparent; color: var(--text-h); }
.active::before { content: ''; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px; border-radius: 999px; background: var(--accent); }
</style>
