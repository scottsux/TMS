<template>
  <div class="container" style="container-type:inline-size;">
    <h1 class="mb-3 title">客户详情</h1>
    <section class="card" style="padding:14px 16px; margin-bottom:12px;">
      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <div class="text-sm opacity-70">名称</div>
          <div class="text-base">{{ customer?.name || '-' }}</div>
        </div>
      </div>
    </section>
    <section class="card" style="padding:0;">
      <div class="col-header">订单</div>
      <div class="table-wrap">
        <table class="table table--compact">
          <thead><tr><th>订单号</th><th>状态</th><th>包裹数</th><th>金额</th><th class="text-right">操作</th></tr></thead>
          <tbody>
            <tr v-for="o in orders" :key="o.id">
              <td class="font-mono">#{{ o.id }}</td>
              <td>{{ o.status }}</td>
              <td class="num">{{ o.parcel_ids.length }}</td>
              <td class="num">${{ (o.final_price ?? 0).toFixed(2) }}</td>
              <td class="text-right"><router-link class="px-3 py-1.5 rounded-lg border text-xs" :to="`/orders/${o.id}`">查看</router-link></td>
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
.title { font-size: 24px; font-weight: 650; }
.col-header { padding:10px 12px; border-bottom:1px solid var(--border); font-weight:600; }
</style>
