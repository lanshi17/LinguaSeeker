import { Tour, type TourProps } from "antd";
import { useI18n } from "@/lib/i18n";

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

/** Reset guide state so it shows again on next visit. */
export function resetGuide(): void {
  document.cookie = `${GUIDE_COOKIE}=; Max-Age=0; Path=/`;
}

/* ── Step keys (i18n) ─────────────────────────────────────────── */

type StepKey = { titleKey: string; descKey: string };

const STEP_KEYS: StepKey[] = [
  { titleKey: "guide.welcome", descKey: "guide.welcomeDesc" },
  { titleKey: "guide.chat", descKey: "guide.chatDesc" },
  { titleKey: "guide.tasks", descKey: "guide.tasksDesc" },
  { titleKey: "guide.evidenceDb", descKey: "guide.evidenceDbDesc" },
  { titleKey: "guide.audit", descKey: "guide.auditDesc" },
  { titleKey: "guide.getStarted", descKey: "guide.getStartedDesc" },
];

const TARGETS = [
  '[data-tour="brand"]',
  '[data-tour="nav-chat"]',
  '[data-tour="nav-pipeline"]',
  '[data-tour="nav-evidence-db"]',
  '[data-tour="nav-audit"]',
  '[data-tour="help-btn"]',
] as const;

function buildSteps(t: (key: string) => string): NonNullable<TourProps["steps"]> {
  return STEP_KEYS.map((s, i) => ({
    title: t(s.titleKey),
    description: t(s.descKey),
    target: () => document.querySelector(TARGETS[i]) as HTMLElement,
    placement: "right" as const,
  }));
}

/* ── Component ─────────────────────────────────────────────────── */

interface UserGuideProps {
  open: boolean;
  onClose: () => void;
}

export function UserGuide({ open, onClose }: UserGuideProps) {
  const { t } = useI18n();

  const handleComplete = () => {
    document.cookie = `${GUIDE_COOKIE}=1; Max-Age=${GUIDE_MAX_AGE}; Path=/; SameSite=Lax`;
    onClose();
  };

  return (
    <Tour
      open={open}
      onClose={handleComplete}
      steps={buildSteps(t)}
      indicatorsRender={(current, total) => (
        <span style={{ color: "var(--color-primary-600)", fontWeight: 600, fontSize: 13 }}>
          {current + 1} / {total}
        </span>
      )}
    />
  );
}
