/** The plan page with a fake API: what's sent when saving, and how errors are shown. */
import { flushPromises, mount, RouterLinkStub, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AssumptionSet, DraftReply, Goal, ProfileOut } from "../api/client";
import { fakeApi, lastBody } from "../test/fakeApi";
import PlanView from "./PlanView.vue";

const SETS: AssumptionSet[] = [
  { name: "conservative", assumptions: { annual_return: 0.02, annual_salary_growth: 0.01, annual_expense_growth: 0.03, annual_inflation: 0.03 } },
  { name: "base", assumptions: { annual_return: 0.05, annual_salary_growth: 0.02, annual_expense_growth: 0.02, annual_inflation: 0.02 } },
  { name: "optimistic", assumptions: { annual_return: 0.07, annual_salary_growth: 0.03, annual_expense_growth: 0.02, annual_inflation: 0.02 } },
];

const HOUSE: Goal = {
  id: 1, is_active: true, name: "Buy a house", goal_type: "house", target_amount: 80_000,
  target_date: "2032-06-01", description: null, keep_savings: 0, keep_investments: 0,
};

const SAVED_PROFILE: ProfileOut = {
  profile: {
    monthly_net_income: 2500, monthly_expenses: 1700, cash: 10_000, investments: 0,
    monthly_investment_contribution: 0, other_monthly_income: 0, debt_balance: 0,
    monthly_debt_payment: 0, age: null, investment_risk: "medium",
  },
  position: {
    total_monthly_income: 2500, monthly_expenses: 1700, monthly_debt_payment: 0,
    monthly_surplus: 800, savings_rate: 0.32, liquid_assets: 10_000, net_worth: 10_000,
  },
};

const NOT_STARTED = { has_profile: false, has_goal: false, ready: false };
const FINANCES_ONLY = { has_profile: true, has_goal: false, ready: false };
const READY = { has_profile: true, has_goal: true, ready: true };

const FIRST_QUESTION: DraftReply = {
  draft: { notes: {}, skipped: [], to_check: [], asked: "monthly_net_income" },
  understood: [],
  question: "How much do you take home each month, after tax?",
  still_missing: ["Take-home pay", "Expenses", "Goal amount", "Goal date", "Goal name"],
  optional_missing: ["Cash", "Investments", "Monthly investment", "Debt"],
  complete: false,
  read_by: "rules",
};

const EMPTY_DB = {
  "POST /plan/draft": [200, FIRST_QUESTION],
  "GET /plan/status": [200, NOT_STARTED],
  "GET /profile": [404, { detail: "no financial profile has been saved yet" }],
  "GET /goals": [200, []],
  "GET /assumptions": [200, SETS],
} as const;

async function mountPlan() {
  const wrapper = mount(PlanView, { global: { stubs: { RouterLink: RouterLinkStub } } });
  await flushPromises();
  return wrapper;
}

const formWith = (wrapper: VueWrapper, fieldId: string) =>
  wrapper.findAll("form").find((f) => f.find(`#${fieldId}`).exists())!;

afterEach(() => vi.unstubAllGlobals());

