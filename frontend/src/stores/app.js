import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    dark: false,
    stats: {
      ordersPending: 234,
      ordersShipped: 1294,
      tasksOpen: 17,
      tasksDone: 42,
      revenue30d: 128430,
    },
  }),
  actions: {
    setDark(v) { this.dark = !!v },
    toggleDark() { this.dark = !this.dark },
  },
})

