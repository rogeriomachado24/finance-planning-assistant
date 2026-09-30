/**
 * Wording for the simulated futures. Every figure is the API's; these functions only choose
 * sentences and which of the API's rows to show.
 */
import type { Uncertainty } from "../api/client";
import { formatCount, formatDate, formatEur, formatMonthYear, formatShare } from "./format";

/** "of 1,000 simulated futures reach €80,000 by 1 Jun 2032", after the share. */
export function probabilitySentence(u: Uncertainty): string {
  return (
    `of ${formatCount(u.paths)} simulated futures reach ${formatEur(u.target_amount)} ` +
    `by ${formatDate(u.target_date)}`
  );
}

/** The end of the simulated period, e.g. "Jun 2042". */
export function horizonEnd(u: Uncertainty): string {
  return formatMonthYear(u.bands[u.bands.length - 1].date);
}

export function goalDateRange(u: Uncertainty): string {
  const { p10, p50, p90 } = u.goal_dates;
  if (p10 && p50 && p90) {
    return (
      `In the middle 80% of futures, the goal is reached between ${formatMonthYear(p10)} ` +
      `and ${formatMonthYear(p90)} (in half of them by ${formatMonthYear(p50)}).`
    );
  }
  if (p10) {
    const half = p50 ? `, and in half of them by ${formatMonthYear(p50)}` : "";
    return (
      `The goal is reached by ${formatMonthYear(p10)} in 10% of futures${half}. ` +
      `In ${formatShare(u.not_reached_share)} of futures, it is not reached by ${horizonEnd(u)}.`
    );
  }
  return `In most simulated futures, the goal is not reached by ${horizonEnd(u)}.`;
}

export function valueRange(u: Uncertainty): string {
  const v = u.value_at_target_date;
  return (
    `On ${formatDate(u.target_date)}, cash + investments are between ${formatEur(v.p10)} and ` +
    `${formatEur(v.p90)} in the middle 80% of futures (${formatEur(v.p50)} in the middle one).`
  );
}

export function shortfallSentence(u: Uncertainty): string | null {
  const s = u.shortfall_when_missed;
  if (!s) return null;
  return (
    `In the futures that miss the target date, they are typically ${formatEur(s.p50)} short ` +
    `(${formatEur(s.p90)} or more in the worst tenth of those).`
  );
}

export type ReachedByRow = { key: string; label: string; share: number; isTarget: boolean };

/**
 * The API's "reached by" checkpoints (each 1 January and the target date), from the first
 * with any futures to the first with nearly all of them, thinned to about `maxRows`.
 */
export function reachedByRows(u: Uncertainty, maxRows = 8): ReachedByRow[] {
  const all = u.reached_by.map((r) => ({
    key: r.date,
    label: `By ${formatDate(r.date)}${r.date === u.target_date ? " (target date)" : ""}`,
    share: r.share,
    isTarget: r.date === u.target_date,
  }));
  const targetIndex = all.findIndex((r) => r.isTarget);
  const firstAny = all.findIndex((r) => r.share > 0);
  const nearlyAll = all.findIndex((r) => r.share > 0.99);
  const from = Math.min(firstAny === -1 ? targetIndex : firstAny, targetIndex);
  const to = Math.max(nearlyAll === -1 ? all.length - 1 : nearlyAll, targetIndex);
  const shown = all.slice(from, to + 1);
  const every = Math.ceil(shown.length / maxRows);
  return shown.filter((r, i) => r.isTarget || i === shown.length - 1 || i % every === 0);
}

/** For newcomers: "95% means about 95 in every 100 simulated futures." Null at the ends. */
export function shareExplained(u: Uncertainty): string | null {
  const p = u.probability_by_target_date;
  if (p < 0.01 || p > 0.99) return null;
  return `${formatShare(p)} means about ${Math.round(p * 100)} in every 100 simulated futures.`;
}
