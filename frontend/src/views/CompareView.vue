<script setup lang="ts">
/**
 * Scenarios side by side: the built-in levers, then the user's saved what-ifs, measured
 * against the current plan under one assumption set.
 */
import { computed, onMounted, ref, watch } from "vue";
import { api, ApiError, type AssumptionSet, type Comparison } from "../api/client";
import AssumptionSetPicker from "../components/AssumptionSetPicker.vue";
import AssumptionsPanel from "../components/AssumptionsPanel.vue";
import ComparisonTable from "../components/ComparisonTable.vue";
import WhatIfForm from "../components/forms/WhatIfForm.vue";
import GoalChart, { type ChartSeries } from "../components/GoalChart.vue";
import { formatDate, formatEur } from "../lib/format";
import { scenarioColors } from "../lib/scenarioColors";

const sets = ref<AssumptionSet[]>([]);
const selectedSet = ref("base");
const comparison = ref<Comparison | null>(null);
const error = ref<ApiError | null>(null);
const loading = ref(true);
const deleting = ref<number | null>(null);
const deleteError = ref<string | null>(null);

let latestRequest = 0;

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
  await loadComparison();
}

async function deleteScenario(id: number, name: string) {
  deleting.value = id;
  deleteError.value = null;
  try {
    await api.deleteScenario(id);
    await loadComparison();
  } catch (e) {
    deleteError.value = `Couldn't delete "${name}": ${e instanceof Error ? e.message : String(e)}`;
  } finally {
    deleting.value = null;
  }
}

watch(selectedSet, loadComparison);
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
const hiddenCount = computed(() => scenarios.value.length - series.value.length);
const selectedRates = computed(() => sets.value.find((s) => s.name === selectedSet.value)?.assumptions);
const noPlanYet = computed(() => error.value?.status === 404);
</script>

<template>
  <div>
    <h1 class="sr-only">Compare scenarios</h1>
    <div v-if="sets.length" class="mb-5">
      <AssumptionSetPicker v-model="selectedSet" :names="sets.map((s) => s.name)" />
    </div>

    <p v-if="loading && !comparison && !error" class="text-sm text-ink-2">Loading scenarios…</p>

    <section v-else-if="noPlanYet" class="rounded-lg border border-hairline bg-surface p-6" aria-labelledby="empty-heading">
      <h2 id="empty-heading" class="font-semibold">No plan yet</h2>
      <p class="mt-1 text-sm text-ink-2">The API says: {{ error?.message }}.</p>
      <RouterLink to="/plan" class="mt-4 inline-block rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-surface">
        Set up your plan
      </RouterLink>
    </section>

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
            @delete="deleteScenario"
          />
        </section>

        <section class="rounded-lg border border-hairline bg-surface p-4 sm:p-5" aria-labelledby="whatif-heading">
          <h2 id="whatif-heading" class="font-semibold">Try your own what-if</h2>
          <p class="mb-4 text-sm text-ink-2">
            Saved scenarios are compared with the plan above. They never change your plan.
          </p>
          <WhatIfForm :current-plan="baseline" @saved="loadComparison" />
        </section>
      </div>

      <div class="lg:sticky lg:top-6 lg:self-start">
        <AssumptionsPanel v-if="selectedRates" :name="selectedSet" :rates="selectedRates" />
      </div>
    </div>
  </div>
</template>
