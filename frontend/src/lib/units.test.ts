import { describe, expect, it } from "vitest";
import { percentToRate, rateToPercent } from "./units";

describe("rate <-> percent", () => {
  it.each([
    [0.05, 5],
    [0.07, 7],
    [0.025, 2.5],
    [0.0525, 5.25],
    [-0.01, -1],
    [0, 0],
  ])("%f is shown as %f%% and converts back exactly", (rate, percent) => {
    expect(rateToPercent(rate)).toBe(percent);
    expect(percentToRate(percent)).toBe(rate);
  });

  it("cleans floating-point noise", () => {
    expect(percentToRate(5.1)).toBe(0.051);
    expect(rateToPercent(0.051)).toBe(5.1);
  });
});
