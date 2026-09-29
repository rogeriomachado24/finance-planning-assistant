import { describe, expect, it } from "vitest";
import { formatDate, formatDuration, formatEur, formatEurCompact, formatPercent } from "./format";

describe("formatEur", () => {
  it("formats whole euros with en-IE grouping", () => {
    expect(formatEur(91961.6)).toBe("€91,962");
    expect(formatEur(0)).toBe("€0");
  });

  it("can show cents", () => {
    expect(formatEur(91961.6, { cents: true })).toBe("€91,961.60");
  });

  it("compacts axis labels", () => {
    expect(formatEurCompact(20000)).toBe("€20K");
    expect(formatEurCompact(1500000)).toBe("€1.5M");
  });
});

describe("formatDate", () => {
  it.each([
    ["2032-06-01", "1 Jun 2032"],
    ["2026-09-01", "1 Sep 2026"],
    ["2031-12-31", "31 Dec 2031"],
  ])("%s -> %s", (iso, expected) => {
    expect(formatDate(iso)).toBe(expected);
  });
});

describe("formatPercent", () => {
  it("shows rates stored as decimals as percentages", () => {
    expect(formatPercent(0.05)).toBe("5%");
    expect(formatPercent(0.025)).toBe("2.5%");
  });
});

describe("formatDuration", () => {
  it.each([
    [1, "1 month"],
    [11, "11 months"],
    [12, "1 year"],
    [29, "2 years 5 months"],
    [0, "0 months"],
  ])("%i months -> %s", (months, expected) => {
    expect(formatDuration(months)).toBe(expected);
  });
});
