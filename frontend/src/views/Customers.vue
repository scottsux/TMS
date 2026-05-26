<template>
  <div class="container" style="container-type:inline-size;">
    <h1 class="mb-3 title">客户</h1>
    <div class="toolbar grid gap-3 md:grid-cols-3">
      <input v-model.trim="q" class="input" placeholder="搜索客户名"/>
      <div class="flex gap-2">
        <button class="btn btn-primary" @click="search">搜索</button>
        <button class="btn" @click="reset">重置</button>
      </div>
    </div>
    <section class="card">
      <div class="table-wrap">
        <table class="table table--compact table--zebra table--sticky">
          <thead><tr><th>客户名</th><th class="text-right">操作</th></tr></thead>
          <tbody>
            <tr v-for="c in rows" :key="c.id">
              <td>{{ c.name }}</td>
              <td class="text-right"><router-link class="px-3 py-1.5 rounded-lg border text-xs" :to="`/customers/${c.id}`">查看</router-link></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
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
.title { font-size: 24px; font-weight: 650; }
</style>
