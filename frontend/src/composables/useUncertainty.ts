/**
 * Loads the simulated futures for the chosen assumption set. Separate from the projection
 * because it takes about a second: the projection shows first, the range follows.
 */
import { onMounted, ref, watch, type Ref } from "vue";
import { api, ApiError, type Uncertainty } from "../api/client";

export function useUncertainty(assumptionSet: Ref<string>) {
  const uncertainty = ref<Uncertainty | null>(null);
  const error = ref<ApiError | null>(null);
  const loading = ref(true);

  let latestRequest = 0;

  async function load() {
    const request = ++latestRequest;
    loading.value = true;
    try {
      const result = await api.simulateUncertainty({ assumption_set: assumptionSet.value });
      if (request !== latestRequest) return; // a newer selection has taken over
      uncertainty.value = result;
      error.value = null;
    } catch (e) {
      if (request !== latestRequest) return;
      uncertainty.value = null;
      error.value = e instanceof ApiError ? e : new ApiError(0, String(e));
    } finally {
      if (request === latestRequest) loading.value = false;
    }
  }

  watch(assumptionSet, load);
  onMounted(load);

  return { uncertainty, error, loading, reload: load };
}
