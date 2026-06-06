/**
 * Merge Tailwind class names with conflict resolution.
 *
 * Uses clsx for conditional class joining and tailwind-merge
 * to resolve conflicting Tailwind utilities (e.g., px-4 vs px-2).
 *
 * Usage: cn("px-4 py-2", isActive && "bg-primary-600", className)
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
