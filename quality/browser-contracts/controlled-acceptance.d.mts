export type ControlledMutationKind = "answer" | "advance";
export function createControlledAcceptance(timeoutMs?: number): {
  track(
    kind: ControlledMutationKind,
    key: string,
    work: Promise<unknown>,
  ): void;
  wait(kind: ControlledMutationKind): Promise<void>;
};
