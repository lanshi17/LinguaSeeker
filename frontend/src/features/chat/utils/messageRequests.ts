export interface AppendMessageBody {
  role: "user";
  content: string;
  evidence_id?: string;
  auto_reply: false;
}

export function buildAppendMessageBody(
  content: string,
  evidenceId?: string,
): AppendMessageBody {
  return {
    role: "user",
    content,
    ...(evidenceId ? { evidence_id: evidenceId } : {}),
    auto_reply: false,
  };
}
