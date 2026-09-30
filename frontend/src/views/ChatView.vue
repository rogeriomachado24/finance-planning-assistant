<script setup lang="ts">
/**
 * Ask questions in plain English. Each reply shows how the question was understood, the
 * engine's figures as cards, and the assumptions behind them. The assistant never
 * calculates: it turns the question into a structured request for the same engine the
 * dashboard uses.
 */
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { api, type AssumptionSet, type ChatResponse, type Health } from "../api/client";
import AssumptionSetPicker from "../components/AssumptionSetPicker.vue";
import ChatResults from "../components/chat/ChatResults.vue";
import { useChat } from "../composables/useChat";
import { usePlanStatus } from "../composables/usePlanStatus";
import { describeIntent } from "../lib/intent";

const { state, send, retry, reset } = useChat();
const { ready: planReady, status: planStatus } = usePlanStatus();

const EXAMPLES = [
  "Am I on track?",
  "What if I invest €200 more per month?",
  "How likely am I to reach my goal?",
  "What if the market falls 30% next year?",
  "How much do I need to invest each month?",
  "Compare my options",
  "What are you assuming?",
];

const draft = ref("");
const sets = ref<AssumptionSet[]>([]);
const health = ref<Health | null>(null);
const logEnd = ref<HTMLElement | null>(null);

onMounted(async () => {
  [sets.value, health.value] = await Promise.all([
    api.assumptionSets().catch(() => []),
    api.health().catch(() => null),
  ]);
});

/** A short heading for replies that aren't answers. */
function statusLabel(response: ChatResponse): string | null {
  if (response.status === "clarification") return "Needs more detail";
  if (response.intent.kind !== "unsupported") return null;
  return {
    advice: "I don't give advice",
    out_of_scope: "Outside what I cover",
    not_understood: "Didn't understand",
  }[response.intent.reason];
}

const modelStatus = computed(() => {
  const llm = health.value?.llm;
  if (!llm) return null;
  if (llm.provider === "mock") return "Rules only (no AI model configured)";
  return llm.available ? `AI model: ${llm.provider}, ready` : `AI model ${llm.provider} unavailable: using rules`;
});

async function submit(text = draft.value) {
  if (!text.trim() || state.sending) return;
  draft.value = "";
  await send(text);
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}

// Keep the newest message in view.
watch(
  () => [state.entries.length, state.sending],
  async () => {
    await nextTick();
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    logEnd.value?.scrollIntoView?.({ block: "end", behavior: reduce ? "auto" : "smooth" });
  },
);
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="sr-only">Ask about your plan</h1>

    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <AssumptionSetPicker v-if="sets.length" v-model="state.assumptionSet" :names="sets.map((s) => s.name)" />
      <div class="flex items-center gap-3 text-xs text-ink-2">
        <span v-if="modelStatus">{{ modelStatus }}</span>
        <button
          v-if="state.entries.length"
          type="button"
          class="rounded-md border border-hairline px-2.5 py-1 hover:bg-surface"
          @click="reset"
        >
          New conversation
        </button>
      </div>
    </div>

    <!-- Empty conversation: what can be asked -->
    <section v-if="!state.entries.length" class="rounded-lg border border-hairline bg-surface p-5">
      <h2 class="font-semibold">Ask about your plan</h2>
      <p class="mt-1 text-sm text-ink-2">
        Questions are turned into requests for the same engine as the dashboard; the assistant
        never calculates. Every answer shows its figures and the assumptions behind them. It
        doesn't give advice.
      </p>
      <p v-if="planStatus.loaded && !planReady" class="mt-3 rounded-md bg-page p-3 text-sm">
        Questions about your projection need your finances and a goal first.
        <RouterLink to="/plan" class="font-medium underline underline-offset-2">Set up your plan</RouterLink>
      </p>
      <div class="mt-4 flex flex-wrap gap-2">
        <button
          v-for="example in EXAMPLES"
          :key="example"
          type="button"
          class="rounded-full border border-hairline bg-page px-3 py-1.5 text-sm hover:border-axis"
          @click="submit(example)"
        >
          {{ example }}
        </button>
      </div>
    </section>

    <!-- The conversation -->
    <div role="log" aria-live="polite" aria-label="Conversation" class="space-y-4">
      <template v-for="entry in state.entries" :key="entry.id">
        <div v-if="entry.role === 'user'" class="flex justify-end">
          <p class="max-w-[85%] rounded-lg bg-ink px-3.5 py-2 text-sm text-surface">{{ entry.text }}</p>
        </div>

        <article
          v-else-if="entry.role === 'assistant'"
          class="rounded-lg border border-hairline bg-surface p-4"
          :aria-label="`Reply: ${entry.response.status}`"
        >
          <p v-if="statusLabel(entry.response)" class="mb-1 text-xs font-medium text-ink-2">
            {{ statusLabel(entry.response) }}
          </p>
          <p class="whitespace-pre-line text-sm leading-relaxed">{{ entry.response.reply }}</p>
          <ChatResults v-if="entry.response.status === 'answered'" :response="entry.response" />
          <p class="mt-3 border-t border-hairline pt-2 text-xs text-muted">
            Understood as: {{ describeIntent(entry.response.intent) }} ·
            by {{ entry.response.parsed_by }} · reply by {{ entry.response.worded_by }}
          </p>
        </article>

        <div v-else class="rounded-lg border border-hairline bg-surface p-4 text-sm" role="alert">
          <p class="font-medium text-error">Couldn't get an answer: {{ entry.text }}</p>
          <button
            type="button"
            class="mt-2 rounded-md border border-hairline px-2.5 py-1 text-xs hover:bg-page"
            @click="retry(entry.id)"
          >
            Try again
          </button>
        </div>
      </template>

      <p v-if="state.sending" class="text-sm text-ink-2">Working it out…</p>
      <!-- scroll margin = the sticky composer's height, so it never covers the newest reply -->
      <div ref="logEnd" class="scroll-mb-36" />
    </div>

    <!-- Composer -->
    <form class="sticky bottom-0 mt-4 bg-page pb-4 pt-2" @submit.prevent="submit()">
      <label for="chat-input" class="sr-only">Your question</label>
      <div class="flex items-end gap-2 rounded-lg border border-axis bg-surface p-2 focus-within:ring-2 focus-within:ring-series-1">
        <textarea
          id="chat-input"
          v-model="draft"
          rows="2"
          maxlength="500"
          placeholder="e.g. What if I spend €200 less per month?"
          class="min-h-0 flex-1 resize-none bg-transparent px-1 text-sm outline-none"
          aria-describedby="chat-hint"
          @keydown="onKeydown"
        />
        <button
          type="submit"
          class="rounded-md bg-ink px-4 py-2 text-sm font-medium text-surface disabled:opacity-60"
          :disabled="state.sending || !draft.trim()"
        >
          Send
        </button>
      </div>
      <p id="chat-hint" class="mt-1 text-xs text-muted">
        Enter to send, Shift+Enter for a new line. Projections, not advice.
      </p>
    </form>
  </div>
</template>
