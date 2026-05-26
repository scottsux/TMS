<template>
  <div class="container" style="container-type:inline-size;">
    <h1 class="mb-3 title">仪表盘</h1>
    <div class="metrics">
      <section class="metric">
        <h2>包裹</h2>
        <p>提交 {{ mock.parcels.SUBMITTED }} · 审核通过 {{ mock.parcels.APPROVED }} · 已到仓 {{ mock.parcels.ARRIVED }} · 已打包 {{ mock.parcels.PACKED }}</p>
      </section>
      <section v-if="role==='staff' || role==='operator'" class="metric">
        <h2>订单</h2>
        <p>草稿 {{ mock.orders.DRAFT }} · 待打包 {{ mock.orders.READY_TO_PACK }} · 打包中 {{ mock.orders.PACKING }} · 完成 {{ mock.orders.COMPLETED }}</p>
      </section>
      <section v-if="role==='staff' || role==='operator'" class="metric">
        <h2>任务</h2>
        <p>待办 {{ mock.tasks.TODO }} · 进行中 {{ mock.tasks.IN_PROGRESS }} · 已完成 {{ mock.tasks.DONE }}</p>
      </section>
      <section v-if="role==='staff'" class="metric">
        <h2>计价规则</h2>
        <p>最终价格 = 实重 × 每公斤单价 + 额外费用</p>
      </section>
      <section v-if="role==='customer'" class="metric">
        <h2>快捷入口</h2>
        <p><router-link to="/upload" class="underline">上传包裹</router-link> · <router-link to="/parcels" class="underline">我的包裹</router-link></p>
      </section>
    </div>

    <section class="metric mt-3">
      <h2>流程概览</h2>
      <p>1. 客户提交包裹 → 员工审核</p>
      <p>2. 包裹到仓 → 员工创建订单</p>
      <p>3. 操作员打包 → 系统计算价格</p>
      <div class="note">仅展示用的静态数据。</div>
    </section>
  </div>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useAuthStore } from '../stores/auth'
const mock = {
  parcels: { SUBMITTED: 12, APPROVED: 8, ARRIVED: 5, PACKED: 3 },
  orders: { DRAFT: 6, READY_TO_PACK: 4, PACKING: 2, COMPLETED: 20 },
  tasks: { TODO: 7, IN_PROGRESS: 2, DONE: 15 },
}
const { role } = storeToRefs(useAuthStore())
</script>

<style scoped>
.metrics { display: grid; grid-template-columns: 1fr; gap: 12px; }
@container (min-width: 720px) { .metrics { grid-template-columns: 1fr 1fr; } }
@container (min-width: 1200px) { .metrics { grid-template-columns: repeat(4, 1fr); } }
.metric { padding: 14px 16px; border: 1px solid var(--border); border-radius: 10px; background: transparent; box-shadow: none; }
.metric h2 { margin: 0 0 6px; font-size: 16px; font-weight: 600; color: var(--text-h); }
.metric p { margin: 0; font-size: 13px; opacity: .88; }
.note { margin-top: 6px; font-size: 12px; opacity: .66; }
</style>
