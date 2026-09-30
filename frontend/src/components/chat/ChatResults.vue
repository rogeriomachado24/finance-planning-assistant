<script setup lang="ts">
/**
 * The engine's figures behind a chat reply, as cards. The reply text is commentary; these
 * numbers come straight from the API (the same values as the dashboard). The reply itself
 * always ends with the assumptions (added by code, never by a model), so they're not
 * repeated here.
 */
import { computed } from "vue";
import type { ChatResponse } from "../../api/client";
import { formatDate, formatEur, formatMonthsEarlier, formatSignedEur } from "../../lib/format";

const props = defineProps<{ response: ChatResponse }>();

const kind = computed(() => props.response.intent.kind);
const results = computed(() => props.response.results);
const current = computed(() => results.value[0]?.result ?? null);

const goalDate = (date: string | null) => (date ? formatDate(date) : "Not within 50 years");
</script>

<template>
  <div v-if="response.assumptions" class="mt-3 space-y-3">
    <!-- What-if: the current plan next to the changed plan -->
    <div v-if="kind === 'what_if' && results.length === 2" class="grid gap-2 sm:grid-cols-2">
      <div
        v-for="(s, i) in results"
        :key="s.name"
        class="rounded-md border border-hairline bg-page p-3"
      >
        <p class="text-xs font-medium text-ink-2">{{ i === 0 ? "Current plan" : "With the change" }}</p>
        <dl class="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-sm">
          <dt class="text-ink-2">Goal reached</dt>
          <dd class="text-right font-medium">{{ goalDate(s.result.projected_goal_date) }}</dd>
          <dt class="text-ink-2">On {{ formatDate(s.result.target_date) }}</dt>
          <dd class="text-right font-medium tabular-nums">
            {{ formatEur(s.result.projected_value_at_target_date) }}
          </dd>
        </dl>
        <p v-if="i === 1" class="mt-1.5 text-xs text-ink-2">
          <template v-if="s.vs_baseline.goal_months_earlier !== null">
            {{ formatMonthsEarlier(s.vs_baseline.goal_months_earlier) }} ·
          </template>
          {{ formatSignedEur(s.vs_baseline.value_at_target_difference) }} on the target date
        </p>
      </div>
    </div>

    <!-- Comparison: one line per scenario -->
    <ul
      v-else-if="kind === 'compare_scenarios'"
      class="divide-y divide-hairline rounded-md border border-hairline bg-page text-sm"
    >
      <li v-for="(s, i) in results" :key="s.name" class="flex flex-wrap justify-between gap-x-4 px-3 py-2">
        <span class="font-medium">{{ s.name }}</span>
        <span class="text-ink-2 tabular-nums">
          {{ goalDate(s.result.projected_goal_date) }}
          <template v-if="i > 0 && s.vs_baseline.goal_months_earlier !== null">
            ({{ formatMonthsEarlier(s.vs_baseline.goal_months_earlier).toLowerCase() }})
          </template>
          · {{ formatEur(s.result.projected_value_at_target_date) }}
        </span>
      </li>
    </ul>

    <!-- Needed per month -->
    <dl
      v-else-if="kind === 'required_contribution' && current"
      class="grid grid-cols-3 gap-2 text-sm"
    >
      <div class="rounded-md border border-hairline bg-page p-3">
        <dt class="text-xs text-ink-2">Needed per month</dt>
        <dd class="text-lg font-semibold">
          {{ current.required_monthly_contribution === null ? "—" : formatEur(current.required_monthly_contribution) }}
        </dd>
      </div>
      <div class="rounded-md border border-hairline bg-page p-3">
        <dt class="text-xs text-ink-2">Invested today</dt>
        <dd class="text-lg font-semibold">{{ formatEur(current.monthly_contribution) }}</dd>
      </div>
      <div class="rounded-md border border-hairline bg-page p-3">
        <dt class="text-xs text-ink-2">Monthly surplus</dt>
        <dd class="text-lg font-semibold">{{ formatEur(current.monthly_surplus) }}</dd>
      </div>
    </dl>

    <!-- On track / goal date -->
    <dl
      v-else-if="(kind === 'run_projection' || kind === 'goal_date') && current"
      class="grid grid-cols-2 gap-2 text-sm"
    >
      <div class="rounded-md border border-hairline bg-page p-3">
        <dt class="text-xs text-ink-2">Goal reached</dt>
        <dd class="text-lg font-semibold">{{ goalDate(current.projected_goal_date) }}</dd>
      </div>
      <div class="rounded-md border border-hairline bg-page p-3">
        <dt class="text-xs text-ink-2">On {{ formatDate(current.target_date) }}</dt>
        <dd class="text-lg font-semibold tabular-nums">
          {{ formatEur(current.projected_value_at_target_date) }}
        </dd>
      </div>
    </dl>

    <p class="text-xs text-ink-2">
      <RouterLink
        :to="kind === 'compare_scenarios' || kind === 'what_if' ? '/compare' : '/'"
        class="font-medium text-ink underline underline-offset-2"
      >
        {{ kind === "compare_scenarios" || kind === "what_if" ? "Open Compare" : "See the projection" }}
      </RouterLink>
    </p>
  </div>
</template>
