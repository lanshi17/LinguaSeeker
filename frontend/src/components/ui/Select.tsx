import { forwardRef, type HTMLAttributes } from "react";
import { Select as AntdSelect } from "antd";

interface SelectOption {
  label: string;
  value: string;
}

interface SelectProps extends Omit<HTMLAttributes<HTMLDivElement>, "onChange"> {
  label?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  disabled?: boolean;
}

export const Select = forwardRef<HTMLDivElement, SelectProps>(
  ({ label, error, options, placeholder, className, id, style, value, onChange, disabled, ...props }, ref) => {
    const selectId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div ref={ref} style={{ width: "100%" }} {...props}>
        {label && (
          <label
            htmlFor={selectId}
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
        <AntdSelect
          id={selectId}
          options={options}
          placeholder={placeholder}
          status={error ? "error" : undefined}
          className={className}
          style={{ width: "100%", ...style }}
          value={value}
          onChange={onChange}
          disabled={disabled}
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

Select.displayName = "Select";
