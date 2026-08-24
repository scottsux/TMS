<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader :title="`订单详情 #${id}`" subtitle="详情页作为流程中枢，集中处理重量、打包完成和发货动作。">
      <template #actions>
        <router-link class="btn" to="/orders">返回订单列表</router-link>
      </template>
    </PageHeader>

    <div v-if="order" class="detail-layout">
      <section class="detail-main">
        <article class="card section-card">
          <div class="section-head">
            <div>
              <div class="section-title">订单状态</div>
              <div class="page-subtitle">当前状态和关键摘要</div>
            </div>
            <StatusBadge type="order" :status="order.status" :label="order.statusZh" />
          </div>
          <div class="metric-grid compact-grid">
            <div class="metric-card">
              <div class="metric-label">客户</div>
              <div class="metric-value text-sm">{{ order.customer }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">包裹数</div>
              <div class="metric-value">{{ order.parcels.length }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">实际重量</div>
              <div class="metric-value">{{ order.actual_weight.toFixed(2) }}kg</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">体积重量</div>
              <div class="metric-value">{{ order.volumetric_weight.toFixed(2) }}kg</div>
            </div>
          </div>
        </article>

        <article v-if="order.forwarding" class="card section-card">
          <div class="section-head">
            <div>
              <div class="section-title">转运信息</div>
              <div class="page-subtitle">收件信息和运输服务</div>
            </div>
          </div>
          <div class="forwarding-grid">
            <div><span class="field-label">渠道</span><div>{{ channelZh(order.forwarding.channel) }}</div></div>
            <div><span class="field-label">目的地</span><div>{{ order.forwarding.destination || '-' }}</div></div>
            <div><span class="field-label">服务</span><div>{{ serviceZh(order.forwarding.service) }}</div></div>
            <div><span class="field-label">收件人</span><div>{{ order.forwarding.consignee?.name || '-' }}</div></div>
            <div><span class="field-label">州 / 省</span><div>{{ order.forwarding.consignee?.state || '-' }}</div></div>
            <div><span class="field-label">城市</span><div>{{ order.forwarding.consignee?.city || '-' }}</div></div>
            <div><span class="field-label">电话</span><div>{{ order.forwarding.consignee?.phone || '-' }}</div></div>
            <div><span class="field-label">邮箱</span><div>{{ order.forwarding.consignee?.email || '-' }}</div></div>
            <div><span class="field-label">邮编</span><div>{{ order.forwarding.consignee?.postcode || '-' }}</div></div>
            <div class="full-span"><span class="field-label">地址</span><div>{{ order.forwarding.consignee?.address || '-' }}</div></div>
          </div>
        </article>

        <article class="card section-card">
          <div class="section-head">
            <div>
              <div class="section-title">包裹清单</div>
              <div class="page-subtitle">查看本订单包含的包裹和备注</div>
            </div>
          </div>
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>包裹 ID</th>
                  <th>运单号</th>
                  <th>品名</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in order.parcels" :key="p.id">
                  <td>#{{ p.id }}</td>
                  <td>{{ p.tracking }}</td>
                  <td>{{ p.desc || '-' }}</td>
                  <td>{{ p.note || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article v-if="can('weight:update')" class="card section-card">
          <div class="section-head">
            <div>
              <div class="section-title">重量处理</div>
              <div class="page-subtitle">保存实际重量，并用公式计算体积重量。</div>
            </div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="action-box">
              <label class="field-label">实际重量(kg)</label>
              <input v-model.number="actualWeightInput" class="input" type="number" min="0" step="0.01" />
              <div class="section-note">当前值 {{ order.actual_weight.toFixed(2) }} kg</div>
              <button class="btn btn-primary" :disabled="sending || !canUpdateWeight || !canSaveActual" @click="saveActualWeight">保存实重</button>
            </div>
            <div class="action-box">
              <label class="field-label">体积重量计算</label>
              <div class="grid gap-3 md:grid-cols-3">
                <input v-model.number="len" class="input" type="number" min="0" step="0.1" placeholder="长(cm)" />
                <input v-model.number="wid" class="input" type="number" min="0" step="0.1" placeholder="宽(cm)" />
                <input v-model.number="hei" class="input" type="number" min="0" step="0.1" placeholder="高(cm)" />
              </div>
              <div class="section-note">公式：长 × 宽 × 高 ÷ 6000，当前 {{ order.volumetric_weight.toFixed(2) }} kg</div>
              <button class="btn" :disabled="sending || !canUpdateWeight || !canCalcVol" @click="calcAndSaveVolWeight">计算并保存</button>
            </div>
          </div>
        </article>
      </section>

      <aside class="detail-side">
        <article class="card section-card">
          <div class="section-title">费用摘要</div>
          <div class="summary-list">
            <div><span>订单状态</span><strong>{{ order.statusZh }}</strong></div>
            <div><span>实际重量</span><strong>{{ order.actual_weight.toFixed(2) }} kg</strong></div>
            <div><span>体积重量</span><strong>{{ order.volumetric_weight.toFixed(2) }} kg</strong></div>
            <div><span>最终价格</span><strong>${{ order.final_price.toFixed(2) }}</strong></div>
          </div>
        </article>

        <article v-if="can('task:complete') || can('order:ship')" class="card section-card">
          <div class="section-title">下一步动作</div>
          <div class="page-subtitle">高风险动作集中在这里，避免分散到列表页。</div>
          <div v-if="msg" :style="{ color: msgType === 'ok' ? 'var(--success)' : 'var(--danger)' }" class="section-note" style="margin-top: 10px;">
            {{ msg }}
          </div>
          <div class="side-actions">
            <button v-if="can('task:complete') && order.status === 'PACKING'" class="btn btn-primary" :disabled="sending" @click="completePacking">
              打包完毕，转为待发货
            </button>
            <button v-if="can('order:ship') && order.status === 'READY_TO_SHIP'" class="btn btn-primary" :disabled="sending" @click="shipAndNotify">
              发货完成并通知客户
            </button>
          </div>
        </article>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { zh } from '../constants/enums'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'

const route = useRoute()
const router = useRouter()
const id = computed(() => route.params.id)
const order = ref(null)
const sending = ref(false)
const msg = ref('')
const msgType = ref('ok')
const taskId = ref(null)
const auth = useAuthStore()
const { role } = storeToRefs(auth)
const { can } = auth
const actualWeightInput = ref(0)
const len = ref(0)
const wid = ref(0)
const hei = ref(0)

const canSaveActual = computed(() => {
  const cur = Number(order.value?.actual_weight ?? 0)
  const next = Number(actualWeightInput.value ?? 0)
  return Number.isFinite(next) && next >= 0 && Math.abs(next - cur) > 1e-6
})

const canCalcVol = computed(() => Number(len.value) > 0 && Number(wid.value) > 0 && Number(hei.value) > 0)

const canUpdateWeight = computed(() => {
  if (!order.value || !can('weight:update')) return false
  if (role.value === 'operator') return order.value.status === 'PACKING'
  return ['PACKING', 'READY_TO_SHIP'].includes(order.value.status)
})

onMounted(async () => {
  await refreshOrder()
})

function channelZh(value) {
  if (!value) return '-'
  return value === 'air' ? '空运' : value === 'sea' ? '海运' : value
}

function serviceZh(value) {
  if (!value) return '-'
  return value === 'express' ? '特快' : value === 'economy' ? '普快' : value
}

async function completePacking() {
  if (!taskId.value) return
  try {
    sending.value = true
    if (!window.confirm('确认将该订单标记为打包完毕，并转为待发货？')) return
    await api.patch(`/tasks/${taskId.value}/complete`, { actual_weight: order.value?.actual_weight || 0 })
    await refreshOrder()
    msg.value = '已标记打包完毕，订单进入待发货'
    msgType.value = 'ok'
  } catch (error) {
    msg.value = `操作失败：${error?.message || '未知错误'}`
    msgType.value = 'err'
  } finally {
    sending.value = false
  }
}

async function shipAndNotify() {
  try {
    sending.value = true
    if (!window.confirm('确认发货完成并通知客户？')) return
    const raw = await api.get(`/orders/${id.value}`)
    await api.patch(`/orders/${id.value}/ship`, {})
    await api.post('/notify/shipped', { customer_id: raw.customer_id || 0, message: 'shipped' })
    await refreshOrder()
    msg.value = '已发货并通知客户'
    msgType.value = 'ok'
    router.push('/orders')
  } catch (error) {
    msg.value = `操作失败：${error?.message || '未知错误'}`
    msgType.value = 'err'
  } finally {
    sending.value = false
  }
}

async function refreshOrder() {
  try {
    const o = await api.get(`/orders/${id.value}`)
    order.value = {
      status: o.status,
      customer_id: o.customer_id,
      customer: o.customer_name || o.customer_id,
      statusZh: zh.order[o.status] || o.status,
      actual_weight: o.actual_weight || 0,
      final_price: o.final_price ?? 0,
      volumetric_weight: o.volumetric_weight || 0,
      parcels: (o.parcel_ids || []).map((pid) => ({ id: pid, tracking: '', note: '' })),
      forwarding: o.forwarding || null,
    }
    actualWeightInput.value = order.value.actual_weight
    const parcels = await api.get('/parcels')
    const map = new Map(parcels.map((p) => [p.id, {
      tracking: p.tracking_number,
      desc: p.item_description || '',
      note: p.note || '',
    }]))
    order.value.parcels = order.value.parcels.map((p) => ({
      id: p.id,
      tracking: map.get(p.id)?.tracking || `P${p.id}`,
      desc: map.get(p.id)?.desc || '',
      note: map.get(p.id)?.note || '',
    }))
    if (can('task:view')) {
      const tasks = await api.get(`/tasks?order_id=${id.value}`)
      taskId.value = tasks[0]?.id ?? null
    } else {
      taskId.value = null
    }
  } catch {
    order.value = null
    taskId.value = null
  }
}

async function saveVolWeight(value) {
  msg.value = ''
  sending.value = true
  try {
    await api.patch(`/orders/${id.value}/volumetric`, { volumetric_weight: value })
    await refreshOrder()
    msg.value = '已保存体积重量'
    msgType.value = 'ok'
  } catch (error) {
    msg.value = `保存失败：${error?.message || '未知错误'}`
    msgType.value = 'err'
  } finally {
    sending.value = false
  }
}

function calcAndSaveVolWeight() {
  const value = Number((((Number(len.value) || 0) * (Number(wid.value) || 0) * (Number(hei.value) || 0)) / 6000).toFixed(2))
  saveVolWeight(value)
}

async function saveActualWeight() {
  msg.value = ''
  sending.value = true
  try {
    await api.patch(`/orders/${id.value}/actual_weight`, { actual_weight: Number(actualWeightInput.value) || 0 })
    await refreshOrder()
    msg.value = '已保存实重'
    msgType.value = 'ok'
  } catch (error) {
    msg.value = `保存失败：${error?.message || '未知错误'}`
    msgType.value = 'err'
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.detail-layout { display: grid; gap: 16px; grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.9fr); }
.detail-main { display: grid; gap: 16px; }
.detail-side { display: grid; gap: 16px; align-content: start; }
.section-card { padding: 16px; }
.section-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 14px; }
.compact-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.compact-grid .metric-card { padding: 14px; background: var(--surface-subtle); }
.compact-grid .metric-value { font-size: 20px; }
.forwarding-grid { display: grid; gap: 12px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.full-span { grid-column: 1 / -1; }
.action-box { display: grid; gap: 10px; padding: 14px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface-subtle); }
.summary-list { display: grid; gap: 10px; margin-top: 14px; }
.summary-list div { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
.summary-list strong { color: var(--text-h); font-variant-numeric: tabular-nums; }
.side-actions { display: grid; gap: 10px; margin-top: 14px; }

@media (max-width: 1100px) {
  .detail-layout { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .compact-grid,
  .forwarding-grid { grid-template-columns: 1fr; }
}
</style>
