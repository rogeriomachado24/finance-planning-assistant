/** A stand-in for the backend in component tests: canned responses per route. */
import { vi } from "vitest";

type Route = readonly [status: number, body: unknown];

/**
 * Stub `fetch`. Keys are "METHOD /path" or just "/path" (any method), without the /api
 * prefix, e.g. { "GET /profile": [404, {...}], "PUT /profile": [200, {...}] }.
 */
export function fakeApi(routes: Record<string, Route>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.replace(/^\/api/, "");
    const method = init?.method ?? "GET";
    const [status, body] = routes[`${method} ${path}`] ??
      routes[path] ?? [404, { detail: `no fake route for ${method} ${path}` }];
    // A 204 (No Content) response must not have a body.
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** The parsed JSON body of the last request sent to `method path`. */
export function lastBody(fetchMock: ReturnType<typeof fakeApi>, method: string, path: string) {
  const call = [...fetchMock.mock.calls]
    .reverse()
    .find(([url, init]) => url === `/api${path}` && (init?.method ?? "GET") === method);
  if (!call) throw new Error(`no ${method} ${path} request was sent`);
  return JSON.parse(call[1]?.body as string);
}
