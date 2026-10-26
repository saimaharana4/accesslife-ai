"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, createKey } from "@/lib/api/client";
import type { ApiSchemas } from "@/lib/api/contracts";
import {
  publishSessionChange,
  subscribeSessionChanges,
} from "@/lib/api/session-events";

export function useDiscoveries() {
  const [data, setData] = useState<ApiSchemas["DiscoveriesPublic"] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const controller = useRef<AbortController | null>(null);
  const locked = useRef(false);
  const intent = useRef<{
    id: string;
    kind: "save" | "remove";
    key: string;
  } | null>(null);
  const mounted = useRef(false);
  const refresh = useCallback(async () => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setLoading(true);
    try {
      const saved = await api.get<ApiSchemas["DiscoveriesPublic"]>(
        "/discoveries",
        request.signal,
      );
      if (!request.signal.aborted) {
        setData(saved);
        setError(null);
      }
    } catch (failure) {
      if (!request.signal.aborted) {
        if (failure instanceof ApiError && [401, 410].includes(failure.status))
          setData(null);
        setError(
          failure instanceof ApiError && failure.status === 401
            ? "Your guest session has ended. Start a fresh duel to save discoveries."
            : "Saved discoveries could not be checked. Reconnect and retry; no preference has been inferred.",
        );
      }
    } finally {
      if (!request.signal.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const resume = () => {
      if (!document.hidden) void refresh();
    };
    window.addEventListener("online", resume);
    window.addEventListener("focus", resume);
    const unsubscribe = subscribeSessionChanges((kind) => {
      if (kind === "session-cleared") {
        controller.current?.abort();
        setData(null);
        setPending(null);
        setLoading(false);
        intent.current = null;
        setError("Your guest session has been cleared.");
      } else if (kind === "discoveries-changed" || kind === "session-updated")
        void refresh();
    });
    return () => {
      mounted.current = false;
      controller.current?.abort();
      window.removeEventListener("online", resume);
      window.removeEventListener("focus", resume);
      unsubscribe();
    };
  }, [refresh]);
  const saved = (id: string) =>
    Boolean(data?.discoveries.some((item) => item.entity.id === id));
  async function toggle(id: string) {
    if (locked.current) return;
    const kind: "save" | "remove" = saved(id) ? "remove" : "save";
    const action =
      intent.current?.id === id && intent.current.kind === kind
        ? intent.current
        : { id, kind, key: createKey() };
    intent.current = action;
    locked.current = true;
    setPending(id);
    setError(null);
    try {
      if (kind === "save")
        await api.post<ApiSchemas["DiscoveryPublic"]>(
          "/discoveries",
          { entity_id: id },
          action.key,
        );
      else await api.delete(`/discoveries/${id}`);
      if (!mounted.current || intent.current !== action) return;
      intent.current = null;
      await refresh();
      publishSessionChange("discoveries-changed", false);
    } catch (failure) {
      if (mounted.current && intent.current === action) {
        if (
          failure instanceof ApiError &&
          [
            "DISCOVERY_REMOVED",
            "DISCOVERY_EXPIRED",
            "IDEMPOTENCY_CONFLICT",
          ].includes(failure.code)
        ) {
          intent.current = null;
          await refresh();
        }
        setError(
          failure instanceof ApiError
            ? failure.message
            : "This change could not be confirmed. Retry to recover it safely.",
        );
      }
    } finally {
      locked.current = false;
      if (mounted.current) setPending(null);
    }
  }
  return { data, error, loading, pending, saved, toggle, refresh };
}
