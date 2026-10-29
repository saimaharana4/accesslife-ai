"use client";

import { useEffect, useRef, useState } from "react";
import { ActionLink, Button } from "@/components/ui/button";
import { api, ApiError, createKey } from "@/lib/api/client";
import type { ApiSchemas } from "@/lib/api/contracts";
import { subscribeSessionChanges } from "@/lib/api/session-events";

function requestKey(storage: string) {
  try {
    const saved = sessionStorage.getItem(storage);
    if (saved && /^[A-Za-z0-9_-]{16,128}$/.test(saved)) return saved;
    const next = createKey();
    sessionStorage.setItem(storage, next);
    return next;
  } catch {
    return createKey();
  }
}

/** Persist only a retry key, never an answer, session token or private pool. */
export function ChallengeShare({
  gameId,
  canonicalOrigin,
  source,
}: {
  gameId: string;
  canonicalOrigin: string | null;
  source: ApiSchemas["RankingSource"];
}) {
  const [created, setCreated] = useState<
    ApiSchemas["ChallengeCreatedPublic"] | null
  >(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [manual, setManual] = useState(false);
  const [retired, setRetired] = useState(false);
  const manualInput = useRef<HTMLInputElement>(null);
  const key = useRef<string | null>(null);
  const locked = useRef(false);
  const epoch = useRef(0);
  useEffect(() => {
    if (manual) manualInput.current?.focus();
  }, [manual]);
  useEffect(
    () =>
      subscribeSessionChanges((kind) => {
        if (kind === "session-cleared") {
          epoch.current += 1;
          key.current = null;
          setCreated(null);
          setRetired(true);
          setNotice("Session cleared. Its challenge links are revoked.");
        }
      }),
    [],
  );
  const url =
    created && canonicalOrigin
      ? `${canonicalOrigin}/c/${created.invitation.slug}`
      : null;
  async function create() {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setNotice("");
    const version = epoch.current;
    key.current ??= requestKey(`tasteduel:challenge-create:v1:${gameId}`);
    try {
      const saved = await api.post<ApiSchemas["ChallengeCreatedPublic"]>(
        "/challenges",
        { game_id: gameId },
        key.current,
      );
      if (version === epoch.current) {
        setCreated(saved);
        window.dispatchEvent(new Event("tasteduel:challenge-ready"));
        setNotice("Challenge ready. The same five comparisons are frozen.");
      }
    } catch (error) {
      if (version === epoch.current)
        setNotice(
          error instanceof ApiError && error.status === 410
            ? "This game's evidence has expired. Play a new solo duel to create a challenge."
            : "The challenge response was interrupted or unavailable. Retry safely to recover the same invitation.",
        );
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setNotice("Challenge link copied.");
    } catch {
      setManual(true);
      setNotice("Copy is unavailable here. Select and copy the link below.");
    }
  }
  async function share() {
    if (!url) return;
    if (!navigator.share) {
      await copy();
      return;
    }
    try {
      await navigator.share({
        title: "Taste Duel — you’ve been poked",
        text: `${created?.invitation.creator_name ?? "A friend"} poked you. Same five rounds. Think you can beat ${created?.invitation.creator_score ?? "their"}/5? Your move.`,
        url,
      });
      setNotice("Share sheet opened. Sending is your choice.");
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setManual(true);
        setNotice("Sharing is unavailable. Copy the link below.");
      }
    }
  }
  async function revoke() {
    if (!created || locked.current) return;
    locked.current = true;
    setBusy(true);
    const version = epoch.current;
    try {
      await api.delete(`/challenges/${created.invitation.slug}`);
      if (version === epoch.current) {
        setCreated(null);
        setRetired(true);
        setNotice(
          "Challenge link retired. Previously downloaded social previews cannot be recalled.",
        );
      }
    } catch {
      if (version === epoch.current)
        setNotice(
          "Retirement could not be confirmed. Retry retiring the same link safely.",
        );
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  return (
    <section
      className="challenge-share"
      aria-labelledby="share-title"
      data-testid="challenge-share"
    >
      <p className="eyebrow">PASS THE CULTURE CLASH ON</p>
      <h2 id="share-title">POKE THE GROUP CHAT.</h2>
      <p>
        Freeze your actual rounds, order and sides. Your friend gets their own
        score against the{" "}
        {source === "qloo"
          ? "same Qloo answers."
          : "same synthetic fixture answers. No live Qloo."}
      </p>
      {!created && !retired ? (
        <Button
          onClick={() => void create()}
          pending={busy}
          pendingLabel="Freezing your five…"
          disabled={!canonicalOrigin}
        >
          Poke a friend <span aria-hidden="true">↗</span>
        </Button>
      ) : created ? (
        <>
          <div className="state-actions">
            <Button onClick={() => void share()}>
              Share the poke <span aria-hidden="true">↗</span>
            </Button>
            <Button variant="secondary" onClick={() => void copy()}>
              Copy challenge link
            </Button>
            <ActionLink href={`/c/${created.invitation.slug}`} variant="quiet">
              View invitation
            </ActionLink>
          </div>
          <p className="ticket-fine-print">
            Expires {new Date(created.invitation.expires_at).toLocaleString()}.
            Clearing the creator's session revokes this link.
          </p>
          {url && (
            <label className="share-link-field" hidden={!manual}>
              Challenge link
              <input
                value={url}
                readOnly
                ref={manualInput}
                onFocus={(event) => event.currentTarget.select()}
              />
            </label>
          )}
          <details className="retire-challenge">
            <summary>Retire this challenge link</summary>
            <p>
              This stops future access and play. Existing backups and downloaded
              previews follow their own retention.
            </p>
            <Button
              variant="secondary"
              pending={busy}
              pendingLabel="Retiring link…"
              onClick={() => void revoke()}
            >
              Confirm retire link
            </Button>
          </details>
        </>
      ) : null}
      {!canonicalOrigin && (
        <p className="ticket-fine-print">
          Sharing needs the configured public application origin. No production
          domain has been assumed.
        </p>
      )}
      <p role="status" aria-live="polite" className="share-notice">
        {notice}
      </p>
      <p className="ticket-fine-print">
        Casual play, not a cheat-proof competition. Prior knowledge, research
        and repeated attempts exist. No global leaderboard.
      </p>
    </section>
  );
}

export { requestKey as challengeRequestKey };
