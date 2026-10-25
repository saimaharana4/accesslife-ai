import type { ReactNode } from "react";

export type StatusPanelProps = {
  title: string;
  eyebrow?: string;
  children?: ReactNode;
  actions?: ReactNode;
  tone?: "neutral" | "pending" | "warning" | "error";
  live?: "off" | "polite" | "assertive";
  headingLevel?: 1 | 2;
  titleId?: string;
};

/** Presentation only: callers own state changes, retry behavior and factual copy. */
export function StatusPanel({
  title,
  eyebrow,
  children,
  actions,
  tone = "neutral",
  live = "off",
  headingLevel = 2,
  titleId,
}: StatusPanelProps) {
  const Heading = headingLevel === 1 ? "h1" : "h2";
  return (
    <section
      className="state-panel"
      data-tone={tone}
      aria-labelledby={titleId}
      aria-label={titleId ? undefined : title}
      aria-live={live}
      aria-atomic={live === "off" ? undefined : true}
    >
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <div
        className={tone === "error" ? "state-error-mark" : "loading-orbit"}
        aria-hidden="true"
      >
        {tone === "error" ? "↗" : "✳"}
      </div>
      <Heading id={titleId}>{title}</Heading>
      {children}
      {actions && <div className="state-actions">{actions}</div>}
    </section>
  );
}
