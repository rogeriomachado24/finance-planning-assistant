/** The compare page with a fake API. */
import { flushPromises, mount, RouterLinkStub } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  AssumptionSet,
  ComparedScenario,
  Comparison,
  FuturesComparison,
  ScenarioResult,
} from "../api/client";
import { fakeApi, lastBody } from "../test/fakeApi";
import CompareView from "./CompareView.vue";

const RATES = { annual_return: 0.05, annual_salary_growth: 0.02, annual_expense_growth: 0.02, annual_inflation: 0.02 };
const SETS: AssumptionSet[] = [{ name: "base", assumptions: RATES }];

function result(name: string, goalDate: string, monthsToGoal: number, value: number): ScenarioResult {
  return {
    scenario_name: name,
    profile: {
      monthly_net_income: 2500, monthly_expenses: 1700, cash: 10_000, investments: 15_000,
      monthly_investment_contribution: 400, other_monthly_income: 0, debt_balance: 0,
      monthly_debt_payment: 0, age: 32, investment_risk: "medium",
    },
    assumptions: RATES,
    monthly_contribution: 400,
    monthly_surplus: 800,
    target_amount: 80_000,
    target_date: "2032-06-01",
    months_to_target_date: 69,
    projected_goal_date: goalDate,
    months_to_goal: monthsToGoal,
    projected_value_at_target_date: value,
    reaches_goal: true,
    shortfall: 0,
    required_monthly_contribution: 630.81,
    goal_progress: { current_amount: 25_000, remaining: 55_000, fraction: 0.3125 },
    warnings: [],
    snapshots: Array.from({ length: 70 }, (_, m) => ({
      month: m, date: `${2026 + Math.floor((8 + m) / 12)}-${String(((8 + m) % 12) + 1).padStart(2, "0")}-01`,
      income: 2500, expenses: 1700, debt_payment: 0, surplus: 800, contribution: 400, withdrawal: 0,
      cash: 10_000, investments: 15_000 + m * 900, debt: 0, liquid_assets: 25_000 + m * 970, net_worth: 25_000 + m * 970,
    })),
  };
}

function compared(name: string, savedId: number | null, earlier: number, diff: number, r: ScenarioResult): ComparedScenario {
  return {
    name, description: `${name} description`, saved_id: savedId, result: r,
    vs_baseline: { goal_months_earlier: earlier, value_at_target_difference: diff },
  };
}

const COMPARISON: Comparison = {
  assumption_set: "base",
  baseline: "Current plan",
  scenarios: [
    compared("Current plan", null, 0, 0, result("Current plan", "2031-07-01", 58, 91_961.6)),
    compared("Higher income", null, 4, 8_901.35, result("Higher income", "2031-03-01", 54, 100_862.95)),
    compared("Spend €200 less", 7, 9, 14_477.05, result("Spend €200 less", "2030-10-01", 49, 106_438.65)),
  ],
};

async function mountCompare() {
  const wrapper = mount(CompareView, { global: { stubs: { RouterLink: RouterLinkStub } } });
  await flushPromises();
  return wrapper;
}

afterEach(() => vi.unstubAllGlobals());

