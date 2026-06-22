import { type HTMLAttributes } from "react";

interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "text" | "line" | "circle" | "block" | "pill";
  width?: string | number;
  height?: string | number;
}

const variantStyles: Record<NonNullable<SkeletonProps["variant"]>, React.CSSProperties> = {
  text: { height: 12, width: "100%", borderRadius: 4 },
  line: { height: 8, width: "75%", borderRadius: 4 },
  circle: { height: 40, width: 40, borderRadius: "50%" },
  block: { height: 96, width: "100%", borderRadius: 8 },
  pill: { height: 24, width: 80, borderRadius: 9999 },
};

export function Skeleton({
  variant = "text",
  width,
  height,
  className,
  style,
  ...props
}: SkeletonProps) {
  const baseStyle = variantStyles[variant];

  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={["skeleton-shimmer", className].filter(Boolean).join(" ")}
      style={{
        ...baseStyle,
        ...(width != null ? { width } : {}),
        ...(height != null ? { height } : {}),
        ...style,
      }}
      {...props}
    />
  );
}