describe("plan page", () => {
  it("starts empty when nothing is stored, with the assumption presets as percentages", async () => {
    fakeApi({ ...EMPTY_DB });
    const wrapper = await mountPlan();

    const income = wrapper.find<HTMLInputElement>("#profile-monthly_net_income");
    expect(income.element.value).toBe("");
    expect(wrapper.find<HTMLInputElement>("#set-base-annual_return").element.value).toBe("5");
    expect(wrapper.find<HTMLInputElement>("#set-optimistic-annual_return").element.value).toBe("7");
    expect(wrapper.text()).toContain("Save goal");
  });

  it("saves the profile, sending 0 for empty optional amounts, and shows the API's surplus", async () => {
    const fetchMock = fakeApi({ ...EMPTY_DB, "PUT /profile": [200, SAVED_PROFILE] });
    const wrapper = await mountPlan();

    await wrapper.find("#profile-monthly_net_income").setValue("2500");
    await wrapper.find("#profile-monthly_expenses").setValue("1700");
    await wrapper.find("#profile-cash").setValue("10000");
    await formWith(wrapper, "profile-cash").trigger("submit");
    await flushPromises();

    expect(lastBody(fetchMock, "PUT", "/profile")).toEqual({
      monthly_net_income: 2500, monthly_expenses: 1700, other_monthly_income: 0, cash: 10_000,
      investments: 0, monthly_investment_contribution: 0, debt_balance: 0,
      monthly_debt_payment: 0, age: null, investment_risk: "medium",
    });
    expect(wrapper.text()).toContain("Saved. Monthly surplus €800, savings rate 32%.");
  });

  it("saves the chosen investment risk, medium by default", async () => {
    const fetchMock = fakeApi({ ...EMPTY_DB, "PUT /profile": [200, SAVED_PROFILE] });
    const wrapper = await mountPlan();

    expect(wrapper.find<HTMLInputElement>("#profile-investment_risk-medium").element.checked).toBe(true);
    await wrapper.find("#profile-monthly_net_income").setValue("2500");
    await wrapper.find("#profile-monthly_expenses").setValue("1700");
    await wrapper.find("#profile-investment_risk-high").setValue(true);
    await formWith(wrapper, "profile-cash").trigger("submit");
    await flushPromises();

    expect(lastBody(fetchMock, "PUT", "/profile")).toMatchObject({ investment_risk: "high" });
  });

  it("shows validation errors from the API next to the field", async () => {
    fakeApi({
      ...EMPTY_DB,
      "PUT /profile": [422, { detail: [{ loc: ["body", "cash"], msg: "Input should be greater than or equal to 0" }] }],
    });
    const wrapper = await mountPlan();

    await formWith(wrapper, "profile-cash").trigger("submit");
    await flushPromises();

    const cash = wrapper.find("#profile-cash");
    expect(cash.attributes("aria-invalid")).toBe("true");
    expect(cash.attributes("aria-describedby")).toContain("profile-cash-error");
    expect(wrapper.find("#profile-cash-error").text()).toBe("Input should be greater than or equal to 0");
    expect(wrapper.text()).toContain("Some values need attention.");
  });

  it("converts percentages back to decimals when saving an assumption set", async () => {
    const fetchMock = fakeApi({ ...EMPTY_DB, "PUT /assumptions/base": [200, SETS[1]] });
    const wrapper = await mountPlan();

    await wrapper.find("#set-base-annual_return").setValue("4.5");
    await formWith(wrapper, "set-base-annual_return").trigger("submit");
    await flushPromises();

    expect(lastBody(fetchMock, "PUT", "/assumptions/base")).toEqual({
      annual_return: 0.045, annual_salary_growth: 0.02, annual_expense_growth: 0.02, annual_inflation: 0.02,
    });
  });

  it("creates a new goal from the prefilled active goal", async () => {
    const car: Goal = { ...HOUSE, id: 2, name: "Buy a car", target_amount: 15_000 };
    const fetchMock = fakeApi({
      ...EMPTY_DB,
      "GET /goals": [200, [HOUSE]],
      "POST /goals": [201, car],
    });
    const wrapper = await mountPlan();
    expect(wrapper.find<HTMLInputElement>("#goal-name").element.value).toBe("Buy a house");

    await wrapper.find("#goal-name").setValue("Buy a car");
    await wrapper.find("#goal-target_amount").setValue("15000");
    await formWith(wrapper, "goal-name").trigger("submit");
    await flushPromises();

    expect(lastBody(fetchMock, "POST", "/goals")).toEqual({
      name: "Buy a car", goal_type: "house", target_amount: 15_000, target_date: "2032-06-01", description: null, keep_savings: 0, keep_investments: 0,
    });
    expect(wrapper.text()).toContain("Saved. This is now your active goal.");
  });

  it("shows the API's reason when a goal is rejected", async () => {
    fakeApi({
      ...EMPTY_DB,
      "POST /goals": [422, { detail: "goal target date 2025-01-01 is before the projection start 2026-09-01" }],
    });
    const wrapper = await mountPlan();

    await formWith(wrapper, "goal-name").trigger("submit");
    await flushPromises();

    expect(wrapper.find('[role="alert"]').text()).toContain("before the projection start");
  });

  it("guides a new user: welcome, steps to do, empty fields with examples", async () => {
    fakeApi({ ...EMPTY_DB });
    const wrapper = await mountPlan();
    const text = wrapper.text();

    expect(text).toContain("Welcome. Enter your own figures in two steps");
    expect(wrapper.find('[aria-label="Setup steps"]').text()).toContain("Your finances (to do)");
    expect(text).not.toContain("Your plan is ready");

    const income = wrapper.find<HTMLInputElement>("#profile-monthly_net_income");
    expect(income.element.value).toBe("");
    expect(income.attributes("placeholder")).toBe("e.g. 2,500");
    expect(wrapper.find("#profile-cash-hint").text()).toContain("Leave empty for €0.");
    expect(wrapper.find("#profile-monthly_net_income-hint").text()).not.toContain("€0");
    expect(wrapper.find<HTMLInputElement>("#goal-name").attributes("placeholder")).toBe("e.g. Buy a house");
    expect(wrapper.find<HTMLSelectElement>("#goal-type").element.value).toBe("other");
  });

  it("says when empty amounts were saved as €0, and ticks the finances step", async () => {
    fakeApi({ ...EMPTY_DB });
    const wrapper = await mountPlan();
    await wrapper.find("#profile-monthly_net_income").setValue("2500");
    await wrapper.find("#profile-monthly_expenses").setValue("1700");

    fakeApi({ ...EMPTY_DB, "GET /plan/status": [200, FINANCES_ONLY], "PUT /profile": [200, SAVED_PROFILE] });
    await formWith(wrapper, "profile-cash").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Empty amounts were saved as €0.");
    const steps = wrapper.find('[aria-label="Setup steps"]').text();
    expect(steps).toContain("Your finances (done)");
    expect(steps).toContain("Your goal (to do)");
  });

  it("points to the projection once the plan is ready", async () => {
    fakeApi({ ...EMPTY_DB, "GET /plan/status": [200, READY] });
    const wrapper = await mountPlan();
    expect(wrapper.text()).toContain("Your plan is ready.");
    expect(wrapper.findComponent(RouterLinkStub).exists()).toBe(true);
    expect(
      wrapper.findAllComponents(RouterLinkStub).some((l) => l.props("to") === "/" && l.text() === "See your projection"),
    ).toBe(true);
  });
});

