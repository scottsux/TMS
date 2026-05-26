<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader title="客户详情" subtitle="查看客户基础信息及其关联订单。">
      <template #actions>
        <router-link class="btn" to="/customers">返回客户列表</router-link>
      </template>
    </PageHeader>
    <section class="card section-card">
      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <div class="field-label">名称</div>
          <div class="detail-value">{{ customer?.name || '-' }}</div>
        </div>
        <div>
          <div class="field-label">关联订单数</div>
          <div class="detail-value">{{ orders.length }}</div>
        </div>
      </div>
    </section>
    <section class="card order-card">
      <div class="col-header">订单</div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>订单号</th><th>状态</th><th class="num">包裹数</th><th class="num">金额</th><th class="num">操作</th></tr></thead>
          <tbody>
            <tr v-for="o in orders" :key="o.id">
              <td>{{ o.order_no || `ORD-${String(o.id).padStart(4, '0')}` }}</td>
              <td>{{ o.status }}</td>
              <td class="num">{{ o.parcel_ids.length }}</td>
              <td class="num">${{ (o.final_price ?? 0).toFixed(2) }}</td>
              <td class="num"><router-link class="btn" :to="`/orders/${o.id}`">查看</router-link></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import api from '../api/client'

const route = useRoute()
const id = computed(() => route.params.id)
const customer = ref(null)
const orders = ref([])

onMounted(async () => {
  try {
    customer.value = await api.get(`/customers/${id.value}`)
  } catch {}
  try {
    orders.value = await api.get(`/orders?customer_id=${id.value}`)
  } catch {}
})
</script>

<style scoped>
.section-card { padding: 16px; margin-bottom: 16px; }
.detail-value { font-size: 16px; color: var(--text-h); font-weight: 600; }
.order-card { padding: 0; }
.col-header { padding: 12px 14px; border-bottom: 1px solid var(--border); font-weight: 600; background: var(--surface-subtle); }
</style>
