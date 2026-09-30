import { describe, expect, it } from "vitest";
import type { ChatIntent } from "../api/client";
import { describeIntent, scenarioName } from "./intent";

const whatIf = (overrides: Record<string, number>, assumption_set: string | null = null) =>
  ({ kind: "what_if", overrides, assumption_set }) as ChatIntent;

describe("describeIntent", () => {
  it.each([
    [whatIf({ monthly_investment_contribution_delta: 200 }), "what if: invest €200 more a month"],
    [whatIf({ monthly_expenses_delta: -150 }), "what if: spend €150 less a month"],
    [whatIf({ monthly_investment_contribution: 0 }), "what if: stop investing"],
    [whatIf({ annual_return: 0.03 }), "what if: a 3% yearly return"],
    [
      whatIf({ monthly_investment_contribution_delta: 200, monthly_expenses_delta: -100 }),
      "what if: invest €200 more a month and spend €100 less a month",
    ],
    [whatIf({ monthly_net_income: 3000 }, "conservative"), "what if: take-home pay of €3,000 a month (conservative assumptions)"],
  ])("describes %j", (intent, expected) => {
    expect(describeIntent(intent)).toBe(expected);
  });

  it("describes questions and refusals", () => {
    expect(describeIntent({ kind: "goal_date", assumption_set: null } as ChatIntent)).toBe(
      "when the goal is reached",
    );
    expect(describeIntent({ kind: "unsupported", reason: "advice" } as ChatIntent)).toBe(
      "a request for advice",
    );
  });
});

describe("scenarioName", () => {
  it("names a saved what-if after its changes", () => {
    expect(scenarioName({ monthly_investment_contribution_delta: 200 })).toBe("Invest €200 more a month");
    expect(scenarioName({ monthly_expenses_delta: -150, annual_return: 0.03 })).toBe(
      "Spend €150 less a month and a 3% yearly return",
    );
  });
});
