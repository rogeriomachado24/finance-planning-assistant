<script setup lang="ts">
/** Edit one assumption set. Rates are typed as percentages and sent as decimals. */
import { reactive, watch } from "vue";
import { api, type AssumptionSet, type Rates } from "../../api/client";
import { useSubmit } from "../../composables/useSubmit";
import { percentToRate, rateToPercent } from "../../lib/units";
import NumberField from "./NumberField.vue";
import SaveBar from "./SaveBar.vue";

const props = defineProps<{ set: AssumptionSet }>();

const FIELDS: { key: keyof Rates; label: string; hint?: string }[] = [
  { key: "annual_return", label: "Investment return", hint: "After fees." },
  { key: "annual_salary_growth", label: "Salary growth" },
  { key: "annual_expense_growth", label: "Expense growth" },
  { key: "annual_inflation", label: "Inflation", hint: "Shown only; not used in calculations." },
];

const percents = reactive(
  Object.fromEntries(FIELDS.map(({ key }) => [key, rateToPercent(props.set.assumptions[key])])) as Record<
    keyof Rates,
    number | null
  >,
);

const { status, error, fieldErrors, submit, markEdited } = useSubmit(() => {
  const rates = Object.fromEntries(
    FIELDS.map(({ key }) => [key, percentToRate(percents[key] ?? 0)]),
  ) as Rates;
  return api.saveAssumptionSet(props.set.name, rates);
});

watch(percents, markEdited);
</script>

<template>
  <form
    class="rounded-lg border border-hairline p-4"
    :aria-labelledby="`set-${set.name}-heading`"
    @submit.prevent="submit"
  >
    <h3 :id="`set-${set.name}-heading`" class="mb-3 font-semibold capitalize">{{ set.name }}</h3>
    <div class="space-y-3">
      <NumberField
        v-for="field in FIELDS"
        :id="`set-${set.name}-${field.key}`"
        :key="field.key"
        v-model="percents[field.key]"
        unit="percent"
        :label="`${field.label}, per year`"
        :hint="field.hint"
        required
        :min="-99.99"
        :max="100"
        :error="fieldErrors[field.key]"
      />
    </div>
    <div class="mt-4">
      <SaveBar label="Save" :status="status" :error="error" />
    </div>
  </form>
</template>
