/**
 * Loads the dashboard's data and re-runs the projection when the assumption set changes.
 * While a new projection loads, the previous one stays on screen (dimmed), so the
 * layout never jumps.
 */
import { onMounted, ref, watch } from "vue";
import {
  api,
  ApiError,
  type AssumptionSet,
  type Goal,
  type ProfileOut,
  type ScenarioResult,
} from "../api/client";

export function useProjection() {
  const assumptionSets = ref<AssumptionSet[]>([]);
  const selectedSet = ref("base");
  const goal = ref<Goal | null>(null);
  const result = ref<ScenarioResult | null>(null);
  /** Today's figures (net worth, savings rate…); they don't depend on the assumptions. */
  const today = ref<ProfileOut | null>(null);
  const error = ref<ApiError | null>(null);
  const loading = ref(true);

  let latestRequest = 0;

  async function loadProjection() {
    const request = ++latestRequest;
    loading.value = true;
    try {
      const projection = await api.simulate({ assumption_set: selectedSet.value });
      if (request !== latestRequest) return; // a newer selection has taken over
      result.value = projection;
      error.value = null;
    } catch (e) {
      if (request !== latestRequest) return;
      result.value = null;
      error.value = e instanceof ApiError ? e : new ApiError(0, String(e));
    } finally {
      if (request === latestRequest) loading.value = false;
    }
  }

  async function load() {
    try {
      const [sets, goals, profile] = await Promise.all([
        api.assumptionSets(),
        api.goals(),
        api.profile().catch(() => null), // optional extra: the projection works without it
      ]);
      assumptionSets.value = sets;
      today.value = profile;
      goal.value = goals.find((g) => g.is_active) ?? null;
    } catch (e) {
      error.value = e instanceof ApiError ? e : new ApiError(0, String(e));
      loading.value = false;
      return;
    }
    await loadProjection();
  }

  watch(selectedSet, loadProjection);
  onMounted(load);

  return { assumptionSets, selectedSet, goal, result, today, error, loading, reload: load };
}
