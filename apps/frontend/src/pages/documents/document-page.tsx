import { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { getEvidenceDocument, getPaperTaskDetail } from '../../services/api';
import { ApiError } from '../../services/http';
import { useToastStore } from '../../store/useToastStore';
import { normalizeEvidence } from '../../utils/normalizeEvidence';
import { normalizePaperResult } from '../../utils/normalizePaperResult';

import type { DocumentEvidenceResponse, PaperTaskDetailResponse } from '../../types/api';

type TabKey = 'reading' | 'judgment';

export const DocumentPage: React.FC = () => {
  const { documentId } = useParams();
  const [searchParams] = useSearchParams();
  const toast = useToastStore();

  const [active, setActive] = useState<TabKey>('reading');
  const [loading, setLoading] = useState(false);
  const [payload, setPayload] = useState<DocumentEvidenceResponse | null>(null);
  const [paperDetail, setPaperDetail] = useState<PaperTaskDetailResponse | null>(null);

  useEffect(() => {
    if (!documentId) return;
    const ac = new AbortController();
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const res = await getEvidenceDocument(documentId, { signal: ac.signal });
        if (!cancelled) setPayload(res);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        const msg = err instanceof ApiError ? err.detail ?? err.message : 'Failed to load evidence';
        toast.pushToast({ level: 'error', title: 'Evidence fetch failed', message: msg, ttlMs: 9000 });
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [documentId, toast]);

  useEffect(() => {
    if (!documentId) return;
    const ac = new AbortController();
    let cancelled = false;
    const paperTaskId = searchParams.get('paperTaskId') ?? documentId;

    const load = async () => {
      try {
        const res = await getPaperTaskDetail(paperTaskId, { signal: ac.signal });
        if (!cancelled) setPaperDetail(res);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [documentId, searchParams]);

  const vm = useMemo(() => normalizeEvidence(payload?.data ?? null), [payload]);
  const paperVm = useMemo(
    () => (paperDetail ? normalizePaperResult(paperDetail) : null),
    [paperDetail]
  );

  if (!documentId) return <div className="muted">Missing documentId</div>;

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div style={{ fontWeight: 900 }}>Document</div>
          <div className="muted" style={{ fontSize: 12 }}>
            document_id: {documentId}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            type="button"
            onClick={() => setActive('reading')}
            style={{
              padding: '8px 12px',
              borderRadius: 999,
              border: '1px solid var(--border)',
              background: active === 'reading' ? 'rgba(124,92,255,0.18)' : 'rgba(255,255,255,0.06)',
              color: 'var(--text)',
              cursor: 'pointer'
            }}
          >
            Reading
          </button>
          <button
            type="button"
            onClick={() => setActive('judgment')}
            style={{
              padding: '8px 12px',
              borderRadius: 999,
              border: '1px solid var(--border)',
              background: active === 'judgment' ? 'rgba(124,92,255,0.18)' : 'rgba(255,255,255,0.06)',
              color: 'var(--text)',
              cursor: 'pointer'
            }}
          >
            Evidence judgment
          </button>
        </div>
      </div>
      <div className="panel-body">
        {loading ? <div className="muted">Loading...</div> : null}
        {vm.warning ? (
          <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12, marginBottom: 12 }}>
            <div style={{ fontWeight: 800, color: 'var(--warning)' }}>Note</div>
            <div className="muted" style={{ marginTop: 6 }}>
              {vm.warning}
            </div>
          </div>
        ) : null}

        {paperVm ? (
          <div className="row" style={{ marginBottom: 12 }}>
            <div className="col">
              <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
                <div style={{ fontWeight: 800 }}>{paperVm.classification.title}</div>
                <div className="muted" style={{ marginTop: 6 }}>
                  status: {paperVm.classification.status}
                  {paperVm.classification.outcome ? ` · outcome: ${paperVm.classification.outcome}` : ''}
                </div>
              </div>
            </div>
            <div className="col">
              <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
                <div style={{ fontWeight: 800 }}>{paperVm.adjudication.title}</div>
                <div className="muted" style={{ marginTop: 6 }}>
                  status: {paperVm.adjudication.status}
                  {paperVm.adjudication.outcome ? ` · outcome: ${paperVm.adjudication.outcome}` : ''}
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {active === 'reading' ? (
          <div className="row">
            <div className="col" data-testid="document-source-panel">
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                Source ({vm.sourceLang})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {vm.segments.map((s) => (
                  <div key={s.id} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{s.sourceText || '—'}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="col" data-testid="document-target-panel">
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                Target ({vm.targetLang})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {vm.segments.map((s) => (
                  <div key={s.id} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{s.targetText || '—'}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div>
            <div style={{ fontWeight: 800 }}>Structured evidence</div>
            <div className="muted" style={{ marginTop: 6 }}>
              Stable document evidence payload from the backend.
            </div>
            <div style={{ marginTop: 10 }}>
              <pre
                data-testid="document-evidence-json"
                style={{
                  overflow: 'auto',
                  padding: 12,
                  borderRadius: 12,
                  border: '1px solid var(--border)',
                  background: 'rgba(255,255,255,0.03)'
                }}
              >
                {JSON.stringify(payload?.data?.ps3_evidence ?? payload?.data?.graph ?? {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
