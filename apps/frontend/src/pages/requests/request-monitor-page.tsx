import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { getPaperTaskDetail, getTaskRequestStatus, reissueLogLink } from '../../services/api';
import { ApiError } from '../../services/http';
import { useRequestPolling } from '../../hooks/useRequestPolling';

import { WorkflowTimeline } from '../../components/workflow/workflow-timeline';
import { useAppStore } from '../../store/appStore';
import { useToastStore } from '../../store/useToastStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { normalizePaperResult } from '../../utils/normalizePaperResult';

import type { PaperTaskDetailResponse, PaperTaskItemResponse, TaskRequestStatusResponse } from '../../types/api';
import type { WorkflowTimelineStep } from '../../types/stream';

function pillColor(status: string) {
  const s = status.toLowerCase();
  if (s.includes('success')) return 'rgba(82,196,26,0.22)';
  if (s.includes('fail')) return 'rgba(255,77,79,0.22)';
  if (s.includes('run') || s.includes('process') || s.includes('start')) return 'rgba(124,92,255,0.22)';
  return 'rgba(255,255,255,0.08)';
}

function formatWarningCode(code: string) {
  return code.replaceAll('_', ' ').toLowerCase();
}

function stepLabel(stepKey: string) {
  if (stepKey === 'classification') return 'ACMG step';
  if (stepKey === 'adjudication') return 'Expert review';
  return stepKey;
}

function isActiveStreamRequest(requestId: string, streamRequestId: string | null, request?: TaskRequestStatusResponse | null) {
  return Boolean(request && streamRequestId === requestId && request.request_id === requestId);
}

function matchesRequestId(requestId: string, request?: TaskRequestStatusResponse | null) {
  return Boolean(request && request.request_id === requestId);
}

function prefersPollingFallback(streamedRequest: TaskRequestStatusResponse | null, requestId?: string) {
  return Boolean(requestId && !streamedRequest);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null;
}

