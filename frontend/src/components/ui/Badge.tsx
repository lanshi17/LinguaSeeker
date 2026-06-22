import { type HTMLAttributes } from "react";
import { Tag } from "antd";

type BadgeVariant = "default" | "success" | "warning" | "error" | "info";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantMap: Record<BadgeVariant, string> = {
  default: "default",
  success: "success",
  warning: "warning",
  error: "error",
  info: "processing",
};

export function Badge({
  variant = "default",
  className,
  children,
  style,
  ...props
}: BadgeProps) {
  return (
    <Tag
      color={variantMap[variant]}
      className={className}
      style={{ borderRadius: 9999, ...style }}
      {...props}
    >
      {children}
    </Tag>
  );
}
