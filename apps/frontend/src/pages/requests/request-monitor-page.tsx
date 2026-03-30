import { useCallback, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';

import { getTaskRequestStatus, reissueLogLink } from '../../services/api';
import { ApiError } from '../../services/http';
import { useRequestPolling } from '../../hooks/useRequestPolling';

import { useAppStore } from '../../store/appStore';
import { useToastStore } from '../../store/useToastStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';

import type { PaperTaskItemResponse, TaskRequestStatusResponse } from '../../types/api';

function pillColor(status: string) {
  const s = status.toLowerCase();
  if (s.includes('success')) return 'rgba(82,196,26,0.22)';
  if (s.includes('fail')) return 'rgba(255,77,79,0.22)';
  if (s.includes('run') || s.includes('process') || s.includes('start')) return 'rgba(124,92,255,0.22)';
  return 'rgba(255,255,255,0.08)';
}

function PaperRow({
  paper,
  expanded,
  onToggle,
  taskTimeline,
  taskDescription,
}: {
  paper: PaperTaskItemResponse;
  expanded: boolean;
  onToggle: () => void;
  taskTimeline: Array<{
    id: 'queued' | 'running' | 'success';
    label: string;
    status: 'pending' | 'running' | 'completed' | 'error';
    description?: string;
    progress?: number;
  }>;
  taskDescription?: string;
}) {
  const doc = paper.document_id;
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
            <Link to={`/documents/${encodeURIComponent(doc)}`}>Open</Link>
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

          <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
            <div style={{ fontWeight: 900 }}>Task workflow</div>
            {taskDescription ? (
              <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                {taskDescription}
              </div>
            ) : null}
            <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {taskTimeline.length === 0 ? (
                <div className="muted" style={{ fontSize: 12 }}>
                  No task data yet
                </div>
              ) : (
                taskTimeline.map((step) => (
                  <div
                    key={step.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                      padding: 10,
                      borderRadius: 10,
                      border: '1px solid var(--border)',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 800 }}>{step.label}</div>
                      {step.description ? (
                        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                          {step.description}
                        </div>
                      ) : null}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      {typeof step.progress === 'number' ? (
                        <div className="muted" style={{ fontSize: 12 }}>
                          {step.progress}%
                        </div>
                      ) : null}
                      <div
                        style={{
                          padding: '6px 10px',
                          borderRadius: 999,
                          border: '1px solid var(--border)',
                          background: pillColor(step.status),
                          fontSize: 12,
                        }}
                      >
                        {step.status}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
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
  const watchRequest = useWorkflowStore((state) => state.watchRequest);
  const watchTask = useWorkflowStore((state) => state.watchTask);
  const resetWorkflow = useWorkflowStore((state) => state.reset);

  const fetcher = useCallback(
    async (signal: AbortSignal) => {
      if (!requestId) throw new ApiError({ status: 0, message: 'Missing requestId' });
      const data = await getTaskRequestStatus(requestId, { signal });
      useAppStore.setState({ currentRequest: data });
      return data;
    },
    [requestId]
  );

  const poll = useRequestPolling<TaskRequestStatusResponse>(fetcher, { enabled: Boolean(requestId), intervalMs: 2000 });

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

  const data = workflowRequest ?? poll.data ?? currentRequest;
  const papers = data?.papers ?? [];

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
          {poll.error ? (
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
          {requestTimeline.length === 0 ? (
            <div className="muted">No workflow data yet</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {requestTimeline.map((step) => (
                <div
                  key={step.id}
                  style={{
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    padding: 12,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 800 }}>{step.label}</div>
                    {step.description ? (
                      <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                        {step.description}
                      </div>
                    ) : null}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {typeof step.progress === 'number' ? (
                      <div className="muted" style={{ fontSize: 12 }}>
                        {step.progress}%
                      </div>
                    ) : null}
                    <div
                      style={{
                        padding: '6px 10px',
                        borderRadius: 999,
                        border: '1px solid var(--border)',
                        background: pillColor(step.status),
                        fontSize: 12,
                      }}
                    >
                      {step.status}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
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
                  }
                }}
                taskTimeline={currentTask?.paper_task_id === p.paper_task_id ? taskTimeline : []}
                taskDescription={currentTask?.paper_task_id === p.paper_task_id ? currentTask.workflow_status_description : undefined}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
