export const STATUS_VARIANT: Record<
  string,
  "default" | "info" | "success" | "error" | "warning"
> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};
