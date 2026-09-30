<script setup lang="ts">
/**
 * Scenarios side by side. Every figure, including the differences from the baseline,
 * comes from the API; this table only formats them. It is also the chart's accessible
 * twin: identity never depends on the line colours alone.
 */
import type { ComparedFutures, ComparedScenario } from "../api/client";
import {
  formatDate,
  formatEur,
  formatMonthsEarlier,
  formatPoints,
  formatPointsDifference,
  formatShare,
  formatSignedEur,
} from "../lib/format";

defineProps<{
  scenarios: ComparedScenario[];
  colors: Map<string, string>;
  baseline: string;
  deleting: number | null;
  /** Simulated futures by scenario name; null while loading or unavailable. */
  futures?: Map<string, ComparedFutures> | null;
  futuresError?: string | null;
}>();
const emit = defineEmits<{ delete: [id: number, name: string] }>();
</script>

<template>
  <!-- Below the sm breakpoint each row stacks into a card; each cell shows its column name. -->
  <div>
    <table class="w-full text-sm max-sm:block">
      <caption class="sr-only">
        Scenario outcomes and their differences from the {{ baseline }}
      </caption>
      <thead class="text-left text-xs text-ink-2 max-sm:sr-only">
        <tr class="border-b border-grid">
          <th scope="col" class="py-2 pr-4 font-medium">Scenario</th>
          <th scope="col" class="py-2 pr-4 font-medium">Goal reached</th>
          <th scope="col" class="py-2 pr-4 text-right font-medium">On the target date</th>
          <th scope="col" class="py-2 pr-4 text-right font-medium">On time in simulated futures</th>
          <th scope="col" class="py-2 pr-4 text-right font-medium">Needed per month</th>
          <th scope="col" class="py-2 font-medium"><span class="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody class="max-sm:block">
        <tr
          v-for="(s, index) in scenarios"
          :key="s.name"
          class="border-b border-grid align-top max-sm:grid max-sm:grid-cols-2 max-sm:gap-x-4 max-sm:gap-y-2 max-sm:py-3"
        >
          <th scope="row" class="py-2.5 pr-4 text-left font-normal max-sm:col-span-2 max-sm:p-0">
            <div class="flex items-center gap-2">
              <span
                v-if="colors.get(s.name)"
                class="h-0.5 w-4 shrink-0 rounded-full"
                :style="{ background: colors.get(s.name) }"
                aria-hidden="true"
              />
              <span v-else class="w-4 shrink-0 text-center text-xs text-muted" title="Not in the chart">–</span>
              <span class="font-medium">{{ s.name }}</span>
              <span v-if="index === 0" class="rounded bg-page px-1.5 py-0.5 text-xs text-ink-2">Baseline</span>
            </div>
            <p v-if="s.description" class="mt-0.5 pl-6 text-xs text-ink-2">{{ s.description }}</p>
          </th>
          <td class="py-2.5 pr-4 max-sm:p-0 max-sm:pl-6" data-label="Goal reached">
            <div class="whitespace-nowrap">
              {{ s.result.projected_goal_date ? formatDate(s.result.projected_goal_date) : "Not within 50 years" }}
            </div>
            <div class="text-xs text-ink-2">
              <template v-if="index === 0">
                {{ s.result.reaches_goal ? "By the target date" : "After the target date" }}
              </template>
              <template v-else-if="s.vs_baseline.goal_months_earlier !== null">
                {{ formatMonthsEarlier(s.vs_baseline.goal_months_earlier) }}
              </template>
            </div>
          </td>
          <td class="py-2.5 pr-4 text-right tabular-nums max-sm:p-0 max-sm:text-left" data-label="On the target date">
            <div>{{ formatEur(s.result.projected_value_at_target_date) }}</div>
            <div v-if="index > 0" class="text-xs text-ink-2">
              {{ formatSignedEur(s.vs_baseline.value_at_target_difference) }}
            </div>
          </td>
          <td
            class="py-2.5 pr-4 text-right tabular-nums max-sm:p-0 max-sm:pl-6 max-sm:text-left"
            data-label="On time in simulated futures"
          >
            <template v-if="futures?.get(s.name)">
              <div>{{ formatShare(futures.get(s.name)!.probability_by_target_date) }}</div>
              <div class="text-xs text-ink-2">
                {{
                  index === 0
                    ? formatPoints(futures.get(s.name)!.probability_margin)
                    : formatPointsDifference(futures.get(s.name)!.probability_difference)
                }}
              </div>
            </template>
            <span v-else-if="futuresError" class="text-ink-2">—</span>
            <span v-else class="text-xs text-ink-2">Simulating…</span>
          </td>
          <td class="py-2.5 pr-4 text-right tabular-nums max-sm:p-0 max-sm:text-left" data-label="Needed per month">
            {{
              s.result.required_monthly_contribution === null
                ? "—"
                : formatEur(s.result.required_monthly_contribution)
            }}
          </td>
          <td class="py-2.5 text-right max-sm:p-0 max-sm:text-left">
            <button
              v-if="s.saved_id !== null"
              type="button"
              class="rounded-md px-2 py-1 text-xs text-ink-2 hover:bg-page hover:text-ink disabled:opacity-60"
              :disabled="deleting === s.saved_id"
              :aria-label="`Delete scenario ${s.name}`"
              @click="emit('delete', s.saved_id, s.name)"
            >
              {{ deleting === s.saved_id ? "Deleting…" : "Delete" }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
/* Stacked (phone) layout: each cell is labelled with its column name. */
@media (width < 40rem) {
  td[data-label]::before {
    content: attr(data-label);
    display: block;
    font-size: 0.75rem;
    color: var(--color-ink-2);
  }
}
</style>
