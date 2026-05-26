<template>
  <div :class="['shell', { dark: isDark }]">
    <header class="topbar">
      <button
        v-if="showSidebarShell"
        class="icon-btn"
        aria-label="Toggle Sidebar"
        @click.stop="toggleSidebar"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
      </button>
      <div class="brand">
        <img class="brand-mark" src="/favicon.svg" alt="" />
        <div>
          <div class="brand-name">TMS 控制台</div>
          <div class="brand-subtitle">Transportation Management System</div>
        </div>
      </div>
      <div class="spacer" />
      <div v-if="showSidebarShell" class="user">
        <button ref="menuButtonRef" class="user-btn" @click="menuOpen = !menuOpen">
          <span class="role">{{ roleLabel }}</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button>
        <div v-if="menuOpen" ref="menuRef" class="menu">
          <div class="menu-item" @click="goLogin">切换角色</div>
          <div class="menu-item" @click="logout">退出</div>
        </div>
      </div>
      <button
        class="icon-btn"
        :aria-pressed="isDark ? 'true' : 'false'"
        aria-label="Toggle Dark Mode"
        @click="toggleDark()"
      >
        <svg v-if="!isDark" width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M12 3v2m0 14v2m9-9h-2M5 12H3m14.95 6.95-1.41-1.41M7.46 7.46 6.05 6.05m12.9 0-1.41 1.41M7.46 16.54 6.05 17.95" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="2"/>
        </svg>
        <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M20 12.5A8.5 8.5 0 1 1 11.5 4 7 7 0 0 0 20 12.5z" stroke="currentColor" stroke-width="2" fill="none"/>
        </svg>
      </button>
    </header>

    <div :class="['layout', { 'sidebar-hidden': showSidebarShell && !sidebarOpen, 'layout-no-sidebar': !showSidebarShell }]">
      <aside v-if="showSidebarShell" :class="['sidebar', { open: sidebarOpen }]">
        <Navbar />
      </aside>
      <div v-if="showSidebarShell && sidebarOpen && isMobileView" class="sidebar-mask" @click="sidebarOpen = false" />
      <main class="content" @click="maybeCloseSidebar">
        <router-view />
      </main>
    </div>
  </div>
  
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Navbar from './components/Navbar.vue'
import { useAppStore } from './stores/app'
import { useAuthStore } from './stores/auth'

const sidebarOpen = ref(true)
const app = useAppStore()
const isDark = computed(() => app.dark)
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const menuOpen = ref(false)
const isMobileView = ref(false)
const menuRef = ref(null)
const menuButtonRef = ref(null)
const roleLabel = computed(() => ({ customer:'客户', staff:'员工', operator:'操作员' }[auth.role] || '未登录'))
const showSidebarShell = computed(() => auth.isAuthed && !route.meta?.public)

function applyTheme(dark) {
  const root = document.documentElement
  root.dataset.theme = dark ? 'dark' : 'light'
}

function toggleDark() { app.toggleDark() }

function isMobile() {
  return window.matchMedia('(max-width: 900px)').matches
}
function toggleSidebar() {
  if (!showSidebarShell.value) return
  sidebarOpen.value = !sidebarOpen.value
}
function maybeCloseSidebar() {
  // Only auto-close on small screens when sidebar is open
  if (sidebarOpen.value && isMobile()) {
    sidebarOpen.value = false
  }
}

// Optional: close with ESC
function onKeydown(ev) {
  if (ev.key === 'Escape' && sidebarOpen.value && isMobile()) sidebarOpen.value = false
  if (ev.key === 'Escape' && menuOpen.value) menuOpen.value = false
}

function onDocumentClick(ev) {
  const target = ev.target
  if (!menuOpen.value) return
  if (menuRef.value?.contains(target) || menuButtonRef.value?.contains(target)) return
  menuOpen.value = false
}

function onResize() {
  isMobileView.value = isMobile()
  if (!isMobileView.value) sidebarOpen.value = true
}

onMounted(() => {
  onResize()
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('resize', onResize)
  document.addEventListener('click', onDocumentClick)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onResize)
  document.removeEventListener('click', onDocumentClick)
})

onMounted(() => {
  const stored = localStorage.getItem('theme')
  if (stored) {
    app.setDark(stored === 'dark')
  } else {
    app.setDark(window.matchMedia('(prefers-color-scheme: dark)').matches)
  }
})

watch(isDark, (v) => {
  applyTheme(v)
  localStorage.setItem('theme', v ? 'dark' : 'light')
}, { immediate: true })

watch(() => route.fullPath, () => {
  menuOpen.value = false
  if (!showSidebarShell.value) sidebarOpen.value = false
})

watch(showSidebarShell, (value) => {
  if (!value) {
    sidebarOpen.value = false
    menuOpen.value = false
    return
  }
  if (!isMobileView.value) sidebarOpen.value = true
}, { immediate: true })

function logout() {
  auth.logout()
  menuOpen.value = false
  router.push('/login')
}
function goLogin() {
  menuOpen.value = false
  router.push('/login')
}
</script>

<style scoped>
.shell { min-height: 100svh; background: var(--bg); color: var(--text); }
.topbar { position: sticky; top: 0; z-index: 30; display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-bottom: 1px solid var(--border); background: color-mix(in oklab, var(--surface) 88%, transparent); backdrop-filter: saturate(1.2) blur(10px); }
.brand { display: flex; align-items: center; gap: 10px; }
.brand-mark { width: 20px; height: 20px; }
.brand-name { font-weight: 700; color: var(--text-h); font-size: 14px; }
.brand-subtitle { font-size: 11px; color: var(--text-muted); }
.spacer { flex: 1; }
.icon-btn { display: inline-grid; place-items: center; width: 36px; height: 36px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text); cursor: pointer; }
.icon-btn:hover { border-color: var(--accent-border); color: var(--text-h); }
.user { position: relative; margin-right: 8px; }
.user-btn { display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: inherit; cursor: pointer; }
.role { font-size: 12px; opacity: .9; }
.menu { position: absolute; right: 0; top: 40px; background: var(--bg); border: 1px solid var(--border); border-radius: 10px; min-width: 140px; box-shadow: var(--shadow); }
.menu-item { padding: 8px 12px; font-size: 13px; cursor: pointer; }
.menu-item:hover { background: color-mix(in oklab, var(--bg) 92%, transparent); }

.layout { display: grid; grid-template-columns: 248px 1fr; min-height: calc(100svh - 58px); position: relative; }
.layout-no-sidebar { grid-template-columns: 1fr; }
.sidebar { border-right: 1px solid var(--border); padding: 16px 12px; background: var(--surface-subtle); position: relative; z-index: 25; }
.content { padding: 24px; }
.sidebar-mask { position: fixed; inset: 58px 0 0 0; background: rgb(15 23 42 / 0.36); z-index: 24; }

@container (max-width: 900px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { position: fixed; inset: 58px auto 0 0; width: 248px; height: calc(100svh - 58px); transform: translateX(-100%); transition: transform .2s ease; box-shadow: var(--shadow); }
  .sidebar.open { transform: translateX(0); }
  .content { padding: 16px; }
}

/* Desktop: allow hiding sidebar via the top-left button */
@media (min-width: 901px) {
  .layout.sidebar-hidden { grid-template-columns: 0 1fr; }
  .layout.sidebar-hidden .sidebar { width: 0; padding: 0; border-right: none; overflow: hidden; }
}
</style>
