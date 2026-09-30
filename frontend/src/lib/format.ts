/**
 * Display formatting only: EUR in en-IE style, dates like "1 Jun 2032". The API has
 * already rounded every amount; nothing here changes a value, it only presents it.
 */

const eur = new Intl.NumberFormat("en-IE", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});
const eurCents = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });
const eurCompact = new Intl.NumberFormat("en-IE", {
  style: "currency",
  currency: "EUR",
  notation: "compact",
  maximumFractionDigits: 1,
});
const percent = new Intl.NumberFormat("en-IE", { style: "percent", maximumFractionDigits: 2 });

// Fixed three-letter months: Intl's en-IE output varies by browser ("Sep" vs "Sept").
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "€91,962" (or "€91,961.60" with cents). */
export function formatEur(value: number, options: { cents?: boolean } = {}): string {
  return (options.cents ? eurCents : eur).format(value);
}

/** Short axis labels: "€20K", "€1.5M". */
export function formatEurCompact(value: number): string {
  return eurCompact.format(value);
}

/** 0.05 -> "5%", 0.025 -> "2.5%". */
export function formatPercent(rate: number): string {
  return percent.format(rate);
}

/** "2032-06-01" -> "1 Jun 2032". Reads the ISO parts directly: no Date, so no time-zone shifts. */
export function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

/** 29 -> "2 years 5 months", 12 -> "1 year", 1 -> "1 month". */
export function formatDuration(months: number): string {
  const years = Math.floor(months / 12);
  const rest = months % 12;
  const parts = [];
  if (years) parts.push(`${years} ${years === 1 ? "year" : "years"}`);
  if (rest || !years) parts.push(`${rest} ${rest === 1 ? "month" : "months"}`);
  return parts.join(" ");
}

/** API difference in months -> "4 months earlier", "1 year later", "Same time". */
export function formatMonthsEarlier(monthsEarlier: number): string {
  if (monthsEarlier === 0) return "Same time";
  return `${formatDuration(Math.abs(monthsEarlier))} ${monthsEarlier > 0 ? "earlier" : "later"}`;
}

/** API difference in euros -> "+€8,900", "−€1,050" (true minus sign), "€0". */
export function formatSignedEur(value: number): string {
  const text = formatEur(Math.abs(value));
  if (text === "€0") return text;
  return `${value > 0 ? "+" : "−"}${text}`;
}

const wholePercent = new Intl.NumberFormat("en-IE", { style: "percent", maximumFractionDigits: 0 });
const count = new Intl.NumberFormat("en-IE");

/**
 * A share of simulated futures, as whole percentages: 0.948 -> "95%". The ends read "more
 * than 99%" and "fewer than 1%", because 1,000 futures can't show certainty.
 */
export function formatShare(share: number): string {
  if (share > 0.99) return "more than 99%";
  if (share < 0.01) return "fewer than 1%";
  return wholePercent.format(share);
}

/** Precision of a share, in whole percentage points: 0.0138 -> "±1 point". */
export function formatPoints(margin: number): string {
  const points = Math.round(margin * 100);
  if (points < 1) return "less than ±1 point";
  return `±${points} ${points === 1 ? "point" : "points"}`;
}

/** "2030-11-01" -> "Nov 2030". */
export function formatMonthYear(iso: string): string {
  const [year, month] = iso.split("-").map(Number);
  return `${MONTHS[month - 1]} ${year}`;
}

/** 1000 -> "1,000". */
export function formatCount(value: number): string {
  return count.format(value);
}

/**
 * API difference in shares -> "+3 points", "−1 point" (true minus sign), "Same" when there is
 * no difference, "Less than 1 point" when it rounds away.
 */
export function formatPointsDifference(difference: number): string {
  if (difference === 0) return "Same";
  const points = Math.round(difference * 100);
  if (points === 0) return "Less than 1 point";
  const size = Math.abs(points);
  return `${points > 0 ? "+" : "−"}${size} ${size === 1 ? "point" : "points"}`;
}

/** A share of futures as a level: 0.5 -> "Half", 0.8 -> "8 in 10", 0.95 -> "95%". */
export function formatShareLevel(share: number): string {
  if (share === 0.5) return "Half";
  const tenths = share * 10;
  if (Number.isInteger(Math.round(tenths * 1e9) / 1e9)) return `${Math.round(tenths)} in 10`;
  return wholePercent.format(share);
}
