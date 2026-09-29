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
