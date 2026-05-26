<template>
  <span :class="['badge', toneClass]">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, required: true },
  type: { type: String, required: true },
  label: { type: String, default: '' },
})

const toneClass = computed(() => {
  const maps = {
    parcel: {
      SUBMITTED: 'badge-muted',
      IN_TRANSIT: 'badge-info',
      ARRIVED: 'badge-ok',
      PACK_REQUESTED: 'badge-warn',
      PACKED: 'badge-ok',
      REJECTED: 'badge-danger',
    },
    order: {
      DRAFT: 'badge-muted',
      READY_TO_PACK: 'badge-info',
      PACKING: 'badge-warn',
      COMPLETED: 'badge-ok',
    },
    task: {
      TODO: 'badge-muted',
      IN_PROGRESS: 'badge-warn',
      DONE: 'badge-ok',
    },
  }
  return maps[props.type]?.[props.status] || 'badge-muted'
})
</script>
