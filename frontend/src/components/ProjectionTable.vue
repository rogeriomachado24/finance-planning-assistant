<script setup lang="ts">
/** The chart's accessible twin: yearly rows plus the target-date and goal rows. */
import { computed } from "vue";
import type { BandPoint, Snapshot } from "../api/client";
import { formatDate, formatEur } from "../lib/format";

const props = defineProps<{
  snapshots: Snapshot[];
  monthsToTarget: number;
  monthsToGoal: number | null;
  band?: BandPoint[];
}>();

const rows = computed(() => {
  const last = props.snapshots.length - 1;
  const months = new Set([0, last, props.monthsToTarget]);
  for (let m = 12; m < last; m += 12) months.add(m);
  if (props.monthsToGoal !== null) months.add(props.monthsToGoal);

  return [...months]
    .sort((a, b) => a - b)
    .map((month) => {
      const notes = [];
      if (month === 0) notes.push("Today");
      if (month === props.monthsToTarget) notes.push("Target date");
      if (month === props.monthsToGoal) notes.push("Goal reached");
      return {
        snapshot: props.snapshots[month],
        band: props.band?.[month] ?? null,
        note: notes.join(" · "),
      };
    });
});
</script>

<template>
  <div class="max-h-[300px] overflow-auto">
    <table class="w-full text-sm">
      <caption class="sr-only">
        Projected cash and investments, yearly, with the target date and goal date<template
          v-if="band"
        >, and the middle 80% of simulated futures</template>
      </caption>
      <thead class="sticky top-0 bg-surface text-left text-xs text-ink-2">
        <tr class="border-b border-grid">
          <th scope="col" class="py-2 pr-4 font-medium">Date</th>
          <th scope="col" class="py-2 pr-4 text-right font-medium">Cash</th>
          <th scope="col" class="py-2 pr-4 text-right font-medium">Investments</th>
          <th scope="col" class="py-2 pr-4 text-right font-medium">Cash + investments</th>
          <th v-if="band" scope="col" class="py-2 pr-4 text-right font-medium">
            Middle 80% of futures
          </th>
          <th scope="col" class="py-2 font-medium"><span class="sr-only">Note</span></th>
        </tr>
      </thead>
      <tbody class="tabular-nums">
        <tr v-for="{ snapshot, band: range, note } in rows" :key="snapshot.month" class="border-b border-grid">
          <td class="py-1.5 pr-4 whitespace-nowrap">{{ formatDate(snapshot.date) }}</td>
          <td class="py-1.5 pr-4 text-right">{{ formatEur(snapshot.cash) }}</td>
          <td class="py-1.5 pr-4 text-right">{{ formatEur(snapshot.investments) }}</td>
          <td class="py-1.5 pr-4 text-right font-medium">{{ formatEur(snapshot.liquid_assets) }}</td>
          <td v-if="band" class="py-1.5 pr-4 text-right whitespace-nowrap">
            {{ range ? `${formatEur(range.p10)} – ${formatEur(range.p90)}` : "—" }}
          </td>
          <td class="py-1.5 text-xs text-ink-2">{{ note }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
