<script setup lang="ts">
/** The top of a page: its name for screen readers (the navigation shows it visually) and one
 * sentence saying what the page answers, for someone seeing it for the first time. */
defineProps<{ title: string; answers: string }>();
</script>

<template>
  <h1 class="sr-only">{{ title }}</h1>
  <p class="mb-4 max-w-prose text-sm text-ink-2">{{ answers }}</p>
</template>
