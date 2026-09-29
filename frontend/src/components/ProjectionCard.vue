<script setup lang="ts">
import { ref } from "vue";
import type { ScenarioResult } from "../api/client";
import ProjectionChart from "./ProjectionChart.vue";
import ProjectionTable from "./ProjectionTable.vue";

defineProps<{ result: ScenarioResult; assumptionSetName: string }>();

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

    <ProjectionTable
      v-if="showTable"
      :snapshots="result.snapshots"
      :months-to-target="result.months_to_target_date"
      :months-to-goal="result.months_to_goal"
    />
    <ProjectionChart
      v-else
      :snapshots="result.snapshots"
      :target-amount="result.target_amount"
      :target-date="result.target_date"
      :months-to-target="result.months_to_target_date"
      :months-to-goal="result.months_to_goal"
    />
  </figure>
</template>
