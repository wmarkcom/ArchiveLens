<template>
  <button class="toggle-switch" :class="{ active: modelValue }" type="button" @click="$emit('update:modelValue', !modelValue)">
    <span />
  </button>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: boolean
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>
