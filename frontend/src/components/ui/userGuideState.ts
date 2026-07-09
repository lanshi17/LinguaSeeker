const GUIDE_COOKIE = "ls_guide_seen";
const GUIDE_MAX_AGE = 365 * 24 * 60 * 60; // 1 year in seconds

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/** Check if the user has completed the guide before. */
export function hasSeenGuide(): boolean {
  return getCookie(GUIDE_COOKIE) === "1";
}

/** Mark the guide as completed for the current browser. */
export function markGuideSeen(): void {
  document.cookie = `${GUIDE_COOKIE}=1; Max-Age=${GUIDE_MAX_AGE}; Path=/; SameSite=Lax`;
}

/** Reset guide state so it shows again on next visit. */
export function resetGuide(): void {
  document.cookie = `${GUIDE_COOKIE}=; Max-Age=0; Path=/`;
}
