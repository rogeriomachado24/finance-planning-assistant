/** The Ask page with a fake API: what's sent, what's shown, and how failures behave. */
import { flushPromises, mount, RouterLinkStub } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AssumptionSet, ChatResponse, ComparedScenario } from "../api/client";
import { useChat } from "../composables/useChat";
import { fakeApi, lastBody } from "../test/fakeApi";
import ChatView from "./ChatView.vue";

const RATES = { annual_return: 0.05, annual_salary_growth: 0.02, annual_expense_growth: 0.02, annual_inflation: 0.02 };
const SETS: AssumptionSet[] = ["conservative", "base", "optimistic"].map((name) => ({ name, assumptions: RATES }));
const HEALTH = { status: "ok", database: "ok", llm: { provider: "phi3", available: true } };

function scenario(name: string, goalDate: string, value: number, earlier: number, diff: number): ComparedScenario {
  return {
    name, description: "", saved_id: null,
    vs_baseline: { goal_months_earlier: earlier, value_at_target_difference: diff },
    result: {
      scenario_name: name,
      profile: {
        monthly_net_income: 2500, monthly_expenses: 1700, cash: 10_000, investments: 15_000,
        monthly_investment_contribution: 400, other_monthly_income: 0, debt_balance: 0,
        monthly_debt_payment: 0, age: 32, investment_risk: "medium",
      },
      assumptions: RATES, monthly_contribution: 400, monthly_surplus: 800, target_amount: 80_000,
      target_date: "2032-06-01", months_to_target_date: 69, projected_goal_date: goalDate,
      months_to_goal: 58 - earlier, projected_value_at_target_date: value, reaches_goal: true,
      shortfall: 0, required_monthly_contribution: 630.81,
    goal_progress: { current_amount: 25_000, remaining: 55_000, fraction: 0.3125 }, warnings: [], snapshots: [],
    },
  };
}

const WHAT_IF: ChatResponse = {
  thread_id: "t-1",
  reply: "With €200 more invested each month, the goal is reached on 1 Jun 2031.\n\nAssumptions: base set. This is a projection, not a guarantee.",
  status: "answered",
  intent: {
    kind: "what_if", assumption_set: null,
    overrides: { monthly_investment_contribution_delta: 200 },
  },
  assumption_set: "base",
  assumptions: RATES,
  results: [
    scenario("Current plan", "2031-07-01", 91_961.6, 0, 0),
    scenario("What-if", "2031-06-01", 94_059.4, 1, 2_097.8),
  ],
  futures: null,
  provider: "phi3",
  parsed_by: "rules",
  worded_by: "template",
};

const ADVICE: ChatResponse = {
  ...WHAT_IF,
  reply: "I can't recommend what to do or which products to choose.",
  status: "declined",
  intent: { kind: "unsupported", reason: "advice" },
  assumption_set: null,
  assumptions: null,
  results: [],
};

async function mountChat() {
  const wrapper = mount(ChatView, { global: { stubs: { RouterLink: RouterLinkStub } } });
  await flushPromises();
  return wrapper;
}

async function ask(wrapper: Awaited<ReturnType<typeof mountChat>>, text: string) {
  await wrapper.find("#chat-input").setValue(text);
  await wrapper.find("form").trigger("submit");
  await flushPromises();
}

beforeEach(() => useChat().reset());
afterEach(() => vi.unstubAllGlobals());

