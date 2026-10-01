<script setup lang="ts">
/**
 * "Describe your situation": a description in, a draft of the forms below out, one question
 * at a time with what's still missing. The API keeps nothing: the draft goes back and forth.
 * Nothing is saved here; the person checks the forms and saves them.
 */
import { onMounted, ref } from "vue";
import { api, ApiError, type DraftReply, type PlanDraft } from "../api/client";
import { changedFields, type DraftUpdate } from "../lib/draft";

const props = defineProps<{
  /** The saved plan as a draft, so a returning user's description changes only what it says. */
  start: PlanDraft;
  /** A returning user: the box describes changes rather than a whole new plan. */
  returning: boolean;
}>();
const emit = defineEmits<{ update: [update: DraftUpdate] }>();

type Turn = { message: string; understood: string[]; readBy: string };

const draft = ref<PlanDraft>(props.start);
const reply = ref<DraftReply | null>(null);
const turns = ref<Turn[]>([]);
const message = ref("");
const sending = ref(false);
const error = ref<string | null>(null);

async function send(text?: string) {
  sending.value = true;
  error.value = null;
  try {
    const result = await api.draftPlan({ message: text, draft: draft.value });
    if (text) {
      turns.value.push({ message: text, understood: result.understood, readBy: result.read_by });
      emit("update", { draft: result.draft, changed: changedFields(draft.value, result.draft) });
      message.value = "";
    }
    draft.value = result.draft;
    reply.value = result;
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    sending.value = false;
  }
}

function submit() {
  const text = message.value.trim();
  if (text && !sending.value) void send(text);
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}

function startOver() {
  draft.value = props.start;
  turns.value = [];
  void send();
}

onMounted(() => send());
</script>

<template>
  <section class="rounded-lg border border-hairline bg-surface p-5" aria-labelledby="describe-heading">
    <h2 id="describe-heading" class="font-semibold">
      {{ returning ? "Describe a change in your own words" : "Describe your situation" }}
    </h2>
    <p class="mt-1 max-w-prose text-sm text-ink-2">
      {{
        returning
          ? "For example “I now spend about 1,800 a month”. The forms below change; save them to keep it."
          : "In your own words, or fill in the forms below. They fill in as you write; nothing is saved until you check and save them, and what you write here isn't stored."
      }}
    </p>

    <!-- What was said and understood, turn by turn -->
    <ol v-if="turns.length" class="mt-4 space-y-3 text-sm">
      <li v-for="(turn, i) in turns" :key="i">
        <p class="text-ink-2">“{{ turn.message }}”</p>
        <ul v-if="turn.understood.length" class="mt-1 flex flex-wrap gap-1.5" aria-label="Understood">
          <li
            v-for="line in turn.understood"
            :key="line"
            class="rounded px-2 py-0.5 text-xs"
            :class="line.includes('please check') ? 'bg-warning/25' : 'bg-page'"
          >
            {{ line }}
          </li>
        </ul>
        <p v-else class="mt-1 text-xs text-ink-2">Nothing new understood from that.</p>
      </li>
    </ol>

    <div aria-live="polite">
      <template v-if="reply && (turns.length || !returning)">
        <p class="mt-4 font-medium">{{ reply.question }}</p>
        <p v-if="reply.still_missing.length || reply.optional_missing.length" class="mt-1 text-xs text-ink-2">
          <template v-if="reply.still_missing.length">Still missing: {{ reply.still_missing.join(", ") }}</template>
          <template v-if="reply.still_missing.length && reply.optional_missing.length"> · </template>
          <template v-if="reply.optional_missing.length">Optional: {{ reply.optional_missing.join(", ") }}</template>
        </p>
      </template>
    </div>

    <form class="mt-3" @submit.prevent="submit">
      <label for="describe-input" class="sr-only">Your description</label>
      <textarea
        id="describe-input"
        v-model="message"
        rows="3"
        maxlength="1000"
        :placeholder="
          turns.length
            ? 'Your answer, or anything else to add or correct'
            : 'e.g. I take home about 2,400 a month, spend 1,600, have 8k saved and 5k in an ETF. I want 60k for a house deposit by June 2032.'
        "
        class="w-full rounded-md border border-axis bg-surface px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-series-1"
        @keydown="onKeydown"
      />
      <div class="mt-2 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          class="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-surface disabled:opacity-60"
          :disabled="sending || !message.trim()"
        >
          {{ sending ? "Reading…" : "Send" }}
        </button>
        <button
          v-if="turns.length"
          type="button"
          class="text-sm text-ink-2 underline hover:text-ink"
          @click="startOver"
        >
          Start over
        </button>
        <span v-if="turns.length" class="text-xs text-ink-2">
          Last message read by {{ turns[turns.length - 1].readBy }}
        </span>
      </div>
      <p v-if="error" class="mt-2 text-sm font-medium text-error" role="alert">{{ error }}</p>
    </form>
  </section>
</template>