describe("compare page", () => {
  it("shows every scenario with the differences the API computed", async () => {
    fakeApi({ "GET /assumptions": [200, SETS], "POST /scenarios/compare": [200, COMPARISON] });
    const wrapper = await mountCompare();
    const rows = wrapper.findAll("tbody tr").map((r) => r.text());

    expect(rows).toHaveLength(3);
    expect(rows[0]).toContain("Baseline");
    expect(rows[1]).toContain("1 Mar 2031");
    expect(rows[1]).toContain("4 months earlier");
    expect(rows[1]).toContain("+€8,901");
    expect(rows[2]).toContain("9 months earlier");
    expect(wrapper.find('[aria-label="Legend"]').text()).toContain("Spend €200 less");
    expect(wrapper.text()).toContain("This is a projection, not a guarantee");
  });

  it("only saved scenarios can be deleted", async () => {
    const fetchMock = fakeApi({
      "GET /assumptions": [200, SETS],
      "POST /scenarios/compare": [200, COMPARISON],
      "DELETE /scenarios/7": [204, null],
    });
    const wrapper = await mountCompare();
    const deleteButtons = wrapper.findAll("button").filter((b) => b.text() === "Delete");

    expect(deleteButtons).toHaveLength(1);
    await deleteButtons[0].trigger("click");
    await flushPromises();
    expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/scenarios/7" && init?.method === "DELETE")).toBe(true);
    const compareCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/scenarios/compare");
    expect(compareCalls).toHaveLength(2); // reloaded after deleting
  });

  it("says so when a delete fails", async () => {
    fakeApi({
      "GET /assumptions": [200, SETS],
      "POST /scenarios/compare": [200, COMPARISON],
      "DELETE /scenarios/7": [404, { detail: "no saved scenario with id 7" }],
    });
    const wrapper = await mountCompare();
    await wrapper.findAll("button").find((b) => b.text() === "Delete")!.trigger("click");
    await flushPromises();

    expect(wrapper.find('[role="alert"]').text()).toBe(
      "Couldn't delete \"Spend €200 less\": no saved scenario with id 7",
    );
  });

  it("saves a what-if with empty fields as 'keep' and percentages as decimals", async () => {
    const fetchMock = fakeApi({
      "GET /assumptions": [200, SETS],
      "POST /scenarios/compare": [200, COMPARISON],
      "POST /scenarios": [201, { id: 8, name: "Return only 3%", description: "", overrides: {} }],
    });
    const wrapper = await mountCompare();

    await wrapper.find("#whatif-name").setValue("Return only 3%");
    await wrapper.find("#whatif-return").setValue("3");
    await wrapper.find("#whatif-contribution").setValue("-100");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(lastBody(fetchMock, "POST", "/scenarios")).toEqual({
      name: "Return only 3%",
      description: "",
      overrides: {
        monthly_investment_contribution_delta: -100,
        monthly_net_income: null,
        monthly_expenses: null,
        annual_return: 0.03,
        annual_salary_growth: null,
        first_year_return: null,
        annual_expense_growth: null,
      },
    });
    expect(wrapper.text()).toContain("It's now in the comparison");
  });

  it("asks for at least one change before saving", async () => {
    const fetchMock = fakeApi({ "GET /assumptions": [200, SETS], "POST /scenarios/compare": [200, COMPARISON] });
    const wrapper = await mountCompare();

    await wrapper.find("#whatif-name").setValue("Nothing new");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Change at least one value");
    expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/scenarios" && init?.method === "POST")).toBe(false);
  });
});

describe("simulated futures per scenario", () => {
  const summary = (p: number, margin: number) => ({
    probability_by_target_date: p,
    probability_margin: margin,
    goal_dates: { p10: "2030-11-01", p50: "2031-07-01", p90: "2032-04-01" },
    not_reached_share: 0,
    value_at_target_date: { p10: 81_725, p50: 92_122, p90: 105_378 },
    shortfall_when_missed: null,
    required_monthly_investment: [],
  });
  const FUTURES: FuturesComparison = {
    assumption_set: "base",
    investment_risk: "medium",
    volatility: 0.1,
    paths: 1000,
    seed: 2026,
    baseline: "Current plan",
    scenarios: [
      { ...summary(0.948, 0.0138), name: "Current plan", saved_id: null, probability_difference: 0 },
      { ...summary(1, 0), name: "Higher income", saved_id: null, probability_difference: 0.052 },
      { ...summary(0.937, 0.0151), name: "Spend €200 less", saved_id: 7, probability_difference: -0.011 },
    ],
  };

  it("adds the share of futures on time, with precision and differences from the API", async () => {
    fakeApi({
      "GET /assumptions": [200, SETS],
      "POST /scenarios/compare": [200, COMPARISON],
      "POST /scenarios/compare/uncertainty": [200, FUTURES],
    });
    const wrapper = await mountCompare();
    const rows = wrapper.findAll("tbody tr").map((r) => r.text());

    expect(rows[0]).toContain("95%");
    expect(rows[0]).toContain("±1 point");
    expect(rows[1]).toContain("more than 99%");
    expect(rows[1]).toContain("+5 points");
    expect(rows[2]).toContain("−1 point");
    expect(wrapper.text()).toContain("Every scenario runs on the same futures");
    expect(wrapper.text()).toContain("medium investment risk: about 10% a year");
  });

  it("shows the table first and says the futures are still simulating", async () => {
    fakeApi({
      "GET /assumptions": [200, SETS],
      "POST /scenarios/compare": [200, COMPARISON],
      "POST /scenarios/compare/uncertainty": [200, { ...FUTURES, assumption_set: "optimistic" }],
    });
    const wrapper = await mountCompare();

    // Futures for another assumption set are never shown next to this comparison
    expect(wrapper.findAll("tbody tr")[0].text()).toContain("Simulating…");
    expect(wrapper.text()).not.toContain("±1 point");
  });

  it("keeps the comparison when the simulation fails, with a way to retry", async () => {
    fakeApi({
      "GET /assumptions": [200, SETS],
      "POST /scenarios/compare": [200, COMPARISON],
      "POST /scenarios/compare/uncertainty": [500, { detail: "simulation failed" }],
    });
    const wrapper = await mountCompare();

    expect(wrapper.findAll("tbody tr")).toHaveLength(3);
    expect(wrapper.text()).toContain("Couldn't simulate the futures: simulation failed");
    expect(wrapper.find("button.underline").text()).toBe("Try again");
  });
});
