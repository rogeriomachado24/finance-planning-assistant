<script setup lang="ts">
/**
 * Liquid assets (cash + investments) month by month, against the goal's target amount.
 * Hand-drawn SVG: one line per series, a dashed target threshold, the target date, and a
 * marker where each series first reaches the goal. With a single series the line gets a
 * light area wash and a direct "goal reached" label; with several, identity comes from
 * the legend (drawn by the parent), the tooltip and the table view, because end labels of
 * converging lines would collide. Hover or arrow keys move a crosshair that reads out the
 * month for every series. An optional band (single series only) shades the middle 80% of
 * simulated futures behind the line, cut to the months the line covers.
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { BandPoint, Snapshot } from "../api/client";
import { linearScale, nearestIndex, valueDomain, yearTicks } from "../lib/chart";
import { formatDate, formatEur, formatEurCompact } from "../lib/format";

export type ChartSeries = {
  key: string;
  name: string;
  /** A colour token, e.g. "var(--color-series-2)". Follows the entity, never its rank. */
  color: string;
  snapshots: Snapshot[];
  monthsToGoal: number | null;
};

const props = defineProps<{
  series: ChartSeries[];
  targetAmount: number;
  targetDate: string;
  monthsToTarget: number;
  /** 10th and 90th percentile of simulated futures by month, from the API. */
  band?: BandPoint[];
}>();

const HEIGHT = 300; // includes the x-axis band, so the card never needs to scroll
const M = { top: 28, right: 16, bottom: 32, left: 60 };
const TOOLTIP_WIDTH = 220;

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

const single = computed(() => props.series.length === 1);
/** The longest series sets the months on the x axis (series end at different months). */
const months = computed(() =>
  props.series.reduce((a, b) => (b.snapshots.length > a.length ? b.snapshots : a), [] as Snapshot[]),
);
const bandPoints = computed(() =>
  single.value && props.band ? props.band.slice(0, months.value.length) : [],
);
const yAxis = computed(() =>
  valueDomain([
    ...props.series.flatMap((s) => s.snapshots.map((p) => p.liquid_assets)),
    ...bandPoints.value.flatMap((b) => [b.p10, b.p90]),
    props.targetAmount,
  ]),
);
const x = computed(() => linearScale([0, months.value.length - 1], [M.left, width.value - M.right]));
const y = computed(() => linearScale(yAxis.value.domain, [HEIGHT - M.bottom, M.top]));
const xTicks = computed(() => yearTicks(months.value.map((s) => s.date)));

const lines = computed(() =>
  props.series.map((s) => {
    const path = s.snapshots
      .map((p, i) => `${i ? "L" : "M"}${x.value(i).toFixed(1)},${y.value(p.liquid_assets).toFixed(1)}`)
      .join("");
    const goal =
      s.monthsToGoal === null
        ? null
        : { x: x.value(s.monthsToGoal), y: y.value(s.snapshots[s.monthsToGoal].liquid_assets) };
    return { ...s, path, goal };
  }),
);

const bandPath = computed(() => {
  const points = bandPoints.value;
  if (!points.length) return null;
  const upper = points.map((b) => `${x.value(b.month).toFixed(1)},${y.value(b.p90).toFixed(1)}`);
  const lower = points.map((b) => `${x.value(b.month).toFixed(1)},${y.value(b.p10).toFixed(1)}`).reverse();
  return `M${upper.join("L")}L${lower.join("L")}Z`;
});

const areaPath = computed(() => {
  if (!single.value || bandPath.value) return null;
  const base = y.value(0).toFixed(1);
  const last = x.value(props.series[0].snapshots.length - 1).toFixed(1);
  return `${lines.value[0].path}L${last},${base}L${x.value(0).toFixed(1)},${base}Z`;
});

const targetY = computed(() => y.value(props.targetAmount));
const targetDateX = computed(() => x.value(props.monthsToTarget));
const goalLabel = computed(() => {
  const s = props.series[0];
  if (!single.value || s.monthsToGoal === null) return null;
  const px = x.value(s.monthsToGoal);
  return {
    x: px,
    y: y.value(s.snapshots[s.monthsToGoal].liquid_assets),
    text: `Goal reached · ${formatDate(s.snapshots[s.monthsToGoal].date)}`,
    anchor: px < M.left + 160 ? "start" : "end",
  } as const;
});

// ---- Hover / keyboard crosshair -----------------------------------------------------------
const active = ref<number | null>(null);
/** Each series' snapshot at the active month (a series may already have ended). */
const readings = computed(() => {
  const month = active.value;
  if (month === null) return [];
  return props.series.map((s) => ({ ...s, point: s.snapshots[month] ?? null }));
});
const activeBand = computed(() =>
  active.value === null ? null : (bandPoints.value[active.value] ?? null),
);
const activeDate = computed(() => (active.value === null ? null : months.value[active.value].date));
const tooltipLeft = computed(() => {
  if (active.value === null) return 0;
  const px = x.value(active.value);
  return px + 12 + TOOLTIP_WIDTH > width.value ? px - 12 - TOOLTIP_WIDTH : px + 12;
});
const readout = computed(() => {
  if (!activeDate.value) return "";
  const values = readings.value
    .filter((r) => r.point)
    .map((r) => `${single.value ? "" : `${r.name} `}${formatEur(r.point!.liquid_assets)}`);
  const band = activeBand.value
    ? `; middle 80% of simulated futures ${formatEur(activeBand.value.p10)} to ${formatEur(activeBand.value.p90)}`
    : "";
  return `${formatDate(activeDate.value)}: ${values.join(", ")}${band}`;
});

