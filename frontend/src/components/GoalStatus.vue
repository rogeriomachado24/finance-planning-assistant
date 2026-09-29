<script setup lang="ts">
/**
 * The headline: when the goal is projected to be reached. Wording describes the
 * projection under the shown assumptions; it never recommends anything.
 */
import { computed } from "vue";
import type { Goal, ScenarioResult } from "../api/client";
import { formatDate, formatDuration, formatEur } from "../lib/format";

const props = defineProps<{ result: ScenarioResult; goal: Goal | null }>();

const headline = computed(() => {
  const date = props.result.projected_goal_date;
  return date ? formatDate(date) : "Not within 50 years";
});

const explanation = computed(() => {
  const r = props.result;
  const target = formatDate(r.target_date);
  if (r.months_to_goal === 0) {
    return "Current cash and investments already cover the target.";
  }
  if (r.reaches_goal && r.months_to_goal !== null) {
    const early = r.months_to_target_date - r.months_to_goal;
    return early === 0
      ? `Under these assumptions, the target is reached on the target date, ${target}.`
      : `Under these assumptions, the target is reached ${formatDuration(early)} before the target date (${target}).`;
  }
  const later = r.projected_goal_date
    ? `It is reached on ${formatDate(r.projected_goal_date)} instead.`
    : "It is not reached within 50 years.";
  return `Under these assumptions, the target is not reached by ${target}: ${formatEur(r.shortfall)} short. ${later}`;
});
</script>

<template>
  <section class="rounded-lg border border-hairline bg-surface p-5" aria-labelledby="goal-heading">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2 id="goal-heading" class="text-sm text-ink-2">
        {{ goal?.name ?? "Goal" }} · {{ formatEur(result.target_amount) }} by
        {{ formatDate(result.target_date) }}
      </h2>
      <span class="inline-flex items-center gap-1.5 text-sm font-medium">
        <svg v-if="result.reaches_goal" viewBox="0 0 16 16" class="size-4 text-good" aria-hidden="true">
          <circle cx="8" cy="8" r="8" fill="currentColor" />
          <path d="M4.5 8.2 7 10.5l4.5-5" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <svg v-else viewBox="0 0 16 16" class="size-4 text-warning" aria-hidden="true">
          <path d="M8 1 15.5 14.5H.5Z" fill="currentColor" stroke-linejoin="round" />
          <path d="M8 6v4" stroke="#0b0b0b" stroke-width="1.6" stroke-linecap="round" />
          <circle cx="8" cy="12.2" r="0.9" fill="#0b0b0b" />
        </svg>
        {{ result.reaches_goal ? "On track" : "Behind target" }}
      </span>
    </div>
    <p class="mt-3 text-sm text-ink-2">Projected goal date</p>
    <p class="text-5xl font-semibold tracking-tight">{{ headline }}</p>
    <p class="mt-3 max-w-prose text-sm">{{ explanation }}</p>
  </section>
</template>
