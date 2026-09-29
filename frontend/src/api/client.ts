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
export type SimulateRequest = Schemas["SimulateRequest"];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const UNREACHABLE =
  "Can't reach the API. Is the backend running? (uvicorn app.main:app, in backend/)";

/** FastAPI sends `detail` as a message, or as a list of field errors from validation. */
function detailMessage(body: unknown): string | null {
  if (typeof body !== "object" || body === null || !("detail" in body)) return null;
  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e: { loc?: unknown[]; msg?: string }) => `${e.loc?.at(-1) ?? "input"}: ${e.msg}`)
      .join("; ");
  }
  return null;
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
    const message = detailMessage(await response.json().catch(() => null));
    // No JSON detail on a 5xx usually means the dev proxy couldn't reach FastAPI.
    throw new ApiError(
      response.status,
      message ?? (response.status >= 500 ? UNREACHABLE : `Request failed (${response.status})`),
    );
  }
  return (await response.json()) as T;
}

export const api = {
  simulate: (body: Partial<SimulateRequest> = {}) =>
    request<ScenarioResult>("/simulate", { method: "POST", body: JSON.stringify(body) }),
  assumptionSets: () => request<AssumptionSet[]>("/assumptions"),
  goals: () => request<Goal[]>("/goals"),
};
