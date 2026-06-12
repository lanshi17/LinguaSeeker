export interface PromptItem {
  key: string;
  eyebrow: string;
  label: string;
  description: string;
  example: string;
}

export const CHAT_PROMPTS: readonly PromptItem[] = [
  {
    key: "start-pipeline",
    eyebrow: "PIPELINE · PHASE 1–4",
    label: "Begin evidence extraction",
    description:
      "Run a paper through the four-phase pipeline: literature acquisition, cross-lingual dual extraction, entity standardisation, and expert review.",
    example:
      "PMID 34521984 — BRCA1 variant c.5266dupC in a 47-year-old proband",
  },
  {
    key: "upload-pdf",
    eyebrow: "PIPELINE · LOCAL",
    label: "Ingest a PDF from disk",
    description:
      "Upload a paper you already have. The pipeline parses, translates where needed, and emits a structured evidence record.",
    example:
      "Drop a PDF · journal-style clinical case report · < 12 MB",
  },
  {
    key: "search-evidence",
    eyebrow: "QUERY · DB",
    label: "Search extracted evidence",
    description:
      "Query the evidence database by gene, variant, disease, or ACMG code. Returns grounded records with source coordinates.",
    example: "BRCA1 ∩ pathogenic ∩ exon 11 · 2019–2024",
  },
  {
    key: "classify-variant",
    eyebrow: "CLASSIFY · ACMG",
    label: "Classify a variant",
    description:
      "Walk the ACMG/AMP 2015 criteria with the agent. Each criterion is checked against evidence and the chain of reasoning is exposed.",
    example: "NM_007294.4(BRCA1):c.181T>G (p.Cys61Gly)",
  },
  {
    key: "interpret-evidence",
    eyebrow: "INTERPRET · CITED",
    label: "Interpret a finding",
    description:
      "Ask the agent to read an existing evidence record and explain its source, confidence, and limitations in plain English.",
    example:
      "Walk me through evidence_id 7f3a — how was pathogenicity assigned?",
  },
  {
    key: "review-changes",
    eyebrow: "REVIEW · LOOP",
    label: "Open expert review queue",
    description:
      "Surface the items flagged for human review — including ambiguous source grounding, OCR gaps, and ClinGen-disagreement.",
    example: "Show awaiting_review, grouped by review_reason",
  },
] as const;
