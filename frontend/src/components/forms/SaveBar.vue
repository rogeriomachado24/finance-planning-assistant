<script setup lang="ts">
/** Submit button plus the outcome of the last save, announced to screen readers. */
import type { ApiError } from "../../api/client";
import type { SubmitStatus } from "../../composables/useSubmit";

defineProps<{ label: string; status: SubmitStatus; error: ApiError | null }>();
</script>

<template>
  <div class="flex flex-wrap items-center gap-3">
    <button
      type="submit"
      class="rounded-md bg-ink px-4 py-2 text-sm font-medium text-surface disabled:opacity-60"
      :disabled="status === 'saving'"
    >
      {{ status === "saving" ? "Saving…" : label }}
    </button>
    <p class="text-sm" aria-live="polite">
      <span v-if="status === 'saved'" class="inline-flex items-center gap-1.5">
        <svg viewBox="0 0 16 16" class="size-4 text-good" aria-hidden="true">
          <circle cx="8" cy="8" r="8" fill="currentColor" />
          <path d="M4.5 8.2 7 10.5l4.5-5" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <slot name="saved">Saved.</slot>
      </span>
      <span v-else-if="status === 'error'" class="font-medium text-error" role="alert">
        {{ error?.message }}
      </span>
    </p>
  </div>
</template>
