<script setup lang="ts">
/**
 * The money a goal keeps aside, so it doesn't look like it disappears: what is kept today,
 * and what it is on the target date (kept investments grow with the portfolio). Every figure
 * comes from the API; this card only formats them.
 */
import type { ScenarioResult } from "../api/client";
import { formatDate, formatEur, formatPercent, formatSignedEur } from "../lib/format";

type KeptAside = NonNullable<ScenarioResult["kept_aside"]>;

defineProps<{ kept: KeptAside; targetDate: string; annualReturn: number }>();
</script>

<template>
  <section class="rounded-lg border border-hairline bg-surface p-5" aria-labelledby="kept-heading">
    <h2 id="kept-heading" class="text-sm text-ink-2">Kept aside: not used for this goal</h2>
    <dl class="mt-3 grid gap-3 text-sm sm:grid-cols-3">
      <div>
        <dt class="text-xs text-ink-2">Savings</dt>
        <dd class="font-semibold tabular-nums">{{ formatEur(kept.savings_at_target) }}</dd>
        <dd class="text-xs text-ink-2">
          <template v-if="kept.savings_at_target < kept.savings_today">
            Cash falls below the {{ formatEur(kept.savings_today) }} kept
          </template>
          <template v-else>Stays the amount kept; cash earns nothing in the model</template>
        </dd>
      </div>
      <div>
        <dt class="text-xs text-ink-2">Investments</dt>
        <dd class="font-semibold tabular-nums">
          {{ formatEur(kept.investments_at_target) }}
        </dd>
        <dd class="text-xs text-ink-2">
          {{ formatEur(kept.investments_today) }} today,
          {{ formatSignedEur(kept.investment_growth) }} by
          {{ formatDate(targetDate) }} at the assumed
          {{ formatPercent(annualReturn) }}
        </dd>
      </div>
      <div>
        <dt class="text-xs text-ink-2">Total kept aside on {{ formatDate(targetDate) }}</dt>
        <dd class="font-semibold tabular-nums">{{ formatEur(kept.total_at_target) }}</dd>
        <dd class="text-xs text-ink-2">
          Cash + investments altogether: {{ formatEur(kept.liquid_at_target) }}
        </dd>
      </div>
    </dl>
  </section>
</template>
