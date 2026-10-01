<script setup lang="ts">
/**
 * "Your goal": saving creates a new goal that becomes the active one; the previous goal
 * is kept in the history below (the API never edits a goal in place).
 */
import { computed, reactive, ref, watch } from "vue";
import { api, type Goal, type GoalIn, type GoalType } from "../../api/client";
import { useSubmit } from "../../composables/useSubmit";
import { type DraftUpdate, fieldLabel, GOAL_FIELDS } from "../../lib/draft";
import { formatDate, formatEur } from "../../lib/format";
import FormField from "./FormField.vue";
import NumberField from "./NumberField.vue";
import SaveBar from "./SaveBar.vue";

const props = defineProps<{
  goals: Goal[];
  /** Values from "Describe your situation": only the changed fields are filled in. */
  update?: DraftUpdate | null;
}>();
const emit = defineEmits<{ saved: [goal: Goal] }>();

const GOAL_TYPES: Record<GoalType, string> = {
  house: "House",
  emergency_fund: "Emergency fund",
  retirement: "Retirement",
  education: "Education",
  vehicle: "Vehicle",
  travel: "Travel",
  other: "Other",
};

const active = computed(() => props.goals.find((g) => g.is_active) ?? null);
const previous = computed(() => props.goals.filter((g) => !g.is_active));

const form = reactive({
  name: active.value?.name ?? "",
  goal_type: (active.value?.goal_type ?? "other") as GoalType,
  target_amount: (active.value?.target_amount ?? null) as number | null,
  target_date: active.value?.target_date ?? "",
  description: active.value?.description ?? "",
});

// Projections start on the first of the current month, so that's the earliest target date.
const today = new Date();
const minDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;

const { status, error, fieldErrors, submit, markEdited } = useSubmit(
  () => {
    const body: GoalIn = {
      name: form.name,
      goal_type: form.goal_type,
      target_amount: form.target_amount ?? 0,
      target_date: form.target_date,
      description: form.description.trim() || null,
    };
    return api.createGoal(body);
  },
  (goal) => emit("saved", goal),
);

watch(form, markEdited);

// Fields a description filled (draft names, e.g. "goal_target_amount"), labelled.
const described = ref(new Set<string>());
watch(
  () => props.update,
  (u) => {
    if (!u) return;
    const d = u.draft;
    for (const key of u.changed) {
      if (!(key in GOAL_FIELDS)) continue;
      described.value.add(key);
      if (key === "goal_name") form.name = d.goal_name ?? "";
      if (key === "goal_type") form.goal_type = d.goal_type ?? "other";
      if (key === "goal_target_amount") form.target_amount = d.goal_target_amount ?? null;
      if (key === "goal_target_date") form.target_date = d.goal_target_date ?? "";
    }
  },
);
const label = (key: string) => fieldLabel(props.update?.draft ?? null, described.value, key);
const withNote = (key: string, hint: string | undefined) => {
  const note = label(key)?.note;
  if (!note) return hint;
  return `${note.charAt(0).toUpperCase()}${note.slice(1)}.${hint ? ` ${hint}` : ""}`;
};

const inputClass =
  "w-full rounded-md border bg-surface px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-series-1";
const borderFor = (field: string) => (fieldErrors.value[field] ? "border-error" : "border-axis");
</script>

<template>
  <div class="space-y-6">
    <p v-if="active" class="text-sm text-ink-2">
      Active goal: <span class="font-medium text-ink">{{ active.name }}</span>,
      {{ formatEur(active.target_amount) }} by {{ formatDate(active.target_date) }}. Saving
      replaces it; the current goal is kept in the history below.
    </p>

    <form class="space-y-4" @submit.prevent="submit">
      <div class="grid gap-4 sm:grid-cols-2">
        <FormField
          id="goal-name"
          label="Name"
          :error="fieldErrors.name"
          :badge="label('goal_name')?.badge"
          :badge-tone="label('goal_name')?.tone"
        >
          <template #default="{ describedBy, invalid }">
            <input
              id="goal-name"
              v-model="form.name"
              type="text"
              required
              maxlength="100"
              placeholder="e.g. Buy a house"
              :class="[inputClass, borderFor('name')]"
              :aria-describedby="describedBy"
              :aria-invalid="invalid || undefined"
            />
          </template>
        </FormField>

        <FormField
          id="goal-type"
          label="Type"
          :error="fieldErrors.goal_type"
          :badge="label('goal_type')?.badge"
          :badge-tone="label('goal_type')?.tone"
        >
          <template #default="{ describedBy }">
            <select
              id="goal-type"
              v-model="form.goal_type"
              :class="[inputClass, 'border-axis']"
              :aria-describedby="describedBy"
            >
              <option v-for="(label, value) in GOAL_TYPES" :key="value" :value="value">
                {{ label }}
              </option>
            </select>
          </template>
        </FormField>

        <NumberField
          id="goal-target_amount"
          v-model="form.target_amount"
          unit="eur"
          label="Target amount"
          :hint="withNote('goal_target_amount', 'Cash + investments you want to have by the target date.')"
          :badge="label('goal_target_amount')?.badge"
          :badge-tone="label('goal_target_amount')?.tone"
          placeholder="e.g. 80,000"
          required
          :min="0.01"
          :error="fieldErrors.target_amount"
        />

        <FormField
          id="goal-target_date"
          label="Target date"
          :hint="withNote('goal_target_date', 'From this month, up to 50 years ahead.')"
          :badge="label('goal_target_date')?.badge"
          :badge-tone="label('goal_target_date')?.tone"
          :error="fieldErrors.target_date"
        >
          <template #default="{ describedBy, invalid }">
            <input
              id="goal-target_date"
              v-model="form.target_date"
              type="date"
              required
              :min="minDate"
              :class="[inputClass, borderFor('target_date')]"
              :aria-describedby="describedBy"
              :aria-invalid="invalid || undefined"
            />
          </template>
        </FormField>
      </div>

      <FormField id="goal-description" label="Description" optional :error="fieldErrors.description">
        <template #default="{ describedBy }">
          <textarea
            id="goal-description"
            v-model="form.description"
            rows="2"
            maxlength="1000"
            placeholder="e.g. Deposit for a first flat"
            :class="[inputClass, 'border-axis']"
            :aria-describedby="describedBy"
          />
        </template>
      </FormField>

      <SaveBar :label="active ? 'Save as new goal' : 'Save goal'" :status="status" :error="error">
        <template #saved>Saved. This is now your active goal.</template>
      </SaveBar>
    </form>

    <div v-if="previous.length">
      <h3 class="text-sm font-semibold">Previous goals</h3>
      <ul class="mt-2 divide-y divide-grid text-sm">
        <li v-for="goal in previous" :key="goal.id" class="flex flex-wrap justify-between gap-2 py-1.5">
          <span>{{ goal.name }}</span>
          <span class="text-ink-2 tabular-nums">
            {{ formatEur(goal.target_amount) }} by {{ formatDate(goal.target_date) }}
          </span>
        </li>
      </ul>
    </div>
  </div>
</template>
