import { createRouter, createWebHistory } from "vue-router";
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

export const router = createRouter({ history: createWebHistory(), routes });

router.afterEach((to) => {
  document.title = `${to.meta.title} · Goal Simulator`;
});
