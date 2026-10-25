import Link from "next/link";
import type { ComponentProps } from "react";

export type ButtonVariant = "primary" | "secondary" | "quiet";

function buttonClasses(variant: ButtonVariant, className?: string) {
  return ["button", `button-${variant}`, className].filter(Boolean).join(" ");
}

export type ButtonProps = ComponentProps<"button"> & {
  variant?: ButtonVariant;
  pending?: boolean;
  pendingLabel?: string;
};

/** Native semantics keep form, keyboard and disabled behavior predictable. */
export function Button({
  variant = "primary",
  pending = false,
  pendingLabel,
  disabled,
  className,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      type={type}
      className={buttonClasses(variant, className)}
      disabled={disabled || pending}
      aria-busy={pending || props["aria-busy"]}
    >
      {pending && pendingLabel ? pendingLabel : children}
    </button>
  );
}

export type ActionLinkProps = ComponentProps<typeof Link> & {
  variant?: ButtonVariant;
};

/** Navigation remains a link; disabled/pending actions should use Button. */
export function ActionLink({
  variant = "primary",
  className,
  children,
  prefetch = false,
  ...props
}: ActionLinkProps) {
  return (
    <Link
      {...props}
      prefetch={prefetch}
      className={buttonClasses(variant, className)}
    >
      {children}
    </Link>
  );
}
