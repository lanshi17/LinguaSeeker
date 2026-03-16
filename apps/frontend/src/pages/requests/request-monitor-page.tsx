import { useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';

import { getTaskRequestStatus, reissueLogLink } from '../../services/api';
import { ApiError } from '../../services/http';
import { useToastStore } from '../../store/useToastStore';
import { useRequestPolling } from '../../hooks/useRequestPolling';

import type { PaperTaskItemResponse, TaskRequestStatusResponse } from '../../types/api';

function pillColor(status: string) {
  const s = status.toLowerCase();
  if (s.includes('success')) return 'rgba(82,196,26,0.22)';
  if (s.includes('fail')) return 'rgba(255,77,79,0.22)';
  if (s.includes('run') || s.includes('process') || s.includes('start')) return 'rgba(124,92,255,0.22)';
  return 'rgba(255,255,255,0.08)';
}

function PaperRow({ paper }: { paper: PaperTaskItemResponse }) {
  const doc = paper.document_id;
  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: 12,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 800, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {paper.filename ?? paper.paper_task_id}
        </div>
        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
          paper_task_id: {paper.paper_task_id}
          {paper.error_code ? ` · error_code: ${paper.error_code}` : ''}
          {paper.duplicate_of ? ` · duplicate_of: ${paper.duplicate_of}` : ''}
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
        {doc ? (
          <Link to={`/documents/${encodeURIComponent(doc)}`}>Open</Link>
        ) : (
          <span className="muted" style={{ fontSize: 12 }}>
            —
          </span>
        )}
      </div>
    </div>
  );
}

export const RequestMonitorPage: React.FC = () => {
  const { requestId } = useParams();
  const toast = useToastStore();

  const fetcher = useCallback(
    async (signal: AbortSignal) => {
      if (!requestId) throw new ApiError({ status: 0, message: 'Missing requestId' });
      return getTaskRequestStatus(requestId, { signal });
    },
    [requestId]
  );

  const poll = useRequestPolling<TaskRequestStatusResponse>(fetcher, { enabled: Boolean(requestId), intervalMs: 2000 });

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

  const data = poll.data;
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
          <div style={{ fontWeight: 900 }}>Papers</div>
          <div className="muted" style={{ fontSize: 12 }}>
            Polling every 2s (pauses when tab hidden)
          </div>
        </div>
        <div className="panel-body">
          {papers.length === 0 ? <div className="muted">No papers yet</div> : null}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {papers.map((p) => (
              <PaperRow key={p.paper_task_id} paper={p} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
