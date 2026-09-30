import { createRouter, createWebHistory, type Router } from "vue-router";
import { usePlanStatus } from "./composables/usePlanStatus";
import ChatView from "./views/ChatView.vue";
import CompareView from "./views/CompareView.vue";
import PlanView from "./views/PlanView.vue";
import ProjectionView from "./views/ProjectionView.vue";

export const routes = [
  { path: "/", name: "projection", component: ProjectionView, meta: { title: "Projection" } },
  { path: "/compare", name: "compare", component: CompareView, meta: { title: "Compare" } },
  { path: "/ask", name: "ask", component: ChatView, meta: { title: "Ask" } },
  { path: "/plan", name: "plan", component: PlanView, meta: { title: "Your plan" } },
];

/**
 * A new user (no finances or goal saved yet) starts on "Your plan". Only on the first page
 * load: afterwards every page can be visited and explains what's missing.
 */
export function startNewUsersOnPlan(router: Router) {
  let firstNavigation = true;
  router.beforeEach(async (to) => {
    if (!firstNavigation) return;
    firstNavigation = false;
    const { ready, refresh } = usePlanStatus();
    try {
      await refresh();
    } catch {
      return; // API unreachable: let the page show its own error
    }
    if (!ready.value && to.name !== "plan") return { name: "plan" };
  });
}

export const router = createRouter({ history: createWebHistory(), routes });
startNewUsersOnPlan(router);

router.afterEach((to) => {
  document.title = `${to.meta.title} · Goal Simulator`;
});
