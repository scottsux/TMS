<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader :title="dashboard.title" :subtitle="dashboard.subtitle">
      <template #actions>
        <button class="btn" :disabled="busy" @click="refresh">刷新</button>
      </template>
    </PageHeader>

    <section class="metric-grid dashboard-metrics">
      <article v-for="metric in dashboard.metrics" :key="metric.label" class="metric-card">
        <div class="metric-label">{{ metric.label }}</div>
        <div class="metric-value">{{ metric.value }}</div>
      </article>
    </section>

    <section class="toolbar toolbar-grid">
      <div class="toolbar-span-3">
        <label class="field-label">{{ dashboard.filterLabels[0] }}</label>
        <input v-model.trim="filterKeyword" class="input" :placeholder="dashboard.filterPlaceholders[0]" />
      </div>
      <div class="toolbar-span-3" v-if="dashboard.showSecondaryFilter">
        <label class="field-label">{{ dashboard.filterLabels[1] }}</label>
        <input v-model.trim="filterSecondary" class="input" :placeholder="dashboard.filterPlaceholders[1]" />
      </div>
      <div class="toolbar-span-3" v-else>
        <label class="field-label">{{ dashboard.filterLabels[1] }}</label>
        <input class="input" :value="dashboard.filterStaticValue" disabled />
      </div>
      <div class="toolbar-span-3">
        <label class="field-label">{{ dashboard.filterLabels[2] }}</label>
        <select v-model="filterStatus" class="input">
          <option value="">全部状态</option>
          <option v-for="item in dashboard.statusOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
      <div class="toolbar-span-12 page-actions dashboard-actions">
        <button class="btn" @click="resetFilters">清空筛选</button>
        <div class="section-note">共 {{ filteredRows.length }} 条结果</div>
      </div>
    </section>

    <section>
      <div class="table-wrap">
        <table v-if="filteredRows.length" class="table">
          <thead>
            <tr>
              <th>{{ dashboard.columns[0] }}</th>
              <th>{{ dashboard.columns[1] }}</th>
              <th>{{ dashboard.columns[2] }}</th>
              <th class="num">{{ dashboard.columns[3] }}</th>
              <th>{{ dashboard.columns[4] }}</th>
              <th class="num">{{ dashboard.columns[5] }}</th>
              <th class="num">{{ dashboard.columns[6] }}</th>
              <th class="num">{{ dashboard.columns[7] }}</th>
              <th class="num">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.id">
              <td>{{ row.time }}</td>
              <td>{{ row.title }}</td>
              <td>{{ row.owner }}</td>
              <td class="num">{{ row.count }}</td>
              <td>
                <StatusBadge :type="row.badge.type" :status="row.badge.status" :label="row.badge.label" />
              </td>
              <td class="num">{{ row.weight }}</td>
              <td class="num">{{ row.volume }}</td>
              <td class="num">{{ row.price }}</td>
              <td class="num">
                <router-link class="btn" :to="row.to">{{ row.action }}</router-link>
              </td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else :title="dashboard.empty.title" :description="dashboard.empty.description" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import { useAuthStore } from '../stores/auth'
import { zh } from '../constants/enums'
import api from '../api/client'

const auth = useAuthStore()
const { role } = storeToRefs(auth)
const busy = ref(false)
const parcels = ref([])
const orders = ref([])
const tasks = ref([])
const notifications = ref([])
const filterKeyword = ref('')
const filterSecondary = ref('')
const filterStatus = ref('')

onMounted(async () => {
  await refresh()
})

