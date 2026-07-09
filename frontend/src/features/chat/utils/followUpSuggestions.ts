const FOLLOW_UP_COUNT = 3;
const PIPELINE_PATTERN =
  /\b(pipeline|task|run|status|started)\b|流水线|任务|状态|启动|运行/i;
const EVIDENCE_PATTERN =
  /\b(evidence|variant|gene|acmg|literature)\b|证据|变异|基因|文献/i;

export function buildFollowUpQuestions(
  content: string,
  t: (key: string) => string,
): string[] {
  const trimmed = content.trim();
  if (!trimmed) return [];

  const firstQuestion = PIPELINE_PATTERN.test(trimmed)
    ? t("chat.followUps.pipelineStatus")
    : EVIDENCE_PATTERN.test(trimmed)
      ? t("chat.followUps.evidenceGaps")
      : t("chat.followUps.nextStep");

  return Array.from(
    new Set([
      firstQuestion,
      t("chat.followUps.summarize"),
      t("chat.followUps.verifyEvidence"),
    ]),
  ).slice(0, FOLLOW_UP_COUNT);
}
