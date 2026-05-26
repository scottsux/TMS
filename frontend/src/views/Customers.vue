<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader title="客户" subtitle="查看客户列表并快速进入客户详情。">
      <template #actions>
        <button class="btn" @click="reset">清空</button>
      </template>
    </PageHeader>
    <section class="toolbar toolbar-grid">
      <div class="toolbar-span-4">
        <label class="field-label">客户名称</label>
        <input v-model.trim="q" class="input" placeholder="搜索客户名" />
      </div>
      <div class="toolbar-span-4 page-actions" style="align-self: end;">
        <button class="btn btn-primary" @click="search">搜索</button>
        <div class="section-note">共 {{ rows.length }} 位客户</div>
      </div>
    </section>
    <section class="customer-table-shell">
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>客户名</th><th class="num">操作</th></tr></thead>
          <tbody>
            <tr v-for="c in rows" :key="c.id">
              <td>{{ c.name }}</td>
              <td class="num"><router-link class="btn" :to="`/customers/${c.id}`">查看</router-link></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import api from '../api/client'
const q = ref('')
const rows = ref([])
onMounted(search)
async function search() {
  const data = await api.get(`/customers${q.value ? `?q=${encodeURIComponent(q.value)}` : ''}`)
  rows.value = data
}
function reset() { q.value = ''; search() }
</script>
<style scoped>
.customer-table-shell {
  margin-top: 4px;
}
</style>
