import type { PaperTaskDetailResponse } from '../types/api';

type JudgmentCard = {
  title: string;
  status: string;
  outcome: string | null;
  graphSyncOk: boolean;
};

type PaperResultViewModel = {
  badges: string[];
  classification: JudgmentCard;
  adjudication: JudgmentCard;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null;
}

function readStep(detail: PaperTaskDetailResponse, stepKey: string): Record<string, unknown> | null {
  const traceChain = asRecord(detail.trace_chain);
  const steps = asRecord(traceChain?.steps);
  return asRecord(steps?.[stepKey]);
}

function readStatus(detail: PaperTaskDetailResponse, stepKey: string): string {
  const processingSteps = asRecord(detail.processing_steps);
  const step = asRecord(processingSteps?.[stepKey]);
  const status = step?.status;
  return typeof status === 'string' ? status : 'PENDING';
}

function readOutcome(detail: PaperTaskDetailResponse, stepKey: string): string | null {
  const step = readStep(detail, stepKey);
  const outcome = step?.outcome;
  return typeof outcome === 'string' ? outcome : null;
}

function readGraphSyncOk(detail: PaperTaskDetailResponse): boolean {
  const resultPayload = asRecord(detail.result_payload);
  const graphSync = asRecord(resultPayload?.graph_sync_result);
  const neo4jOk = graphSync?.neo4j_ok;
  if (typeof neo4jOk === 'boolean') return neo4jOk;
  const neo4jSynced = graphSync?.neo4j_synced;
  return typeof neo4jSynced === 'boolean' ? neo4jSynced : false;
}

export function normalizePaperResult(detail: PaperTaskDetailResponse): PaperResultViewModel {
  const badges: string[] = [];
  if (detail.duplicate_of) badges.push('Duplicate reuse');
  if (detail.fulltext_unavailable) badges.push('Fulltext unavailable');

  return {
    badges,
    classification: {
      title: 'ACMG classification',
      status: readStatus(detail, 'classification'),
      outcome: readOutcome(detail, 'classification'),
      graphSyncOk: readGraphSyncOk(detail),
    },
    adjudication: {
      title: 'Expert adjudication',
      status: readStatus(detail, 'adjudication'),
      outcome: readOutcome(detail, 'adjudication'),
      graphSyncOk: readGraphSyncOk(detail),
    },
  };
}
