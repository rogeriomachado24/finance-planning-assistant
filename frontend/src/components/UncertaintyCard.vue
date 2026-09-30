<script setup lang="ts">
/**
 * How sure is the projection: the share of 1,000 simulated futures that reach the goal on
 * time, how precise that share is, when the goal is reached, and how far off the misses
 * are. Figures and shares all come from the API; the bars only draw the shares given.
 */
import { computed } from "vue";
import type { ApiError, Uncertainty } from "../api/client";
import { formatCount, formatPercent, formatPoints, formatShare } from "../lib/format";
import {
  goalDateRange,
  probabilitySentence,
  reachedByRows,
  shareExplained,
  shortfallSentence,
  valueRange,
} from "../lib/uncertainty";

const props = defineProps<{
  uncertainty: Uncertainty | null;
  loading: boolean;
  error: ApiError | null;
}>();
defineEmits<{ retry: [] }>();

const RISK_LABELS = { low: "Low", medium: "Medium", high: "High" } as const;

const u = computed(() => props.uncertainty);
const rows = computed(() => (u.value ? reachedByRows(u.value) : []));
const shortfall = computed(() => (u.value ? shortfallSentence(u.value) : null));
</script>

<template>
  <section
    class="rounded-lg border border-hairline bg-surface p-5 transition-opacity"
    :class="{ 'opacity-60': loading && u }"
    aria-labelledby="uncertainty-heading"
    :aria-busy="loading"
  >
    <h2 id="uncertainty-heading" class="text-sm text-ink-2">How sure is this?</h2>

    <p v-if="!u && loading" class="mt-3 text-sm text-ink-2">Simulating 1,000 futures…</p>

    <div v-else-if="!u && error" role="alert" class="mt-3 text-sm">
      <p>Couldn't simulate the range of outcomes: {{ error.message }}</p>
      <button
        type="button"
        class="mt-2 rounded-md border border-hairline px-3 py-1.5 text-sm hover:bg-page"
        @click="$emit('retry')"
      >
        Try again
      </button>
    </div>

    <template v-else-if="u">
      <p class="mt-3">
        <span class="text-4xl font-semibold tracking-tight">{{ formatShare(u.probability_by_target_date) }}</span
        >{{ " " }}<span class="ml-1 text-sm">{{ probabilitySentence(u) }}.</span>
      </p>
      <p class="mt-1 text-xs text-ink-2">
        Precision {{ formatPoints(u.probability_margin) }}: {{ formatCount(u.paths) }} futures are a
        sample, so the share is an estimate.
        {{ shareExplained(u) }}
      </p>

      <div class="mt-4 grid gap-5 md:grid-cols-2">
        <div class="space-y-3 text-sm">
          <p>{{ goalDateRange(u) }}</p>
          <p>{{ valueRange(u) }}</p>
          <p v-if="shortfall">{{ shortfall }}</p>
        </div>

        <div>
          <h3 id="reached-by-heading" class="text-xs font-medium text-ink-2">
            Share of futures that have reached the goal
          </h3>
          <ul class="mt-2 space-y-1.5 text-sm" aria-labelledby="reached-by-heading">
            <li
              v-for="row in rows"
              :key="row.key"
              class="grid grid-cols-[minmax(0,1fr)_4rem_6.5rem] items-center gap-2"
            >
              <span :class="{ 'font-medium': row.isTarget }">{{ row.label }}</span>
              <span
                class="h-2 overflow-hidden rounded-full"
                :style="{ background: 'color-mix(in oklab, var(--color-series-1) 22%, var(--color-surface))' }"
                aria-hidden="true"
              >
                <span class="block h-full rounded-full bg-series-1" :style="{ width: `${row.share * 100}%` }" />
              </span>
              <span class="text-right tabular-nums" :class="{ 'font-medium': row.isTarget }">
                {{ formatShare(row.share) }}
              </span>
            </li>
          </ul>
        </div>
      </div>

      <p class="mt-4 border-t border-grid pt-3 text-xs text-ink-2">
        Investment returns vary from year to year around the assumed
        {{ formatPercent(u.assumptions.annual_return) }} ({{ u.assumption_set }} assumptions);
        income, expenses and contributions follow your plan.
        {{ RISK_LABELS[u.investment_risk] }} investment risk: returns vary by about
        {{ formatPercent(u.volatility) }} a year. The risk level sets how widely returns vary;
        the typical return comes from your assumptions
        (<RouterLink to="/plan" class="underline hover:text-ink">change the risk level in Your plan</RouterLink>).
        This is a projection, not a guarantee: the shares are only as good as the assumed return
        and risk level.
      </p>
    </template>
  </section>
</template>
