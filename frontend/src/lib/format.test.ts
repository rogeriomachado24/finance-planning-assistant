import { describe, expect, it } from "vitest";
import {
  formatCount,
  formatDate,
  formatDuration,
  formatEur,
  formatEurCompact,
  formatMonthsEarlier,
  formatMonthYear,
  formatPercent,
  formatPoints,
  formatPointsDifference,
  formatShare,
  formatShareLevel,
  formatSignedEur,
} from "./format";

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

describe("differences from the baseline", () => {
  it.each([
    [0, "Same time"],
    [4, "4 months earlier"],
    [-1, "1 month later"],
    [14, "1 year 2 months earlier"],
  ])("%i months -> %s", (months, expected) => {
    expect(formatMonthsEarlier(months)).toBe(expected);
  });

  it.each([
    [8900.4, "+€8,900"],
    [-1050, "−€1,050"],
    [0, "€0"],
    [0.3, "€0"],
  ])("%f -> %s", (value, expected) => {
    expect(formatSignedEur(value)).toBe(expected);
  });
});

describe("formatShare", () => {
  it("rounds a share of futures to whole percentages", () => {
    expect(formatShare(0.948)).toBe("95%");
    expect(formatShare(0.5)).toBe("50%");
    expect(formatShare(0.99)).toBe("99%");
    expect(formatShare(0.01)).toBe("1%");
  });

  it("never claims certainty at the ends", () => {
    expect(formatShare(1)).toBe("more than 99%");
    expect(formatShare(0.994)).toBe("more than 99%");
    expect(formatShare(0)).toBe("fewer than 1%");
    expect(formatShare(0.004)).toBe("fewer than 1%");
  });
});

describe("formatPoints", () => {
  it("shows the precision in whole percentage points", () => {
    expect(formatPoints(0.0138)).toBe("±1 point");
    expect(formatPoints(0.0231)).toBe("±2 points");
    expect(formatPoints(0.003)).toBe("less than ±1 point");
    expect(formatPoints(0)).toBe("less than ±1 point");
  });
});

describe("formatMonthYear and formatCount", () => {
  it("formats without time zones or locale surprises", () => {
    expect(formatMonthYear("2030-11-01")).toBe("Nov 2030");
    expect(formatCount(1000)).toBe("1,000");
  });
});

describe("formatPointsDifference", () => {
  it("shows the API's whole-point difference with a sign", () => {
    expect(formatPointsDifference(3)).toBe("+3 points");
    expect(formatPointsDifference(-1)).toBe("−1 point");
    expect(formatPointsDifference(0)).toBe("Same");
  });
});

describe("formatShareLevel", () => {
  it("names the usual levels in words", () => {
    expect(formatShareLevel(0.5)).toBe("Half");
    expect(formatShareLevel(0.8)).toBe("8 in 10");
    expect(formatShareLevel(0.9)).toBe("9 in 10");
    expect(formatShareLevel(0.95)).toBe("95%");
  });
});
