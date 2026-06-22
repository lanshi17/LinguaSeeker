import { type HTMLAttributes, forwardRef } from "react";
import { Card as AntdCard } from "antd";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Remove default padding. */
  noPadding?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ noPadding = false, className, children, style, ...props }, ref) => {
    return (
      <div ref={ref} className={className} style={style} {...props}>
        <AntdCard
          styles={{
            body: noPadding ? { padding: 0 } : undefined,
          }}
          style={{ width: "100%" }}
        >
          {children}
        </AntdCard>
      </div>
    );
  },
);

Card.displayName = "Card";
