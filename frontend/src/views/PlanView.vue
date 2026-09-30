<script setup lang="ts">
/**
 * "Your plan": the facts (finances), the goal and the assumptions that projections use.
 * A new user is guided through it in three steps; the fields start empty, with examples.
 */
import { onMounted, ref } from "vue";
import { api, ApiError, type AssumptionSet, type Goal, type Profile } from "../api/client";
import AssumptionSetForm from "../components/forms/AssumptionSetForm.vue";
import GoalForm from "../components/forms/GoalForm.vue";
import ProfileForm from "../components/forms/ProfileForm.vue";
import { usePlanStatus } from "../composables/usePlanStatus";

const profile = ref<Profile | null>(null);
const goals = ref<Goal[]>([]);
const sets = ref<AssumptionSet[]>([]);
const loading = ref(true);
const error = ref<ApiError | null>(null);
const { status, ready, refresh } = usePlanStatus();

async function loadProfile(): Promise<Profile | null> {
  try {
    return (await api.profile()).profile;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null; // nothing saved yet
    throw e;
  }
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    [profile.value, goals.value, sets.value] = await Promise.all([
      loadProfile(),
      api.goals(),
      api.assumptionSets(),
      refresh().catch(() => {}), // the step indicator is a guide; the forms work without it
    ]);
  } catch (e) {
    error.value = e instanceof ApiError ? e : new ApiError(0, String(e));
  } finally {
    loading.value = false;
  }
}

async function onGoalSaved() {
  [goals.value] = await Promise.all([api.goals(), refresh().catch(() => {})]);
}

const STEPS = [
  { key: "hasProfile", label: "Your finances", target: "finances-heading" },
  { key: "hasGoal", label: "Your goal", target: "goal-form-heading" },
] as const;

onMounted(load);
</script>

<template>
  <div class="space-y-8">
    <div>
      <h1 class="text-xl font-semibold">Your plan</h1>
      <p v-if="!ready" class="mt-1 max-w-prose text-sm text-ink-2">
        Welcome. Enter your own figures in two steps, and the simulator projects when you'll reach
        your goal. Everything stays on this computer.
      </p>
      <p v-else class="mt-1 max-w-prose text-sm text-ink-2">
        The projection uses your finances today, one goal, and a set of assumptions about the
        future. Change anything below and the projection follows.
      </p>

      <!-- Progress through the setup -->
      <ol v-if="status.loaded" class="mt-4 flex flex-wrap gap-2 text-sm" aria-label="Setup steps">
        <li
          v-for="(step, i) in STEPS"
          :key="step.key"
          class="flex items-center gap-2 rounded-full border px-3 py-1"
          :class="status[step.key] ? 'border-hairline bg-surface' : 'border-axis bg-surface font-medium'"
        >
          <svg v-if="status[step.key]" viewBox="0 0 16 16" class="size-4 text-good" aria-hidden="true">
            <circle cx="8" cy="8" r="8" fill="currentColor" />
            <path d="M4.5 8.2 7 10.5l4.5-5" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span v-else class="grid size-4 place-items-center rounded-full bg-ink text-[10px] text-surface" aria-hidden="true">{{ i + 1 }}</span>
          <a :href="`#${step.target}`" class="hover:underline">{{ step.label }}</a>
          <span class="sr-only">{{ status[step.key] ? " (done)" : " (to do)" }}</span>
        </li>
        <li class="flex items-center gap-2 rounded-full border border-hairline px-3 py-1 text-ink-2">
          <span class="grid size-4 place-items-center rounded-full bg-grid text-[10px] text-ink" aria-hidden="true">3</span>
          <a href="#sets-heading" class="hover:underline">Assumptions</a> (optional)
        </li>
      </ol>

      <div
        v-if="ready"
        class="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-hairline bg-surface p-4"
      >
        <p class="text-sm"><span class="font-medium">Your plan is ready.</span> See when you'll reach your goal.</p>
        <RouterLink to="/" class="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-surface">
          See your projection
        </RouterLink>
      </div>
    </div>

    <p v-if="loading" class="text-sm text-ink-2">Loading your plan…</p>

    <section v-else-if="error" class="rounded-lg border border-hairline bg-surface p-6" role="alert">
      <h2 class="font-semibold">Couldn't load your plan</h2>
      <p class="mt-1 text-sm text-ink-2">{{ error.message }}</p>
      <button
        type="button"
        class="mt-3 rounded-md border border-hairline px-3 py-1.5 text-sm hover:bg-page"
        @click="load"
      >
        Try again
      </button>
    </section>

    <template v-else>
      <section class="scroll-mt-6 rounded-lg border border-hairline bg-surface p-5" aria-labelledby="finances-heading">
        <h2 id="finances-heading" class="scroll-mt-6 font-semibold">1. Your finances today</h2>
        <p class="mb-4 text-sm text-ink-2">
          Monthly amounts in euros. Grey figures are only examples: type your own.
        </p>
        <ProfileForm :initial="profile" @saved="refresh().catch(() => {})" />
      </section>

      <section class="rounded-lg border border-hairline bg-surface p-5" aria-labelledby="goal-form-heading">
        <h2 id="goal-form-heading" class="scroll-mt-6 font-semibold">2. Your goal</h2>
        <p class="mb-4 text-sm text-ink-2">What you're saving for, how much, and by when.</p>
        <GoalForm :goals="goals" @saved="onGoalSaved" />
      </section>

      <section class="rounded-lg border border-hairline bg-surface p-5" aria-labelledby="sets-heading">
        <h2 id="sets-heading" class="scroll-mt-6 font-semibold">3. Assumptions (optional)</h2>
        <p class="mb-4 max-w-prose text-sm text-ink-2">
          Guesses about the future, not facts about you, so they come pre-filled with illustrative
          rates and the projection works straight away. Three sets, from cautious to hopeful, show
          how much the outcome depends on them. Change them to your own view at any time.
        </p>
        <div class="grid gap-4 md:grid-cols-3">
          <AssumptionSetForm v-for="set in sets" :key="set.name" :set="set" />
        </div>
      </section>
    </template>
  </div>
</template>
