<template>
  <section class="panel">
    <div class="panel-header">
      <h2>{{ title }}</h2>
      <span class="status-pill muted">待实现</span>
    </div>
    <div class="empty-state">当前页面将在后续阶段按 Figma 和 OpenAPI 接入。</div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => String(route.meta.title ?? '页面'))
</script>
