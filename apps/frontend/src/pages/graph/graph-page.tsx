import { useMemo, useState } from 'react';

import { getEvidenceGraphStats, resyncEvidenceDocument, searchEvidence } from '../../services/api';
import { ApiError } from '../../services/http';
import { useToastStore } from '../../store/useToastStore';

import type {
  EvidenceGraphEdge,
  EvidenceGraphNode,
  EvidenceSearchPayload,
  EvidenceSearchResponse,
  GraphSearchRequest,
} from '../../types/api';

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

  const [searchLoading, setSearchLoading] = useState(false);
  const [searchForm, setSearchForm] = useState({
    gene_symbol: '',
    variant: '',
    protein_change: '',
    disease_name: '',
  });
  const [searchResult, setSearchResult] = useState<EvidenceSearchResponse | null>(null);

  const statsText = useMemo(() => (stats ? prettyJson(stats) : 'No data yet.'), [stats]);
  const resyncText = useMemo(() => (resyncResult ? prettyJson(resyncResult) : 'No data yet.'), [resyncResult]);
  const searchText = useMemo(() => (searchResult ? prettyJson(searchResult.data) : 'No graph search results yet.'), [searchResult]);

  const graphData: EvidenceSearchPayload = searchResult?.data ?? {};
  const nodes: EvidenceGraphNode[] = graphData.nodes ?? [];
  const edges: EvidenceGraphEdge[] = graphData.edges ?? [];
  const totalEvidence = graphData.total_evidence ?? 0;
  const documentCount = graphData.document_count ?? 0;

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

  const updateSearchField = (field: keyof GraphSearchRequest, value: string) => {
    setSearchForm((current) => ({ ...current, [field]: value }));
  };

  const runSearch = async () => {
    const payload = Object.fromEntries(
      Object.entries(searchForm)
        .map(([key, value]) => [key, value.trim()])
        .filter(([, value]) => value.length > 0)
    ) as GraphSearchRequest;

    setSearchLoading(true);
    try {
      const res = await searchEvidence(payload);
      setSearchResult(res);
    } catch (err) {
      const msg = normalizeError(err);
      toast.pushToast({ level: 'error', title: 'Graph search failed', message: msg, ttlMs: 8000 });
      setSearchResult(null);
    } finally {
      setSearchLoading(false);
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
              Route-aligned console for evidence search, graph stats, and Neo4j resync.
            </div>
          </div>
        </div>
        <div className="panel-body">
          <div className="graph-console__grid">
            <section>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0, fontWeight: 800 }}>Graph search</h3>
                <div className="graph-console__actions">
                  <button
                    type="button"
                    className="graph-console__btn graph-console__btn--primary"
                    onClick={runSearch}
                    disabled={searchLoading}
                  >
                    {searchLoading ? 'Searching…' : 'Search graph'}
                  </button>
                </div>
              </div>
              <div className="graph-console__search-grid">
                <label className="graph-console__field" htmlFor="graph-search-gene">
                  <div className="muted graph-console__label">Gene symbol</div>
                  <input
                    className="graph-console__input"
                    id="graph-search-gene"
                    value={searchForm.gene_symbol}
                    onChange={(e) => updateSearchField('gene_symbol', e.target.value)}
                    placeholder="BRCA1"
                  />
                </label>
                <label className="graph-console__field" htmlFor="graph-search-variant">
                  <div className="muted graph-console__label">Variant</div>
                  <input
                    className="graph-console__input"
                    id="graph-search-variant"
                    value={searchForm.variant}
                    onChange={(e) => updateSearchField('variant', e.target.value)}
                    placeholder="c.68_69delAG"
                  />
                </label>
                <label className="graph-console__field" htmlFor="graph-search-protein">
                  <div className="muted graph-console__label">Protein change</div>
                  <input
                    className="graph-console__input"
                    id="graph-search-protein"
                    value={searchForm.protein_change}
                    onChange={(e) => updateSearchField('protein_change', e.target.value)}
                    placeholder="p.Glu23Valfs"
                  />
                </label>
                <label className="graph-console__field" htmlFor="graph-search-disease">
                  <div className="muted graph-console__label">Disease name</div>
                  <input
                    className="graph-console__input"
                    id="graph-search-disease"
                    value={searchForm.disease_name}
                    onChange={(e) => updateSearchField('disease_name', e.target.value)}
                    placeholder="Breast cancer"
                  />
                </label>
              </div>
              <div className="graph-console__summary">
                <div className="graph-console__summary-card">Nodes: {nodes.length}</div>
                <div className="graph-console__summary-card">Edges: {edges.length}</div>
                <div className="graph-console__summary-card">Evidence: {totalEvidence}</div>
                <div className="graph-console__summary-card">Documents: {documentCount}</div>
              </div>
              <div className="graph-console__results-grid">
                <section>
                  <h4 style={{ margin: 0 }}>Nodes</h4>
                  <ul data-testid="graph-node-list" className="graph-console__list">
                    {nodes.map((node) => (
                      <li key={node.id} className="graph-console__list-item">
                        <strong>{node.label ?? node.id}</strong>
                        <span className="muted">{node.type ?? 'unknown'}</span>
                      </li>
                    ))}
                  </ul>
                </section>
                <section>
                  <h4 style={{ margin: 0 }}>Edges</h4>
                  <ul data-testid="graph-edge-list" className="graph-console__list">
                    {edges.map((edge, index) => (
                      <li
                        key={`${edge.source}-${edge.target}-${index}`}
                        className="graph-console__list-item"
                      >
                        <strong>{edge.relationship}</strong>
                        <span className="muted">{edge.source} → {edge.target}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              </div>
              <div style={{ marginTop: 10 }}>
                <pre className="graph-console__pre" role="region" aria-label="Graph search JSON" aria-live="polite">
                  {searchText}
                </pre>
              </div>
            </section>

            <section>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0, fontWeight: 800 }}>Graph stats</h3>
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
              <h3 style={{ margin: 0, fontWeight: 800 }}>Resync document to Neo4j</h3>
              <div className="muted" style={{ marginTop: 6 }}>
                POST /evidence/sync/document/{'{document_id}'}
              </div>
              <div style={{ marginTop: 10 }}>
                <label className="graph-console__field" htmlFor="graph-resync-document-id">
                  <div className="muted graph-console__label">document_id</div>
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

