<script setup lang="ts">
/**
 * "What does this mean for me?": a short summary of the page, on request. Code chooses the
 * facts from the engine's results; a model may reword them, and its text is only shown when
 * every figure was copied exactly. The facts it was written from can be opened below it.
 */
import { ref, watch } from "vue";
import { ApiError, type PageSummary } from "../api/client";

const props = defineProps<{
  /** Fetches the summary for the page as it is now. */
  load: () => Promise<PageSummary>;
  /** Changes when the page's inputs change (e.g. the assumption set), so the summary resets. */
  resetKey: string;
}>();

const summary = ref<PageSummary | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
let latestRequest = 0;

async function explain() {
  const request = ++latestRequest;
  loading.value = true;
  error.value = null;
  try {
    const result = await props.load();
    if (request === latestRequest) summary.value = result;
  } catch (e) {
    if (request === latestRequest) error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    if (request === latestRequest) loading.value = false;
  }
}

// A summary describes one page state: another assumption set needs a new one.
watch(
  () => props.resetKey,
  () => {
    latestRequest++;
    summary.value = null;
    error.value = null;
    loading.value = false;
  },
);
</script>

<template>
  <section aria-labelledby="summary-heading" class="rounded-lg border border-hairline bg-surface p-4" :aria-busy="loading">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 id="summary-heading" class="text-sm font-medium">What does this mean for me?</h2>
      <button
        v-if="!summary"
        type="button"
        class="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-surface disabled:opacity-60"
        :disabled="loading"
        @click="explain"
      >
        {{ loading ? "Writing a summary…" : "Explain this page" }}
      </button>
    </div>

    <div aria-live="polite">
      <template v-if="summary">
        <!-- The facts as a labelled list; a model's checked rewording is a paragraph instead -->
        <ul v-if="summary.worded_by === 'template'" class="mt-2 max-w-prose space-y-1.5 text-sm">
          <li v-for="point in summary.points" :key="point.label" class="flex gap-2">
            <span class="mt-2 size-1.5 shrink-0 rounded-full bg-ink-2" aria-hidden="true" />
            <span><span class="font-semibold">{{ point.label }}:</span> {{ point.text }}</span>
          </li>
        </ul>
        <p v-else class="mt-2 max-w-prose text-sm leading-relaxed">{{ summary.summary }}</p>
        <p class="mt-2 text-xs text-ink-2">
          <template v-if="summary.worded_by === 'template'">
            The facts from the results on this page.
          </template>
          <template v-else>
            Written by {{ summary.worded_by }} and checked: every figure was copied from the
            results on this page.
          </template>
          A projection, not a guarantee.
        </p>
        <!-- Only worth comparing when a model reworded them; a template summary is the facts -->
        <details v-if="summary.worded_by !== 'template'" class="mt-2 text-xs text-ink-2">
          <summary class="cursor-pointer hover:text-ink">The facts it was written from</summary>
          <ul class="mt-1 list-disc space-y-0.5 pl-5">
            <li v-for="point in summary.points" :key="point.label">
              <span class="font-medium">{{ point.label }}:</span> {{ point.text }}
            </li>
          </ul>
        </details>
      </template>
      <p v-else-if="error" class="mt-2 text-sm text-error" role="alert">
        Couldn't write a summary: {{ error }}
      </p>
    </div>
  </section>
</template>
