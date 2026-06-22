import { forwardRef, useCallback, type InputHTMLAttributes } from "react";
import { Input as AntdInput, type GetRef } from "antd";

type InputRef = GetRef<typeof AntdInput>;

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className, id, style, size: _htmlSize, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    // Bridge antd's InputRef to expose the native HTMLInputElement.
    const antdRef = useCallback(
      (instance: InputRef | null) => {
        if (typeof ref === "function") {
          ref(instance?.input ?? null);
        } else if (ref) {
          (ref as React.MutableRefObject<HTMLInputElement | null>).current =
            instance?.input ?? null;
        }
      },
      [ref],
    );

    return (
      <div style={{ width: "100%" }}>
        {label && (
          <label
            htmlFor={inputId}
            style={{
              display: "block",
              marginBottom: 6,
              fontSize: 14,
              fontWeight: 500,
              color: "rgba(0, 0, 0, 0.88)",
            }}
          >
            {label}
          </label>
        )}
        <AntdInput
          ref={antdRef}
          id={inputId}
          status={error ? "error" : undefined}
          className={className}
          style={style}
          {...props}
        />
        {error && (
          <p style={{ marginTop: 4, fontSize: 14, color: "#ff4d4f" }}>
            {error}
          </p>
        )}
      </div>
    );
  },
);

Input.displayName = "Input";
