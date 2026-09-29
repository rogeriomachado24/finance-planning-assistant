<script setup lang="ts">
import type { ProjectionWarning } from "../api/client";
import { formatDate } from "../lib/format";

defineProps<{ warnings: ProjectionWarning[] }>();
</script>

<template>
  <section v-if="warnings.length" class="rounded-lg border border-hairline bg-surface p-4" aria-labelledby="warnings-heading">
    <h2 id="warnings-heading" class="text-sm font-semibold">Things to know about this projection</h2>
    <ul class="mt-2 space-y-2 text-sm">
      <li v-for="w in warnings" :key="w.code" class="flex gap-2">
        <svg viewBox="0 0 16 16" class="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true">
          <path d="M8 1 15.5 14.5H.5Z" fill="currentColor" stroke-linejoin="round" />
          <path d="M8 6v4" stroke="#0b0b0b" stroke-width="1.6" stroke-linecap="round" />
          <circle cx="8" cy="12.2" r="0.9" fill="#0b0b0b" />
        </svg>
        <span>
          {{ w.message }}
          <span class="text-ink-2">From {{ formatDate(w.date) }}.</span>
        </span>
      </li>
    </ul>
  </section>
</template>
