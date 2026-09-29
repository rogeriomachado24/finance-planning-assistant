import { describe, expect, it } from "vitest";
import { linearScale, nearestIndex, niceTicks, valueDomain, yearTicks } from "./chart";

describe("niceTicks", () => {
  it("uses round steps and ends at or above the maximum", () => {
    expect(niceTicks(96_600)).toEqual([0, 20_000, 40_000, 60_000, 80_000, 100_000]);
    expect(niceTicks(84_000)).toEqual([0, 20_000, 40_000, 60_000, 80_000, 100_000]);
    expect(niceTicks(1_150)).toEqual([0, 250, 500, 750, 1_000, 1_250]);
  });

  it("handles an empty range", () => {
    expect(niceTicks(0)).toEqual([0]);
  });
});

describe("valueDomain", () => {
  it("starts at zero for positive balances", () => {
    expect(valueDomain([25_000, 91_962, 80_000]).domain).toEqual([0, 100_000]);
  });

  it("extends below zero when the balance goes negative", () => {
    const { domain } = valueDomain([1_000, -2_000]);
    expect(domain[0]).toBeLessThan(-2_000);
  });
});

describe("yearTicks", () => {
  const months = (start: string, count: number) =>
    Array.from({ length: count }, (_, i) => {
      const [y, m] = start.split("-").map(Number);
      const index = y * 12 + (m - 1) + i;
      return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}-01`;
    });

  it("labels every January for short horizons", () => {
    const dates = months("2026-09", 70);
    expect(yearTicks(dates).map((i) => dates[i])).toEqual([
      "2027-01-01",
      "2028-01-01",
      "2029-01-01",
      "2030-01-01",
      "2031-01-01",
      "2032-01-01",
    ]);
  });

  it("thins labels on long horizons", () => {
    const dates = months("2026-09", 600);
    const years = yearTicks(dates).map((i) => Number(dates[i].slice(0, 4)));
    expect(years.length).toBeLessThanOrEqual(8);
    expect(years.every((y) => y % 10 === 0)).toBe(true);
  });
});

describe("nearestIndex", () => {
  const scale = linearScale([0, 10], [100, 200]); // 10px per month

  it("snaps to the closest month", () => {
    expect(nearestIndex(134, 11, scale)).toBe(3);
    expect(nearestIndex(136, 11, scale)).toBe(4);
  });

  it("clamps outside the plot", () => {
    expect(nearestIndex(0, 11, scale)).toBe(0);
    expect(nearestIndex(999, 11, scale)).toBe(10);
  });
});
