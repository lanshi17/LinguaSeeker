import { useMemo } from "react";
import { useI18n } from "@/lib/i18n";
import type { WelcomeAction } from "./WelcomeBlock";
import { buildFollowUpQuestions } from "../utils/followUpSuggestions";

interface FollowUpSuggestionsProps {
  content: string;
  disabled?: boolean;
  onPick: (action: WelcomeAction) => void;
}

export function FollowUpSuggestions({
  content,
  disabled = false,
  onPick,
}: FollowUpSuggestionsProps) {
  const { t } = useI18n();
  const questions = useMemo(
    () => buildFollowUpQuestions(content, t),
    [content, t],
  );

  if (questions.length === 0) return null;

  return (
    <div className="cv-followups" aria-label={t("chat.followUps.label")}>
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          className="cv-followup-chip"
          disabled={disabled}
          onClick={() => onPick({ kind: "send-message", message: question })}
        >
          {question}
        </button>
      ))}
    </div>
  );
}
