/** New users start on "Your plan", only on the first page load. */
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import { startNewUsersOnPlan } from "./router";
import { fakeApi } from "./test/fakeApi";

const Page = { template: "<div />" };

async function firstLoad(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "projection", component: Page },
      { path: "/compare", name: "compare", component: Page },
      { path: "/plan", name: "plan", component: Page },
    ],
  });
  startNewUsersOnPlan(router);
  await router.push(path);
  return router;
}

const status = (ready: boolean) => ({ has_profile: ready, has_goal: ready, ready });

afterEach(() => vi.unstubAllGlobals());

describe("first page load", () => {
  it("sends a new user to Your plan", async () => {
    fakeApi({ "/plan/status": [200, status(false)] });
    const router = await firstLoad("/");
    expect(router.currentRoute.value.name).toBe("plan");
  });

  it("only redirects once: afterwards every page can be visited", async () => {
    fakeApi({ "/plan/status": [200, status(false)] });
    const router = await firstLoad("/compare");
    await router.push("/");
    expect(router.currentRoute.value.name).toBe("projection");
  });

  it("leaves a user with a plan where they wanted to go", async () => {
    fakeApi({ "/plan/status": [200, status(true)] });
    expect((await firstLoad("/compare")).currentRoute.value.name).toBe("compare");
  });

  it("doesn't redirect when the API is unreachable (the page explains that instead)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    expect((await firstLoad("/")).currentRoute.value.name).toBe("projection");
  });
});
