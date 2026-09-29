/**
 * Typed calls to the FastAPI backend. Types come from `schema.d.ts`, generated from the
 * backend's OpenAPI description (`npm run api:types`), so they can't drift from the API.
 * The frontend never computes financial figures: it only displays what these calls return.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];
export type ScenarioResult = Schemas["ScenarioResultOut"];
export type Snapshot = Schemas["SnapshotOut"];
export type ProjectionWarning = Schemas["WarningOut"];
export type AssumptionSet = Schemas["AssumptionSetOut"];
export type Rates = Schemas["Rates"];
export type Goal = Schemas["GoalOut"];
export type GoalIn = Schemas["GoalIn"];
export type GoalType = Schemas["GoalType"];
export type Profile = Schemas["Profile"];
export type ProfileIn = Schemas["ProfileIn"];
export type ProfileOut = Schemas["ProfileOut"];
export type PositionOut = Schemas["PositionOut"];
export type SimulateRequest = Schemas["SimulateRequest"];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** Validation messages by field name, e.g. { cash: "Input should be ≥ 0" }. */
    readonly fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}

const UNREACHABLE =
  "Can't reach the API. Is the backend running? (uvicorn app.main:app, in backend/)";

type Detail = { message: string; fieldErrors: Record<string, string> };

/**
 * FastAPI sends `detail` as a message (our 404s and domain 422s), or as a list of field
 * errors from schema validation: [{ loc: ["body", "cash"], msg: "..." }, ...].
 */
function parseDetail(body: unknown): Detail | null {
  if (typeof body !== "object" || body === null || !("detail" in body)) return null;
  const detail = body.detail;
  if (typeof detail === "string") return { message: detail, fieldErrors: {} };
  if (!Array.isArray(detail)) return null;
  const fieldErrors: Record<string, string> = {};
  for (const e of detail as { loc?: unknown[]; msg?: string }[]) {
    fieldErrors[String(e.loc?.at(-1) ?? "input")] = e.msg ?? "Invalid value";
  }
  return { message: "Some values need attention.", fieldErrors };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, UNREACHABLE);
  }
  if (!response.ok) {
    const detail = parseDetail(await response.json().catch(() => null));
    // No JSON detail on a 5xx usually means the dev proxy couldn't reach FastAPI.
    const fallback = response.status >= 500 ? UNREACHABLE : `Request failed (${response.status})`;
    throw new ApiError(response.status, detail?.message ?? fallback, detail?.fieldErrors);
  }
  return (await response.json()) as T;
}

const send = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const api = {
  simulate: (body: Partial<SimulateRequest> = {}) =>
    request<ScenarioResult>("/simulate", send("POST", body)),
  profile: () => request<ProfileOut>("/profile"),
  saveProfile: (body: ProfileIn) => request<ProfileOut>("/profile", send("PUT", body)),
  goals: () => request<Goal[]>("/goals"),
  createGoal: (body: GoalIn) => request<Goal>("/goals", send("POST", body)),
  assumptionSets: () => request<AssumptionSet[]>("/assumptions"),
  saveAssumptionSet: (name: string, rates: Rates) =>
    request<AssumptionSet>(`/assumptions/${encodeURIComponent(name)}`, send("PUT", rates)),
};
