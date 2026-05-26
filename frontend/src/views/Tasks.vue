<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader title="任务" subtitle="接入真实打包任务，按待办、进行中和已完成组织仓库操作。打包完成后会停留在进行中待发货。">
      <template #actions>
        <button class="btn" :disabled="busy" @click="refresh">刷新</button>
      </template>
    </PageHeader>

    <section class="board">
      <article class="col">
        <div class="col-header">待办 {{ todo.length }}</div>
        <div v-if="todo.length">
          <div v-for="t in todo" :key="t.id" class="item">
            <div class="item-head">
              <div class="title">{{ t.orderNo }}</div>
              <StatusBadge type="task" :status="t.badgeStatus" :label="t.statusZh" />
            </div>
            <div class="meta">客户：{{ t.customer }}</div>
            <div class="meta">包裹数：{{ t.parcelCount }}</div>
            <div class="actions">
              <button v-if="role === 'operator'" class="btn btn-primary" :disabled="busy" @click="startTask(t)">开始处理</button>
              <router-link class="btn" :to="`/orders/${t.orderId}`">查看订单</router-link>
            </div>
          </div>
        </div>
        <div v-else class="empty-wrap">
          <EmptyState title="没有待办任务" description="新的打包申请会自动生成待办任务。" />
        </div>
      </article>

      <article class="col">
        <div class="col-header">进行中 {{ inprogress.length }}</div>
        <div v-if="inprogress.length">
          <div v-for="t in inprogress" :key="t.id" class="item">
            <div class="item-head">
              <div class="title">{{ t.orderNo }}</div>
              <StatusBadge type="task" :status="t.badgeStatus" :label="t.statusZh" />
            </div>
            <div class="meta">客户：{{ t.customer }}</div>
            <div class="meta">包裹数：{{ t.parcelCount }}</div>
            <div v-if="t.orderStatus === 'READY_TO_SHIP'" class="meta">当前阶段：待发货</div>
            <div class="actions">
              <router-link class="btn btn-primary" :to="`/orders/${t.orderId}`">{{ t.orderStatus === 'READY_TO_SHIP' ? '去发货' : '填写重量并完成' }}</router-link>
            </div>
          </div>
        </div>
        <div v-else class="empty-wrap">
          <EmptyState title="没有进行中的任务" description="操作员开始处理后，任务会移动到这里。" />
        </div>
      </article>

      <article class="col">
        <div class="col-header">已完成 {{ done.length }}</div>
        <div v-if="done.length">
          <div v-for="t in done" :key="t.id" class="item">
            <div class="item-head">
              <div class="title">{{ t.orderNo }}</div>
              <StatusBadge type="task" :status="t.badgeStatus" :label="t.statusZh" />
            </div>
            <div class="meta">客户：{{ t.customer }}</div>
            <div class="meta">包裹数：{{ t.parcelCount }}</div>
            <div class="meta">实际重量：{{ (t.actualWeight || 0).toFixed(2) }} kg</div>
          </div>
        </div>
        <div v-else class="empty-wrap">
          <EmptyState title="没有已完成任务" description="任务完成后会显示重量结果。" />
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import { zh } from '../constants/enums'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'

const busy = ref(false)
const rows = ref([])
const role = useAuthStore().role

onMounted(async () => {
  await refresh()
})

const todo = computed(() => rows.value.filter((row) => row.status === 'TODO'))
const inprogress = computed(() => rows.value.filter((row) => row.status === 'IN_PROGRESS'))
const done = computed(() => rows.value.filter((row) => row.status === 'DONE'))

async function refresh() {
  try {
    busy.value = true
    const [tasks, orders] = await Promise.all([api.get('/tasks'), api.get('/orders')])
    const orderMap = new Map(orders.map((o) => [o.id, o]))
    rows.value = tasks.map((task) => {
      const order = orderMap.get(task.order_id) || {}
      return {
        id: task.id,
        orderId: task.order_id,
        orderNo: order.order_no || `ORD-${String(task.order_id).padStart(4, '0')}`,
        customer: order.customer_name || order.customer_id || '-',
        parcelCount: (order.parcel_ids || []).length,
        status: task.status,
        badgeStatus: task.status === 'IN_PROGRESS' && order.status === 'READY_TO_SHIP' ? 'READY_TO_SHIP' : task.status,
        orderStatus: order.status || '',
        statusZh: task.status === 'IN_PROGRESS' && order.status === 'READY_TO_SHIP'
          ? '待发货'
          : (zh.task[task.status] || task.status),
        actualWeight: task.actual_weight || 0,
      }
    })
  } catch {
    rows.value = []
  } finally {
    busy.value = false
  }
}

async function startTask(task) {
  try {
    busy.value = true
    await api.patch(`/tasks/${task.id}/start`, {})
    await refresh()
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.board { display: grid; gap: 16px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.col {
  padding: 14px 16px 16px;
  overflow: hidden;
  min-height: 280px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: var(--surface);
}
.col-header { padding: 0 0 12px; font-size: 14px; font-weight: 600; color: var(--text-h); background: transparent; }
.item {
  padding: 14px 16px;
  display: grid;
  gap: 8px;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface);
}
.item + .item { margin-top: 10px; }
.item-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.title { font-size: 14px; color: var(--text-h); font-weight: 600; }
.meta { font-size: 12px; color: var(--text-muted); }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.empty-wrap :deep(.empty-state) {
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface);
  padding: 28px 18px;
}

@media (max-width: 1024px) {
  .board { grid-template-columns: 1fr; }
}
</style>
