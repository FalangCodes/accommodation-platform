import { isAxiosError } from "axios";

/** Return readable API errors; validation payloads must never reach React as objects. */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  const detail: unknown = isAxiosError(error) ? error.response?.data?.detail : undefined;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((entry: unknown) => {
      if (entry && typeof entry === "object" && "msg" in entry && typeof entry.msg === "string") {
        return [entry.msg];
      }
      return [];
    });
    if (messages.length) return messages.join("; ");
  }
  return fallback;
}
