/** The first page load in a tab: new users start on "Your plan", returning users are welcomed. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import { markWelcomed } from "./lib/welcome";
import { guideFirstVisit } from "./router";
import { fakeApi } from "./test/fakeApi";

const Page = { template: "<div />" };

async function firstLoad(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "projection", component: Page },
      { path: "/compare", name: "compare", component: Page },
      { path: "/plan", name: "plan", component: Page },
      { path: "/welcome", name: "welcome", component: Page },
    ],
  });
  guideFirstVisit(router);
  await router.push(path);
  return router;
}

const status = (hasProfile: boolean, hasGoal: boolean) => ({
  has_profile: hasProfile,
  has_goal: hasGoal,
  ready: hasProfile && hasGoal,
});

beforeEach(() => sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("first page load", () => {
  it("sends a new user to Your plan", async () => {
    fakeApi({ "/plan/status": [200, status(false, false)] });
    const router = await firstLoad("/");
    expect(router.currentRoute.value.name).toBe("plan");
  });

  it("only redirects once: afterwards every page can be visited", async () => {
    fakeApi({ "/plan/status": [200, status(false, false)] });
    const router = await firstLoad("/compare");
    await router.push("/");
    expect(router.currentRoute.value.name).toBe("projection");
  });

  it("welcomes a returning user first, remembering where they were going", async () => {
    fakeApi({ "/plan/status": [200, status(true, true)] });
    const router = await firstLoad("/compare");
    expect(router.currentRoute.value.name).toBe("welcome");
    expect(router.currentRoute.value.query.next).toBe("/compare");
  });

  it("welcomes a user with a half-finished plan too", async () => {
    fakeApi({ "/plan/status": [200, status(true, false)] });
    expect((await firstLoad("/")).currentRoute.value.name).toBe("welcome");
  });

  it("doesn't welcome again in the same tab (e.g. after a reload)", async () => {
    markWelcomed();
    fakeApi({ "/plan/status": [200, status(true, true)] });
    expect((await firstLoad("/compare")).currentRoute.value.name).toBe("compare");
  });

  it("doesn't redirect when the API is unreachable (the page explains that instead)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    expect((await firstLoad("/")).currentRoute.value.name).toBe("projection");
  });
});
