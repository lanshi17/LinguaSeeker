import { cn } from "@/lib/utils/cn";

interface SpinnerProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

const sizeStyles = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-10 w-10",
};

export function Spinner({ className, size = "md" }: SpinnerProps) {
  return (
    <svg
      className={cn("animate-spin text-primary-600", sizeStyles[size], className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-label="Loading"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}
