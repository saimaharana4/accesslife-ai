"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api/client";
import type { ApiSchemas } from "@/lib/api/contracts";
import { challengeRequestKey } from "./challenge-share";

type Outcome = ApiSchemas["DuelOutcomePublic"];
export function DuelVerdict({
  gameId,
  fixed,
}: {
  gameId: string;
  fixed: boolean;
}) {
  const router = useRouter();
  const [results, setResults] = useState<
    ApiSchemas["DuelResultsPublic"] | null
  >(null);
  const [older, setOlder] = useState<Outcome[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const paging = useRef<AbortController | null>(null);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let request: AbortController | undefined;
    let stopped = false,
      terminal = false,
      failures = 0;
    let pollable = true;
    async function refresh() {
      clearTimeout(timer);
      if (stopped || terminal || document.hidden) return;
      request?.abort();
      const controller = new AbortController();
      request = controller;
      try {
        const value = await api.get<ApiSchemas["DuelResultsPublic"]>(
          `/games/${gameId}/duels`,
          controller.signal,
        );
        if (!controller.signal.aborted && !stopped) {
          setResults(value);
          setNotice("");
          failures = 0;
          pollable = value.status === "active";
          if (!pollable) {
            setOlder([]);
            setNext(null);
          }
        }
      } catch (error) {
        if (controller.signal.aborted || stopped) return;
        failures += 1;
        if (
          error instanceof ApiError &&
          [401, 404, 410].includes(error.status)
        ) {
          terminal = true;
          paging.current?.abort();
          setResults(null);
          setOlder([]);
          setNotice(
            "This duel is no longer available. A session or its evidence expired, or the link was retired.",
          );
        } else
          setNotice(
            "Live score check paused. Showing the last saved verdict; we’ll retry when the connection is back.",
          );
      } finally {
        if (!stopped && !terminal && pollable && !controller.signal.aborted)
          timer = setTimeout(
            () => void refresh(),
            Math.min(60_000, 10_000 * 2 ** Math.min(failures, 3)),
          );
      }
    }
    const wake = () => {
      if (!document.hidden) void refresh();
      else {
        clearTimeout(timer);
        request?.abort();
      }
    };
    void refresh();
    window.addEventListener("online", wake);
    window.addEventListener("focus", wake);
    window.addEventListener("tasteduel:challenge-ready", wake);
    document.addEventListener("visibilitychange", wake);
    return () => {
      stopped = true;
      clearTimeout(timer);
      request?.abort();
      paging.current?.abort();
      window.removeEventListener("online", wake);
      window.removeEventListener("focus", wake);
      window.removeEventListener("tasteduel:challenge-ready", wake);
      document.removeEventListener("visibilitychange", wake);
    };
  }, [gameId, attempt]);
  async function more() {
    const cursor = older.length ? next : results?.next_cursor;
    if (!cursor || lock.current) return;
    lock.current = true;
    setBusy(true);
    const controller = new AbortController();
    paging.current = controller;
    try {
      const page = await api.get<ApiSchemas["DuelResultsPublic"]>(
        `/games/${gameId}/duels?cursor=${encodeURIComponent(cursor)}`,
        controller.signal,
      );
      if (!controller.signal.aborted) {
        setOlder((rows) => [...rows, ...page.outcomes]);
        setNext(page.next_cursor ?? null);
      }
    } catch {
      if (!controller.signal.aborted)
        setNotice("Couldn’t load older attempts. Try again.");
    } finally {
      lock.current = false;
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  async function replay() {
    if (!results?.replay_slug || lock.current) return;
    lock.current = true;
    setBusy(true);
    const controller = new AbortController();
    paging.current = controller;
    try {
      const key = challengeRequestKey(
        `tasteduel:challenge-play:v1:again:${gameId}`,
      );
      const game = await api.post<ApiSchemas["GamePublic"]>(
        `/challenges/${results.replay_slug}/plays`,
        { new_attempt: true },
        key,
        controller.signal,
      );
      if (!controller.signal.aborted) {
        try {
          sessionStorage.removeItem(
            `tasteduel:challenge-play:v1:${results.replay_slug}`,
          );
        } catch {
          /* Optional storage. */
        }
        router.push(
          `${game.phase === "completed" ? "/results" : "/g"}/${game.game_id}`,
        );
      }
    } catch {
      if (!controller.signal.aborted)
        setNotice(
          "Couldn’t open another attempt. Retry safely while the invitation is active.",
        );
    } finally {
      lock.current = false;
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  const outcomes = Array.from(
    new Map(
      [...(results?.outcomes ?? []), ...older].map((row) => [
        row.attempt_id,
        row,
      ]),
    ).values(),
  );
  if (results?.status === "not_shared") return null;
  return (
    <section
      className="duel-verdict"
      aria-labelledby="duel-verdict-title"
      data-testid="duel-verdict"
    >
      <p className="eyebrow">THE GROUP CHAT HAS ENTERED THE ARENA</p>
      <h2 id="duel-verdict-title">
        {results?.status === "retired"
          ? "THIS POKE IS RETIRED."
          : outcomes.length
            ? "THE VERDICT IS IN."
            : "BRAGGING RIGHTS: PENDING."}
      </h2>
      <div role="status" aria-live="polite" aria-atomic="true">
        {outcomes.map((duel) => {
          const creator = duel.creator_name ?? "Mystery player";
          const guest = duel.challenger_name ?? "Their friend";
          return (
            <article className="duel-outcome" key={duel.attempt_id}>
              <p className="mono-label">ATTEMPT {duel.attempt_number}</p>
              <h3>
                {duel.outcome === "tie"
                  ? "A TIE. THE AUDACITY IS MUTUAL."
                  : "HOORAY. SOMEONE’S INSUFFERABLE NOW."}
              </h3>
              <p>
                {duel.outcome === "tie"
                  ? `${creator} and ${guest} tied. Two egos. Zero closure.`
                  : duel.outcome === "creator"
                    ? `${creator} conquered the duel. The confidence was annoyingly justified.`
                    : `${creator} poked ${guest}. ${guest} poked back. Plot twist: the invite came with consequences.`}
              </p>
              <p className="duel-scoreline">
                <strong>
                  {creator}: {duel.creator_score}/5
                </strong>
                <span aria-hidden="true"> / </span>
                <strong>
                  {guest}: {duel.challenger_score}/5
                </strong>
              </p>
            </article>
          );
        })}
      </div>
      {!outcomes.length && !notice && (
        <p>
          {results?.status === "retired"
            ? "This invitation no longer accepts plays."
            : results
              ? "When a friend finishes, their verdict lands here automatically while this page is open."
              : "Checking the shared scoreboard…"}
        </p>
      )}
      {(older.length ? next : results?.next_cursor) && (
        <Button variant="secondary" pending={busy} onClick={() => void more()}>
          Older attempts
        </Button>
      )}
      {fixed && results?.status === "active" && results.replay_slug && (
        <Button
          variant="secondary"
          pending={busy}
          onClick={() => void replay()}
        >
          Play these five again ↗
        </Button>
      )}
      {notice && (
        <>
          <p role="status">{notice}</p>
          <button
            className="inline-link"
            onClick={() => setAttempt((n) => n + 1)}
          >
            Check again
          </button>
        </>
      )}
      <p className="ticket-fine-print">
        Every attempt keeps its own score. Replays use known answers; this is
        casual play, not a ranking of your taste. Results close 10 minutes after
        all started attempts finish, or after an hour without activity.
      </p>
    </section>
  );
}
