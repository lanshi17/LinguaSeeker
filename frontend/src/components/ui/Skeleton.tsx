import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  /** Geometric preset. Defaults to a soft text line. */
  variant?: "text" | "line" | "circle" | "block" | "pill";
  /** Width override (Tailwind class or arbitrary value). */
  width?: string;
  /** Height override (Tailwind class or arbitrary value). */
  height?: string;
}

const variantStyles: Record<NonNullable<SkeletonProps["variant"]>, string> = {
  text: "h-3 w-full rounded",
  line: "h-2 w-3/4 rounded",
  circle: "h-10 w-10 rounded-full",
  block: "h-24 w-full rounded-md",
  pill: "h-6 w-20 rounded-full",
};

/**
 * Animated placeholder block. Uses a slow shimmer gradient (1.6s) so the user
 * perceives movement as progress, not a frozen screen.
 */
export function Skeleton({
  variant = "text",
  width,
  height,
  className,
  style,
  ...props
}: SkeletonProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={cn(
        "skeleton-shimmer",
        variantStyles[variant],
        width,
        height,
        className,
      )}
      style={style}
      {...props}
    />
  );
}
