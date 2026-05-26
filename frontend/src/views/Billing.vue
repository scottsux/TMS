<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader title="结算" subtitle="围绕待结算订单、计价规则和人工覆盖建立业务后台视图。">
      <template #actions>
        <button class="btn" :disabled="busy" @click="refresh">刷新</button>
      </template>
    </PageHeader>

    <section class="metric-grid" style="margin-bottom: 16px;">
      <article class="metric-card">
        <div class="metric-label">待结算订单</div>
        <div class="metric-value">{{ completedOrders.length }}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">待结算金额</div>
        <div class="metric-value">${{ pendingAmount.toFixed(2) }}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">平均订单重量</div>
        <div class="metric-value">{{ averageWeight.toFixed(2) }}kg</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">人工覆盖次数</div>
        <div class="metric-value">{{ overrides.length }}</div>
      </article>
    </section>

    <div class="billing-layout">
      <section class="card section-card">
        <div class="section-head">
          <div>
            <div class="section-title">待结算订单</div>
            <div class="page-subtitle">只展示已完成订单，方便员工补录价格或人工覆盖。</div>
          </div>
        </div>
        <div class="table-wrap">
          <table v-if="completedOrders.length" class="table">
            <thead>
              <tr>
                <th>订单</th>
                <th>客户</th>
                <th class="num">实际重量</th>
                <th class="num">当前价格</th>
                <th class="num">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in completedOrders" :key="row.id">
                <td>{{ row.order_no || `ORD-${String(row.id).padStart(4, '0')}` }}</td>
                <td>{{ row.customer_name || row.customer_id }}</td>
                <td class="num">{{ (row.actual_weight || 0).toFixed(2) }} kg</td>
                <td class="num">${{ (row.final_price || 0).toFixed(2) }}</td>
                <td class="num">
                  <button class="btn" @click="selectOrder(row)">计价 / 覆盖</button>
                </td>
              </tr>
            </tbody>
          </table>
          <EmptyState v-else title="暂无待结算订单" description="完成打包后的订单会自动出现在这里。" />
        </div>
      </section>

      <section class="card section-card">
        <div class="section-head">
          <div>
            <div class="section-title">计价规则</div>
            <div class="page-subtitle">按实际重量、每公斤单价和额外费用计算，也支持人工覆盖。</div>
          </div>
        </div>
        <div class="grid gap-3">
          <div>
            <label class="field-label">选中订单</label>
            <div class="section-note">{{ selectedOrderLabel }}</div>
          </div>
          <div class="grid gap-3 md:grid-cols-3">
            <div>
              <label class="field-label">实际重量(kg)</label>
              <input v-model.number="actual_weight" class="input" type="number" min="0" step="0.01" />
            </div>
            <div>
              <label class="field-label">单价</label>
              <input v-model.number="rate_per_kg" class="input" type="number" min="0" step="1" />
            </div>
            <div>
              <label class="field-label">额外费用</label>
              <input v-model.number="extra_fee" class="input" type="number" min="0" step="1" />
            </div>
          </div>
          <div class="summary-box">
            <div class="summary-row"><span>自动计算结果</span><strong>${{ final_price.toFixed(2) }}</strong></div>
            <div class="summary-row"><span>人工覆盖价格</span><input v-model.number="override_price" class="input compact-input" type="number" min="0" step="0.01" /></div>
          </div>
          <div class="page-actions" style="justify-content: flex-end;">
            <button class="btn" :disabled="!selectedOrder || busy" @click="applyPrice">保存计价</button>
            <button class="btn btn-primary" :disabled="!selectedOrder || busy || override_price === null" @click="applyOverride">覆盖最终价格</button>
          </div>
          <div v-if="message" :style="{ color: messageType === 'ok' ? 'var(--success)' : 'var(--danger)' }" class="section-note">{{ message }}</div>
        </div>
      </section>
    </div>

    <section class="card section-card" style="margin-top: 16px;">
      <div class="section-head">
        <div>
          <div class="section-title">人工覆盖记录</div>
          <div class="page-subtitle">MVP 阶段保存在前端，用于追踪价格调整。</div>
        </div>
      </div>
      <div class="table-wrap">
        <table v-if="overrides.length" class="table">
          <thead>
            <tr>
              <th>时间</th>
              <th>订单</th>
              <th class="num">覆盖价格</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in overrides" :key="`${item.id}-${item.ts}`">
              <td>{{ item.ts }}</td>
              <td>{{ item.order_no }}</td>
              <td class="num">${{ item.price.toFixed(2) }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="暂无覆盖记录" description="当员工手动修改最终价格后，这里会出现记录。" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import api from '../api/client'

const busy = ref(false)
const rows = ref([])
const selectedOrder = ref(null)
const actual_weight = ref(0)
const rate_per_kg = ref(50)
const extra_fee = ref(0)
const override_price = ref(null)
const message = ref('')
const messageType = ref('ok')
const overrides = ref([])

onMounted(async () => {
  loadOverrides()
  await refresh()
})

const completedOrders = computed(() => rows.value.filter((row) => row.status === 'COMPLETED'))
const pendingAmount = computed(() => completedOrders.value.reduce((sum, row) => sum + (row.final_price || 0), 0))
const averageWeight = computed(() => {
  if (!completedOrders.value.length) return 0
  return completedOrders.value.reduce((sum, row) => sum + (row.actual_weight || 0), 0) / completedOrders.value.length
})
const final_price = computed(() => {
  const result = (Number(actual_weight.value) || 0) * (Number(rate_per_kg.value) || 0) + (Number(extra_fee.value) || 0)
  return Math.round(result * 100) / 100
})
const selectedOrderLabel = computed(() => {
  if (!selectedOrder.value) return '未选择订单'
  return `${selectedOrder.value.order_no || `ORD-${String(selectedOrder.value.id).padStart(4, '0')}`} · ${selectedOrder.value.customer_name || selectedOrder.value.customer_id}`
})

async function refresh() {
  try {
    rows.value = await api.get('/orders')
  } catch {
    rows.value = []
  }
}

function selectOrder(order) {
  selectedOrder.value = order
  actual_weight.value = Number(order.actual_weight || 0)
  override_price.value = order.final_price ?? null
  message.value = ''
}

async function applyPrice() {
  if (!selectedOrder.value) return
  try {
    busy.value = true
    await api.patch(`/orders/${selectedOrder.value.id}/price`, {
      actual_weight: Number(actual_weight.value) || 0,
      rate_per_kg: Number(rate_per_kg.value) || 0,
      extra_fee: Number(extra_fee.value) || 0,
    })
    message.value = '已保存自动计价结果'
    messageType.value = 'ok'
    await refresh()
  } catch (error) {
    message.value = error?.message || '保存失败'
    messageType.value = 'err'
  } finally {
    busy.value = false
  }
}

async function applyOverride() {
  if (!selectedOrder.value || override_price.value === null) return
  try {
    busy.value = true
    await api.patch(`/orders/${selectedOrder.value.id}/override_price`, {
      final_price: Number(override_price.value) || 0,
    })
    const order_no = selectedOrder.value.order_no || `ORD-${String(selectedOrder.value.id).padStart(4, '0')}`
    overrides.value.unshift({ id: selectedOrder.value.id, order_no, price: Number(override_price.value) || 0, ts: nowText() })
    persistOverrides()
    message.value = '已覆盖最终价格'
    messageType.value = 'ok'
    await refresh()
  } catch (error) {
    message.value = error?.message || '覆盖失败'
    messageType.value = 'err'
  } finally {
    busy.value = false
  }
}

function storageKey() {
  return 'tms_billing_overrides'
}

function persistOverrides() {
  try {
    localStorage.setItem(storageKey(), JSON.stringify(overrides.value))
  } catch {}
}

function loadOverrides() {
  try {
    overrides.value = JSON.parse(localStorage.getItem(storageKey()) || '[]')
  } catch {
    overrides.value = []
  }
}

function nowText() {
  const d = new Date()
  const Y = d.getFullYear()
  const M = String(d.getMonth() + 1).padStart(2, '0')
  const D = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${Y}-${M}-${D} ${h}:${m}`
}
</script>

<style scoped>
.billing-layout { display: grid; gap: 16px; grid-template-columns: minmax(0, 1.4fr) minmax(320px, 1fr); }
.section-card { padding: 16px; }
.section-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 14px; }
.summary-box { display: grid; gap: 10px; padding: 14px; border-radius: var(--radius); background: var(--surface-subtle); border: 1px solid var(--border); }
.summary-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.compact-input { width: 140px; }

@media (max-width: 1100px) {
  .billing-layout { grid-template-columns: 1fr; }
}
</style>
