/**
 * "Describe your plan" on the forms: which fields a description changed, and the label each
 * one gets. The values themselves come from the API's draft; nothing is computed here.
 */
import type { Goal, PlanDraft, Profile } from "../api/client";

/** One message's effect on the forms: the new draft and the fields it changed. */
export type DraftUpdate = { draft: PlanDraft; changed: string[] };

export const PROFILE_FIELDS = [
  "monthly_net_income",
  "other_monthly_income",
  "monthly_expenses",
  "cash",
  "investments",
  "monthly_investment_contribution",
  "debt_balance",
  "monthly_debt_payment",
  "age",
] as const;

/** Draft field -> goal form field. */
export const GOAL_FIELDS = {
  goal_name: "name",
  goal_type: "goal_type",
  goal_target_amount: "target_amount",
  goal_target_date: "target_date",
} as const;

type DraftField = (typeof PROFILE_FIELDS)[number] | keyof typeof GOAL_FIELDS;
const ALL_FIELDS: DraftField[] = [...PROFILE_FIELDS, ...(Object.keys(GOAL_FIELDS) as DraftField[])];

/** The saved plan as the starting draft, so a description changes only what it mentions. */
export function draftFromPlan(profile: Profile | null, goal: Goal | null): PlanDraft {
  const draft: PlanDraft = { notes: {}, skipped: [], to_check: [] };
  if (profile) for (const f of PROFILE_FIELDS) draft[f] = profile[f];
  if (goal) {
    draft.goal_name = goal.name;
    draft.goal_type = goal.goal_type;
    draft.goal_target_amount = goal.target_amount;
    draft.goal_target_date = goal.target_date;
  }
  return draft;
}

/** Fields whose value a message changed. */
export function changedFields(before: PlanDraft, after: PlanDraft): DraftField[] {
  return ALL_FIELDS.filter((f) => (after[f] ?? null) !== null && after[f] !== before[f]);
}

export type FieldLabel = { badge: string; tone: "info" | "check"; note: string | null };

/**
 * The label for a field a description filled: "From your description", or "Read by the AI:
 * please check" when a language model read it; with how it was worked out ("€900 + €700").
 */
export function fieldLabel(draft: PlanDraft | null, described: Set<string>, field: string): FieldLabel | null {
  if (!draft || !described.has(field)) return null;
  const note = draft.notes[field] ?? null;
  return draft.to_check.includes(field)
    ? { badge: "Read by the AI: please check", tone: "check", note }
    : { badge: "From your description", tone: "info", note };
}
