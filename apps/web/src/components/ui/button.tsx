"use client";
import { Button as AriaButton, type ButtonProps } from "react-aria-components";
export function Button({ className = "", ...props }: ButtonProps) {
  return <AriaButton {...props} className={`button ${className}`} />;
}
