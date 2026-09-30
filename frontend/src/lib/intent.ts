/**
 * "Understood as …": how the chat read a message, in words. Shown under each reply so a
 * misreading is visible immediately. Formatting only: amounts come from the intent as is.
 */
import type { ChatIntent, Overrides } from "../api/client";
import { formatEur, formatPercent } from "./format";

type Change = (value: number) => string;

const CHANGES: [keyof Overrides, Change][] = [
  ["monthly_investment_contribution", (v) => (v === 0 ? "stop investing" : `invest ${formatEur(v)} a month`)],
  ["monthly_investment_contribution_delta", (v) => `invest ${formatEur(Math.abs(v))} ${v > 0 ? "more" : "less"} a month`],
  ["monthly_net_income", (v) => `take-home pay of ${formatEur(v)} a month`],
  ["monthly_net_income_delta", (v) => `${formatEur(Math.abs(v))} ${v > 0 ? "more" : "less"} take-home pay a month`],
  ["monthly_expenses", (v) => `expenses of ${formatEur(v)} a month`],
  ["monthly_expenses_delta", (v) => `spend ${formatEur(Math.abs(v))} ${v > 0 ? "more" : "less"} a month`],
  ["annual_return", (v) => `a ${formatPercent(v)} yearly return`],
  ["annual_salary_growth", (v) => `salary growth of ${formatPercent(v)} a year`],
  ["annual_expense_growth", (v) => `expense growth of ${formatPercent(v)} a year`],
  ["first_year_return", (v) => `investments ${v < 0 ? "fall" : "rise"} ${formatPercent(Math.abs(v))} in the first year`],
];

const QUESTIONS: Record<string, string> = {
  run_projection: "how the plan is doing",
  goal_date: "when the goal is reached",
  required_contribution: "how much is needed each month",
  compare_scenarios: "compare the scenarios",
  likelihood: "how likely the goal is reached on time",
  explain_assumptions: "the assumptions used",
  needs_clarification: "something unclear",
};

const REASONS: Record<string, string> = {
  advice: "a request for advice",
  out_of_scope: "outside what the simulator covers",
  not_understood: "not understood",
};

/** The changes a what-if makes, in words: ["invest €200 more a month", ...]. */
export function describeChanges(overrides: Overrides): string[] {
  return CHANGES.flatMap(([key, describe]) => {
    const value = overrides[key];
    return value === null || value === undefined ? [] : [describe(value)];
  });
}

/** A default name for saving a what-if: "Invest €200 more a month". */
export function scenarioName(overrides: Overrides): string {
  const text = describeChanges(overrides).join(" and ");
  return (text.charAt(0).toUpperCase() + text.slice(1)).slice(0, 100);
}

export function describeIntent(intent: ChatIntent): string {
  let text: string;
  if (intent.kind === "what_if") {
    text = `what if: ${describeChanges(intent.overrides).join(" and ")}`;
  } else if (intent.kind === "required_contribution" && intent.share) {
    text = `how much is needed each month to reach it in ${formatPercent(intent.share)} of simulated futures`;
  } else if (intent.kind === "likelihood" && intent.overrides) {
    text = `how likely, if: ${describeChanges(intent.overrides).join(" and ")}`;
  } else if (intent.kind === "unsupported") {
    text = REASONS[intent.reason];
  } else {
    text = QUESTIONS[intent.kind];
  }
  const set = "assumption_set" in intent && intent.assumption_set;
  return set ? `${text} (${set} assumptions)` : text;
}
