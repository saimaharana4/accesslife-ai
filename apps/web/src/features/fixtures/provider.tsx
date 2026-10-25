"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { fixtureReducer, isBusy, type FixtureEvent } from "./state.ts";
import { InMemoryFixtureTransport, FixtureFailure } from "./transport.ts";
import type {
  FixtureChoice,
  FixtureSeed,
  FixtureState,
  FixtureStory,
  FixtureTransport,
} from "./types.ts";

type FixtureActions = {
  start(seed: FixtureSeed, story?: FixtureStory): void;
  answer(choiceId: string): void;
  advance(): void;
  retry(): void;
  interrupt(): void;
  reset(): void;
  save(choice: FixtureChoice): void;
  showStory(story: "expired" | "interrupted"): void;
};
type FixtureContextValue = { state: FixtureState; actions: FixtureActions };
const FixtureContext = createContext<FixtureContextValue | null>(null);

export function FixtureProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<FixtureState>({ kind: "idle" });
  const current = useRef<FixtureState>(state);
  const transport = useRef<FixtureTransport | null>(null);
  if (!transport.current) transport.current = new InMemoryFixtureTransport();
  const sequence = useRef(0);
  const request = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const commit = useCallback((event: FixtureEvent) => {
    // Synchronous ref update also guards multiple DOM clicks in one React batch.
    const next = fixtureReducer(current.current, event);
    current.current = next;
    if (mounted.current) setState(next);
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      // Strict Mode immediately remounts effects; only cancel a real unmount.
      queueMicrotask(() => {
        if (!mounted.current) {
          request.current?.abort();
          sequence.current += 1;
        }
      });
    };
  }, []);

  const run = useCallback(
    async (pending: FixtureState) => {
      if (!("operation" in pending)) return;
      const controller = new AbortController();
      request.current = controller;
      try {
        if (pending.kind === "preparing")
          commit({
            type: "STARTED",
            operation: pending.operation,
            result: await transport.current!.start(
              pending.seed,
              pending.story,
              pending.key,
              controller.signal,
            ),
          });
        else if (pending.kind === "submitting")
          commit({
            type: "ANSWERED",
            operation: pending.operation,
            answer: await transport.current!.answer(
              pending.game.id,
              pending.round.id,
              pending.choiceId,
              pending.key,
              controller.signal,
            ),
          });
        else if (pending.kind === "advancing")
          commit({
            type: "ADVANCED",
            operation: pending.operation,
            result: await transport.current!.advance(
              pending.game.id,
              pending.round.id,
              pending.key,
              controller.signal,
            ),
          });
      } catch (error) {
        if (!controller.signal.aborted)
          commit({
            type: "ISSUE",
            operation: pending.operation,
            issue: error instanceof FixtureFailure ? error.kind : "retry",
            message:
              error instanceof FixtureFailure
                ? error.message
                : "The local fixture could not finish. Retry the same action.",
          });
      } finally {
        if (request.current === controller) request.current = null;
      }
    },
    [commit],
  );

  const interrupt = useCallback(() => {
    request.current?.abort();
    request.current = null;
    commit({ type: "INTERRUPT" });
  }, [commit]);
  const actions = useMemo<FixtureActions>(
    () => ({
      start(seed, story = "normal") {
        if (isBusy(current.current)) return;
        const operation = ++sequence.current;
        commit({
          type: "START",
          seed,
          story,
          operation,
          key: `fixture-start-${operation}`,
        });
        void run(current.current);
      },
      answer(choiceId) {
        const previous = current.current;
        if (previous.kind !== "unanswered") return;
        commit({
          type: "ANSWER",
          operation: ++sequence.current,
          choiceId,
          key: `${previous.game.id}:${previous.round.id}:answer`,
        });
        if (current.current.kind === "submitting") void run(current.current);
      },
      advance() {
        const previous = current.current;
        if (previous.kind !== "revealed") return;
        commit({
          type: "ADVANCE",
          operation: ++sequence.current,
          key: `${previous.game.id}:${previous.round.id}:advance`,
        });
        void run(current.current);
      },
      retry() {
        if (current.current.kind !== "issue" || !current.current.recovery)
          return;
        commit({ type: "RETRY", operation: ++sequence.current });
        void run(current.current);
      },
      interrupt,
      reset() {
        interrupt();
        commit({ type: "RESET" });
      },
      save(choice) {
        commit({ type: "SAVE", choice });
      },
      showStory(story) {
        interrupt();
        commit({
          type: "STORY",
          issue: story,
          message:
            story === "expired"
              ? "This is the expired-fixture story. No stored game was restored or reranked."
              : "This is the interrupted-fixture story. Refreshing this UI-only build clears all in-memory progress.",
        });
      },
    }),
    [commit, run, interrupt],
  );
  return (
    <FixtureContext.Provider value={{ state, actions }}>
      {children}
    </FixtureContext.Provider>
  );
}

export function useFixture() {
  const context = useContext(FixtureContext);
  if (!context) throw new Error("Fixture entry requires FixtureProvider.");
  return context;
}
