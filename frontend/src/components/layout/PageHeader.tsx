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
        <Typography.Title level={3} style={{ margin: 0 }}>
          {title}
        </Typography.Title>
        {description && (
          <Typography.Text type="secondary" style={{ marginTop: 4, display: "block", fontSize: 14 }}>
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
