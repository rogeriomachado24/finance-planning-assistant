<script setup lang="ts">
/**
 * Scenarios side by side: the built-in levers, then the user's saved what-ifs, measured
 * against the current plan under one assumption set.
 */
import PageIntro from "../components/PageIntro.vue";
import { computed, onMounted, ref, watch } from "vue";
import {
  api,
  ApiError,
  type AssumptionSet,
  type ComparedFutures,
  type Comparison,
  type FuturesComparison,
} from "../api/client";
import AssumptionSetPicker from "../components/AssumptionSetPicker.vue";
import AssumptionsPanel from "../components/AssumptionsPanel.vue";
import ComparisonTable from "../components/ComparisonTable.vue";
import PageSummary from "../components/PageSummary.vue";
import SetupNeeded from "../components/SetupNeeded.vue";
import WhatIfForm from "../components/forms/WhatIfForm.vue";
import GoalChart, { type ChartSeries } from "../components/GoalChart.vue";
import { formatCount, formatDate, formatEur, formatPercent } from "../lib/format";
import { scenarioColors } from "../lib/scenarioColors";

const RISK_LABELS = { low: "Low", medium: "Medium", high: "High" } as const;

const sets = ref<AssumptionSet[]>([]);
const selectedSet = ref("base");
const comparison = ref<Comparison | null>(null);
const error = ref<ApiError | null>(null);
const loading = ref(true);
const deleting = ref<number | null>(null);
const deleteError = ref<string | null>(null);

let latestRequest = 0;

// Simulated futures per scenario: slower (about half a second per scenario), so they load
// after the table and fill in its last column.
const futures = ref<FuturesComparison | null>(null);
const futuresError = ref<ApiError | null>(null);
let latestFutures = 0;

async function loadFutures() {
  const request = ++latestFutures;
  futuresError.value = null;
  try {
    const result = await api.compareUncertainty(selectedSet.value);
    if (request === latestFutures) futures.value = result;
  } catch (e) {
    if (request !== latestFutures) return;
    futures.value = null;
    futuresError.value = e instanceof ApiError ? e : new ApiError(0, String(e));
  }
}

function reloadAll() {
  void loadFutures();
  return loadComparison();
}

async function loadComparison() {
  const request = ++latestRequest;
  loading.value = true;
  try {
    const result = await api.compare(selectedSet.value);
    if (request !== latestRequest) return; // a newer selection has taken over
    comparison.value = result;
    error.value = null;
  } catch (e) {
    if (request !== latestRequest) return;
    comparison.value = null;
    error.value = e instanceof ApiError ? e : new ApiError(0, String(e));
  } finally {
    if (request === latestRequest) loading.value = false;
  }
}

async function load() {
  try {
    sets.value = await api.assumptionSets();
  } catch (e) {
    error.value = e instanceof ApiError ? e : new ApiError(0, String(e));
    loading.value = false;
    return;
  }
  await reloadAll();
}