function PaperRow({
  paper,
  expanded,
  onToggle,
  taskTimeline,
  taskDescription,
  detail,
  detailLoading,
}: {
  paper: PaperTaskItemResponse;
  expanded: boolean;
  onToggle: () => void;
  taskTimeline: WorkflowTimelineStep[];
  taskDescription?: string;
  detail?: PaperTaskDetailResponse | null;
  detailLoading?: boolean;
}) {
  const doc = paper.document_id;
  const resultVm = detail ? normalizePaperResult(detail) : null;
  const warningCodes = Array.isArray(detail?.warning_codes)
    ? detail.warning_codes.filter((code) => !(detail?.fulltext_unavailable && code === 'FULLTEXT_UNAVAILABLE'))
    : [];
  const processingSteps = detail?.processing_steps && typeof detail.processing_steps === 'object'
    ? Object.entries(detail.processing_steps as Record<string, unknown>)
    : [];
  const traceSteps = detail?.trace_chain && typeof detail.trace_chain === 'object'
    ? asRecord((detail.trace_chain as Record<string, unknown>).steps)
    : null;
  const acquisitionStep = asRecord(traceSteps?.acquisition);
  const acquisitionDetail = asRecord(acquisitionStep?.detail);
  const sourceTrace = Array.isArray(acquisitionDetail?.source_trace) ? acquisitionDetail?.source_trace : [];

  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 800, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {paper.filename ?? paper.paper_task_id}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              padding: '6px 10px',
              borderRadius: 999,
              border: '1px solid var(--border)',
              background: pillColor(paper.status),
              fontSize: 12
            }}
          >
            {paper.status}
          </div>
          <button
            type="button"
            onClick={onToggle}
            style={{
              padding: '8px 12px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'rgba(255,255,255,0.04)',
              color: 'var(--text)',
              cursor: 'pointer'
            }}
          >
            {expanded ? 'Hide details' : 'Details'}
          </button>
          {doc ? (
            <Link to={`/documents/${encodeURIComponent(doc)}?paperTaskId=${encodeURIComponent(paper.paper_task_id)}`}>Open</Link>
          ) : (
            <span className="muted" style={{ fontSize: 12 }}>
              —
            </span>
          )}
        </div>
      </div>
      {expanded ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="muted" style={{ fontSize: 12 }}>
            paper_task_id: {paper.paper_task_id}
            {paper.error_code ? ` · error_code: ${paper.error_code}` : ''}
            {paper.duplicate_of ? ` · duplicate_of: ${paper.duplicate_of}` : ''}
          </div>

          {detailLoading ? (
            <div className="muted" style={{ fontSize: 12 }}>
              Loading paper detail...
            </div>
          ) : null}

          {resultVm || warningCodes.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {resultVm?.badges.map((badge) => (
                <div
                  key={badge}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 999,
                    border: '1px solid var(--border)',
                    background: 'rgba(255,255,255,0.06)',
                    fontSize: 12,
                  }}
                >
                  {badge}
                </div>
              ))}
              {warningCodes.map((code) => (
                <div
                  key={code}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 999,
                    border: '1px solid var(--border)',
                    background: 'rgba(255,255,255,0.03)',
                    fontSize: 12,
                  }}
                >
                  {formatWarningCode(code)}
                </div>
              ))}
            </div>
          ) : null}

          <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
            <WorkflowTimeline
              title="Task workflow"
              steps={
                processingSteps.length > 0
                  ? processingSteps.map(([stepKey, stepValue]) => {
                      const step = asRecord(stepValue);
                      const status = typeof step?.status === 'string' ? step.status : 'PENDING';
                      const message = typeof step?.message === 'string' ? step.message : undefined;
                      const normalizedStatus = status.toLowerCase();

                      return {
                        id: stepKey,
                        label: stepLabel(stepKey),
                        status: normalizedStatus.includes('fail') || normalizedStatus.includes('error')
                          ? 'error'
                          : normalizedStatus.includes('complete') || normalizedStatus.includes('success') || normalizedStatus.includes('skip')
                            ? 'completed'
                            : normalizedStatus.includes('run') || normalizedStatus.includes('process') || normalizedStatus.includes('start')
                              ? 'running'
                              : 'pending',
                        description: message,
                      };
                    })
                  : taskTimeline
              }
              emptyMessage="No task data yet"
            />
            {taskDescription ? (
              <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                {taskDescription}
              </div>
            ) : null}
          </div>

          {resultVm ? (
            <div className="row">
              <div className="col">
                <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
                  <div style={{ fontWeight: 900 }}>{resultVm.classification.title}</div>
                  <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                    status: {resultVm.classification.status}
                    {resultVm.classification.outcome ? ` · outcome: ${resultVm.classification.outcome}` : ''}
                  </div>
                </div>
              </div>
              <div className="col">
                <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
                  <div style={{ fontWeight: 900 }}>{resultVm.adjudication.title}</div>
                  <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                    status: {resultVm.adjudication.status}
                    {resultVm.adjudication.outcome ? ` · outcome: ${resultVm.adjudication.outcome}` : ''}
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {acquisitionDetail ? (
            <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
              <div style={{ fontWeight: 900 }}>Source trace</div>
              <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                provider: {String(acquisitionDetail.provider ?? 'unknown')}
              </div>
              {sourceTrace.length > 0 ? (
                <div className="muted" style={{ marginTop: 4, fontSize: 12 }}>
                  attempts: {sourceTrace.length}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export const RequestMonitorPage: React.FC = () => {
  const { requestId } = useParams();
  const toast = useToastStore();
  const { currentRequest, fetchRequest, ui, togglePaperTaskExpand } = useAppStore();

  const workflowRequest = useWorkflowStore((state) => state.currentRequest);
  const currentTask = useWorkflowStore((state) => state.currentTask);
  const requestTimeline = useWorkflowStore((state) => state.requestTimeline);
  const taskTimeline = useWorkflowStore((state) => state.taskTimeline);
  const requestConnection = useWorkflowStore((state) => state.requestConnection);
  const watchRequest = useWorkflowStore((state) => state.watchRequest);
  const watchTask = useWorkflowStore((state) => state.watchTask);
  const resetWorkflow = useWorkflowStore((state) => state.reset);
  const [paperDetails, setPaperDetails] = useState<Record<string, PaperTaskDetailResponse | null>>({});
  const [paperDetailLoading, setPaperDetailLoading] = useState<Record<string, boolean>>({});

  const fetcher = useCallback(
    async (signal: AbortSignal) => {
      if (!requestId) throw new ApiError({ status: 0, message: 'Missing requestId' });
      return getTaskRequestStatus(requestId, { signal });
    },
    [requestId]
  );

  const streamedRequest = requestId && isActiveStreamRequest(requestId, requestConnection.requestId, workflowRequest)
    ? workflowRequest
    : null;
  const poll = useRequestPolling<TaskRequestStatusResponse>(fetcher, {
    enabled: prefersPollingFallback(streamedRequest, requestId),
    intervalMs: 2000,
  });

  useEffect(() => {
    if (!requestId) return;
    void fetchRequest(requestId);
  }, [fetchRequest, requestId]);

  useEffect(() => {
    if (!requestId) return;
    watchRequest(requestId);
    return () => {
      resetWorkflow();
    };
  }, [requestId, resetWorkflow, watchRequest]);

  const streamedSnapshot = requestId && matchesRequestId(requestId, streamedRequest) ? streamedRequest : null;
  const pollingSnapshot = requestId && matchesRequestId(requestId, poll.data) ? poll.data : null;
  const appStoreSnapshot = requestId && matchesRequestId(requestId, currentRequest) ? currentRequest : null;
  const data = streamedSnapshot ?? pollingSnapshot ?? appStoreSnapshot;
  const shouldShowPollError = Boolean(poll.error && !streamedSnapshot && !appStoreSnapshot);
  const papers = data?.papers ?? [];

  const loadPaperDetail = useCallback(
    async (paperTaskId: string) => {
      if (paperDetails[paperTaskId] || paperDetailLoading[paperTaskId]) {
        return;
      }
      setPaperDetailLoading((state) => ({ ...state, [paperTaskId]: true }));
      try {
        const detail = await getPaperTaskDetail(paperTaskId);
        if (detail) {
          setPaperDetails((state) => ({ ...state, [paperTaskId]: detail }));
        }
      } catch (err) {
        const apiMsg = err instanceof ApiError ? err.detail ?? err.message : 'Failed to load paper detail';
        toast.pushToast({ level: 'error', title: 'Paper detail load failed', message: apiMsg, ttlMs: 9000 });
      } finally {
        setPaperDetailLoading((state) => ({ ...state, [paperTaskId]: false }));
      }
    },
    [paperDetailLoading, paperDetails, toast]
  );

  const reissue = async () => {
    if (!requestId) return;
    try {
      const res = await reissueLogLink(requestId);
      window.open(res.log_link, '_blank', 'noopener,noreferrer');
    } catch (err) {
      const apiMsg = err instanceof ApiError ? err.detail ?? err.message : 'Reissue failed';
      toast.pushToast({ level: 'error', title: 'Log link reissue failed', message: apiMsg, ttlMs: 9000 });
    }
  };

  if (!requestId) {
    return <div className="muted">Missing requestId</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="panel">
        <div className="panel-header">
          <div>
            <div style={{ fontWeight: 900 }}>Request Monitor</div>
            <div className="muted" style={{ fontSize: 12 }}>
              request_id: {requestId}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button
              type="button"
              onClick={reissue}
              style={{
                padding: '10px 14px',
                borderRadius: 12,
                border: '1px solid var(--border)',
                background: 'rgba(255,255,255,0.06)',
                color: 'var(--text)',
                cursor: 'pointer'
              }}
            >
              Reissue log link
            </button>
            <Link to={`/requests/${encodeURIComponent(requestId)}/export`}>Export</Link>
          </div>
        </div>
        <div className="panel-body">
          {poll.loading && !data ? <div className="muted">Loading...</div> : null}
          {shouldShowPollError ? (
            <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
              <div style={{ fontWeight: 800, color: 'var(--danger)' }}>Error</div>
              <div className="muted" style={{ marginTop: 6 }}>
                {poll.error.detail ?? poll.error.message}
              </div>
            </div>
          ) : null}
          {data ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div className="muted">Status</div>
              <div
                style={{
                  padding: '6px 10px',
                  borderRadius: 999,
                  border: '1px solid var(--border)',
                  background: pillColor(data.status),
                  fontSize: 12
                }}
              >
                {data.status}
              </div>
              <div className="muted" style={{ fontSize: 12 }}>
                Papers: {papers.length}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div style={{ fontWeight: 900 }}>Workflow</div>
          <div className="muted" style={{ fontSize: 12 }}>
            Live status (WebSocket-first)
          </div>
        </div>
        <div className="panel-body">
          <WorkflowTimeline steps={requestTimeline} emptyMessage="No workflow data yet" />
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div style={{ fontWeight: 900 }}>Papers</div>
          <div className="muted" style={{ fontSize: 12 }}>
            Polling every 2s (pauses when tab hidden)
          </div>
        </div>
        <div className="panel-body">
          {papers.length === 0 ? <div className="muted">No papers yet</div> : null}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {papers.map((p) => (
              <PaperRow
                key={p.paper_task_id}
                paper={p}
                expanded={ui.expandedPaperTasks.includes(p.paper_task_id)}
                onToggle={() => {
                  const isExpanded = ui.expandedPaperTasks.includes(p.paper_task_id);
                  togglePaperTaskExpand(p.paper_task_id);
                  if (!isExpanded) {
                    watchTask(p.paper_task_id);
                    void loadPaperDetail(p.paper_task_id);
                  }
                }}
                taskTimeline={currentTask?.paper_task_id === p.paper_task_id ? taskTimeline : []}
                taskDescription={currentTask?.paper_task_id === p.paper_task_id ? currentTask.workflow_status_description : undefined}
                detail={paperDetails[p.paper_task_id]}
                detailLoading={paperDetailLoading[p.paper_task_id]}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
