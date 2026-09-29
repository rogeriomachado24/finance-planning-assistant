<script setup lang="ts">
/** Segmented control choosing which assumption set the projection uses. */
const model = defineModel<string>({ required: true });
defineProps<{ names: string[] }>();
</script>

<template>
  <fieldset class="flex flex-wrap items-center gap-3">
    <legend class="sr-only">Assumption set</legend>
    <span class="text-sm text-ink-2" aria-hidden="true">Assumptions</span>
    <div class="inline-flex rounded-lg border border-hairline bg-surface p-0.5">
      <label
        v-for="name in names"
        :key="name"
        class="cursor-pointer rounded-md px-3 py-1 text-sm capitalize has-checked:bg-ink has-checked:text-surface has-focus-visible:ring-2 has-focus-visible:ring-series-1"
      >
        <input v-model="model" type="radio" name="assumption-set" :value="name" class="sr-only" />
        {{ name }}
      </label>
    </div>
  </fieldset>
</template>
