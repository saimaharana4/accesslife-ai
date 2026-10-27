"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ActionLink, Button } from "@/components/ui/button";
import { StatusPanel } from "@/components/ui/status-panel";
import { api, ApiError, ensureSession } from "@/lib/api/client";
import type { ApiSchemas } from "@/lib/api/contracts";
import { subscribeSessionChanges } from "@/lib/api/session-events";
import { challengeRequestKey } from "./challenge-share";

export function LiveInvitation({ slug }: { slug: string }) {
  const router = useRouter();
  const [invitation, setInvitation] = useState<
    ApiSchemas["ChallengeInvitationPublic"] | null
  >(null);
  const [status, setStatus] = useState<
    "loading" | "ready" | "expired" | "revoked" | "missing" | "error"
  >("loading");
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const key = useRef<string | null>(null);
  const lock = useRef(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setStatus("loading");
    setInvitation(null);
    void api
      .get<ApiSchemas["ChallengeInvitationPublic"]>(
        `/challenges/${slug}`,
        controller.signal,
      )
      .then((value) => {
        if (!controller.signal.aborted) {
          setInvitation(value);
          setStatus("ready");
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setStatus(
            error instanceof ApiError && error.status === 410
              ? error.code === "CHALLENGE_REVOKED"
                ? "revoked"
                : "expired"
              : error instanceof ApiError && error.status === 404
                ? "missing"
                : "error",
          );
      });
    return () => controller.abort();
  }, [slug, attempt]);
  useEffect(() => {
    const refresh = () => {
      if (!document.hidden && !lock.current) setAttempt((value) => value + 1);
    };
    window.addEventListener("online", refresh);
    window.addEventListener("focus", refresh);
    const unsubscribe = subscribeSessionChanges((kind) => {
      if (kind === "session-cleared") {
        request.current?.abort();
        key.current = null;
        lock.current = false;
        setBusy(false);
        setNotice(
          "Your session was cleared. Start a new guest replay if this invitation is still available.",
        );
        refresh();
      }
    });
    return () => {
      window.removeEventListener("online", refresh);
      window.removeEventListener("focus", refresh);
      unsubscribe();
      request.current?.abort();
    };
  }, []);
  async function play() {
    if (lock.current || !invitation) return;
    lock.current = true;
    setBusy(true);
    setNotice("");
    const controller = new AbortController();
    request.current = controller;
    key.current ??= challengeRequestKey(`tasteduel:challenge-play:v1:${slug}`);
    try {
      await ensureSession(controller.signal);
      const game = await api.post<ApiSchemas["GamePublic"]>(
        `/challenges/${slug}/plays`,
        {},
        key.current,
        controller.signal,
      );
      if (!controller.signal.aborted) router.push(`/g/${game.game_id}`);
    } catch (error) {
      if (!controller.signal.aborted) {
        if (error instanceof ApiError && error.status === 410) {
          setStatus(error.code === "CHALLENGE_REVOKED" ? "revoked" : "expired");
          setInvitation(null);
        } else
          setNotice(
            "The replay response was interrupted or unavailable. Retry to recover the same game.",
          );
      }
    } finally {
      if (request.current === controller) {
        lock.current = false;
        setBusy(false);
      }
    }
  }
  if (!invitation || status !== "ready") {
    const title = {
      loading: "Opening the invitation.",
      expired: "THIS FIVE HAS EXPIRED.",
      revoked: "THIS LINK IS RETIRED.",
      missing: "INVITATION NOT FOUND.",
      error: "INVITATION UNAVAILABLE.",
      ready: "INVITATION UNAVAILABLE.",
    }[status];
    return (
      <StatusPanel
        live="polite"
        headingLevel={1}
        title={title}
        eyebrow="TASTE DUEL · FRIEND CHALLENGE"
        tone={status === "loading" ? "pending" : "warning"}
        actions={
          <>
            <ActionLink href="/">Start a new solo duel</ActionLink>
            {status === "error" && (
              <Button
                variant="secondary"
                onClick={() => setAttempt((value) => value + 1)}
              >
                Retry invitation
              </Button>
            )}
          </>
        }
      >
        <p>
          {status === "loading"
            ? "Checking the frozen invitation. No answers are being fetched."
            : status === "expired"
              ? "Its evidence is no longer available for play. This invitation cannot silently become a different challenge."
              : status === "revoked"
                ? "The creator's guest session or this challenge has been revoked. Existing backups follow their retention policy."
                : "This link cannot be opened now. Start fresh without changing any historic scores."}
        </p>
      </StatusPanel>
    );
  }
  return (
    <section className="challenge-page" aria-labelledby="challenge-title">
      <div className="challenge-ticket" data-testid="challenge-invitation">
        <p className="eyebrow">AN OPEN INVITATION TO A CULTURE CLASH</p>
        <div className="challenge-mark" aria-hidden="true">
          ✳
        </div>
        <h1 id="challenge-title" className="challenge-title">
          SAME FIVE.
          <br />
          <span className="text-accent">YOUR PREDICTIONS.</span>
        </h1>
        <p className="challenge-summary">
          The favourite: <strong>{invitation.seed.name}.</strong>
          <br />
          Creator's prediction score:{" "}
          <strong>{invitation.creator_score} out of 5.</strong>
        </p>
        <div className="challenge-rules">
          <span>FIVE FROZEN ROUNDS</span>
          <span aria-hidden="true">/</span>
          <span>SAME SIDES</span>
          <span aria-hidden="true">/</span>
          <span>NO TIMER</span>
        </div>
        <p className="invitation-source">
          {invitation.source === "qloo"
            ? "Qloo supplies the frozen cultural answers. Your predictions are your own."
            : "Synthetic fixture challenge. No live Qloo evidence or real cultural ranking."}
        </p>
        <div className="state-actions">
          <Button
            onClick={() => void play()}
            pending={busy}
            pendingLabel="Opening your replay…"
          >
            Play these five <span aria-hidden="true">↗</span>
          </Button>
          <ActionLink href="/" variant="secondary">
            Choose my own favourite
          </ActionLink>
        </div>
        <p role="status" aria-live="polite" className="share-notice">
          {notice}
        </p>
        <p className="ticket-fine-print">
          Available until {new Date(invitation.expires_at).toLocaleString()}.
          Earlier revocation is possible. No account required.
        </p>
      </div>
      <aside className="challenge-aside">
        <p className="mono-label">
          ONE SHARED JOURNEY. TWO INDEPENDENT SCORES.
        </p>
        <p>
          Exactly the creator's played comparisons, order and sides. Your replay
          does not adapt or ask Qloo for a new answer.
        </p>
        <p>
          Correct predictions measure game performance, not personal taste.
          Casual play allows prior knowledge, research and repeated attempts.
        </p>
        <ActionLink href="/how-it-works" variant="quiet">
          What are we predicting? <span aria-hidden="true">↗</span>
        </ActionLink>
      </aside>
    </section>
  );
}
