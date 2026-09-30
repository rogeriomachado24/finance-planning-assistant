/**
 * What's been set up so far (finances, goal), shared by every page and the router.
 * Projections need both; the "Your plan" page refreshes this after each save.
 */
import { computed, reactive } from "vue";
import { api } from "../api/client";

const status = reactive({ loaded: false, hasProfile: false, hasGoal: false });

async function refresh() {
  const s = await api.planStatus();
  Object.assign(status, { loaded: true, hasProfile: s.has_profile, hasGoal: s.has_goal });
}

const ready = computed(() => status.hasProfile && status.hasGoal);

export function usePlanStatus() {
  return { status, ready, refresh };
}
