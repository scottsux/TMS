<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader title="订单" subtitle="集中查看待打包、打包中和已完成订单，主操作收敛到详情页。">
      <template #actions>
        <button class="btn" :disabled="busy" @click="refresh">刷新</button>
      </template>
    </PageHeader>

    <section class="metric-grid" style="margin-bottom: 16px;">
      <article class="metric-card">
        <div class="metric-label">订单总数</div>
        <div class="metric-value">{{ filteredSorted.length }}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">待打包</div>
        <div class="metric-value">{{ countByStatus('READY_TO_PACK') }}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">打包中</div>
        <div class="metric-value">{{ countByStatus('PACKING') }}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">已完成金额</div>
        <div class="metric-value">${{ totalCompletedAmount.toFixed(2) }}</div>
      </article>
    </section>

    <section class="toolbar toolbar-grid">
      <div class="toolbar-span-3">
        <label class="field-label">运单号</label>
        <input v-model.trim="qTracking" class="input" placeholder="搜索关联包裹运单号" />
      </div>
      <div v-if="role !== 'customer'" class="toolbar-span-3">
        <label class="field-label">客户</label>
        <input v-model.trim="qCustomer" class="input" placeholder="搜索客户名" />
      </div>
      <div class="toolbar-span-3">
        <label class="field-label">订单状态</label>
        <select v-model="status" class="input">
          <option value="">全部状态</option>
          <option value="DRAFT">草稿</option>
          <option value="READY_TO_PACK">待打包</option>
          <option value="PACKING">打包中</option>
          <option value="COMPLETED">已完成</option>
        </select>
      </div>
      <div class="toolbar-span-3">
        <label class="field-label">排序</label>
        <select v-model="sortBy" class="input">
          <option value="latest">最新创建</option>
          <option value="oldest">最早创建</option>
          <option value="amount_up">金额升序</option>
          <option value="amount_down">金额降序</option>
        </select>
      </div>
      <div class="toolbar-span-3">
        <label class="field-label">开始时间</label>
        <input v-model="dateFrom" class="input" type="datetime-local" />
      </div>
      <div class="toolbar-span-3">
        <label class="field-label">结束时间</label>
        <input v-model="dateTo" class="input" type="datetime-local" />
      </div>
      <div class="toolbar-span-6 page-actions" style="justify-content: flex-end; align-self: end;">
        <button class="btn" @click="resetFilters">清空筛选</button>
        <div class="section-note">共 {{ filteredSorted.length }} 条结果</div>
      </div>
    </section>

    <section class="card">
      <div class="table-wrap">
        <table v-if="filteredSorted.length" class="table">
          <thead>
            <tr>
              <th>下单时间</th>
              <th>订单号</th>
              <th v-if="role !== 'customer'">客户</th>
              <th class="num">包裹数</th>
              <th>状态</th>
              <th class="num">实重(kg)</th>
              <th class="num">体积重(kg)</th>
              <th class="num">最终价格</th>
              <th class="num">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in filteredSorted" :key="o.id">
              <td>{{ dateTimeShort(o.created_at) }}</td>
              <td>{{ o.order_no || `ORD-${String(o.id).padStart(4, '0')}` }}</td>
              <td v-if="role !== 'customer'">{{ o.customer_name ?? o.customer }}</td>
              <td class="num">{{ o.parcels.length }}</td>
              <td>
                <StatusBadge type="order" :status="o.status" :label="mapStatus(o.status)" />
              </td>
              <td class="num">{{ o.actual_weight.toFixed(2) }}</td>
              <td class="num">{{ o.volumetric_weight.toFixed(2) }}</td>
              <td class="num">${{ o.final_price.toFixed(2) }}</td>
              <td class="num">
                <div class="row-actions">
                  <router-link class="btn" :to="`/orders/${o.id}`">查看</router-link>
                  <button v-if="role !== 'customer' && o.status === 'READY_TO_PACK'" class="btn" :disabled="busy" @click="start(o)">开始打包</button>
                  <button v-if="can('order:create')" class="btn btn-primary" :disabled="busy" @click="openAdjust(o)">调整包裹</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="没有符合条件的订单" description="调整筛选条件后再试，或等待新的打包申请生成订单。" />
      </div>
    </section>

    <div v-if="modalOpen" class="modal">
      <div class="modal-card">
        <div class="modal-header">
          调整订单包裹
          <button class="close" @click="modalOpen = false">×</button>
        </div>
        <div class="modal-body">
          <div class="page-subtitle" style="margin-bottom: 12px;">
            当前订单：{{ targetOrder?.order_no || `ORD-${String(targetOrder?.id || '').padStart(4, '0')}` }}
          </div>
          <div class="grid gap-3">
            <div>
              <label class="field-label">新增包裹 ID</label>
              <input v-model="addInput" class="input" placeholder="例如 5,6,7" />
            </div>
            <div>
              <label class="field-label">移除包裹 ID</label>
              <input v-model="removeInput" class="input" placeholder="例如 2,3" />
            </div>
            <div class="section-note">会校验包裹是否存在、是否被占用，以及客户是否一致。</div>
          </div>
        </div>
        <div class="modal-footer">
          <span v-if="msg" :style="{ color: msgType === 'ok' ? 'var(--success)' : 'var(--danger)' }" class="section-note">{{ msg }}</span>
          <button class="btn" @click="modalOpen = false">取消</button>
          <button class="btn btn-primary" :disabled="busy" @click="applyAdjust">应用调整</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'

