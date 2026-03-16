import { useMemo, useState } from 'react';

import { getEvidenceGraphStats, resyncEvidenceDocument } from '../../services/api';
import { ApiError } from '../../services/http';
import { useToastStore } from '../../store/useToastStore';

import type { EvidenceSearchResponse } from '../../types/api';

import './graph-page.css';

function prettyJson(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function normalizeError(err: unknown) {
  if (err instanceof ApiError) return err.detail ?? err.message;
  if (err instanceof Error) return err.message;
  return 'Unknown error';
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const GraphPage: React.FC = () => {
  const toast = useToastStore();

  const [statsLoading, setStatsLoading] = useState(false);
  const [stats, setStats] = useState<EvidenceSearchResponse | null>(null);

  const [docId, setDocId] = useState('');
  const [resyncLoading, setResyncLoading] = useState(false);
  const [resyncResult, setResyncResult] = useState<EvidenceSearchResponse | null>(null);

  const statsText = useMemo(() => (stats ? prettyJson(stats) : 'No data yet.'), [stats]);
  const resyncText = useMemo(() => (resyncResult ? prettyJson(resyncResult) : 'No data yet.'), [resyncResult]);

  const refreshStats = async () => {
    setStatsLoading(true);
    try {
      const res = await getEvidenceGraphStats();
      setStats(res);
    } catch (err) {
      const msg = normalizeError(err);
      toast.pushToast({ level: 'error', title: 'Graph stats failed', message: msg, ttlMs: 8000 });
      setStats(null);
    } finally {
      setStatsLoading(false);
    }
  };

  const runResync = async () => {
    const trimmed = docId.trim();
    if (!trimmed) {
      toast.pushToast({ level: 'warning', title: 'Missing document_id', message: 'Please input a document UUID', ttlMs: 5000 });
      return;
    }
    if (!UUID_RE.test(trimmed)) {
      toast.pushToast({ level: 'warning', title: 'Invalid document_id', message: 'document_id must be a UUID (e.g., xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)', ttlMs: 7000 });
      return;
    }

    setResyncLoading(true);
    try {
      const res = await resyncEvidenceDocument(trimmed);
      setResyncResult(res);
    } catch (err) {
      const msg = normalizeError(err);
      toast.pushToast({ level: 'error', title: 'Resync failed', message: msg, ttlMs: 8000 });
      setResyncResult(null);
    } finally {
      setResyncLoading(false);
    }
  };

  return (
    <div className="graph-console">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title" style={{ margin: 0 }}>
              Graph Console
            </h2>
            <div className="muted">
              OpenAPI aligned: /evidence/graph/stats + /evidence/sync/document/{'{document_id}'}
            </div>
          </div>
        </div>
        <div className="panel-body">
          <div className="graph-console__grid">
            <section>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0, fontWeight: 800 }}>Graph Stats</h3>
                <div className="graph-console__actions">
                  <button
                    type="button"
                    className="graph-console__btn graph-console__btn--primary"
                    onClick={refreshStats}
                    disabled={statsLoading}
                  >
                    {statsLoading ? 'Loading…' : 'Refresh'}
                  </button>
                </div>
              </div>
              <div style={{ marginTop: 10 }}>
                <pre className="graph-console__pre" role="region" aria-label="Graph stats JSON" aria-live="polite">
                  {statsText}
                </pre>
              </div>
            </section>

            <section>
              <h3 style={{ margin: 0, fontWeight: 800 }}>Resync Document to Neo4j</h3>
              <div className="muted" style={{ marginTop: 6 }}>
                POST /evidence/sync/document/{'{document_id}'}
              </div>
              <div style={{ marginTop: 10 }}>
                <label className="graph-console__field" htmlFor="graph-resync-document-id">
                  <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                    document_id
                  </div>
                  <input
                    className="graph-console__input"
                    id="graph-resync-document-id"
                    name="document_id"
                    autoComplete="off"
                    spellCheck={false}
                    value={docId}
                    onChange={(e) => setDocId(e.target.value)}
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx…"
                    disabled={resyncLoading}
                  />
                </label>
              </div>
              <div className="graph-console__actions" style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="graph-console__btn"
                  onClick={runResync}
                  disabled={resyncLoading}
                >
                  {resyncLoading ? 'Resyncing…' : 'Resync'}
                </button>
              </div>
              <div style={{ marginTop: 10 }}>
                <pre className="graph-console__pre" role="region" aria-label="Resync result JSON" aria-live="polite">
                  {resyncText}
                </pre>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
};
