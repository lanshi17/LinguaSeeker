import { Tour, type TourProps } from "antd";
import { useI18n } from "@/lib/i18n";
import { markGuideSeen } from "./userGuideState";

/* ── Step keys (i18n) ─────────────────────────────────────────── */

type StepKey = { titleKey: string; descKey: string };

const STEP_KEYS: StepKey[] = [
  { titleKey: "guide.welcome", descKey: "guide.welcomeDesc" },
  { titleKey: "guide.evidenceDb", descKey: "guide.evidenceDbDesc" },
  { titleKey: "guide.chat", descKey: "guide.chatDesc" },
  { titleKey: "guide.tasks", descKey: "guide.tasksDesc" },
  { titleKey: "guide.audit", descKey: "guide.auditDesc" },
  { titleKey: "guide.getStarted", descKey: "guide.getStartedDesc" },
];

const TARGETS = [
  '[data-tour="brand"]',
  '[data-tour="nav-evidence-db"]',
  '[data-tour="nav-chat"]',
  '[data-tour="nav-pipeline"]',
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
    markGuideSeen();
    onClose();
  };

  return (
    <Tour
      open={open}
      onClose={handleComplete}
      mask={false}
      steps={buildSteps(t)}
      indicatorsRender={(current, total) => (
        <span style={{ color: "var(--color-primary-600)", fontWeight: 600, fontSize: 13 }}>
          {current + 1} / {total}
        </span>
      )}
    />
  );
}
