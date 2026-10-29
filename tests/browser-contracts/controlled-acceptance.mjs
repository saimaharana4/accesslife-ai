/** Test-only barrier: browser network-idle is not proof of a routed mutation's commit. */
export function createControlledAcceptance(timeoutMs = 25_000) {
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000)
    throw new Error("Invalid controlled acceptance deadline");
  const slots = new Map();
  for (const kind of ["answer", "advance"]) {
    let resolve, reject;
    const completion = new Promise((yes, no) => {
      resolve = yes;
      reject = no;
    });
    // A routed failure can precede the waiting caller. Preserve its rejection
    // without allowing an unhandled rejection to bypass the test's assertion.
    completion.catch(() => {});
    slots.set(kind, {
      completion,
      resolve,
      reject,
      registered: false,
      deadline: null,
    });
  }
  function slot(kind) {
    if (!slots.has(kind)) throw new Error("Invalid controlled mutation kind");
    return slots.get(kind);
  }
  return {
    track(kind, key, work) {
      const current = slot(kind);
      if (
        current.registered ||
        typeof key !== "string" ||
        !/^[A-Za-z0-9_-]{16,128}$/.test(key) ||
        !(work instanceof Promise)
      )
        throw new Error("One exact controlled mutation identity is required");
      current.registered = true;
      Promise.resolve(work).then(
        () => current.resolve(),
        () =>
          current.reject(
            new Error(
              `Controlled ${kind} acceptance failed; diagnostics redacted`,
            ),
          ),
      );
    },
    async wait(kind) {
      const current = slot(kind);
      current.deadline ??= Date.now() + timeoutMs;
      const remaining = current.deadline - Date.now();
      if (remaining <= 0)
        throw new Error(`Controlled ${kind} acceptance deadline exceeded`);
      let timer;
      try {
        await Promise.race([
          current.completion,
          new Promise((_, reject) => {
            timer = setTimeout(
              () =>
                reject(
                  new Error(`Controlled ${kind} acceptance deadline exceeded`),
                ),
              remaining,
            );
          }),
        ]);
      } finally {
        clearTimeout(timer);
      }
    },
  };
}
