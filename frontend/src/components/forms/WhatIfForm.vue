<script setup lang="ts">
/**
 * Save your own what-if scenario. Every field is a change relative to the saved plan;
 * empty means "keep it". Placeholders show today's values from the current plan.
 */
import { computed, reactive, watch } from "vue";
import { api, ApiError, type Overrides, type ScenarioResult } from "../../api/client";
import { useSubmit } from "../../composables/useSubmit";
import { formatEur, formatPercent } from "../../lib/format";
import { percentToRate, rateToPercent } from "../../lib/units";
import FormField from "./FormField.vue";
import NumberField from "./NumberField.vue";
import SaveBar from "./SaveBar.vue";

const props = defineProps<{ currentPlan: ScenarioResult }>();
const emit = defineEmits<{ saved: [] }>();

const form = reactive({
  name: "",
  description: "",
  contributionChange: null as number | null,
  income: null as number | null,
  expenses: null as number | null,
  returnPercent: null as number | null,
  salaryGrowthPercent: null as number | null,
  expenseGrowthPercent: null as number | null,
});

/** Today's values: formatted for the hints, bare numbers for the placeholders. */
const now = computed(() => {
  const { profile, assumptions, monthly_contribution } = props.currentPlan;
  const money = (v: number) => ({ hint: `Now ${formatEur(v)}.`, placeholder: String(v) });
  const pct = (r: number) => ({ hint: `Now ${formatPercent(r)}.`, placeholder: String(rateToPercent(r)) });
  return {
    contribution: money(monthly_contribution),
    income: money(profile.monthly_net_income),
    expenses: money(profile.monthly_expenses),
    return: pct(assumptions.annual_return),
    salary: pct(assumptions.annual_salary_growth),
    expenseGrowth: pct(assumptions.annual_expense_growth),
  };
});

const rate = (percent: number | null) => (percent === null ? null : percentToRate(percent));

const { status, error, fieldErrors, submit, markEdited } = useSubmit(
  async () => {
    const overrides: Overrides = {
      monthly_investment_contribution_delta: form.contributionChange,
      monthly_net_income: form.income,
      monthly_expenses: form.expenses,
      annual_return: rate(form.returnPercent),
      annual_salary_growth: rate(form.salaryGrowthPercent),
      annual_expense_growth: rate(form.expenseGrowthPercent),
    };
    if (Object.values(overrides).every((v) => v === null)) {
      throw new ApiError(0, "Change at least one value; otherwise it's the current plan.");
    }
    return api.saveScenario({ name: form.name, description: form.description.trim(), overrides });
  },
  () => emit("saved"),
);

watch(form, markEdited);
</script>

<template>
  <form class="space-y-4" @submit.prevent="submit">
    <div class="grid gap-4 sm:grid-cols-2">
      <FormField id="whatif-name" label="Name" hint="A scenario with the same name is replaced." :error="fieldErrors.name">
        <template #default="{ describedBy, invalid }">
          <input
            id="whatif-name"
            v-model="form.name"
            type="text"
            required
            maxlength="100"
            placeholder="e.g. Spend €200 less"
            class="w-full rounded-md border bg-surface px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-series-1"
            :class="invalid ? 'border-error' : 'border-axis'"
            :aria-describedby="describedBy"
            :aria-invalid="invalid || undefined"
          />
        </template>
      </FormField>
      <FormField id="whatif-description" label="Description" optional>
        <template #default="{ describedBy }">
          <input
            id="whatif-description"
            v-model="form.description"
            type="text"
            maxlength="1000"
            class="w-full rounded-md border border-axis bg-surface px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-series-1"
            :aria-describedby="describedBy"
          />
        </template>
      </FormField>
    </div>

    <fieldset>
      <legend class="mb-2 text-sm font-semibold">Changes (leave empty to keep today's value)</legend>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <NumberField
          id="whatif-contribution"
          v-model="form.contributionChange"
          unit="eur"
          label="Change to monthly investment"
          :hint="`${now.contribution.hint} Use a minus sign to invest less.`"
          placeholder="200"
          :error="fieldErrors.monthly_investment_contribution_delta"
        />
        <NumberField
          id="whatif-income"
          v-model="form.income"
          unit="eur"
          label="Monthly take-home pay"
          :hint="now.income.hint"
          :placeholder="now.income.placeholder"
          :min="0"
          :error="fieldErrors.monthly_net_income"
        />
        <NumberField
          id="whatif-expenses"
          v-model="form.expenses"
          unit="eur"
          label="Monthly expenses"
          :hint="now.expenses.hint"
          :placeholder="now.expenses.placeholder"
          :min="0"
          :error="fieldErrors.monthly_expenses"
        />
        <NumberField
          id="whatif-return"
          v-model="form.returnPercent"
          unit="percent"
          label="Investment return, per year"
          :hint="now.return.hint"
          :placeholder="now.return.placeholder"
          :min="-99.99"
          :max="100"
          :error="fieldErrors.annual_return"
        />
        <NumberField
          id="whatif-salary"
          v-model="form.salaryGrowthPercent"
          unit="percent"
          label="Salary growth, per year"
          :hint="now.salary.hint"
          :placeholder="now.salary.placeholder"
          :min="-99.99"
          :max="100"
          :error="fieldErrors.annual_salary_growth"
        />
        <NumberField
          id="whatif-expense-growth"
          v-model="form.expenseGrowthPercent"
          unit="percent"
          label="Expense growth, per year"
          :hint="now.expenseGrowth.hint"
          :placeholder="now.expenseGrowth.placeholder"
          :min="-99.99"
          :max="100"
          :error="fieldErrors.annual_expense_growth"
        />
      </div>
    </fieldset>

    <SaveBar label="Save and compare" :status="status" :error="error">
      <template #saved>Saved. It's now in the comparison.</template>
    </SaveBar>
  </form>
</template>
