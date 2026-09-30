/** A simulated-futures response shaped like the API's, for component and wording tests. */
import type { Uncertainty } from "../api/client";

export function uncertainty(overrides: Partial<Uncertainty> = {}): Uncertainty {
  return {
    scenario_name: "Current plan",
    assumption_set: "base",
    assumptions: {
      annual_return: 0.05, annual_salary_growth: 0.02, annual_expense_growth: 0.02, annual_inflation: 0.02,
    },
    investment_risk: "medium",
    volatility: 0.1,
    paths: 1000,
    seed: 2026,
    horizon_months: 189,
    target_amount: 80_000,
    target_date: "2032-06-01",
    months_to_target_date: 69,
    probability_by_target_date: 0.948,
    probability_margin: 0.0138,
    goal_dates: { p10: "2030-11-01", p50: "2031-07-01", p90: "2032-04-01" },
    not_reached_share: 0,
    value_at_target_date: { p10: 81_725.32, p50: 92_121.74, p90: 105_378.11 },
    shortfall_when_missed: { p10: 641.35, p50: 2_408.58, p90: 5_964.24 },
    required_monthly_investment: [
      { share: 0.5, monthly_amount: 638.23 },
      { share: 0.8, monthly_amount: 766.2 },
      { share: 0.9, monthly_amount: 836.54 },
    ],
    reached_by: [
      { date: "2027-01-01", share: 0 },
      { date: "2028-01-01", share: 0 },
      { date: "2029-01-01", share: 0 },
      { date: "2030-01-01", share: 0.003 },
      { date: "2031-01-01", share: 0.175 },
      { date: "2032-01-01", share: 0.819 },
      { date: "2032-06-01", share: 0.948 },
      { date: "2033-01-01", share: 0.994 },
      { date: "2034-01-01", share: 1 },
    ],
    bands: Array.from({ length: 190 }, (_, month) => ({
      month,
      date: `${2026 + Math.floor((8 + month) / 12)}-${String(((8 + month) % 12) + 1).padStart(2, "0")}-01`,
      p10: 25_000 + month * 800,
      p50: 25_000 + month * 970,
      p90: 25_000 + month * 1_150,
    })),
    ...overrides,
  };
}
