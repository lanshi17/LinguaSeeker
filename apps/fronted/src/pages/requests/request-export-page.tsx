import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { getEvidenceDocument, getTaskRequestStatus } from '../../services/api';
import { ApiError } from '../../services/http';
import { useToastStore } from '../../store/useToastStore';
import { normalizeEvidence } from '../../utils/normalizeEvidence';

import type { EvidenceSearchResponse, TaskRequestStatusResponse } from '../../types/api';

export const RequestExportPage: React.FC = () => {
  const { requestId } = useParams();
  const toast = useToastStore();
  const [searchParams, setSearchParams] = useSearchParams();

  const [requestStatus, setRequestStatus] = useState<TaskRequestStatusResponse | null>(null);
  const [evidence, setEvidence] = useState<EvidenceSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const documentId = searchParams.get('documentId');

  useEffect(() => {
    if (!requestId) return;
    let cancelled = false;
    const ac = new AbortController();

    const load = async () => {
      setLoading(true);
      try {
        const res = await getTaskRequestStatus(requestId, { signal: ac.signal });
        if (!cancelled) setRequestStatus(res);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        const msg = err instanceof ApiError ? err.detail ?? err.message : 'Failed to load request';
        toast.pushToast({ level: 'error', title: 'Request load failed', message: msg, ttlMs: 9000 });
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [requestId, toast]);

  const availableDocs = useMemo(() => {
    const docs = (requestStatus?.papers ?? [])
      .map((p) => p.document_id)
      .filter((x): x is string => typeof x === 'string' && x.length > 0);
    return Array.from(new Set(docs));
  }, [requestStatus]);

  const selectedDoc = documentId ?? availableDocs[0] ?? null;

  useEffect(() => {
    if (!selectedDoc) return;
    let cancelled = false;
    const ac = new AbortController();

    const load = async () => {
      setLoading(true);
      try {
        const res = await getEvidenceDocument(selectedDoc, { signal: ac.signal });
        if (!cancelled) setEvidence(res);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        const msg = err instanceof ApiError ? err.detail ?? err.message : 'Failed to load evidence';
        toast.pushToast({ level: 'error', title: 'Evidence load failed', message: msg, ttlMs: 9000 });
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [selectedDoc, toast]);

  const vm = useMemo(() => normalizeEvidence(evidence?.data ?? null), [evidence]);

  if (!requestId) return <div className="muted">Missing requestId</div>;

  return (
    <div className="panel">
      <div className="panel-header no-print">
        <div>
          <div style={{ fontWeight: 900 }}>Export</div>
          <div className="muted" style={{ fontSize: 12 }}>
            request_id: {requestId}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Link to={`/requests/${encodeURIComponent(requestId)}`}>Back</Link>
          <button
            type="button"
            onClick={() => window.print()}
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              border: '1px solid var(--border)',
              background: 'rgba(124,92,255,0.18)',
              color: 'var(--text)',
              cursor: 'pointer'
            }}
          >
            Print / Save as PDF
          </button>
        </div>
      </div>

      <div className="panel-body">
        {loading ? <div className="muted no-print">Loading...</div> : null}

        <div className="no-print" style={{ marginBottom: 12 }}>
          <div className="muted" style={{ fontSize: 12 }}>
            Select a document to export:
          </div>
          <select
            value={selectedDoc ?? ''}
            onChange={(e) => setSearchParams({ documentId: e.target.value })}
            style={{ marginTop: 6, padding: 10, borderRadius: 12, border: '1px solid var(--border)', minWidth: 320 }}
            disabled={availableDocs.length === 0}
          >
            {availableDocs.length === 0 ? <option value="">No documents</option> : null}
            {availableDocs.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>

        <div className="print-only" style={{ fontWeight: 900, marginBottom: 10 }}>
          Multi-ACMG Export
        </div>

        <section>
          <div style={{ fontWeight: 900, marginBottom: 8 }}>Reading</div>
          {vm.warning ? <div className="muted" style={{ marginBottom: 8 }}>
            {vm.warning}
          </div> : null}
          <div className="row">
            <div className="col">
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                Source ({vm.sourceLang})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {vm.segments.map((s) => (
                  <div key={s.id} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{s.sourceText || '—'}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="col">
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                Target ({vm.targetLang})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {vm.segments.map((s) => (
                  <div key={s.id} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{s.targetText || '—'}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <div className="page-break" />

        <section>
          <div style={{ fontWeight: 900, marginBottom: 8 }}>Evidence judgment</div>
          <div className="muted" style={{ marginBottom: 8 }}>
            Contract-tolerant MVP: this section renders raw evidence payload until a stable judgment schema is available.
          </div>
          <pre
            style={{
              overflow: 'auto',
              padding: 12,
              borderRadius: 12,
              border: '1px solid var(--border)',
              background: 'rgba(255,255,255,0.03)'
            }}
          >
            {JSON.stringify(evidence?.data ?? null, null, 2)}
          </pre>
        </section>
      </div>
    </div>
  );
};
