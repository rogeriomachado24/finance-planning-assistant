/**
 * Unit conversion for rate inputs. People type "5" meaning 5%; the API stores 0.05.
 * This is a change of unit for display and input, not a financial calculation.
 */

/** 0.05 -> 5. Rounded so 0.07 shows as 7, not 7.000000000000001. */
export function rateToPercent(rate: number): number {
  return Number((rate * 100).toFixed(6));
}

/** 5 -> 0.05. Rounded so 5.1 becomes 0.051, not 0.050999999999999997. */
export function percentToRate(percent: number): number {
  return Number((percent / 100).toPrecision(12));
}
