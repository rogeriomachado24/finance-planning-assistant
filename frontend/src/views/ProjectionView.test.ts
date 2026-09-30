/** The projection page, mounted with a fake API: what the user sees in each state. */
import { flushPromises, mount, RouterLinkStub } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AssumptionSet, Goal, ScenarioResult, Snapshot } from "../api/client";
import { fakeApi, lastBody } from "../test/fakeApi";
import ProjectionView from "./ProjectionView.vue";

const RATES = { annual_return: 0.05, annual_salary_growth: 0.02, annual_expense_growth: 0.02, annual_inflation: 0.02 };

const SETS: AssumptionSet[] = ["conservative", "base", "optimistic"].map((name) => ({
  name,
  assumptions: RATES,
}));

const GOAL: Goal = {
  id: 1,
  is_active: true,
  name: "Buy a house",
  goal_type: "house",
  target_amount: 80_000,
  target_date: "2032-06-01",
  description: null,
};

function snapshot(month: number, liquid: number): Snapshot {
  const date = `${2026 + Math.floor((8 + month) / 12)}-${String(((8 + month) % 12) + 1).padStart(2, "0")}-01`;
  return {
    month, date, income: 2500, expenses: 1700, debt_payment: 0, surplus: 800, contribution: 400,
    withdrawal: 0, cash: liquid / 2, investments: liquid / 2, debt: 0, liquid_assets: liquid, net_worth: liquid,
  };
}

function result(overrides: Partial<ScenarioResult> = {}): ScenarioResult {
  return {
    scenario_name: "Current plan",
    profile: {
      monthly_net_income: 2500, monthly_expenses: 1700, cash: 10_000, investments: 15_000,
      monthly_investment_contribution: 400, other_monthly_income: 0, debt_balance: 0,
      monthly_debt_payment: 0, age: 32,
    },
    assumptions: RATES,
    monthly_contribution: 400,
    monthly_surplus: 800,
    target_amount: 80_000,
    target_date: "2032-06-01",
    months_to_target_date: 69,
    projected_goal_date: "2031-07-01",
    months_to_goal: 58,
    projected_value_at_target_date: 91_961.6,
    reaches_goal: true,
    shortfall: 0,
    required_monthly_contribution: 630.81,
    goal_progress: { current_amount: 25_000, remaining: 55_000, fraction: 0.3125 },
    warnings: [],
    snapshots: Array.from({ length: 70 }, (_, m) => snapshot(m, 25_000 + m * 970)),
    ...overrides,
  };
}

async function mountApp() {
  const wrapper = mount(ProjectionView, { global: { stubs: { RouterLink: RouterLinkStub } } });
  await flushPromises();
  return wrapper;
}

afterEach(() => vi.unstubAllGlobals());

describe("dashboard", () => {
  it("shows the projected goal date, the figures and the assumptions", async () => {
    fakeApi({ "/assumptions": [200, SETS], "/goals": [200, [GOAL]], "/simulate": [200, result()] });
    const text = (await mountApp()).text();

    expect(text).toContain("Buy a house · €80,000 by 1 Jun 2032");
    expect(text).toContain("1 Jul 2031");
    expect(text).toContain("On track");
    expect(text).toContain("reached 11 months before the target date");
    expect(text).toContain("€91,962");
    expect(text).toContain("€631");
    expect(text).toContain("Investment return");
    expect(text).toContain("This is a projection, not a guarantee");
  });

  it("describes a missed target without giving advice", async () => {
    fakeApi({
      "/assumptions": [200, SETS],
      "/goals": [200, [GOAL]],
      "/simulate": [
        200,
        result({
          reaches_goal: false,
          shortfall: 948.35,
          projected_goal_date: "2032-08-01",
          months_to_goal: 71,
          // like the API: the series runs to the later of the target date and the goal date
          snapshots: Array.from({ length: 72 }, (_, m) => snapshot(m, 25_000 + m * 790)),
        }),
      ],
    });
    const text = (await mountApp()).text();

    expect(text).toContain("Behind target");
    expect(text).toContain("not reached by 1 Jun 2032: €948 short");
    expect(text).toContain("It is reached on 1 Aug 2032 instead");
    expect(text).not.toMatch(/\byou should\b/i);
  });

  it("re-runs the projection with the chosen assumption set", async () => {
    const fetchMock = fakeApi({ "/assumptions": [200, SETS], "/goals": [200, [GOAL]], "/simulate": [200, result()] });
    const wrapper = await mountApp();

    await wrapper.find('input[value="conservative"]').setValue();
    await flushPromises();

    expect(lastBody(fetchMock, "POST", "/simulate")).toEqual({ assumption_set: "conservative" });
  });

  it.each([
    [{ has_profile: false, has_goal: false, ready: false }, "needs your finances and a goal"],
    [{ has_profile: true, has_goal: false, ready: false }, "needs a goal"],
  ])("names what's missing before a projection is possible (%j)", async (status, expected) => {
    fakeApi({
      "/assumptions": [200, SETS],
      "/goals": [200, []],
      "/plan/status": [200, status],
      "/simulate": [404, { detail: "no active goal has been saved yet" }],
    });
    const text = (await mountApp()).text();

    expect(text).toContain("Set up your plan first");
    expect(text).toContain(`To show your projection, the simulator ${expected}.`);
    expect(text).toContain("python -m app.seed");
  });

  it("says so when the API can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const text = (await mountApp()).text();

    expect(text).toContain("Couldn't load the projection");
    expect(text).toContain("Is the backend running?");
  });
});

describe("where you are today", () => {
  const PROFILE_OUT = {
    profile: {
      monthly_net_income: 2500, monthly_expenses: 1700, cash: 10_000, investments: 15_000,
      monthly_investment_contribution: 400, other_monthly_income: 0, debt_balance: 2_000,
      monthly_debt_payment: 0, age: 32,
    },
    position: {
      total_monthly_income: 2500, monthly_expenses: 1700, monthly_debt_payment: 0,
      monthly_surplus: 800, savings_rate: 0.32, liquid_assets: 25_000, net_worth: 23_000,
    },
  };

  it("shows progress towards the goal and today's figures, all from the API", async () => {
    fakeApi({
      "/assumptions": [200, SETS], "/goals": [200, [GOAL]], "/simulate": [200, result()],
      "/profile": [200, PROFILE_OUT],
    });
    const wrapper = await mountApp();
    const today = wrapper.find('[aria-labelledby="today-heading"]');

    expect(today.text()).toContain("€25,000 of €80,000 · 31.25% of the goal");
    expect(today.text()).toContain("€55,000 to go");
    const meter = today.find('[role="meter"]');
    expect(meter.attributes("aria-valuenow")).toBe("31");
    expect(meter.attributes("aria-valuetext")).toContain("31.25% of the goal");
    expect(today.text()).toContain("€23,000"); // net worth
    expect(today.text()).toContain("after €2,000 debt");
    expect(today.text()).toContain("32%"); // savings rate
  });

  it("still shows the progress when today's figures can't be loaded", async () => {
    fakeApi({ "/assumptions": [200, SETS], "/goals": [200, [GOAL]], "/simulate": [200, result()] });
    const today = (await mountApp()).find('[aria-labelledby="today-heading"]');
    expect(today.text()).toContain("31.25% of the goal");
    expect(today.find("dl").exists()).toBe(false);
  });
});
