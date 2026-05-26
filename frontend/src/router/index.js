import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '../views/Dashboard.vue'
import Orders from '../views/Orders.vue'
import Upload from '../views/Upload.vue'
import Tasks from '../views/Tasks.vue'
import Billing from '../views/Billing.vue'
import Login from '../views/Login.vue'
import Customers from '../views/Customers.vue'
import CustomerDetail from '../views/CustomerDetail.vue'
import Parcels from '../views/Parcels.vue'
import OrderDetail from '../views/OrderDetail.vue'

const routes = [
  { path: '/login', component: Login, meta: { title: '登录', public: true } },
  { path: '/', component: Dashboard, meta: { title: '仪表盘' } },
  { path: '/orders', component: Orders, meta: { title: '订单', roles: ['staff','operator','customer'] } },
  { path: '/orders/:id', component: OrderDetail, meta: { title: '订单详情', roles: ['staff','operator','customer'] } },
  { path: '/upload', component: Upload, meta: { title: '上传', roles: ['customer','staff'] } },
  { path: '/tasks', component: Tasks, meta: { title: '任务', roles: ['staff','operator'] } },
  { path: '/billing', component: Billing, meta: { title: '结算', roles: ['staff'] } },
  { path: '/customers', component: Customers, meta: { title: '客户', roles: ['staff'] } },
  { path: '/customers/:id', component: CustomerDetail, meta: { title: '客户详情', roles: ['staff'] } },
  { path: '/parcels', component: Parcels, meta: { title: '包裹', roles: ['staff','customer','operator'] } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  const suffix = 'TMS 管理台'
  const title = to.meta?.title ? `${to.meta.title} · ${suffix}` : suffix
  document.title = title
})

// auth guard
import { useAuthStore } from '../stores/auth'
router.beforeEach((to) => {
  // Force landing on /login once per browser session (even if authed),
  // but keep auth persistence so refresh后不退出。
  try {
    const hit = sessionStorage.getItem('first_visit_done')
    if (!hit && to.path !== '/login') {
      sessionStorage.setItem('first_visit_done', '1')
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  } catch {}

  const auth = useAuthStore()
  if (to.meta?.public) return true
  if (!auth.isAuthed) return { path: '/login', query: { redirect: to.fullPath } }
  const allow = to.meta?.roles
  if (allow && auth.role && !allow.includes(auth.role)) return { path: '/' }
  return true
})

export default router
