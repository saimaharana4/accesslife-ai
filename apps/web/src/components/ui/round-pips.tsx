export type RoundPipsProps = {
  /** One-based active round; zero represents a not-yet-started game. */
  current: number;
  total?: number;
  completed?: number;
  label?: string;
};

export function RoundPips({
  current,
  total = 5,
  completed = Math.max(0, current - 1),
  label,
}: RoundPipsProps) {
  if (
    !Number.isInteger(total) ||
    total < 1 ||
    total > 100 ||
    !Number.isInteger(current) ||
    current < 0 ||
    current > total ||
    !Number.isInteger(completed) ||
    completed < 0 ||
    completed > current
  ) {
    throw new RangeError("Round progress must use bounded integer ordinals.");
  }
  const progressLabel =
    label ??
    (completed === total
      ? `${total} of ${total} rounds completed`
      : current === 0
        ? `Not started, ${total} rounds`
        : `Round ${current} of ${total}`);

  return (
    <div className="round-pips" role="group" aria-label={progressLabel}>
      {Array.from({ length: total }, (_, index) => {
        const ordinal = index + 1;
        const state =
          ordinal <= completed
            ? " is-complete"
            : ordinal === current
              ? " is-current"
              : "";
        return (
          <span
            key={ordinal}
            className={`round-pip${state}`}
            aria-hidden="true"
          />
        );
      })}
      <span aria-hidden="true">
        {String(current).padStart(2, "0")} / {String(total).padStart(2, "0")}
      </span>
    </div>
  );
}
