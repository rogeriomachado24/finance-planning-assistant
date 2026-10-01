<script setup lang="ts">
import { routes } from "./router";
</script>

<template>
  <div class="min-h-screen">
    <header class="border-b border-hairline bg-surface">
      <div class="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-x-6 gap-y-3 px-4 pt-4 sm:px-6">
        <div class="pb-3">
          <p class="text-lg font-semibold">Goal Simulator</p>
          <p class="text-sm text-ink-2">
            Projections from a deterministic engine, under the assumptions shown. Not financial
            advice.
          </p>
        </div>
        <nav aria-label="Main" class="flex gap-1">
          <RouterLink
            v-for="route in routes.filter((r) => !r.meta.hidden)"
            :key="route.path"
            :to="route.path"
            class="border-b-2 border-transparent px-3 pb-3 text-sm text-ink-2 hover:text-ink"
            exact-active-class="!border-ink font-medium !text-ink"
          >
            {{ route.meta.title }}
          </RouterLink>
        </nav>
      </div>
    </header>

    <main class="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <RouterView />
    </main>
  </div>
</template>
