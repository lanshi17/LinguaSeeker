import { type HTMLAttributes } from "react";

interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  /** Geometric preset. Defaults to a soft text line. */
  variant?: "text" | "line" | "circle" | "block" | "pill";
  /** Width override (CSS value or legacy Tailwind class like "w-20"). */
  width?: string;
  /** Height override (CSS value or legacy Tailwind class like "h-3"). */
  height?: string;
}

const variantStyles: Record<NonNullable<SkeletonProps["variant"]>, React.CSSProperties> = {
  text: { height: 12, width: "100%", borderRadius: 4 },
  line: { height: 8, width: "75%", borderRadius: 4 },
  circle: { height: 40, width: 40, borderRadius: "50%" },
  block: { height: 96, width: "100%", borderRadius: 8 },
  pill: { height: 24, width: 80, borderRadius: 9999 },
};

/** True when the value is a legacy Tailwind utility class (e.g. "w-20", "h-3.5"). */
function isTailwindClass(value: string): boolean {
  return /^[wh]-/.test(value);
}

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
  const baseStyle = variantStyles[variant];

  // Collect any legacy Tailwind classes from width/height props into className.
  const extraClasses: string[] = [];
  const inlineWidth = width && !isTailwindClass(width) ? width : undefined;
  const inlineHeight = height && !isTailwindClass(height) ? height : undefined;
  if (width && isTailwindClass(width)) extraClasses.push(width);
  if (height && isTailwindClass(height)) extraClasses.push(height);

  const combinedClassName = [
    "skeleton-shimmer",
    className,
    ...extraClasses,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={combinedClassName}
      style={{
        ...baseStyle,
        ...(inlineWidth ? { width: inlineWidth } : {}),
        ...(inlineHeight ? { height: inlineHeight } : {}),
        ...style,
      }}
      {...props}
    />
  );
}
