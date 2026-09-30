/**
 * The conversation with the assistant. State lives at module level, so switching pages
 * keeps it. The backend remembers context per `threadId` (for follow-ups like "and with
 * €300 instead?"); "New conversation" starts a fresh thread.
 */
import { reactive } from "vue";
import { api, ApiError, type ChatResponse } from "../api/client";

export type ChatEntry =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; response: ChatResponse }
  | { id: number; role: "error"; text: string; question: string };

const state = reactive({
  entries: [] as ChatEntry[],
  threadId: null as string | null,
  assumptionSet: "base",
  sending: false,
});
let nextId = 1;

async function send(message: string) {
  const question = message.trim();
  if (!question || state.sending) return;
  state.entries.push({ id: nextId++, role: "user", text: question });
  state.sending = true;
  try {
    const response = await api.chat({
      message: question,
      thread_id: state.threadId,
      assumption_set: state.assumptionSet,
    });
    state.threadId = response.thread_id;
    state.entries.push({ id: nextId++, role: "assistant", response });
  } catch (e) {
    const text = e instanceof ApiError ? e.message : String(e);
    state.entries.push({ id: nextId++, role: "error", text, question });
  } finally {
    state.sending = false;
  }
}

/** Send the failed question again, replacing the error and the question's first copy. */
async function retry(errorId: number) {
  const index = state.entries.findIndex((e) => e.id === errorId);
  const entry = state.entries[index];
  if (!entry || entry.role !== "error") return;
  state.entries.splice(index - 1, 2);
  await send(entry.question);
}

function reset() {
  state.entries = [];
  state.threadId = null;
}

export function useChat() {
  return { state, send, retry, reset };
}
