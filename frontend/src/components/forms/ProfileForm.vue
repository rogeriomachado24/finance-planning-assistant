<script setup lang="ts">
/**
 * "Your finances today": create or replace the profile. After saving, it shows the
 * surplus and savings rate the API computed from what was stored.
 */
import { reactive, ref, watch } from "vue";
import { api, type PositionOut, type Profile, type ProfileIn } from "../../api/client";
import { useSubmit } from "../../composables/useSubmit";
import { formatEur, formatPercent } from "../../lib/format";
import NumberField from "./NumberField.vue";
import SaveBar from "./SaveBar.vue";

const props = defineProps<{ initial: Profile | null }>();
const emit = defineEmits<{ saved: [] }>();

type MoneyField = Exclude<keyof ProfileIn, "age">;
type FormState = Record<MoneyField, number | null> & { age: number | null };

const form = reactive<FormState>({
  monthly_net_income: props.initial?.monthly_net_income ?? null,
  other_monthly_income: props.initial?.other_monthly_income ?? null,
  monthly_expenses: props.initial?.monthly_expenses ?? null,
  cash: props.initial?.cash ?? null,
  investments: props.initial?.investments ?? null,
  monthly_investment_contribution: props.initial?.monthly_investment_contribution ?? null,
  debt_balance: props.initial?.debt_balance ?? null,
  monthly_debt_payment: props.initial?.monthly_debt_payment ?? null,
  age: props.initial?.age ?? null,
});

const GROUPS: { title: string; fields: { key: MoneyField; label: string; hint: string; required?: boolean }[] }[] = [
  {
    title: "Income",
    fields: [
      { key: "monthly_net_income", label: "Monthly take-home pay", hint: "After tax. Grows with salary growth.", required: true },
      { key: "other_monthly_income", label: "Other monthly income", hint: "E.g. rent received. Stays the same over time." },
    ],
  },
  {
    title: "Spending",
    fields: [
      { key: "monthly_expenses", label: "Monthly expenses", hint: "Living costs, excluding debt payments.", required: true },
    ],
  },
  {
    title: "Savings",
    fields: [
      { key: "cash", label: "Cash", hint: "Current and savings accounts. Earns no interest in the projection." },
      { key: "investments", label: "Investments", hint: "Current value. Grows at the assumed return." },
      { key: "monthly_investment_contribution", label: "Invested each month", hint: "Moved from cash to investments at the end of each month." },
    ],
  },
  {
    title: "Debt",
    fields: [
      { key: "debt_balance", label: "Debt balance", hint: "What you still owe. No interest is modelled." },
      { key: "monthly_debt_payment", label: "Monthly debt payment", hint: "Stops once the balance is repaid." },
    ],
  },
];

const position = ref<PositionOut | null>(null);

const { status, error, fieldErrors, submit, markEdited } = useSubmit(
  () => {
    const body: ProfileIn = {
      monthly_net_income: form.monthly_net_income ?? 0,
      monthly_expenses: form.monthly_expenses ?? 0,
      other_monthly_income: form.other_monthly_income ?? 0,
      cash: form.cash ?? 0,
      investments: form.investments ?? 0,
      monthly_investment_contribution: form.monthly_investment_contribution ?? 0,
      debt_balance: form.debt_balance ?? 0,
      monthly_debt_payment: form.monthly_debt_payment ?? 0,
      age: form.age,
    };
    return api.saveProfile(body);
  },
  (saved) => {
    position.value = saved.position;
    emit("saved");
  },
);

watch(form, markEdited);
</script>

<template>
  <form class="space-y-6" @submit.prevent="submit">
    <fieldset v-for="group in GROUPS" :key="group.title">
      <legend class="mb-2 text-sm font-semibold">{{ group.title }}</legend>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <NumberField
          v-for="field in group.fields"
          :id="`profile-${field.key}`"
          :key="field.key"
          v-model="form[field.key]"
          unit="eur"
          :label="field.label"
          :hint="field.hint"
          :required="field.required"
          :optional="!field.required"
          :min="0"
          :error="fieldErrors[field.key]"
        />
      </div>
    </fieldset>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <NumberField
        id="profile-age"
        v-model="form.age"
        label="Age"
        hint="For your reference; not used in the projection."
        optional
        :min="0"
        :max="120"
        :step="1"
        :error="fieldErrors.age"
      />
    </div>

    <SaveBar label="Save finances" :status="status" :error="error">
      <template #saved>
        <template v-if="position">
          Saved. Monthly surplus {{ formatEur(position.monthly_surplus) }}<template
            v-if="position.savings_rate !== null"
          >, savings rate {{ formatPercent(position.savings_rate) }}</template>.
        </template>
      </template>
    </SaveBar>
  </form>
</template>