async function deleteScenario(id: number, name: string) {
  deleting.value = id;
  deleteError.value = null;
  try {
    await api.deleteScenario(id);
    await reloadAll();
  } catch (e) {
    deleteError.value = `Couldn't delete "${name}": ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    deleting.value = null;
  }
}

watch(selectedSet, reloadAll);
onMounted(load);

const scenarios = computed(() => comparison.value?.scenarios ?? []);
const baseline = computed(() => scenarios.value[0]?.result ?? null);
const colors = computed(() => scenarioColors(scenarios.value));
const series = computed<ChartSeries[]>(() =>
  scenarios.value
    .filter((s) => colors.value.has(s.name))
    .map((s) => ({
      key: s.name,
      name: s.name,
      color: colors.value.get(s.name)!,
      snapshots: s.result.snapshots,
      monthsToGoal: s.result.months_to_goal,
    })),
);
/** Futures by scenario name, only when they match the comparison on screen. */
const futuresByName = computed(() => {
  const f = futures.value;
  const c = comparison.value;
  if (!f || !c || f.assumption_set !== c.assumption_set) return null;
  const byName = new Map<string, ComparedFutures>(f.scenarios.map((s) => [s.name, s]));
  return c.scenarios.every((s) => byName.has(s.name)) ? byName : null;
});
const hiddenCount = computed(() => scenarios.value.length - series.value.length);
const selectedRates = computed(() => sets.value.find((s) => s.name === selectedSet.value)?.assumptions);
const noPlanYet = computed(() => error.value?.status === 404);
</script>

<template>
  <div>
    <PageIntro title="Compare scenarios" answers="How would different choices change when you reach your goal? Each scenario is measured against your current plan, which never changes here." />
    <div v-if="sets.length" class="mb-5">
      <AssumptionSetPicker v-model="selectedSet" :names="sets.map((s) => s.name)" />
    </div>

    <p v-if="loading && !comparison && !error" class="text-sm text-ink-2">Loading scenarios…</p>

    <SetupNeeded v-else-if="noPlanYet" what="a comparison" />

    <section v-else-if="error" class="rounded-lg border border-hairline bg-surface p-6" role="alert">
      <h2 class="font-semibold">Couldn't load the comparison</h2>
      <p class="mt-1 text-sm text-ink-2">{{ error.message }}</p>
      <button type="button" class="mt-3 rounded-md border border-hairline px-3 py-1.5 text-sm hover:bg-page" @click="load">
        Try again
      </button>
    </section>

    <div
      v-else-if="comparison && baseline"
      class="grid gap-5 transition-opacity lg:grid-cols-[1fr_320px]"
      :class="{ 'opacity-60': loading }"
      :aria-busy="loading"
    >
      <div class="min-w-0 space-y-5">
        <!-- Reset when the set or the scenarios change: a summary describes one comparison -->
        <PageSummary
          :load="() => api.explainCompare(selectedSet)"
          :reset-key="`${selectedSet}|${scenarios.map((s) => s.name).join('|')}`"
        />
        <figure class="rounded-lg border border-hairline bg-surface p-4 sm:p-5">
          <figcaption class="mb-3">
            <h2 class="font-semibold">Cash + investments by scenario</h2>
            <p class="text-sm text-ink-2">
              Target {{ formatEur(baseline.target_amount) }} by {{ formatDate(baseline.target_date) }},
              under the {{ comparison.assumption_set }} assumptions.
            </p>
          </figcaption>
          <!-- Legend: always present with two or more series -->
          <ul class="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2" aria-label="Legend">
            <li v-for="s in series" :key="s.key" class="flex items-center gap-1.5">
              <span class="h-0.5 w-4 rounded-full" :style="{ background: s.color }" aria-hidden="true" />
              {{ s.name }}
            </li>
          </ul>
          <GoalChart
            :series="series"
            :target-amount="baseline.target_amount"
            :target-date="baseline.target_date"
            :months-to-target="baseline.months_to_target_date"
          />
          <p v-if="hiddenCount" class="mt-2 text-xs text-ink-2">
            The chart shows 8 scenarios; {{ hiddenCount }} more are in the table below.
          </p>
        </figure>

        <section class="rounded-lg border border-hairline bg-surface p-4 sm:p-5" aria-labelledby="table-heading">
          <h2 id="table-heading" class="font-semibold">Side by side</h2>
          <p class="mb-3 text-sm text-ink-2">
            Differences are measured from the {{ comparison.baseline.toLowerCase() }}.
          </p>
          <p v-if="deleteError" class="mb-3 text-sm font-medium text-error" role="alert">
            {{ deleteError }}
          </p>
          <ComparisonTable
            :scenarios="scenarios"
            :colors="colors"
            :baseline="comparison.baseline.toLowerCase()"
            :deleting="deleting"
            :futures="futuresByName"
            :futures-error="futuresError?.message ?? null"
            @delete="deleteScenario"
          />
          <p v-if="futures && futuresByName" class="mt-3 text-xs text-ink-2">
            On time in simulated futures: the share of {{ formatCount(futures.paths) }} futures that
            reach the goal by the target date, with investment returns varying around the assumed
            return ({{ RISK_LABELS[futures.investment_risk].toLowerCase() }} investment risk: about
            {{ formatPercent(futures.volatility) }} a year). Every scenario runs on the same
            futures, so the differences come from the scenario, not from luck. Cash is safe in the
            model and investments vary, so investing more of the surplus can lower this share even
            when the typical outcome improves. A projection, not a guarantee.
          </p>
          <p v-else-if="futuresError" class="mt-3 text-xs text-ink-2" role="alert">
            Couldn't simulate the futures: {{ futuresError.message }}
            <button type="button" class="ml-1 underline hover:text-ink" @click="loadFutures">
              Try again
            </button>
          </p>
        </section>

        <section class="rounded-lg border border-hairline bg-surface p-4 sm:p-5" aria-labelledby="whatif-heading">
          <h2 id="whatif-heading" class="font-semibold">Try your own what-if</h2>
          <p class="mb-4 text-sm text-ink-2">
            Saved scenarios are compared with the plan above. They never change your plan.
          </p>
          <WhatIfForm :current-plan="baseline" @saved="reloadAll" />
        </section>
      </div>

      <div class="lg:sticky lg:top-6 lg:self-start">
        <AssumptionsPanel v-if="selectedRates" :name="selectedSet" :rates="selectedRates" />
      </div>
    </div>
  </div>
</template>
