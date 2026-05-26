<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader title="包裹" subtitle="围绕到仓、申请打包和通知状态组织日常操作。">
      <template #actions>
        <button v-if="role === 'customer'" class="btn btn-primary" :disabled="!hasArrived || busy" @click="startSelect">选择申请打包</button>
        <button class="btn" :disabled="busy" @click="refresh">刷新</button>
      </template>
    </PageHeader>

    <section v-if="role === 'operator'" class="card notice-panel">
      <div class="notice-head">
        <div>
          <div class="section-title">通知中心</div>
          <div class="page-subtitle">跟进客户的打包申请和已打包待发货通知。</div>
        </div>
        <div class="page-actions">
          <button class="btn" :disabled="busy" @click="refreshNotices">刷新</button>
          <button class="btn" :disabled="busy || !notices.length" @click="clearNotices">清空可打包</button>
          <button class="btn" :disabled="busy || !shipNotices.length" @click="clearShipNotices">清空待发货</button>
        </div>
      </div>
      <div class="notice-grid">
        <div class="notice-block">
          <div class="field-label">客户申请打包 {{ notices.length }}</div>
          <ul v-if="notices.length" class="notice-list">
            <li v-for="(n, i) in notices" :key="`r2p-${i}`">客户 {{ n.customer_id }} 于 {{ dateTimeShort(n.ts) }} 提交打包申请</li>
          </ul>
          <div v-else class="section-note">暂无新的打包申请。</div>
        </div>
        <div class="notice-block">
          <div class="field-label">打包完毕待发货 {{ shipNotices.length }}</div>
          <ul v-if="shipNotices.length" class="notice-list">
            <li v-for="(n, i) in shipNotices" :key="`r2s-${i}`">客户 {{ n.customer_id }} 于 {{ dateTimeShort(n.ts) }} 完成打包</li>
          </ul>
          <div v-else class="section-note">暂无待发货通知。</div>
        </div>
      </div>
    </section>

    <section class="toolbar toolbar-grid">
      <div class="toolbar-span-4">
        <label class="field-label">运单号</label>
        <input v-model.trim="q" class="input" placeholder="搜索运单号" />
      </div>
      <div class="toolbar-span-4">
        <label class="field-label">包裹状态</label>
        <select v-model="filterStatus" class="input">
          <option value="">全部状态</option>
          <option value="IN_TRANSIT">在途</option>
          <option value="ARRIVED">已到仓</option>
          <option value="PACK_REQUESTED">申请打包</option>
          <option value="PACKED">已打包</option>
        </select>
      </div>
      <div v-if="role === 'staff'" class="toolbar-span-4">
        <label class="field-label">客户</label>
        <select v-model="filterCustomerId" class="input">
          <option value="">全部客户</option>
          <option v-for="c in customers" :key="c.id" :value="String(c.id)">{{ c.name }}</option>
        </select>
      </div>
      <div v-if="role === 'customer'" class="toolbar-span-4">
        <div class="field-label">打包提示</div>
        <div class="section-note">{{ hasArrived ? '勾选已到仓包裹后提交打包申请。' : '当前没有可申请打包的已到仓包裹。' }}</div>
      </div>
      <div class="toolbar-span-12 page-actions" style="justify-content: space-between;">
        <div v-if="role === 'customer' && selectMode" class="selection-banner">
          <span>已选 {{ selected.size }} 件包裹</span>
          <div class="page-actions">
            <button class="btn" :disabled="busy" @click="cancelSelect">取消选择</button>
            <button class="btn btn-primary" :disabled="busy || selected.size === 0" @click="proceedInfo">下一步：填写转运信息</button>
          </div>
        </div>
        <div v-else class="section-note">共 {{ filtered.length }} 条包裹记录</div>
      </div>
    </section>

    <section class="card">
      <div class="table-wrap">
        <table v-if="filtered.length" class="table">
          <thead>
            <tr>
              <th v-if="role === 'customer' && selectMode">选择</th>
              <th>运单号</th>
              <th v-if="role !== 'customer'">客户</th>
              <th>状态</th>
              <th>备注</th>
              <th v-if="role === 'customer'">打包提示</th>
              <th v-else class="num">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in filtered" :key="p.id">
              <td v-if="role === 'customer' && selectMode">
                <input type="checkbox" :disabled="p.status !== 'ARRIVED'" :checked="selected.has(p.id)" @change="onSelect(p)" />
              </td>
              <td>{{ p.tracking }}</td>
              <td v-if="role !== 'customer'">{{ p.customer }}</td>
              <td><StatusBadge type="parcel" :status="p.status" :label="p.statusZh" /></td>
              <td>{{ p.note || '-' }}</td>
              <td v-if="role === 'customer'">{{ parcelPrompt(p) }}</td>
              <td v-else class="num">
                <button v-if="p.status === 'IN_TRANSIT'" class="btn" :disabled="busy" @click="setStatus(p, 'ARRIVED')">标记到仓</button>
                <span v-else class="section-note">-</span>
              </td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="没有符合条件的包裹" description="可以调整状态筛选或等待新的包裹同步进仓。" />
      </div>
    </section>

    <div v-if="notifyOpen" class="modal">
      <div class="modal-card notify-card">
        <div class="modal-header">
          填写转运信息
          <button class="close" @click="notifyOpen = false">×</button>
        </div>
        <div class="modal-body">
          <div class="grid gap-3 md:grid-cols-2">
            <div>
              <label class="field-label">转运渠道</label>
              <select v-model="channel" class="input">
                <option value="air">空运</option>
                <option value="sea">海运</option>
              </select>
            </div>
            <div>
              <label class="field-label">目的地</label>
              <input v-model.trim="destination" class="input" placeholder="例如 英国" />
            </div>
            <div>
              <label class="field-label">服务</label>
              <select v-model="service" class="input">
                <option value="express">特快</option>
                <option value="economy">普快</option>
              </select>
            </div>
          </div>
          <div class="grid gap-3 md:grid-cols-2" style="margin-top: 12px;">
            <div>
              <label class="field-label">收件人姓名</label>
              <input v-model.trim="consignee_name" class="input" placeholder="英文姓名" />
            </div>
            <div>
              <label class="field-label">州 / 省</label>
              <input v-model.trim="consignee_state" class="input" placeholder="州、省" />
            </div>
            <div>
              <label class="field-label">城市</label>
              <input v-model.trim="consignee_city" class="input" placeholder="城市" />
            </div>
            <div>
              <label class="field-label">收件人电话</label>
              <input v-model.trim="consignee_phone" class="input" placeholder="电话" />
            </div>
            <div class="md:col-span-2">
              <label class="field-label">联系地址</label>
              <input v-model.trim="consignee_address" class="input" placeholder="完整地址" />
            </div>
            <div>
              <label class="field-label">收件人邮箱</label>
              <input v-model.trim="consignee_email" class="input" placeholder="邮箱" />
            </div>
            <div>
              <label class="field-label">收件人邮编</label>
              <input v-model.trim="consignee_postcode" class="input" placeholder="邮编" />
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <span v-if="msg" :style="{ color: msgType === 'ok' ? 'var(--success)' : 'var(--danger)' }" class="section-note">{{ msg }}</span>
          <button class="btn" :disabled="busy" @click="saveDraft">仅保存信息</button>
          <button class="btn btn-primary" :disabled="busy" @click="notifyReadyToPack">提交并通知</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import { useAuthStore } from '../stores/auth'
