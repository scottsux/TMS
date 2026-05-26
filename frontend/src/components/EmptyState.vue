<template>
  <div class="empty-state">
    <div class="section-title">{{ title }}</div>
    <p v-if="description" class="page-subtitle">{{ description }}</p>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>
