<script setup lang="ts">
defineProps<{ label: string; value: string; note?: string }>();
</script>

<template>
  <div class="rounded-lg border border-hairline bg-surface p-4">
    <div class="text-sm text-ink-2">{{ label }}</div>
    <div class="mt-1 text-2xl font-semibold">{{ value }}</div>
    <div v-if="note" class="mt-1 text-xs text-ink-2">{{ note }}</div>
  </div>
</template>
