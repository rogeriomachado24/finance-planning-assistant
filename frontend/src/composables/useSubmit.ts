/** The save cycle shared by every form: idle -> saving -> saved | error. */
import { computed, ref } from "vue";
import { ApiError } from "../api/client";

export type SubmitStatus = "idle" | "saving" | "saved" | "error";

export function useSubmit<T>(action: () => Promise<T>, onSuccess?: (result: T) => void) {
  const status = ref<SubmitStatus>("idle");
  const error = ref<ApiError | null>(null);
  const fieldErrors = computed(() => error.value?.fieldErrors ?? {});

  async function submit() {
    status.value = "saving";
    error.value = null;
    try {
      const result = await action();
      status.value = "saved";
      onSuccess?.(result);
    } catch (e) {
      error.value = e instanceof ApiError ? e : new ApiError(0, String(e));
      status.value = "error";
    }
  }

  /** Call when the user edits the form again, so "Saved" doesn't describe stale values. */
  function markEdited() {
    if (status.value === "saved") status.value = "idle";
  }

  return { status, error, fieldErrors, submit, markEdited };
}
