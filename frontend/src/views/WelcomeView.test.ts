/** The welcome screen: continue with the saved plan, or start fresh after a confirmation. */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import type { Goal, ProfileOut } from "../api/client";
import { wasWelcomed } from "../lib/welcome";
import { fakeApi } from "../test/fakeApi";
import WelcomeView from "./WelcomeView.vue";

const Page = { template: "<div />" };

const GOAL: Goal = {
  id: 1, is_active: true, name: "Buy a house", goal_type: "house", target_amount: 80_000,
  target_date: "2032-06-01", description: null, keep_savings: 0, keep_investments: 0,
};
const PROFILE: ProfileOut = {
  profile: {
    monthly_net_income: 2500, monthly_expenses: 1700, cash: 10_000, investments: 15_000,
    monthly_investment_contribution: 400, other_monthly_income: 0, debt_balance: 0,
    monthly_debt_payment: 0, age: null, investment_risk: "medium",
  },
  position: {
    total_monthly_income: 2500, monthly_expenses: 1700, monthly_debt_payment: 0,
    monthly_surplus: 800, savings_rate: 0.32, liquid_assets: 25_000, net_worth: 25_000,
  },
};
const SAVED = {
  "GET /profile": [200, PROFILE],
  "GET /goals": [200, [GOAL]],
  "GET /plan/status": [200, { has_profile: false, has_goal: false, ready: false }],
  "DELETE /plan": [204, null],
} as const;

async function mountWelcome(next?: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "projection", component: Page },
      { path: "/compare", name: "compare", component: Page },
      { path: "/plan", name: "plan", component: Page },
      { path: "/welcome", name: "welcome", component: WelcomeView },
    ],
  });
  await router.push(next ? { name: "welcome", query: { next } } : { name: "welcome" });
  const wrapper = mount(WelcomeView, { global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

const button = (wrapper: Awaited<ReturnType<typeof mountWelcome>>["wrapper"], text: string) =>
  wrapper.findAll("button").find((b) => b.text() === text)!;

beforeEach(() => sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("welcome screen", () => {
  it("shows the saved plan", async () => {
    fakeApi(SAVED);
    const text = (await mountWelcome()).wrapper.text().replace(/\s+/g, " ");
    expect(text).toContain("Buy a house: €80,000 by 1 Jun 2032");
    expect(text).toContain("Take-home pay €2,500 a month, expenses €1,700 a month");
  });

  it("continues to where the person was going, and doesn't ask again in this tab", async () => {
    fakeApi(SAVED);
    const { wrapper, router } = await mountWelcome("/compare");
    await button(wrapper, "Continue with my plan").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("compare");
    expect(wasWelcomed()).toBe(true);
  });

  it("asks before deleting, and Cancel deletes nothing", async () => {
    const fetchMock = fakeApi(SAVED);
    const { wrapper } = await mountWelcome();
    await button(wrapper, "Start fresh").trigger("click");
    expect(wrapper.text()).toContain("It can't be undone. Your assumption sets stay as they are.");

    await button(wrapper, "Cancel").trigger("click");
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
    expect(wrapper.text()).toContain("Continue with my plan");
  });

  it("starts fresh: deletes the plan and opens Your plan", async () => {
    const fetchMock = fakeApi(SAVED);
    const { wrapper, router } = await mountWelcome();
    await button(wrapper, "Start fresh").trigger("click");
    await button(wrapper, "Delete and start fresh").trigger("click");
    await flushPromises();

    expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/plan" && init?.method === "DELETE")).toBe(true);
    expect(router.currentRoute.value.name).toBe("plan");
    expect(wasWelcomed()).toBe(true);
  });
});
