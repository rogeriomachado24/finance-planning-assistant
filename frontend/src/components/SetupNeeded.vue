<script setup lang="ts">
/** Shown instead of a page's content until the plan has finances and a goal. */
import { computed, onMounted } from "vue";
import { usePlanStatus } from "../composables/usePlanStatus";

defineProps<{ what: string }>();

const { status, refresh } = usePlanStatus();
onMounted(() => refresh().catch(() => {})); // name exactly what's missing right now
const missing = computed(() =>
  [!status.hasProfile && "your finances", !status.hasGoal && "a goal"].filter(Boolean).join(" and "),
);
</script>

<template>
  <section class="rounded-lg border border-hairline bg-surface p-6" aria-labelledby="setup-heading">
    <h2 id="setup-heading" class="font-semibold">Set up your plan first</h2>
    <p class="mt-1 text-sm text-ink-2">
      To show {{ what }}, the simulator needs {{ missing || "your finances and a goal" }}. It takes
      about two minutes.
    </p>
    <RouterLink
      to="/plan"
      class="mt-4 inline-block rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-surface"
    >
      Set up your plan
    </RouterLink>
    <p class="mt-3 text-xs text-ink-2">
      Just exploring? Load a sample plan with
      <code class="rounded bg-page px-1.5 py-0.5">python -m app.seed</code> in
      <code class="rounded bg-page px-1.5 py-0.5">backend/</code>, then reload.
    </p>
  </section>
</template>
