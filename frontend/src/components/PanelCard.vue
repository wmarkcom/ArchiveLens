<template>
  <section class="panel-card" :class="{ compact }">
    <div v-if="title || subtitle || $slots.actions" class="panel-title-row">
      <div>
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="subtitle">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </div>
    <slot />
  </section>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    subtitle?: string
    compact?: boolean
  }>(),
  {
    title: '',
    subtitle: '',
    compact: false,
  },
)
</script>
