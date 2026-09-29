<script setup lang="ts">
/**
 * Liquid assets (cash + investments) month by month, against the goal's target amount.
 * Hand-drawn SVG: one series line with a light area wash, a dashed target threshold,
 * the target date, and a marker where the goal is first reached. Hover or arrow keys
 * move a crosshair that reads out the month; the table view carries every value too.
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { Snapshot } from "../api/client";
import { linearScale, nearestIndex, valueDomain, yearTicks } from "../lib/chart";
import { formatDate, formatEur, formatEurCompact } from "../lib/format";

const props = defineProps<{
  snapshots: Snapshot[];
  targetAmount: number;
  targetDate: string;
  monthsToTarget: number;
  monthsToGoal: number | null;
}>();

const HEIGHT = 300; // includes the x-axis band, so the card never needs to scroll
const M = { top: 28, right: 16, bottom: 32, left: 60 };
const TOOLTIP_WIDTH = 200;

const container = ref<HTMLDivElement | null>(null);
const width = ref(640);
let observer: ResizeObserver | undefined;

onMounted(() => {
  if (!container.value || typeof ResizeObserver === "undefined") return;
  observer = new ResizeObserver(([entry]) => {
    width.value = Math.max(300, Math.floor(entry.contentRect.width));
  });
  observer.observe(container.value);
});
onBeforeUnmount(() => observer?.disconnect());

const values = computed(() => props.snapshots.map((s) => s.liquid_assets));
const yAxis = computed(() => valueDomain([...values.value, props.targetAmount]));
const x = computed(() =>
  linearScale([0, props.snapshots.length - 1], [M.left, width.value - M.right]),
);
const y = computed(() => linearScale(yAxis.value.domain, [HEIGHT - M.bottom, M.top]));
const xTicks = computed(() => yearTicks(props.snapshots.map((s) => s.date)));

const linePath = computed(() =>
  values.value
    .map((v, i) => `${i ? "L" : "M"}${x.value(i).toFixed(1)},${y.value(v).toFixed(1)}`)
    .join(""),
);
const areaPath = computed(() => {
  const base = y.value(0).toFixed(1);
  const last = x.value(values.value.length - 1).toFixed(1);
  return `${linePath.value}L${last},${base}L${x.value(0).toFixed(1)},${base}Z`;
});

const targetY = computed(() => y.value(props.targetAmount));
const targetDateX = computed(() => x.value(props.monthsToTarget));
const goalPoint = computed(() => {
  const month = props.monthsToGoal;
  if (month === null) return null;
  const px = x.value(month);
  return {
    x: px,
    y: y.value(values.value[month]),
    label: `Goal reached · ${formatDate(props.snapshots[month].date)}`,
    anchor: px < M.left + 160 ? "start" : "end",
  } as const;
});

// ---- Hover / keyboard crosshair -----------------------------------------------------------
const active = ref<number | null>(null);
const activeSnapshot = computed(() =>
  active.value === null ? null : props.snapshots[active.value],
);
const tooltipLeft = computed(() => {
  if (active.value === null) return 0;
  const px = x.value(active.value);
  return px + 12 + TOOLTIP_WIDTH > width.value ? px - 12 - TOOLTIP_WIDTH : px + 12;
});
const readout = computed(() => {
  const s = activeSnapshot.value;
  return s ? `${formatDate(s.date)}: ${formatEur(s.liquid_assets)} in cash and investments` : "";
});

function onPointerMove(event: PointerEvent) {
  const svg = event.currentTarget as SVGSVGElement;
  const localX = event.clientX - svg.getBoundingClientRect().left;
  active.value = nearestIndex(localX, props.snapshots.length, x.value);
}

function onKeydown(event: KeyboardEvent) {
  const last = props.snapshots.length - 1;
  const current = active.value ?? 0;
  const moves: Record<string, number> = {
    ArrowRight: current + 1,
    ArrowLeft: current - 1,
    PageUp: current + 12,
    PageDown: current - 12,
    Home: 0,
    End: last,
  };
  if (event.key === "Escape") {
    active.value = null;
    return;
  }
  if (!(event.key in moves)) return;
  event.preventDefault();
  active.value = Math.min(last, Math.max(0, moves[event.key]));
}
</script>

<template>
  <div
    ref="container"
    class="relative outline-none focus-visible:ring-2 focus-visible:ring-series-1 rounded-md"
    tabindex="0"
    role="group"
    aria-label="Projection chart of cash plus investments by month. Use the arrow keys to read values, Page Up and Page Down to move by a year."
    @keydown="onKeydown"
    @focus="active ??= 0"
    @blur="active = null"
  >
    <svg
      :width="width"
      :height="HEIGHT"
      class="block touch-pan-y"
      aria-hidden="true"
      @pointermove="onPointerMove"
      @pointerleave="active = null"
    >
      <!-- Grid and y-axis labels -->
      <g v-for="tick in yAxis.ticks" :key="tick">
        <line
          :x1="M.left"
          :x2="width - M.right"
          :y1="y(tick)"
          :y2="y(tick)"
          :class="tick === 0 ? 'stroke-axis' : 'stroke-grid'"
          stroke-width="1"
          shape-rendering="crispEdges"
        />
        <text
          :x="M.left - 8"
          :y="y(tick)"
          text-anchor="end"
          dominant-baseline="middle"
          class="fill-muted text-xs tabular-nums"
        >
          {{ formatEurCompact(tick) }}
        </text>
      </g>

      <!-- X-axis year labels -->
      <text
        v-for="i in xTicks"
        :key="i"
        :x="x(i)"
        :y="HEIGHT - M.bottom + 20"
        text-anchor="middle"
        class="fill-muted text-xs tabular-nums"
      >
        {{ snapshots[i].date.slice(0, 4) }}
      </text>

      <!-- Target date: vertical reference -->
      <line
        :x1="targetDateX"
        :x2="targetDateX"
        :y1="M.top"
        :y2="HEIGHT - M.bottom"
        class="stroke-axis"
        stroke-width="1"
        shape-rendering="crispEdges"
      />
      <text
        :x="targetDateX"
        :y="M.top - 10"
        :text-anchor="targetDateX > width - M.right - 60 ? 'end' : 'middle'"
        class="fill-ink-2 text-xs"
      >
        Target date · {{ formatDate(targetDate) }}
      </text>

      <!-- Series: area wash + 2px line -->
      <path :d="areaPath" class="fill-series-1" fill-opacity="0.1" />
      <path
        :d="linePath"
        fill="none"
        class="stroke-series-1"
        stroke-width="2"
        stroke-linejoin="round"
        stroke-linecap="round"
      />

      <!-- Target amount: dashed threshold (dashing means "threshold", never a gridline) -->
      <line
        :x1="M.left"
        :x2="width - M.right"
        :y1="targetY"
        :y2="targetY"
        class="stroke-ink-2"
        stroke-width="1"
        stroke-dasharray="4 3"
        shape-rendering="crispEdges"
      />
      <!-- Below the line, so it never meets the goal label (which sits above it) -->
      <text
        :x="M.left + 6"
        :y="targetY + 16"
        class="fill-ink-2 text-xs halo"
      >
        Target {{ formatEur(targetAmount) }}
      </text>

      <!-- Where the goal is first reached -->
      <g v-if="goalPoint">
        <circle :cx="goalPoint.x" :cy="goalPoint.y" r="5" class="fill-series-1 stroke-surface" stroke-width="2" />
        <text
          :x="goalPoint.anchor === 'end' ? goalPoint.x - 10 : goalPoint.x + 10"
          :y="goalPoint.y - 10"
          :text-anchor="goalPoint.anchor"
          class="fill-ink text-xs font-medium halo"
        >
          {{ goalPoint.label }}
        </text>
      </g>

      <!-- Crosshair -->
      <g v-if="active !== null">
        <line
          :x1="x(active)"
          :x2="x(active)"
          :y1="M.top"
          :y2="HEIGHT - M.bottom"
          class="stroke-ink-2"
          stroke-width="1"
          shape-rendering="crispEdges"
        />
        <circle :cx="x(active)" :cy="y(values[active])" r="4" class="fill-series-1 stroke-surface" stroke-width="2" />
      </g>
    </svg>

    <!-- Tooltip: value first, then its label, then the breakdown -->
    <div
      v-if="activeSnapshot"
      class="pointer-events-none absolute rounded-md border border-hairline bg-surface px-3 py-2 text-xs shadow-sm"
      :style="{ left: `${tooltipLeft}px`, top: `${M.top}px`, width: `${TOOLTIP_WIDTH}px` }"
    >
      <div class="text-ink-2">{{ formatDate(activeSnapshot.date) }}</div>
      <div class="mt-1 flex items-center gap-2">
        <span class="h-0.5 w-3 rounded-full bg-series-1" />
        <span class="text-sm font-semibold text-ink">{{ formatEur(activeSnapshot.liquid_assets) }}</span>
      </div>
      <div class="text-ink-2">Cash + investments</div>
      <dl class="mt-1.5 grid grid-cols-[1fr_auto] gap-x-3 text-ink-2 tabular-nums">
        <dt>Cash</dt>
        <dd class="text-right">{{ formatEur(activeSnapshot.cash) }}</dd>
        <dt>Investments</dt>
        <dd class="text-right">{{ formatEur(activeSnapshot.investments) }}</dd>
      </dl>
    </div>

    <p class="sr-only" aria-live="polite">{{ readout }}</p>
  </div>
</template>

<style scoped>
/* A surface-coloured outline behind label text keeps it legible where it crosses a line. */
.halo {
  paint-order: stroke;
  stroke: var(--color-surface);
  stroke-width: 4px;
  stroke-linejoin: round;
}
</style>
