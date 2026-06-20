<template>
  <span class="badge" :class="`badge-${tone}`">
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup lang="ts">
import type { StatusTone } from '../data/mock'

withDefaults(
  defineProps<{
    label?: string
    tone?: StatusTone
  }>(),
  {
    label: '',
    tone: 'slate',
  },
)
</script>
