"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api/client";
import type { ApiSchemas } from "@/lib/api/contracts";
import {
  publishSessionChange,
  subscribeSessionChanges,
} from "@/lib/api/session-events";

export function NameGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [status, setStatus] = useState<"checking" | "ask" | "ready" | "error">(
    "checking",
  );
  const [name, setName] = useState("");
  const [inviter, setInviter] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [closed, setClosed] = useState(false);
  const [invitationCheck, setInvitationCheck] = useState<{
    slug: string;
    valid: boolean;
  } | null>(null);
  const bootstrap = useRef<string | null>(null);
  const epoch = useRef(0);
  const request = useRef<AbortController | null>(null);
  const expiry = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const lock = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const challenge = /^\/c\/([A-Za-z0-9_-]{22,80})$/.exec(pathname)?.[1];
  const about = pathname === "/how-it-works";

  function accept(session: ApiSchemas["SessionPublic"]) {
    clearTimeout(expiry.current);
    const remaining = Date.parse(session.expires_at) - Date.now();
    if (remaining <= 0) {
      setStatus("ask");
      return;
    }
    setStatus(session.display_name ? "ready" : "ask");
    expiry.current = setTimeout(
      () => setAttempt((n) => n + 1),
      Math.min(remaining, 2_147_483_647),
    );
  }

  useEffect(() => {
    const controller = new AbortController();
    const version = epoch.current;
    void api
      .get<ApiSchemas["SessionPublic"]>("/sessions/current", controller.signal)
      .then((session) => {
        if (!controller.signal.aborted && version === epoch.current)
          accept(session);
      })
      .catch((error) => {
        if (!controller.signal.aborted && version === epoch.current) {
          if (error instanceof ApiError && error.status === 401) {
            bootstrap.current = null;
            setName("");
            setStatus("ask");
          } else
            setStatus((previous) =>
              previous === "ready" ? previous : "error",
            );
        }
      });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    setInviter(null);
    if (!challenge) return;
    const controller = new AbortController();
    void api
      .get<ApiSchemas["ChallengeInvitationPublic"]>(
        `/challenges/${challenge}`,
        controller.signal,
      )
      .then((invitation) => {
        if (!controller.signal.aborted) {
          setInviter(invitation.creator_name ?? "A friend");
          setInvitationCheck({ slug: challenge, valid: true });
        }
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setInvitationCheck({ slug: challenge, valid: false });
      });
    return () => controller.abort();
  }, [challenge]);

  useEffect(() => {
    const unsubscribe = subscribeSessionChanges((kind) => {
      if (kind === "session-cleared") {
        epoch.current += 1;
        bootstrap.current = null;
        request.current?.abort();
        clearTimeout(expiry.current);
        setName("");
        setNotice("");
        setBusy(false);
        lock.current = false;
        setStatus("ask");
      } else if (kind === "session-updated") setAttempt((n) => n + 1);
    });
    const refresh = () => {
      if (!document.hidden && !lock.current) setAttempt((n) => n + 1);
    };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      unsubscribe();
      request.current?.abort();
      clearTimeout(expiry.current);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setNotice("");
    const controller = new AbortController();
    request.current = controller;
    const version = ++epoch.current;
    try {
      // This memory-only 256-bit key is credential material; never store it.
      bootstrap.current ??= btoa(
        String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))),
      )
        .replaceAll("+", "-")
        .replaceAll("/", "_")
        .replaceAll("=", "");
      const session = await api.post<ApiSchemas["SessionPublic"]>(
        "/sessions",
        { display_name: name.trim() },
        bootstrap.current,
        controller.signal,
      );
      if (!controller.signal.aborted && version === epoch.current) {
        accept(session);
        publishSessionChange("session-updated");
        requestAnimationFrame(() => {
          const target = document.querySelector<HTMLHeadingElement>("#main h1");
          target?.setAttribute("tabindex", "-1");
          target?.focus();
        });
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        if (error instanceof ApiError && error.code === "PLAY_CLOSED")
          setClosed(true);
        if (error instanceof ApiError && error.status === 401)
          bootstrap.current = null;
        if (error instanceof ApiError && error.status === 409)
          setAttempt((n) => n + 1);
        setNotice(
          error instanceof ApiError && error.status === 422
            ? "Keep it to 1–24 characters, without markup or hidden characters."
            : "Couldn’t save your nickname. Your next move: try again.",
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setBusy(false);
        lock.current = false;
      }
    }
  }

  if (
    about ||
    (challenge && invitationCheck?.slug === challenge && !invitationCheck.valid)
  )
    return children;
  if (closed)
    return (
      <section className="name-entry">
        <div>
          <p className="eyebrow">TASTE DUEL</p>
          <h1>
            PLAY HAS CLOSED
            <br />
            <span className="text-accent">FOR THIS DEMO.</span>
          </h1>
          <p>
            Thanks for bringing your curiosity. Existing games remain subject to
            their session and evidence expiry.
          </p>
          <a href="/how-it-works">How Taste Duel works</a>
        </div>
      </section>
    );
  if (status === "ready" && (!challenge || invitationCheck?.slug === challenge))
    return children;
  if (
    status === "checking" ||
    status === "error" ||
    (challenge && invitationCheck?.slug !== challenge)
  )
    return (
      <section className="name-entry" aria-live="polite">
        <p className="eyebrow">TASTE DUEL · YOUR ENTRANCE</p>
        <h1>
          {status === "error" ? "A LITTLE HOLD-UP." : "SETTING THE STAGE."}
        </h1>
        <p>
          {status === "error"
            ? "Your session couldn’t be checked. Let’s give it another go."
            : "Checking your guest session…"}
        </p>
        {status === "error" && (
          <Button
            onClick={() => {
              setStatus("checking");
              setAttempt((n) => n + 1);
            }}
          >
            Try again
          </Button>
        )}
      </section>
    );
  return (
    <section
      className="name-entry"
      aria-labelledby="name-title"
      data-testid="name-entry"
    >
      <div className="name-entry-copy">
        <p className="eyebrow">
          {inviter ? "YOU’VE BEEN POKED" : "GOOD TASTE. BIG ENTRANCE."}
        </p>
        {inviter && (
          <p className="name-inviter">
            <strong>{inviter}</strong> poked you. Your move.
          </p>
        )}
        <h1 id="name-title" ref={heading} tabIndex={-1}>
          HOW MAY I<br />
          <span className="text-accent">CALL YOU?</span>
        </h1>
        <p>
          Every duel needs a name.
          <br />A nickname is plenty. The confidence? Optional.
        </p>
        <form className="name-form" onSubmit={(event) => void submit(event)}>
          <label htmlFor="nickname">Your nickname</label>
          <input
            id="nickname"
            name="nickname"
            autoComplete="nickname"
            placeholder="Your main-character name"
            required
            maxLength={96}
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-describedby="nickname-help nickname-notice"
            disabled={busy}
          />
          <p id="nickname-help" className="seed-help">
            Up to 24 characters. Friends see this name on challenges and
            results. It expires with your guest session.
          </p>
          <Button
            type="submit"
            pending={busy}
            pendingLabel="Making your entrance…"
            disabled={
              !name.trim() ||
              [...name.normalize("NFKC").trim().replace(/\s+/g, " ")].length >
                24
            }
          >
            Let’s go <span aria-hidden="true">↗</span>
          </Button>
          <p id="nickname-notice" role="status">
            {notice}
          </p>
        </form>
      </div>
      <div className="name-entry-art" aria-hidden="true">
        <span className="name-orbit">✳</span>
        <p>
          SMALL TALK.
          <br />
          <span>BIG DUEL.</span>
        </p>
        <span className="mono-label">NO ACCOUNT. JUST A LITTLE AUDACITY.</span>
      </div>
    </section>
  );
}
