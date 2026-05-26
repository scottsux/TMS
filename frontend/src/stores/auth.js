import { defineStore } from 'pinia'
import api from '../api/client'

const PERMISSIONS = {
  customer: new Set(['parcel:create', 'parcel:edit']),
  staff: new Set([
    'parcel:create', 'parcel:edit', 'parcel:approve', 'parcel:arrived',
    'order:create', 'task:assign', 'price:update'
  ]),
  operator: new Set(['task:start', 'task:complete'])
}

const STORAGE_KEY = 'tms_auth'

export const useAuthStore = defineStore('auth', {
  state: () => {
    let initial = { token: null, role: null, user: null }
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) initial = JSON.parse(raw)
    } catch {}
    return initial
  },
  getters: {
    isAuthed: (s) => !!s.token,
  },
  actions: {
    async login({ email, password }) {
      const res = await api.post('/auth/login', { email, password })
      this.role = res.role
      this.token = res.token
      this.user = res.user
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: this.token, role: this.role, user: this.user })) } catch {}
    },
    logout() {
      this.token = null
      this.role = null
      this.user = null
      try { localStorage.removeItem(STORAGE_KEY) } catch {}
    },
    can(action) {
      if (!this.role) return false
      return PERMISSIONS[this.role]?.has(action) || false
    },
  }
})
