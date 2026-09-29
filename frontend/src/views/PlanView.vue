<script setup lang="ts">
/** "Your plan": the facts (profile), the goal and the assumptions that projections use. */
import { onMounted, ref } from "vue";
import { api, ApiError, type AssumptionSet, type Goal, type Profile } from "../api/client";
import AssumptionSetForm from "../components/forms/AssumptionSetForm.vue";
import GoalForm from "../components/forms/GoalForm.vue";
import ProfileForm from "../components/forms/ProfileForm.vue";

const profile = ref<Profile | null>(null);
const goals = ref<Goal[]>([]);
const sets = ref<AssumptionSet[]>([]);
const loading = ref(true);
const error = ref<ApiError | null>(null);

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
    ]);
  } catch (e) {
    error.value = e instanceof ApiError ? e : new ApiError(0, String(e));
  } finally {
    loading.value = false;
  }
}

async function reloadGoals() {
  goals.value = await api.goals();
}

onMounted(load);
</script>

<template>
  <div class="space-y-8">
    <div>
      <h1 class="text-xl font-semibold">Your plan</h1>
      <p class="mt-1 max-w-prose text-sm text-ink-2">
        The projection uses these three things: your finances today, one goal, and a set of
        assumptions about the future. Everything is stored locally.
        <RouterLink to="/" class="font-medium text-ink underline underline-offset-2">
          See the projection
        </RouterLink>
      </p>
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
      <section class="rounded-lg border border-hairline bg-surface p-5" aria-labelledby="finances-heading">
        <h2 id="finances-heading" class="font-semibold">Your finances today</h2>
        <p class="mb-4 text-sm text-ink-2">Monthly amounts in euros.</p>
        <ProfileForm :initial="profile" />
      </section>

      <section class="rounded-lg border border-hairline bg-surface p-5" aria-labelledby="goal-form-heading">
        <h2 id="goal-form-heading" class="mb-4 font-semibold">Your goal</h2>
        <GoalForm :goals="goals" @saved="reloadGoals" />
      </section>

      <section class="rounded-lg border border-hairline bg-surface p-5" aria-labelledby="sets-heading">
        <h2 id="sets-heading" class="font-semibold">Assumptions</h2>
        <p class="mb-4 max-w-prose text-sm text-ink-2">
          Three sets, from cautious to hopeful, so you can see how much the outcome depends on
          them. The starting values are illustrative, not forecasts; change them to your own view.
        </p>
        <div class="grid gap-4 md:grid-cols-3">
          <AssumptionSetForm v-for="set in sets" :key="set.name" :set="set" />
        </div>
      </section>
    </template>
  </div>
</template>
