<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader title="订单异常" subtitle="记录并处理不会改变订单状态机的运营异常。">
      <template #actions>
        <button class="btn" :disabled="busy" @click="refresh">刷新</button>
      </template>
    </PageHeader>

    <section class="metric-grid" style="margin-bottom: 16px;">
      <article class="metric-card"><div class="metric-label">未解决</div><div class="metric-value">{{ openCount }}</div></article>
      <article class="metric-card"><div class="metric-label">已解决</div><div class="metric-value">{{ resolvedCount }}</div></article>
      <article class="metric-card"><div class="metric-label">当前显示</div><div class="metric-value">{{ filteredRows.length }}</div></article>
    </section>

    <section class="exception-layout">
      <article v-if="can('exception:create')" class="card section-card">
        <div class="section-head"><div><div class="section-title">登记异常</div><div class="page-subtitle">异常会阻止发货和价格操作，直到员工解决。</div></div></div>
        <div class="grid gap-3">
          <div><label class="field-label">订单 ID</label><input v-model.number="orderId" class="input" type="number" min="1" /></div>
          <div><label class="field-label">异常类型</label><select v-model="type" class="input"><option v-for="item in typeOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></div>
          <div><label class="field-label">原因或说明</label><textarea v-model.trim="reason" class="input textarea" rows="4" placeholder="说明发生的情况和需要处理的事项" /></div>
          <div class="page-actions"><button class="btn btn-primary" :disabled="busy || !canSubmit" @click="createException">提交异常</button></div>
        </div>
      </article>

      <article class="card section-card">
        <div class="section-head"><div><div class="section-title">异常列表</div><div class="page-subtitle">客户仅看到自己的异常；员工可解决全部未解决异常。</div></div></div>
        <div class="toolbar"><div><label class="field-label">状态</label><select v-model="status" class="input"><option value="">全部</option><option value="OPEN">未解决</option><option value="RESOLVED">已解决</option></select></div></div>
        <div class="table-wrap">
          <table v-if="filteredRows.length" class="table">
            <thead><tr><th>订单</th><th>类型</th><th>状态</th><th>原因</th><th>登记时间</th><th v-if="can('exception:resolve')" class="num">操作</th></tr></thead>
            <tbody>
              <tr v-for="item in filteredRows" :key="item.id">
                <td><router-link :to="`/orders/${item.order_id}`">{{ item.order_no || `ORD-${String(item.order_id).padStart(4, '0')}` }}</router-link></td>
                <td>{{ typeLabel(item.type) }}</td><td>{{ item.status === 'OPEN' ? '未解决' : '已解决' }}</td><td>{{ item.reason }}</td><td>{{ dateTime(item.created_at) }}</td>
                <td v-if="can('exception:resolve')" class="num"><button v-if="item.status === 'OPEN'" class="btn" :disabled="busy" @click="openResolve(item)">解决</button><span v-else class="section-note">{{ item.resolution_note || '-' }}</span></td>
              </tr>
            </tbody>
          </table>
          <EmptyState v-else title="暂无异常记录" description="登记异常后会在这里显示。" />
        </div>
      </article>
    </section>

    <div v-if="resolving" class="modal"><div class="modal-card"><div class="modal-header">解决订单异常<button class="close" @click="resolving = null">×</button></div><div class="modal-body"><label class="field-label">解决说明</label><textarea v-model.trim="resolutionNote" class="input textarea" rows="4" placeholder="记录采取的处理措施" /></div><div class="modal-footer"><button class="btn" @click="resolving = null">取消</button><button class="btn btn-primary" :disabled="busy || !resolutionNote" @click="resolveException">确认解决</button></div></div></div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import EmptyState from '../components/EmptyState.vue'
import PageHeader from '../components/PageHeader.vue'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'

const auth = useAuthStore()
const { can, role } = auth
const rows = ref([])
const status = ref('')
const orderId = ref(null)
const type = ref(role === 'operator' ? 'DAMAGED' : 'CUSTOMER_CANCEL')
const reason = ref('')
const busy = ref(false)
const resolving = ref(null)
const resolutionNote = ref('')

const allTypes = [
  { value: 'CUSTOMER_CANCEL', label: '客户取消', roles: ['customer', 'staff'] },
  { value: 'ADDRESS_ERROR', label: '地址错误', roles: ['customer', 'staff'] },
  { value: 'PRICE_DISPUTE', label: '价格争议', roles: ['customer', 'staff'] },
  { value: 'DAMAGED', label: '包裹破损', roles: ['staff', 'operator'] },
  { value: 'PROHIBITED', label: '违禁品', roles: ['staff', 'operator'] },
]

const typeOptions = computed(() => allTypes.filter((item) => item.roles.includes(role)))
const filteredRows = computed(() => rows.value.filter((item) => !status.value || item.status === status.value))
const openCount = computed(() => rows.value.filter((item) => item.status === 'OPEN').length)
const resolvedCount = computed(() => rows.value.filter((item) => item.status === 'RESOLVED').length)
const canSubmit = computed(() => Number(orderId.value) > 0 && !!type.value && !!reason.value)

onMounted(refresh)

async function refresh() {
  try { rows.value = await api.get('/exceptions') } catch { rows.value = [] }
}

function typeLabel(value) { return allTypes.find((item) => item.value === value)?.label || value }
function dateTime(value) { return value ? new Date(value).toLocaleString() : '-' }

async function createException() {
  try {
    busy.value = true
    await api.post(`/orders/${orderId.value}/exceptions`, { type: type.value, reason: reason.value })
    reason.value = ''
    await refresh()
  } finally { busy.value = false }
}

function openResolve(item) { resolving.value = item; resolutionNote.value = '' }
async function resolveException() {
  if (!resolving.value) return
  try {
    busy.value = true
    await api.patch(`/exceptions/${resolving.value.id}/resolve`, { resolution_note: resolutionNote.value })
    resolving.value = null
    await refresh()
  } finally { busy.value = false }
}
</script>

<style scoped>
.exception-layout { display: grid; gap: 16px; grid-template-columns: minmax(280px, .75fr) minmax(0, 1.6fr); }
.section-card { padding: 16px; }
.section-head { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 14px; }
.textarea { resize: vertical; min-height: 96px; }
@media (max-width: 1000px) { .exception-layout { grid-template-columns: 1fr; } }
</style>
