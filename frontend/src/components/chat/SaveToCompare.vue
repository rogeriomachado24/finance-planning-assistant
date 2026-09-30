<script setup lang="ts">
/** Keep a what-if from the chat as a saved scenario, so it appears on the Compare page. */
import { ref, useId } from "vue";
import { api, type Overrides } from "../../api/client";
import { useSubmit } from "../../composables/useSubmit";
import { scenarioName } from "../../lib/intent";

const props = defineProps<{ overrides: Overrides }>();

const open = ref(false);
const name = ref(scenarioName(props.overrides));
const savedAs = ref("");

const { status, error, fieldErrors, submit } = useSubmit(
  () =>
    api.saveScenario({
      name: name.value,
      description: "Saved from the chat.",
      overrides: props.overrides,
    }),
  (saved) => {
    savedAs.value = saved.name;
    open.value = false;
  },
);

const inputId = useId(); // unique per reply, so each label points at its own field
</script>

<template>
  <div class="text-sm">
    <p v-if="savedAs" class="flex flex-wrap items-center gap-x-2" aria-live="polite">
      <span>Saved as “{{ savedAs }}”.</span>
      <RouterLink to="/compare" class="font-medium underline underline-offset-2">Open Compare</RouterLink>
    </p>

    <button
      v-else-if="!open"
      type="button"
      class="rounded-md border border-hairline px-2.5 py-1 text-xs hover:bg-page"
      @click="open = true"
    >
      Save to Compare
    </button>

    <form v-else class="flex flex-wrap items-end gap-2" @submit.prevent="submit">
      <div class="min-w-48 flex-1">
        <label :for="inputId" class="block text-xs text-ink-2">Scenario name</label>
        <input
          :id="inputId"
          v-model="name"
          type="text"
          required
          maxlength="100"
          class="mt-0.5 w-full rounded-md border border-axis bg-surface px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-series-1"
        />
      </div>
      <button
        type="submit"
        class="rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-surface disabled:opacity-60"
        :disabled="status === 'saving'"
      >
        {{ status === "saving" ? "Saving…" : "Save" }}
      </button>
      <button type="button" class="rounded-md px-2 py-1.5 text-xs text-ink-2 hover:text-ink" @click="open = false">
        Cancel
      </button>
      <p class="basis-full text-xs text-ink-2">A saved scenario with the same name is replaced.</p>
      <p v-if="status === 'error'" class="basis-full text-xs font-medium text-error" role="alert">
        {{ fieldErrors.name ?? error?.message }}
      </p>
    </form>
  </div>
</template>