describe("describe your situation", () => {
  const FILLED: DraftReply = {
    draft: {
      monthly_net_income: 2400, monthly_expenses: 1600, cash: 8000, goal_name: "House deposit",
      goal_type: "house", goal_target_amount: 60_000, goal_target_date: "2032-06-01",
      notes: { monthly_expenses: "€900 + €700" }, skipped: [], to_check: ["cash"],
      asked: "investments",
    },
    understood: [
      "Take-home pay: €2,400 a month",
      "Expenses: €1,600 a month (€900 + €700)",
      "Cash: €8,000 · read by the AI, please check",
    ],
    question: "And in investments, such as funds or ETFs? If nothing, say 0.",
    still_missing: [],
    optional_missing: ["Investments", "Monthly investment", "Debt"],
    complete: true,
    read_by: "qwen2.5:3b",
  };

  it("fills the forms from a description, labels them, and saves nothing by itself", async () => {
    const fetchMock = fakeApi({
      ...EMPTY_DB,
      "POST /plan/draft": [[200, FIRST_QUESTION], [200, FILLED]], // first question, then the reply
    });
    const wrapper = await mountPlan();

    await wrapper.find("#describe-input").setValue("I take home 2,400, rent 900 and 700 for the rest…");
    await wrapper.find("#describe-input").element.closest("form")!.dispatchEvent(new Event("submit"));
    await flushPromises();

    expect(lastBody(fetchMock, "POST", "/plan/draft").message).toBe("I take home 2,400, rent 900 and 700 for the rest…");
    const value = (id: string) => wrapper.find<HTMLInputElement>(id).element.value;
    expect(value("#profile-monthly_net_income")).toBe("2400");
    expect(value("#profile-cash")).toBe("8000");
    expect(value("#goal-name")).toBe("House deposit");
    expect(value("#goal-target_date")).toBe("2032-06-01");

    const label = (id: string) => wrapper.find(`label[for="${id}"]`).text();
    expect(label("profile-monthly_net_income")).toContain("From your description");
    expect(label("profile-cash")).toContain("Read by the AI: please check");
    expect(label("profile-investments")).not.toContain("From your description");
    expect(wrapper.find("#profile-monthly_expenses-hint").text()).toContain("€900 + €700.");

    const box = wrapper.find('[aria-labelledby="describe-heading"]').text();
    expect(box).toContain("Expenses: €1,600 a month (€900 + €700)");
    expect(box).toContain("And in investments, such as funds or ETFs?");
    expect(box).toContain("Optional: Investments, Monthly investment, Debt");
    expect(box).toContain("Last message read by qwen2.5:3b");
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(false);
  });

  it("starts a returning user from the saved plan", async () => {
    const fetchMock = fakeApi({
      ...EMPTY_DB,
      "GET /plan/status": [200, READY],
      "GET /profile": [200, SAVED_PROFILE],
      "GET /goals": [200, [HOUSE]],
    });
    const wrapper = await mountPlan();

    expect(wrapper.text()).toContain("Describe a change in your own words");
    const sent = lastBody(fetchMock, "POST", "/plan/draft").draft;
    expect(sent.monthly_net_income).toBe(2500);
    expect(sent.goal_target_amount).toBe(80_000);
  });
});
