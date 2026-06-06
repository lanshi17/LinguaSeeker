/**
 * Merge Tailwind class names with conflict resolution.
 *
 * Usage: cn("px-4 py-2", isActive && "bg-primary-600", className)
 */

import { type ClassValue, clsx } from "clsx";

export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