import { zh } from '../constants/enums'
import api from '../api/client'

const rows = ref([])
const q = ref('')
const filterStatus = ref('')
const customers = ref([])
const filterCustomerId = ref('')
const busy = ref(false)
const auth = useAuthStore()
const { role } = storeToRefs(auth)
const poll = ref(null)

const notices = ref([])
const shipNotices = ref([])
const notifyOpen = ref(false)
const selectMode = ref(false)
const selected = ref(new Set())
const channel = ref('air')
const destination = ref('英国')
const service = ref('express')
const consignee_name = ref('')
const consignee_state = ref('')
const consignee_city = ref('')
const consignee_address = ref('')
const consignee_phone = ref('')
const consignee_email = ref('')
const consignee_postcode = ref('')
const msg = ref('')
const msgType = ref('ok')

onMounted(async () => {
  loadDraft()
  await refresh()
  if (role.value === 'operator' || role.value === 'customer') await refreshNotices()
  startPoll()
})

onUnmounted(() => {
  if (poll.value) clearInterval(poll.value)
})

watch(role, async (value) => {
  if (value === 'operator' || value === 'customer') {
    await refreshNotices()
    startPoll()
  } else if (poll.value) {
    clearInterval(poll.value)
    poll.value = null
  }
})

const filtered = computed(() => {
  let list = rows.value.filter((r) =>
    (!q.value || r.tracking.toLowerCase().includes(q.value.toLowerCase())) &&
    (!filterStatus.value || r.status === filterStatus.value),
  )
  if (role.value === 'staff' && filterCustomerId.value) {
    const cid = Number(filterCustomerId.value)
    list = list.filter((r) => r.customer_id === cid)
  }
  return list
})

const hasArrived = computed(() => filtered.value.some((r) => r.status === 'ARRIVED'))

async function refresh() {
  try {
    let url = '/parcels'
    if (role.value === 'customer') url += `?customer_id=${auth.user?.id ?? 1}`
    const data = await api.get(url)
    rows.value = data.map((p) => ({
      id: p.id,
      tracking: p.tracking_number,
      customer: p.customer_name || p.customer_id,
      customer_id: p.customer_id,
      status: p.status,
      statusZh: zh.parcel[p.status] || p.status,
      note: p.note || '',
      packed_at: p.packed_at || '',
      shipped_at: p.shipped_at || '',
    }))
    if (role.value === 'staff') {
      try {
        customers.value = await api.get('/customers')
      } catch {
        customers.value = []
      }
    }
  } catch {
    rows.value = []
  }
}

