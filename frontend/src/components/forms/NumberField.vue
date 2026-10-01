<script setup lang="ts">
/** A number input with a € prefix or % suffix. Empty input means `null`. */
import FormField from "./FormField.vue";

const model = defineModel<number | null>({ required: true });

withDefaults(
  defineProps<{
    id: string;
    label: string;
    unit?: "eur" | "percent" | "none";
    hint?: string;
    error?: string;
    optional?: boolean;
    required?: boolean;
    min?: number;
    max?: number;
    step?: number | "any";
    placeholder?: string;
    badge?: string;
    badgeTone?: "info" | "check";
  }>(),
  { unit: "none", step: 0.01 },
);

function onInput(event: Event) {
  const raw = (event.target as HTMLInputElement).value;
  model.value = raw === "" ? null : Number(raw);
}
</script>

<template>
  <FormField
    :id="id"
    :label="label"
    :hint="hint"
    :error="error"
    :optional="optional"
    :badge="badge"
    :badge-tone="badgeTone"
  >
    <template #default="{ describedBy, invalid }">
      <div
        class="flex items-center rounded-md border bg-surface focus-within:ring-2 focus-within:ring-series-1"
        :class="invalid ? 'border-error' : 'border-axis'"
      >
        <span v-if="unit === 'eur'" class="pl-3 text-sm text-ink-2" aria-hidden="true">€</span>
        <input
          :id="id"
          type="number"
          inputmode="decimal"
          class="w-full min-w-0 bg-transparent px-3 py-2 text-sm tabular-nums outline-none"
          :value="model ?? ''"
          :required="required"
          :min="min"
          :max="max"
          :step="step"
          :placeholder="placeholder"
          :aria-describedby="describedBy"
          :aria-invalid="invalid || undefined"
          @input="onInput"
        />
        <span v-if="unit === 'percent'" class="pr-3 text-sm text-ink-2" aria-hidden="true">%</span>
      </div>
    </template>
  </FormField>
</template>