function onPointerMove(event: PointerEvent) {
  const svg = event.currentTarget as SVGSVGElement;
  const localX = event.clientX - svg.getBoundingClientRect().left;
  active.value = nearestIndex(localX, months.value.length, x.value);
}

function onKeydown(event: KeyboardEvent) {
  const last = months.value.length - 1;
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
    aria-label="Chart of cash plus investments by month. Use the arrow keys to read values, Page Up and Page Down to move by a year."
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
        {{ months[i].date.slice(0, 4) }}
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

      <!-- Band: middle 80% of simulated futures, under the line it surrounds -->
      <path
        v-if="bandPath"
        :d="bandPath"
        :style="{ fill: series[0].color, fillOpacity: 'var(--band-opacity)' }"
      />

      <!-- Series: 2px lines (plus a light area wash when there is only one and no band) -->
      <path v-if="areaPath" :d="areaPath" :style="{ fill: series[0].color }" fill-opacity="0.1" />
      <path
        v-for="line in lines"
        :key="line.key"
        :d="line.path"
        fill="none"
        :style="{ stroke: line.color }"
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
      <text :x="M.left + 6" :y="targetY + 16" class="fill-ink-2 text-xs halo">
        Target {{ formatEur(targetAmount) }}
      </text>

      <!-- Where each series first reaches the goal -->
      <template v-for="line in lines" :key="`goal-${line.key}`">
        <circle
          v-if="line.goal"
          :cx="line.goal.x"
          :cy="line.goal.y"
          r="5"
          class="stroke-surface"
          :style="{ fill: line.color }"
          stroke-width="2"
        />
      </template>
      <text
        v-if="goalLabel"
        :x="goalLabel.anchor === 'end' ? goalLabel.x - 10 : goalLabel.x + 10"
        :y="goalLabel.y - 10"
        :text-anchor="goalLabel.anchor"
        class="fill-ink text-xs font-medium halo"
      >
        {{ goalLabel.text }}
      </text>

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
        <template v-for="r in readings" :key="`dot-${r.key}`">
          <circle
            v-if="r.point"
            :cx="x(active)"
            :cy="y(r.point.liquid_assets)"
            r="4"
            class="stroke-surface"
            :style="{ fill: r.color }"
            stroke-width="2"
          />
        </template>
      </g>
    </svg>

    <!-- Tooltip: values lead, names follow; one row per series -->
    <div
      v-if="activeDate"
      class="pointer-events-none absolute rounded-md border border-hairline bg-surface px-3 py-2 text-xs shadow-sm"
      :style="{ left: `${tooltipLeft}px`, top: `${M.top}px`, width: `${TOOLTIP_WIDTH}px` }"
    >
      <div class="text-ink-2">{{ formatDate(activeDate) }}</div>
      <template v-if="single && readings[0]?.point">
        <div class="mt-1 flex items-center gap-2">
          <span class="h-0.5 w-3 rounded-full" :style="{ background: series[0].color }" />
          <span class="text-sm font-semibold text-ink">{{ formatEur(readings[0].point.liquid_assets) }}</span>
        </div>
        <div class="text-ink-2">Cash + investments</div>
        <dl class="mt-1.5 grid grid-cols-[1fr_auto] gap-x-3 text-ink-2 tabular-nums">
          <dt>Cash</dt>
          <dd class="text-right">{{ formatEur(readings[0].point.cash) }}</dd>
          <dt>Investments</dt>
          <dd class="text-right">{{ formatEur(readings[0].point.investments) }}</dd>
        </dl>
        <div v-if="activeBand" class="mt-1.5 border-t border-grid pt-1.5 text-ink-2">
          <div>Middle 80% of simulated futures</div>
          <div class="font-medium text-ink tabular-nums">
            {{ formatEur(activeBand.p10) }} – {{ formatEur(activeBand.p90) }}
          </div>
        </div>
      </template>
      <ul v-else class="mt-1 space-y-0.5">
        <li v-for="r in readings" :key="r.key" class="flex items-center gap-2">
          <span class="h-0.5 w-3 shrink-0 rounded-full" :style="{ background: r.color }" />
          <span class="font-semibold text-ink tabular-nums">
            {{ r.point ? formatEur(r.point.liquid_assets) : "—" }}
          </span>
          <span class="truncate text-ink-2">{{ r.name }}</span>
        </li>
      </ul>
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
