import test from "node:test";
import assert from "node:assert/strict";
import { createControlledAcceptance } from "./controlled-acceptance.mjs";

test("reload barrier waits for delayed route registration and accepted commit, not old network-idle", async () => {
  const barrier = createControlledAcceptance();
  let settled = false,
    committed = false,
    commit;
  const waiting = barrier.wait("answer").then(() => {
    assert.equal(committed, true);
    settled = true;
  });
  await Promise.resolve(); // Browser's previously reached network-idle resolves immediately.
  assert.equal(settled, false);
  const work = new Promise((resolve) => {
    commit = resolve;
  });
  barrier.track("answer", "synthetic-answer-key-0001", work);
  await Promise.resolve();
  assert.equal(settled, false);
  committed = true;
  commit();
  await waiting;
  assert.equal(settled, true);
});

test("answer acceptance never releases an unconfirmed explicit advance", async () => {
  const barrier = createControlledAcceptance();
  let advanceDone = false,
    finish;
  barrier.track("answer", "synthetic-answer-key-0001", Promise.resolve());
  const advance = barrier.wait("advance").then(() => {
    advanceDone = true;
  });
  await barrier.wait("answer");
  assert.equal(advanceDone, false);
  barrier.track(
    "advance",
    "synthetic-advance-key-0001",
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  assert.equal(advanceDone, false);
  finish();
  await advance;
});

test("failed acceptance rejects even when failure precedes wait and private diagnostics stay redacted", async () => {
  const barrier = createControlledAcceptance();
  barrier.track(
    "answer",
    "synthetic-answer-key-0001",
    Promise.reject(new Error("SYNTHETIC_PRIVATE_DIAGNOSTICS")),
  );
  await Promise.resolve();
  await assert.rejects(
    barrier.wait("answer"),
    (error) =>
      /acceptance failed/.test(error.message) &&
      !error.message.includes("SYNTHETIC_PRIVATE"),
  );
});

test("missing acceptance has a finite deadline that repeated waits cannot extend", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "Date"], now: 0 });
  const barrier = createControlledAcceptance(100);
  const waiting = assert.rejects(barrier.wait("answer"), /deadline exceeded/);
  t.mock.timers.tick(100);
  await waiting;
  await assert.rejects(barrier.wait("answer"), /deadline exceeded/);
});

test("duplicate registration, changed identity and non-promise acknowledgements fail closed", async () => {
  const barrier = createControlledAcceptance();
  barrier.track("answer", "synthetic-answer-key-0001", Promise.resolve());
  assert.throws(() =>
    barrier.track("answer", "synthetic-changed-key-0001", Promise.resolve()),
  );
  assert.throws(() => barrier.track("advance", "short", Promise.resolve()));
  assert.throws(() =>
    barrier.track("advance", "synthetic-advance-key-0001", undefined),
  );
  assert.throws(() =>
    barrier.track("other", "synthetic-other-key-0001", Promise.resolve()),
  );
  await barrier.wait("answer");
});
