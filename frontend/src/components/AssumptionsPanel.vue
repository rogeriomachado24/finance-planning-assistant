<script setup lang="ts">
/** Assumptions and simplifications, always shown next to the projection. */
import type { Rates } from "../api/client";
import { formatPercent } from "../lib/format";

defineProps<{ name: string; rates: Rates }>();

const RATE_LABELS: [keyof Rates, string][] = [
  ["annual_return", "Investment return"],
  ["annual_salary_growth", "Salary growth"],
  ["annual_expense_growth", "Expense growth"],
  ["annual_inflation", "Inflation"],
];

// docs/PHASE1_DESIGN.md, section 3.5
const SIMPLIFICATIONS = [
  "No taxes on investment gains",
  "No investment fees (the return is after fees)",
  "No interest on debt",
  "Amounts are not adjusted for inflation",
  "Salary growth applies to net income",
  "Rates stay constant every year",
  "Cash earns no interest",
];
</script>

<template>
  <aside class="rounded-lg border border-hairline bg-surface p-5 text-sm" aria-labelledby="assumptions-heading">
    <h2 id="assumptions-heading" class="font-semibold">Assumptions</h2>
    <p class="text-ink-2">
      <span class="capitalize">{{ name }}</span> set, per year. Editable; not forecasts.
    </p>
    <dl class="mt-3 divide-y divide-grid">
      <div v-for="[key, label] in RATE_LABELS" :key="key" class="flex justify-between py-1.5">
        <dt class="text-ink-2">{{ label }}</dt>
        <dd class="font-medium tabular-nums">{{ formatPercent(rates[key]) }}</dd>
      </div>
    </dl>
    <p class="mt-1 text-xs text-ink-2">Inflation is shown for reference and not used in the calculations.</p>

    <h3 class="mt-5 font-semibold">Simplifications</h3>
    <ul class="mt-1.5 list-disc space-y-0.5 pl-5 text-ink-2">
      <li v-for="item in SIMPLIFICATIONS" :key="item">{{ item }}</li>
    </ul>

    <p class="mt-5 rounded-md bg-page p-3 text-xs text-ink-2">
      This is a projection, not a guarantee, and not financial advice. Results depend entirely
      on the assumptions above.
    </p>
  </aside>
</template>
