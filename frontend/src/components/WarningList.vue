<script setup lang="ts">
/**
 * Notes the engine raised about the projection. Most are cautions (contribution reduced,
 * investments sold, money running out); "debt paid off" is good news and looks it.
 */
import type { ProjectionWarning } from "../api/client";
import { formatDate } from "../lib/format";

defineProps<{ warnings: ProjectionWarning[] }>();

const isGoodNews = (w: ProjectionWarning) => w.code === "debt_paid_off";
</script>

<template>
  <section v-if="warnings.length" class="rounded-lg border border-hairline bg-surface p-4" aria-labelledby="warnings-heading">
    <h2 id="warnings-heading" class="text-sm font-semibold">Things to know about this projection</h2>
    <ul class="mt-2 space-y-2 text-sm">
      <li v-for="w in warnings" :key="w.code" class="flex gap-2">
        <svg v-if="isGoodNews(w)" viewBox="0 0 16 16" class="mt-0.5 size-4 shrink-0 text-good" aria-hidden="true">
          <circle cx="8" cy="8" r="8" fill="currentColor" />
          <path d="M4.5 8.2 7 10.5l4.5-5" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <svg v-else viewBox="0 0 16 16" class="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true">
          <path d="M8 1 15.5 14.5H.5Z" fill="currentColor" stroke-linejoin="round" />
          <path d="M8 6v4" stroke="#0b0b0b" stroke-width="1.6" stroke-linecap="round" />
          <circle cx="8" cy="12.2" r="0.9" fill="#0b0b0b" />
        </svg>
        <span>
          <span class="sr-only">{{ isGoodNews(w) ? "Note:" : "Caution:" }}</span>
          {{ w.message }}
          <span class="text-ink-2">From {{ formatDate(w.date) }}.</span>
        </span>
      </li>
    </ul>
  </section>
</template>