async function refresh() {
  try {
    busy.value = true
    const customerId = auth.user?.id ?? 1
    const parcelUrl = role.value === 'customer' ? `/parcels?customer_id=${customerId}` : '/parcels'
    const orderUrl = role.value === 'customer' ? `/orders?customer_id=${customerId}` : '/orders'
    const jobs = [api.get(parcelUrl), api.get(orderUrl)]
    if (role.value === 'staff' || role.value === 'operator') jobs.push(api.get('/tasks'))
    else jobs.push(Promise.resolve([]))
    if (role.value === 'operator') jobs.push(api.get('/notifications?type=ready_to_pack'))
    else jobs.push(Promise.resolve([]))
    const [parcelData, orderData, taskData, noticeData] = await Promise.all(jobs)
    parcels.value = parcelData
    orders.value = orderData
    tasks.value = taskData
    notifications.value = noticeData
  } catch {
    parcels.value = []
    orders.value = []
    tasks.value = []
    notifications.value = []
  } finally {
    busy.value = false
  }
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

function resetFilters() {
  filterKeyword.value = ''
  filterSecondary.value = ''
  filterStatus.value = ''
}

const baseRows = computed(() => {
  if (role.value === 'operator') {
    return tasks.value.map((task) => {
      const order = orders.value.find((item) => item.id === task.order_id) || {}
      return {
        id: `task-${task.id}`,
        title: order.order_no || `ORD-${String(task.order_id).padStart(4, '0')}`,
        owner: order.customer_name || String(order.customer_id || '-'),
        count: (order.parcel_ids || []).length,
        badge: { type: 'task', status: task.status, label: zh.task[task.status] || task.status },
        weight: `${Number(task.actual_weight || order.actual_weight || 0).toFixed(2)} kg`,
        volume: `${Number(order.volumetric_weight || 0).toFixed(2)} kg`,
        price: notifications.value.length && task.status === 'TODO' ? `${notifications.value.length} 条通知` : '-',
        time: dateTimeShort(order.created_at),
        to: `/orders/${task.order_id}`,
        action: task.status === 'TODO' ? '处理' : '查看',
        status: task.status,
        keyword: order.order_no || `ORD-${String(task.order_id).padStart(4, '0')}`,
        secondary: order.customer_name || String(order.customer_id || '-'),
      }
    })
  }

  return [...orders.value]
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
    .map((order) => ({
      id: `order-${order.id}`,
      title: order.order_no || `ORD-${String(order.id).padStart(4, '0')}`,
      owner: order.customer_name || String(order.customer_id),
      count: (order.parcel_ids || []).length,
      badge: { type: 'order', status: order.status, label: zh.order[order.status] || order.status },
      weight: `${Number(order.actual_weight || 0).toFixed(2)} kg`,
      volume: `${Number(order.volumetric_weight || 0).toFixed(2)} kg`,
      price: `$${Number(order.final_price || 0).toFixed(2)}`,
      time: dateTimeShort(order.created_at),
      to: `/orders/${order.id}`,
      action: '查看',
      status: order.status,
      keyword: order.order_no || `ORD-${String(order.id).padStart(4, '0')}`,
      secondary: order.customer_name || String(order.customer_id),
    }))
})

const filteredRows = computed(() => {
  return baseRows.value.filter((row) => {
    const matchKeyword = !filterKeyword.value.trim() || row.keyword.toLowerCase().includes(filterKeyword.value.trim().toLowerCase())
    const matchSecondary = !filterSecondary.value.trim() || row.secondary.toLowerCase().includes(filterSecondary.value.trim().toLowerCase())
    const matchStatus = !filterStatus.value || row.status === filterStatus.value
    return matchKeyword && matchSecondary && matchStatus
  })
})

const dashboard = computed(() => {
  if (role.value === 'customer') {
    return {
      title: '客户工作台',
      subtitle: '集中查看到仓、已申请打包和最近订单，主操作收敛到详情页。',
      metrics: [
        { label: '待到仓包裹', value: parcels.value.filter((p) => p.status === 'IN_TRANSIT').length },
        { label: '可申请打包', value: parcels.value.filter((p) => p.status === 'ARRIVED').length },
        { label: '已申请打包', value: parcels.value.filter((p) => p.status === 'PACK_REQUESTED').length },
        { label: '最近订单数', value: orders.value.length },
      ],
      filterLabels: ['订单号', '客户', '订单状态'],
      filterPlaceholders: ['搜索订单号', '我的订单', ''],
      filterStaticValue: '当前客户',
      showSecondaryFilter: false,
      statusOptions: [
        { value: 'DRAFT', label: '草稿' },
        { value: 'READY_TO_PACK', label: '待打包' },
        { value: 'PACKING', label: '打包中' },
        { value: 'READY_TO_SHIP', label: '待发货' },
        { value: 'COMPLETED', label: '已完成' },
      ],
      columns: ['下单时间', '订单号', '客户', '包裹数', '状态', '实重(kg)', '体积重(kg)', '最终价格'],
      empty: { title: '没有符合条件的订单', description: '提交打包申请后，订单会出现在这里。' },
    }
  }

  if (role.value === 'operator') {
    return {
      title: '仓库工作台',
      subtitle: '集中查看待办、进行中和已完成任务，主操作收敛到订单详情页。',
      metrics: [
        { label: '待办任务', value: tasks.value.filter((t) => t.status === 'TODO').length },
        { label: '进行中 / 待发货', value: tasks.value.filter((t) => t.status === 'IN_PROGRESS').length },
        { label: '已完成', value: tasks.value.filter((t) => t.status === 'DONE').length },
        { label: '打包申请通知', value: notifications.value.length },
      ],
      filterLabels: ['任务 / 订单号', '客户', '任务状态'],
      filterPlaceholders: ['搜索任务或订单号', '搜索客户名', ''],
      filterStaticValue: '',
      showSecondaryFilter: true,
      statusOptions: [
        { value: 'TODO', label: '待办' },
        { value: 'IN_PROGRESS', label: '进行中' },
        { value: 'DONE', label: '已完成' },
      ],
      columns: ['创建时间', '订单号', '客户', '包裹数', '状态', '实重(kg)', '体积重(kg)', '通知'],
      empty: { title: '没有符合条件的任务', description: '新的打包申请会在这里形成待办任务。' },
    }
  }

  return {
    title: '运营概览',
    subtitle: '集中查看待打包、打包中和已完成订单，主操作收敛到详情页。',
    metrics: [
      { label: '订单总数', value: orders.value.length },
      { label: '待打包', value: orders.value.filter((o) => o.status === 'READY_TO_PACK').length },
      { label: '待发货', value: orders.value.filter((o) => o.status === 'READY_TO_SHIP').length },
      { label: '已完成金额', value: `$${orders.value.filter((o) => o.status === 'COMPLETED').reduce((sum, item) => sum + Number(item.final_price || 0), 0).toFixed(2)}` },
    ],
    filterLabels: ['订单号', '客户', '订单状态'],
    filterPlaceholders: ['搜索订单号', '搜索客户名', ''],
    filterStaticValue: '',
    showSecondaryFilter: true,
    statusOptions: [
      { value: 'DRAFT', label: '草稿' },
      { value: 'READY_TO_PACK', label: '待打包' },
      { value: 'PACKING', label: '打包中' },
      { value: 'READY_TO_SHIP', label: '待发货' },
      { value: 'COMPLETED', label: '已完成' },
    ],
    columns: ['下单时间', '订单号', '客户', '包裹数', '状态', '实重(kg)', '体积重(kg)', '最终价格'],
    empty: { title: '没有符合条件的订单', description: '新的打包申请生成订单后，会显示在这里。' },
  }
})
</script>

<style scoped>
.dashboard-metrics {
  margin-bottom: 16px;
}

.dashboard-actions {
  justify-content: flex-end;
  align-self: end;
}

@media (max-width: 768px) {
  .dashboard-actions {
    justify-content: space-between;
  }
}
</style>
