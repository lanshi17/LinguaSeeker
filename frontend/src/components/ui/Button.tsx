
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Button as AntdButton, type ButtonProps as AntdButtonProps } from "antd";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const variantMap: Record<ButtonVariant, { type: AntdButtonProps["type"]; danger?: boolean }> = {
  primary: { type: "primary" },
  secondary: { type: "default" },
  ghost: { type: "text" },
  danger: { type: "primary", danger: true },
};

const sizeMap: Record<ButtonSize, AntdButtonProps["size"]> = {
  sm: "small",
  md: "middle",
  lg: "large",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      className,
      children,
      type: htmlType,
      color: _htmlColor,
      ...rest
    },
    ref,
  ) => {
    const { type, danger } = variantMap[variant];

    return (
      <AntdButton
        ref={ref}
        type={type}
        danger={danger}
        htmlType={htmlType}
        size={sizeMap[size]}
        loading={loading}
        disabled={disabled}
        className={className}
        {...rest}
      >
        {children}
      </AntdButton>
    );
  },
);

Button.displayName = "Button";
