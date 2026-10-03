export const SESSION_ENDED_EVENT = "accomfind:session-ended";

export type SessionEndReason = "account_inactive" | "email_unverified" | "session_expired";

const publicAuthPaths = ["/login", "/register", "/verify-email", "/forgot-password", "/reset-password"];

export function endSession(reason: SessionEndReason) {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  window.dispatchEvent(new CustomEvent(SESSION_ENDED_EVENT, { detail: reason }));
  if (!publicAuthPaths.includes(window.location.pathname)) {
    window.location.href = `/login?reason=${reason}`;
  }
}
