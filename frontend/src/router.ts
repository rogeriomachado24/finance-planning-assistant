import { createRouter, createWebHistory, type Router } from "vue-router";
import { usePlanStatus } from "./composables/usePlanStatus";
import { wasWelcomed } from "./lib/welcome";
import ChatView from "./views/ChatView.vue";
import CompareView from "./views/CompareView.vue";
import PlanView from "./views/PlanView.vue";
import ProjectionView from "./views/ProjectionView.vue";
import WelcomeView from "./views/WelcomeView.vue";

export const routes = [
  { path: "/", name: "projection", component: ProjectionView, meta: { title: "Projection" } },
  { path: "/compare", name: "compare", component: CompareView, meta: { title: "Compare" } },
  { path: "/ask", name: "ask", component: ChatView, meta: { title: "Ask" } },
  { path: "/plan", name: "plan", component: PlanView, meta: { title: "Your plan" } },
  // Not in the navigation: shown once per tab, before the pages (see guideFirstVisit).
  { path: "/welcome", name: "welcome", component: WelcomeView, meta: { title: "Welcome back", hidden: true } },
];

/**
 * The first page load in a browser tab: a new user (nothing saved) starts on "Your plan"; a
 * returning user first sees the welcome screen, to continue with the saved plan or start
 * fresh. Only once: afterwards every page can be visited and explains what's missing.
 */
export function guideFirstVisit(router: Router) {
  let firstNavigation = true;
  router.beforeEach(async (to) => {
    if (!firstNavigation) return;
    firstNavigation = false;
    const { status, refresh } = usePlanStatus();
    try {
      await refresh();
    } catch {
      return; // API unreachable: let the page show its own error
    }
    const somethingSaved = status.hasProfile || status.hasGoal;
    if (!somethingSaved) return to.name === "plan" ? undefined : { name: "plan" };
    if (!wasWelcomed() && to.name !== "welcome") {
      return { name: "welcome", query: to.fullPath === "/" ? {} : { next: to.fullPath } };
    }
  });
}

export const router = createRouter({ history: createWebHistory(), routes });
guideFirstVisit(router);

router.afterEach((to) => {
  document.title = `${to.meta.title} · Goal Simulator`;
});
