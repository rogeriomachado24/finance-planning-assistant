<script setup lang="ts">
/**
 * Shown once per browser tab when a plan is saved: continue with it, or start fresh (clears
 * the finances, goals and saved scenarios, after a confirmation; the assumption sets stay).
 */
import { computed, onMounted, ref } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { api, ApiError, type Goal, type Profile } from "../api/client";
import { useChat } from "../composables/useChat";
import { usePlanStatus } from "../composables/usePlanStatus";
import { formatDate, formatEur } from "../lib/format";
import { markWelcomed } from "../lib/welcome";

const route = useRoute();
const router = useRouter();

const profile = ref<Profile | null>(null);
const goal = ref<Goal | null>(null);
const loading = ref(true);
const confirming = ref(false);
const clearing = ref(false);
const error = ref<string | null>(null);

/** Where the person was going when the welcome screen came first. */
const next = computed(() => {
  const target = route.query.next;
  return typeof target === "string" && target.startsWith("/") ? target : "/";
});

onMounted(async () => {
  try {
    const [saved, goals] = await Promise.all([
      api.profile().then((p) => p.profile).catch(() => null), // a goal may exist without finances
      api.goals(),
    ]);
    profile.value = saved;
    goal.value = goals.find((g) => g.is_active) ?? null;
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    loading.value = false;
  }
});

// Leaving through the navigation bar also counts as having chosen (the plan stays).
onBeforeRouteLeave(() => markWelcomed());

function continueWithPlan() {
  markWelcomed();
  void router.replace(next.value);
}

async function startFresh() {
  clearing.value = true;
  error.value = null;
  try {
    await api.clearPlan();
    useChat().reset(); // the conversation was about the old plan
    await usePlanStatus().refresh();
    markWelcomed();
    void router.replace({ name: "plan" });
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    clearing.value = false;
  }
}
</script>

<template>
  <section class="mx-auto max-w-xl rounded-lg border border-hairline bg-surface p-6" aria-labelledby="welcome-heading">
    <h1 id="welcome-heading" class="text-xl font-semibold">Welcome back</h1>
    <p v-if="loading" class="mt-2 text-sm text-ink-2">Loading your plan…</p>

    <template v-else>
      <p class="mt-2 text-sm text-ink-2">A plan is saved on this computer:</p>
      <ul class="mt-2 space-y-1 text-sm">
        <li v-if="goal">
          <span class="font-medium">{{ goal.name }}</span>: {{ formatEur(goal.target_amount) }} by
          {{ formatDate(goal.target_date) }}
        </li>
        <li v-if="profile">
          Take-home pay {{ formatEur(profile.monthly_net_income) }} a month, expenses
          {{ formatEur(profile.monthly_expenses) }} a month
        </li>
      </ul>

      <div v-if="!confirming" class="mt-5 flex flex-wrap gap-3">
        <button
          type="button"
          class="rounded-md bg-ink px-4 py-2 text-sm font-medium text-surface"
          @click="continueWithPlan"
        >
          Continue with my plan
        </button>
        <button
          type="button"
          class="rounded-md border border-axis px-4 py-2 text-sm font-medium hover:bg-page"
          @click="confirming = true"
        >
          Start fresh
        </button>
      </div>

      <div v-else class="mt-5 rounded-md border border-warning bg-warning/10 p-4" role="alertdialog" aria-labelledby="confirm-heading">
        <h2 id="confirm-heading" class="text-sm font-semibold">Start fresh?</h2>
        <p class="mt-1 text-sm">
          This deletes your finances, your goals and your saved scenarios from this computer. It
          can't be undone. Your assumption sets stay as they are.
        </p>
        <div class="mt-3 flex flex-wrap gap-3">
          <button
            type="button"
            class="rounded-md bg-ink px-4 py-2 text-sm font-medium text-surface disabled:opacity-60"
            :disabled="clearing"
            @click="startFresh"
          >
            {{ clearing ? "Clearing…" : "Delete and start fresh" }}
          </button>
          <button
            type="button"
            class="rounded-md border border-axis px-4 py-2 text-sm font-medium hover:bg-page"
            :disabled="clearing"
            @click="confirming = false"
          >
            Cancel
          </button>
        </div>
      </div>
    </template>

    <p v-if="error" class="mt-3 text-sm font-medium text-error" role="alert">{{ error }}</p>
  </section>
</template>
