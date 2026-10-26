export type SessionChange =
  | "session-updated"
  | "session-cleared"
  | "game-changed"
  | "discoveries-changed";
const eventName = "tasteduel:change";
const channelName = "tasteduel-state-v1";
let tabId: string | undefined;
function ownTab() {
  return (tabId ??= crypto.randomUUID());
}
function valid(value: unknown): value is SessionChange {
  return (
    typeof value === "string" &&
    [
      "session-updated",
      "session-cleared",
      "game-changed",
      "discoveries-changed",
    ].includes(value)
  );
}
export function clearGuestIntents() {
  try {
    const keys = Object.keys(sessionStorage).filter(
      (key) =>
        key === "tasteduel.generation-intent.v1" ||
        key.startsWith("tasteduel:mutation:v1:"),
    );
    for (const key of keys) sessionStorage.removeItem(key);
  } catch {
    /* Browser storage is optional. */
  }
}
/** Invalidation hints only: no names, answers, game IDs, credentials or preferences. */
export function publishSessionChange(kind: SessionChange, includeLocal = true) {
  if (typeof window === "undefined") return;
  if (includeLocal)
    window.dispatchEvent(new CustomEvent(eventName, { detail: kind }));
  if (typeof BroadcastChannel !== "undefined") {
    const channel = new BroadcastChannel(channelName);
    channel.postMessage({ kind, source: ownTab() });
    channel.close();
  }
}
export function subscribeSessionChanges(
  listener: (kind: SessionChange) => void,
) {
  const local = (event: Event) => {
    const value = (event as CustomEvent).detail;
    if (valid(value)) listener(value);
  };
  window.addEventListener(eventName, local);
  const channel =
    typeof BroadcastChannel !== "undefined"
      ? new BroadcastChannel(channelName)
      : undefined;
  if (channel)
    channel.onmessage = (event) => {
      if (
        !event.data ||
        event.data.source === ownTab() ||
        !valid(event.data.kind)
      )
        return;
      if (event.data.kind === "session-cleared") clearGuestIntents();
      listener(event.data.kind);
    };
  return () => {
    window.removeEventListener(eventName, local);
    channel?.close();
  };
}
