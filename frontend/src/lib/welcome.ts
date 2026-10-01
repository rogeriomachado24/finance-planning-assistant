/**
 * Whether the welcome screen ("Continue with my plan" or "Start fresh") was already shown in
 * this browser tab. Kept in sessionStorage, so a reload doesn't ask again but opening the app
 * in a new tab or window does. Storage can be unavailable (private windows, blocked site data):
 * then the screen simply shows once per page load.
 */
const KEY = "goal-simulator:welcomed";

export function wasWelcomed(): boolean {
  try {
    return sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function markWelcomed(): void {
  try {
    sessionStorage.setItem(KEY, "1");
  } catch {
    // Not remembered; the router only checks on the first page load anyway.
  }
}
