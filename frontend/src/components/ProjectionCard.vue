<script setup lang="ts">
import { ref } from "vue";
import type { BandPoint, ScenarioResult } from "../api/client";
import { formatCount, formatPercent } from "../lib/format";
import GoalChart from "./GoalChart.vue";
import ProjectionTable from "./ProjectionTable.vue";

defineProps<{
  result: ScenarioResult;
  assumptionSetName: string;
  /** Middle 80% of simulated futures, when loaded for the same assumption set. */
  band?: BandPoint[];
  paths?: number;
}>();

const showTable = ref(false);
</script>

<template>
  <figure class="rounded-lg border border-hairline bg-surface p-4 sm:p-5">
    <figcaption class="mb-3 flex items-start justify-between gap-4">
      <div>
        <h2 class="font-semibold">Cash + investments over time</h2>
        <p class="text-sm text-ink-2">
          Monthly projection under the {{ assumptionSetName }} assumptions. Both count towards
          the goal.
        </p>
      </div>
      <button
        type="button"
        class="shrink-0 rounded-md border border-hairline px-2.5 py-1 text-xs text-ink-2 hover:bg-page"
        :aria-pressed="showTable"
        @click="showTable = !showTable"
      >
        {{ showTable ? "Chart view" : "Table view" }}
      </button>
    </figcaption>

    <!-- Legend: only needed once there are two marks to tell apart -->
    <ul v-if="band && !showTable" class="mb-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-2">
      <li class="flex items-center gap-2">
        <span class="h-0.5 w-4 rounded-full bg-series-1" aria-hidden="true" />
        Projection at the assumed {{ formatPercent(result.assumptions.annual_return) }} return
      </li>
      <li class="flex items-center gap-2">
        <span
          class="h-3 w-4 rounded-sm"
          :style="{ background: 'var(--color-series-1)', opacity: 'var(--band-opacity)' }"
          aria-hidden="true"
        />
        Middle 80% of {{ paths ? formatCount(paths) : "" }} simulated futures
      </li>
    </ul>

    <ProjectionTable
      v-if="showTable"
      :snapshots="result.snapshots"
      :months-to-target="result.months_to_target_date"
      :months-to-goal="result.months_to_goal"
      :band="band"
    />
    <GoalChart
      v-else
      :series="[
        {
          key: 'plan',
          name: result.scenario_name,
          color: 'var(--color-series-1)',
          snapshots: result.snapshots,
          monthsToGoal: result.months_to_goal,
        },
      ]"
      :target-amount="result.target_amount"
      :target-date="result.target_date"
      :months-to-target="result.months_to_target_date"
      :band="band"
    />
  </figure>
</template>
