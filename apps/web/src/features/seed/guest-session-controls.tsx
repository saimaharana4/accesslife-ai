"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, ApiError, cancelSessionHandshake } from "@/lib/api/client";
import type { ApiSchemas } from "@/lib/api/contracts";
import {
  clearGuestIntents,
  publishSessionChange,
  subscribeSessionChanges,
} from "@/lib/api/session-events";
export function GuestSessionControls() {
  const [active, setActive] = useState(false),
    [confirm, setConfirm] = useState(false),
    [pending, setPending] = useState(false),
    [message, setMessage] = useState("");
  const controller = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    try {
      const session = await api.get<ApiSchemas["SessionPublic"]>(
        "/sessions/current",
        request.signal,
      );
      if (!request.signal.aborted) setActive(session.active);
    } catch (failure) {
      if (
        !request.signal.aborted &&
        failure instanceof ApiError &&
        failure.status === 401
      )
        setActive(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    const unsubscribe = subscribeSessionChanges((kind) => {
      if (kind === "session-cleared") {
        cancelSessionHandshake();
        controller.current?.abort();
        setActive(false);
        setConfirm(false);
      } else if (kind === "session-updated") void refresh();
    });
    window.addEventListener("focus", refresh);
    return () => {
      unsubscribe();
      controller.current?.abort();
      window.removeEventListener("focus", refresh);
    };
  }, [refresh]);
  async function clear() {
    if (pending) return;
    setPending(true);
    setMessage("");
    try {
      cancelSessionHandshake();
      await api.delete("/sessions/current");
      clearGuestIntents();
      publishSessionChange("session-cleared");
      setActive(false);
      setConfirm(false);
      document.querySelector<HTMLAnchorElement>(".wordmark")?.focus();
      setMessage(
        "Guest session cleared. Private games and saved discoveries are no longer accessible.",
      );
    } catch {
      setMessage(
        "Clearing could not be confirmed. Retry; your saved state has not been assumed cleared.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="guest-session-controls">
      {active && (
        <details>
          <summary>Guest session</summary>
          <div className="guest-session-panel">
            <p>
              Anonymous play. Saves expire with this session or their supporting
              evidence.
            </p>
            {confirm ? (
              <>
                <p>
                  Clear private access, discoveries and dependent share links
                  for this session? Existing backups are not rewritten.
                </p>
                <Button onClick={() => void clear()} pending={pending}>
                  Clear this session
                </Button>
                <Button
                  variant="quiet"
                  onClick={() => setConfirm(false)}
                  disabled={pending}
                >
                  Keep playing
                </Button>
              </>
            ) : (
              <Button variant="quiet" onClick={() => setConfirm(true)}>
                Clear guest session
              </Button>
            )}
          </div>
        </details>
      )}
      <span role="status">{message}</span>
    </div>
  );
}
