<script setup lang="ts">
import { computed } from "vue";
import AssumptionSetPicker from "../components/AssumptionSetPicker.vue";
import AssumptionsPanel from "../components/AssumptionsPanel.vue";
import GoalStatus from "../components/GoalStatus.vue";
import SetupNeeded from "../components/SetupNeeded.vue";
import ProjectionCard from "../components/ProjectionCard.vue";
import StatTile from "../components/StatTile.vue";
import TodayCard from "../components/TodayCard.vue";
import WarningList from "../components/WarningList.vue";
import { useProjection } from "../composables/useProjection";
import { formatDate, formatEur, formatPercent } from "../lib/format";

const { assumptionSets, selectedSet, goal, result, today, error, loading, reload } = useProjection();

const setNames = computed(() => assumptionSets.value.map((s) => s.name));
const noPlanYet = computed(() => error.value?.status === 404);
</script>

<template>
  <div>
    <h1 class="sr-only">Projection</h1>
    <!-- Filter row: scopes everything below it -->
    <div v-if="setNames.length" class="mb-5">
      <AssumptionSetPicker v-model="selectedSet" :names="setNames" />
    </div>

    <p v-if="loading && !result && !error" class="text-sm text-ink-2">Loading projection…</p>

    <SetupNeeded v-else-if="noPlanYet" what="your projection" />

    <section
      v-else-if="error"
      class="rounded-lg border border-hairline bg-surface p-6"
      role="alert"
    >
      <h2 class="font-semibold">Couldn't load the projection</h2>
      <p class="mt-1 text-sm text-ink-2">{{ error.message }}</p>
      <button
        type="button"
        class="mt-3 rounded-md border border-hairline px-3 py-1.5 text-sm hover:bg-page"
        @click="reload"
      >
        Try again
      </button>
    </section>

    <div
      v-else-if="result"
      class="grid gap-5 transition-opacity lg:grid-cols-[1fr_320px]"
      :class="{ 'opacity-60': loading }"
      :aria-busy="loading"
    >
      <div class="min-w-0 space-y-5">
        <GoalStatus :result="result" :goal="goal" />
        <TodayCard :result="result" :today="today" />

        <div class="grid gap-4 sm:grid-cols-3">
          <StatTile
            label="Value on the target date"
            :value="formatEur(result.projected_value_at_target_date)"
            :note="`Target ${formatEur(result.target_amount)} on ${formatDate(result.target_date)}`"
          />
          <StatTile
            label="Needed per month"
            :value="result.required_monthly_contribution === null ? '—' : formatEur(result.required_monthly_contribution)"
            :note="`Invested at ${formatPercent(result.assumptions.annual_return)} a year, to reach the target on time`"
          />
          <StatTile
            label="Invested each month"
            :value="formatEur(result.monthly_contribution)"
            note="Planned contribution from your profile"
          />
        </div>

        <ProjectionCard :result="result" :assumption-set-name="selectedSet" />
        <WarningList :warnings="result.warnings" />
      </div>

      <div class="lg:sticky lg:top-6 lg:self-start">
        <AssumptionsPanel :name="selectedSet" :rates="result.assumptions" />
      </div>
    </div>
  </div>
</template>
