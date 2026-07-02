import type { ReactNode } from "react";
import { Flex, Typography } from "antd";

interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <Flex align="center" justify="space-between" className={className}>
      <div>
        <Typography.Text
          style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--color-text-secondary)",
            display: "block",
            marginBottom: 2,
          }}
        >
          {title}
        </Typography.Text>
        {description && (
          <Typography.Text type="secondary" style={{ display: "block", fontSize: 13 }}>
            {description}
          </Typography.Text>
        )}
      </div>
      {actions && (
        <Flex align="center" gap={12}>
          {actions}
        </Flex>
      )}
    </Flex>
  );
}