describe("Ask page", () => {
  it("offers examples and says whether the model is ready", async () => {
    fakeApi({ "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH] });
    const wrapper = await mountChat();
    expect(wrapper.text()).toContain("AI model: phi3, ready");
    expect(wrapper.text()).toContain("never calculates");
    expect(wrapper.findAll("button").some((b) => b.text() === "Compare my options")).toBe(true);
  });

  it("shows the reply, the engine's figures and how the question was understood", async () => {
    const fetchMock = fakeApi({
      "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [200, WHAT_IF],
    });
    const wrapper = await mountChat();
    await ask(wrapper, "What if I invest €200 more per month?");

    expect(lastBody(fetchMock, "POST", "/chat")).toEqual({
      message: "What if I invest €200 more per month?", thread_id: null, assumption_set: "base",
    });
    const reply = wrapper.find("article");
    expect(reply.text()).toContain("This is a projection, not a guarantee.");
    expect(reply.text()).toContain("€91,962"); // current plan card
    expect(reply.text()).toContain("€94,059"); // what-if card
    expect(reply.text().replace(/\s+/g, " ")).toContain("1 month earlier · +€2,098");
    expect(reply.text()).toContain("Understood as: what if: invest €200 more a month · by rules");
  });

  it("continues the same conversation, with the chosen assumption set", async () => {
    const fetchMock = fakeApi({
      "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [200, WHAT_IF],
    });
    const wrapper = await mountChat();
    await ask(wrapper, "What if I invest €200 more per month?");
    await wrapper.find('input[value="optimistic"]').setValue();
    await ask(wrapper, "And with €300 instead?");

    expect(lastBody(fetchMock, "POST", "/chat")).toMatchObject({
      thread_id: "t-1", assumption_set: "optimistic",
    });
  });

  it("labels refusals by their reason and shows no figures", async () => {
    fakeApi({ "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [200, ADVICE] });
    const wrapper = await mountChat();
    await ask(wrapper, "Should I buy an ETF?");

    const reply = wrapper.find("article");
    expect(reply.text()).toContain("I don't give advice");
    expect(reply.text()).not.toContain("€");
  });

  it("keeps the question when the API fails, and retries it", async () => {
    fakeApi({ "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [500, null] });
    const wrapper = await mountChat();
    await ask(wrapper, "Am I on track?");
    expect(wrapper.find('[role="alert"]').text()).toContain("Is the backend running?");

    fakeApi({ "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [200, WHAT_IF] });
    await wrapper.findAll("button").find((b) => b.text() === "Try again")!.trigger("click");
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.findAll(".bg-ink").filter((b) => b.text() === "Am I on track?")).toHaveLength(1);
    expect(wrapper.find("article").exists()).toBe(true);
  });

  it("starts a new conversation", async () => {
    const fetchMock = fakeApi({
      "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [200, WHAT_IF],
    });
    const wrapper = await mountChat();
    await ask(wrapper, "What if I invest €200 more per month?");
    await wrapper.findAll("button").find((b) => b.text() === "New conversation")!.trigger("click");
    await ask(wrapper, "Am I on track?");
    expect(lastBody(fetchMock, "POST", "/chat").thread_id).toBeNull();
  });

  it("saves a what-if to Compare under a suggested name", async () => {
    const fetchMock = fakeApi({
      "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [200, WHAT_IF],
      "POST /scenarios": [201, { id: 5, name: "Invest €200 more a month", description: "", overrides: {} }],
    });
    const wrapper = await mountChat();
    await ask(wrapper, "What if I invest €200 more per month?");

    await wrapper.findAll("button").find((b) => b.text() === "Save to Compare")!.trigger("click");
    const name = wrapper.find<HTMLInputElement>("article input[type=text]");
    expect(name.element.value).toBe("Invest €200 more a month");
    await wrapper.find("article form").trigger("submit");
    await flushPromises();

    expect(lastBody(fetchMock, "POST", "/scenarios")).toEqual({
      name: "Invest €200 more a month",
      description: "Saved from the chat.",
      overrides: { monthly_investment_contribution_delta: 200 },
    });
    expect(wrapper.find("article").text()).toContain("Saved as “Invest €200 more a month”.");
  });

  it("shows how likely, from simulated futures, with the difference the API computed", async () => {
    const summary = {
      goal_dates: { p10: "2031-08-01", p50: "2032-01-01", p90: "2032-12-01" },
      not_reached_share: 0, value_at_target_date: { p10: 70_000, p50: 83_000, p90: 97_000 },
      shortfall_when_missed: null, required_monthly_investment: [],
    };
    const likely: ChatResponse = {
      ...WHAT_IF,
      reply: "With a 30% fall in investments in the first year, the goal is reached by 1 Jun 2032 in about 70% of 1,000 simulated futures.",
      intent: { kind: "likelihood", assumption_set: null, overrides: { first_year_return: -0.3 } },
      futures: {
        assumption_set: "base", investment_risk: "medium", volatility: 0.1, paths: 1000, seed: 2026,
        baseline: "Current plan",
        scenarios: [
          { ...summary, name: "Current plan", saved_id: null, probability_by_target_date: 0.926, probability_margin: 0.0162, probability_difference: 0, points_difference: 0 },
          { ...summary, name: "What-if", saved_id: null, probability_by_target_date: 0.699, probability_margin: 0.0284, probability_difference: -0.227, points_difference: -23 },
        ],
      },
    };
    fakeApi({ "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [200, likely] });
    const wrapper = await mountChat();
    await ask(wrapper, "How likely is that?");

    const reply = wrapper.find("article").text().replace(/\s+/g, " ");
    expect(reply).toContain("Understood as: how likely, if: investments fall 30% in the first year");
    expect(reply).toContain("93%");
    expect(reply).toContain("±2 points");
    expect(reply).toContain("70%");
    expect(reply).toContain("−23 points");
    expect(reply).toContain("goal reached Aug 2031 – Dec 2032 in the middle 80%");
    expect(wrapper.findAll("button").some((b) => b.text() === "Save to Compare")).toBe(true);
  });

  it("shows the amount for the chosen share next to the one at the assumed return", async () => {
    const plan = WHAT_IF.results[0];
    const needed: ChatResponse = {
      ...WHAT_IF,
      reply: "To reach €80,000 by 1 Jun 2032 in at least 90% of 1,000 simulated futures, about €837 a month would need to be invested from next month.",
      intent: { kind: "required_contribution", assumption_set: null, share: 0.9 },
      results: [plan],
      futures: {
        assumption_set: "base", investment_risk: "medium", volatility: 0.1, paths: 1000, seed: 2026,
        baseline: "Current plan",
        scenarios: [{
          name: "Current plan", saved_id: null, probability_by_target_date: 0.948,
          probability_margin: 0.0138, probability_difference: 0, points_difference: 0,
          goal_dates: { p10: "2030-11-01", p50: "2031-07-01", p90: "2032-04-01" },
          not_reached_share: 0, value_at_target_date: { p10: 81_725, p50: 92_122, p90: 105_378 },
          shortfall_when_missed: null,
          required_monthly_investment: [{ share: 0.9, monthly_amount: 836.54 }],
        }],
      },
    };
    fakeApi({ "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [200, needed] });
    const wrapper = await mountChat();
    await ask(wrapper, "How much would I need to invest to be 90% sure?");

    const reply = wrapper.find("article").text().replace(/\s+/g, " ");
    expect(reply).toContain("9 in 10 of futures€837");
    expect(reply).toContain("At the assumed return€631");
    expect(reply).toContain("Understood as: how much is needed each month to reach it in 90% of simulated futures");
  });

  it("offers Save to Compare only for what-ifs", async () => {
    fakeApi({ "GET /assumptions": [200, SETS], "GET /health": [200, HEALTH], "POST /chat": [200, ADVICE] });
    const wrapper = await mountChat();
    await ask(wrapper, "Should I buy an ETF?");
    expect(wrapper.findAll("button").some((b) => b.text() === "Save to Compare")).toBe(false);
  });
});