function parcelPrompt(parcel) {
  if (parcel.shipped_at) return `已发货 ${dateTimeShort(parcel.shipped_at)}`
  if (parcel.packed_at) return `已打包 ${dateTimeShort(parcel.packed_at)}`
  return '-'
}

async function setStatus(row, next) {
  try {
    busy.value = true
    await api.patch(`/parcels/${row.id}/status`, { status: next })
    await refresh()
  } finally {
    busy.value = false
  }
}

async function notifyReadyToPack() {
  try {
    busy.value = true
    await api.post('/notify/ready_to_pack', {
      customer_id: auth.user?.id ?? 1,
      parcel_ids: Array.from(selected.value),
      channel: channel.value,
      destination: destination.value,
      service: service.value,
      consignee_name: consignee_name.value,
      consignee_state: consignee_state.value,
      consignee_city: consignee_city.value,
      consignee_address: consignee_address.value,
      consignee_phone: consignee_phone.value,
      consignee_email: consignee_email.value,
      consignee_postcode: consignee_postcode.value,
    })
    msg.value = '已提交并通知操作员'
    msgType.value = 'ok'
    notifyOpen.value = false
    selectMode.value = false
    selected.value = new Set()
    await refresh()
  } catch {
    msg.value = '提交失败'
    msgType.value = 'err'
  } finally {
    busy.value = false
  }
}

async function loadNotices() {
  try {
    notices.value = await api.get('/notifications?type=ready_to_pack')
  } catch {
    notices.value = []
  }
}

async function loadShipNotices() {
  try {
    shipNotices.value = await api.get('/notifications?type=ready_to_ship')
  } catch {
    shipNotices.value = []
  }
}

async function refreshNotices() {
  busy.value = true
  try {
    await Promise.all([loadNotices(), loadShipNotices()])
  } finally {
    busy.value = false
  }
}

async function clearNotices() {
  try {
    busy.value = true
    await api.delete('/notifications?type=ready_to_pack')
    await refreshNotices()
  } finally {
    busy.value = false
  }
}

async function clearShipNotices() {
  try {
    busy.value = true
    await api.delete('/notifications?type=ready_to_ship')
    await refreshNotices()
  } finally {
    busy.value = false
  }
}

function startPoll() {
  if (role.value !== 'operator' && role.value !== 'customer') return
  if (poll.value) clearInterval(poll.value)
  poll.value = setInterval(() => {
    refreshNotices()
  }, 10000)
}

function startSelect() {
  msg.value = ''
  if (!hasArrived.value) {
    msg.value = '暂无已到仓包裹'
    msgType.value = 'err'
    return
  }
  selectMode.value = true
  selected.value = new Set()
}

function onSelect(parcel) {
  const next = new Set(selected.value)
  if (next.has(parcel.id)) next.delete(parcel.id)
  else next.add(parcel.id)
  selected.value = next
}

function proceedInfo() {
  notifyOpen.value = true
}

function cancelSelect() {
  selectMode.value = false
  selected.value = new Set()
}

function draftKey() {
  return `forwarding_prefs_c${auth.user?.id ?? 1}`
}

function saveDraft() {
  try {
    localStorage.setItem(draftKey(), JSON.stringify({
      channel: channel.value,
      destination: destination.value,
      service: service.value,
      consignee_name: consignee_name.value,
      consignee_state: consignee_state.value,
      consignee_city: consignee_city.value,
      consignee_address: consignee_address.value,
      consignee_phone: consignee_phone.value,
      consignee_email: consignee_email.value,
      consignee_postcode: consignee_postcode.value,
    }))
    msg.value = '已保存'
    msgType.value = 'ok'
  } catch {
    msg.value = '保存失败'
    msgType.value = 'err'
  }
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(draftKey())
    if (!raw) return
    const draft = JSON.parse(raw)
    channel.value = draft.channel || channel.value
    destination.value = draft.destination || destination.value
    service.value = draft.service || service.value
    consignee_name.value = draft.consignee_name || ''
    consignee_state.value = draft.consignee_state || ''
    consignee_city.value = draft.consignee_city || ''
    consignee_address.value = draft.consignee_address || ''
    consignee_phone.value = draft.consignee_phone || ''
    consignee_email.value = draft.consignee_email || ''
    consignee_postcode.value = draft.consignee_postcode || ''
  } catch {}
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
</script>

<style scoped>
.notice-panel { padding: 16px; margin-bottom: 16px; }
.notice-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.notice-grid { display: grid; gap: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 14px; }
.notice-block { border: 1px solid var(--border); border-radius: var(--radius); padding: 12px; background: var(--surface-subtle); }
.notice-list { margin: 0; padding-left: 18px; color: var(--text); font-size: 13px; }
.notice-list li + li { margin-top: 6px; }
.selection-banner { display: flex; align-items: center; justify-content: space-between; width: 100%; gap: 12px; font-size: 13px; color: var(--text-h); }
.notify-card { width: min(760px, 94vw); }

@media (max-width: 768px) {
  .notice-grid { grid-template-columns: 1fr; }
  .notice-head,
  .selection-banner { flex-direction: column; align-items: stretch; }
}
</style>
