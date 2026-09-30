<script setup lang="ts">
/**
 * Where you are today: progress towards the goal (a meter), and today's figures. Every
 * value comes from the API; the meter only draws the fraction it was given.
 */
import { computed } from "vue";
import type { ProfileOut, ScenarioResult } from "../api/client";
import { formatEur, formatPercent } from "../lib/format";

const props = defineProps<{ result: ScenarioResult; today: ProfileOut | null }>();

const progress = computed(() => props.result.goal_progress);
const covered = computed(() => progress.value.remaining === 0);
const label = computed(
  () =>
    `${formatEur(progress.value.current_amount)} of ${formatEur(props.result.target_amount)}` +
    ` · ${formatPercent(progress.value.fraction)} of the goal`,
);
</script>

<template>
  <section class="rounded-lg border border-hairline bg-surface p-5" aria-labelledby="today-heading">
    <h2 id="today-heading" class="text-sm text-ink-2">Where you are today</h2>

    <!-- Meter: the fill and a lighter track of the same hue -->
    <div
      class="mt-3 h-2.5 overflow-hidden rounded-full"
      :style="{ background: 'color-mix(in oklab, var(--color-series-1) 22%, var(--color-surface))' }"
      role="meter"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="Math.round(progress.fraction * 100)"
      :aria-valuetext="label"
      aria-labelledby="today-heading"
    >
      <div class="h-full rounded-full bg-series-1" :style="{ width: `${progress.fraction * 100}%` }" />
    </div>
    <p class="mt-2 text-sm">
      <span class="font-medium">{{ label }}</span>
      <span class="text-ink-2">
        · {{ covered ? "the target is already covered" : `${formatEur(progress.remaining)} to go` }}
      </span>
    </p>

    <dl v-if="today" class="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
      <div>
        <dt class="text-xs text-ink-2">Cash + investments</dt>
        <dd class="font-semibold">{{ formatEur(today.position.liquid_assets) }}</dd>
      </div>
      <div>
        <dt class="text-xs text-ink-2">Net worth</dt>
        <dd class="font-semibold">{{ formatEur(today.position.net_worth) }}</dd>
        <dd v-if="today.profile.debt_balance" class="text-xs text-ink-2">
          after {{ formatEur(today.profile.debt_balance) }} debt
        </dd>
      </div>
      <div>
        <dt class="text-xs text-ink-2">Monthly surplus</dt>
        <dd class="font-semibold">{{ formatEur(today.position.monthly_surplus) }}</dd>
      </div>
      <div>
        <dt class="text-xs text-ink-2">Savings rate</dt>
        <dd class="font-semibold">
          {{ today.position.savings_rate === null ? "—" : formatPercent(today.position.savings_rate) }}
        </dd>
      </div>
    </dl>
  </section>
</template>
