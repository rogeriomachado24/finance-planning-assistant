/**
 * Geometry for the projection chart: mapping values to pixels and choosing axis ticks.
 * Pure functions, so they're unit-tested without rendering anything.
 */

export type Scale = (value: number) => number;

/** Map [d0, d1] onto [r0, r1] linearly. */
export function linearScale([d0, d1]: [number, number], [r0, r1]: [number, number]): Scale {
  const span = d1 - d0 || 1;
  return (value) => r0 + ((value - d0) / span) * (r1 - r0);
}

/**
 * Round y-axis ticks from 0 to at least `max`: steps of 1, 2, 2.5 or 5 x 10^n, so labels
 * read €0 / €20K / €40K rather than €0 / €17,391 / €34,782.
 */
export function niceTicks(max: number, targetCount = 5): number[] {
  if (max <= 0) return [0];
  const rough = max / targetCount;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough)!;
  const ticks = [];
  for (let value = 0; value < max + step; value += step) {
    ticks.push(Number(value.toPrecision(12)));
    if (value >= max) break;
  }
  return ticks;
}

/**
 * Month indexes (into the snapshot series) that start a new year, thinned to at most
 * `maxTicks` labels: every year for short horizons, every 2, 5 or 10 years for long ones.
 */
export function yearTicks(dates: string[], maxTicks = 8): number[] {
  const januaries = dates.flatMap((iso, i) => (iso.slice(5, 7) === "01" ? [i] : []));
  const every = [1, 2, 5, 10, 20].find((n) => Math.ceil(januaries.length / n) <= maxTicks) ?? 20;
  return januaries.filter((i) => Number(dates[i].slice(0, 4)) % every === 0);
}

/**
 * Y domain [bottom, top] and its ticks. Starts at 0, unless the plan runs out of money and
 * the balance goes negative; the top is the first round tick above the largest value.
 */
export function valueDomain(values: number[]): { domain: [number, number]; ticks: number[] } {
  const ticks = niceTicks(Math.max(0, ...values) * 1.05);
  const low = Math.min(0, ...values);
  return { domain: [low < 0 ? low * 1.05 : 0, ticks.at(-1)!], ticks };
}

/** Index of the point closest to pixel `x`, for the hover crosshair. */
export function nearestIndex(x: number, count: number, scale: Scale): number {
  if (count <= 1) return 0;
  const step = scale(1) - scale(0);
  return Math.min(count - 1, Math.max(0, Math.round((x - scale(0)) / step)));
}
