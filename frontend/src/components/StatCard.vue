<template>
  <article class="stat-card">
    <div class="stat-icon" :class="`tone-${tone}`">•</div>
    <div>
      <p>{{ label }}</p>
      <strong>{{ value }}</strong>
    </div>
    <StatusBadge :tone="tone">{{ helper }}</StatusBadge>
  </article>
</template>

<script setup lang="ts">
import StatusBadge from './StatusBadge.vue'
import type { StatusTone } from '../data/mock'

defineProps<{
  label: string
  value: string
  helper: string
  tone: StatusTone
}>()
</script>
