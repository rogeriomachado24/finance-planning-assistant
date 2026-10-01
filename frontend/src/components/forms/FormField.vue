<script setup lang="ts">
/**
 * Label, hint and error around one input. The input (in the slot) gets the ids to point
 * `aria-describedby` at, so screen readers read the hint and the error with the field.
 */
import { computed } from "vue";

const props = defineProps<{
  id: string;
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  /** A label after the field name, e.g. "From your description". */
  badge?: string;
  badgeTone?: "info" | "check";
}>();

const describedBy = computed(
  () =>
    [props.hint && `${props.id}-hint`, props.error && `${props.id}-error`]
      .filter(Boolean)
      .join(" ") || undefined,
);
</script>

<template>
  <div>
    <label :for="id" class="block text-sm font-medium">
      {{ label }}
      <span v-if="optional" class="font-normal text-ink-2">(optional)</span>
      <span
        v-if="badge"
        class="ml-1 rounded px-1.5 py-0.5 text-xs font-normal"
        :class="badgeTone === 'check' ? 'bg-warning/25 text-ink' : 'bg-series-1/10 text-ink-2'"
      >{{ badge }}</span>
    </label>
    <div class="mt-1">
      <slot :described-by="describedBy" :invalid="Boolean(error)" />
    </div>
    <p v-if="hint" :id="`${id}-hint`" class="mt-1 text-xs text-ink-2">{{ hint }}</p>
    <p v-if="error" :id="`${id}-error`" class="mt-1 text-xs font-medium text-error">
      {{ error }}
    </p>
  </div>
</template>