const rows = ref([])
const busy = ref(false)
const poll = ref(null)
const { role, user, can } = useAuthStore()
const qTracking = ref('')
const qCustomer = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const status = ref('')
const sortBy = ref('latest')
const trackingIndex = ref(new Map())
const modalOpen = ref(false)
const targetOrder = ref(null)
const addInput = ref('')
const removeInput = ref('')
const msg = ref('')
const msgType = ref('ok')

onMounted(async () => {
  await refresh()
  startPoll()
})

onUnmounted(() => {
  if (poll.value) clearInterval(poll.value)
})

const filteredSorted = computed(() => {
  let list = rows.value.slice()
  if (status.value) list = list.filter((o) => o.status === status.value)
  const from = dateFrom.value ? new Date(dateFrom.value) : null
  const to = dateTo.value ? new Date(dateTo.value) : null
  if (from) list = list.filter((o) => o.created_at && new Date(o.created_at) >= from)
  if (to) list = list.filter((o) => o.created_at && new Date(o.created_at) <= to)
  if (qTracking.value.trim()) {
    const keyword = qTracking.value.trim().toLowerCase()
    list = list.filter((o) => o.parcels.some((pid) => (trackingIndex.value.get(pid) || '').toLowerCase().includes(keyword)))
  }
  if (qCustomer.value.trim() && role !== 'customer') {
    const keyword = qCustomer.value.trim().toLowerCase()
    list = list.filter((o) => (o.customer_name || '').toLowerCase().includes(keyword))
  }
  if (sortBy.value === 'latest') list.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
  else if (sortBy.value === 'oldest') list.sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)))
  else if (sortBy.value === 'amount_up') list.sort((a, b) => (a.final_price || 0) - (b.final_price || 0))
  else if (sortBy.value === 'amount_down') list.sort((a, b) => (b.final_price || 0) - (a.final_price || 0))
  return list
})

const totalCompletedAmount = computed(() => filteredSorted.value
  .filter((row) => row.status === 'COMPLETED')
  .reduce((sum, row) => sum + (row.final_price || 0), 0))

function countByStatus(target) {
  return filteredSorted.value.filter((row) => row.status === target).length
}

function mapStatus(value) {
  return ({ DRAFT: '草稿', READY_TO_PACK: '待打包', PACKING: '打包中', COMPLETED: '已完成' }[value] || value)
}

function dateTimeShort(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return String(ts)
  const Y = d.getFullYear()
  const M = String(d.getMonth() + 1).padStart(2, '0')
  const D = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${Y}-${M}-${D} ${h}:${m}`
}

async function findTaskId(orderId) {
  const list = await api.get(`/tasks?order_id=${orderId}`)
  return list[0]?.id
}

async function refresh() {
  try {
    let url = '/orders'
    if (role === 'customer') url += `?customer_id=${user?.id ?? 1}`
    const data = await api.get(url)
    rows.value = data.map((o) => ({
      id: o.id,
      customer: o.customer_id,
      customer_name: o.customer_name,
      parcels: o.parcel_ids || [],
      status: o.status,
      actual_weight: o.actual_weight || 0,
      volumetric_weight: o.volumetric_weight || 0,
      final_price: o.final_price ?? 0,
      created_at: o.created_at,
      order_no: o.order_no || null,
    }))
    const parcelUrl = role === 'customer' ? `/parcels?customer_id=${user?.id ?? 1}` : '/parcels'
    const plist = await api.get(parcelUrl)
    trackingIndex.value = new Map(plist.map((p) => [p.id, p.tracking_number]))
  } catch {
    rows.value = []
    trackingIndex.value = new Map()
  }
}

function startPoll() {
  if (poll.value) clearInterval(poll.value)
  poll.value = setInterval(() => {
    refresh()
  }, 10000)
}

function resetFilters() {
  qTracking.value = ''
  qCustomer.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  status.value = ''
  sortBy.value = 'latest'
}

async function start(order) {
  try {
    busy.value = true
    const tid = await findTaskId(order.id)
    if (!tid) return
    await api.patch(`/tasks/${tid}/start`, {})
    await refresh()
  } finally {
    busy.value = false
  }
}

function openAdjust(order) {
  targetOrder.value = order
  addInput.value = ''
  removeInput.value = ''
  msg.value = ''
  msgType.value = 'ok'
  modalOpen.value = true
}

function parseIds(text) {
  if (!text.trim()) return []
  return text.split(',').map((s) => Number(s.trim())).filter((n) => Number.isFinite(n))
}

async function applyAdjust() {
  if (!targetOrder.value) return
  msg.value = ''
  try {
    busy.value = true
    await api.patch(`/orders/${targetOrder.value.id}/parcels`, {
      add: parseIds(addInput.value),
      remove: parseIds(removeInput.value),
    })
    msg.value = '已更新订单包裹'
    msgType.value = 'ok'
    await refresh()
    modalOpen.value = false
  } catch (error) {
    msg.value = error?.message || '操作失败'
    msgType.value = 'err'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.row-actions { display: inline-flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
</style>
