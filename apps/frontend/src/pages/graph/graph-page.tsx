import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { getEvidenceGraphStats, resyncEvidenceDocument, searchEvidenceGraph } from '../../services/api';
import { ApiError } from '../../services/http';
import { useToastStore } from '../../store/useToastStore';

import type { EvidenceSearchResponse } from '../../types/api';

import './graph-page.css';

type GraphNode = {
  id: string;
  type?: string;
  label?: string;
};

type GraphEdge = {
  source: string;
  target: string;
  relationship?: string;
};

type GraphData = {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  evidence_records?: Array<Record<string, unknown>>;
  document_count?: number;
  total_evidence?: number;
};

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

  const [geneSymbol, setGeneSymbol] = useState('');
  const [variant, setVariant] = useState('');
  const [proteinChange, setProteinChange] = useState('');
  const [diseaseName, setDiseaseName] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResult, setSearchResult] = useState<EvidenceSearchResponse | null>(null);

  const statsText = useMemo(() => (stats ? prettyJson(stats) : 'No data yet.'), [stats]);
  const resyncText = useMemo(() => (resyncResult ? prettyJson(resyncResult) : 'No data yet.'), [resyncResult]);
  const graphData = (searchResult?.data ?? null) as GraphData | null;
  const nodes = graphData?.nodes ?? [];
  const edges = graphData?.edges ?? [];
  const evidenceRecords = graphData?.evidence_records ?? [];

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

  const runSearch = async () => {
    if (!geneSymbol.trim() && !variant.trim() && !proteinChange.trim()) {
      toast.pushToast({ level: 'warning', title: 'Missing search input', message: 'Provide gene, variant, or protein change', ttlMs: 6000 });
      return;
    }

    setSearchLoading(true);
    try {
      const res = await searchEvidenceGraph({
        gene_symbol: geneSymbol.trim() || undefined,
        variant: variant.trim() || undefined,
        protein_change: proteinChange.trim() || undefined,
        disease_name: diseaseName.trim() || undefined,
      });
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
              Knowledge Graph Explorer
            </h2>
            <div className="muted">
              Search evidence graph, inspect nodes, and jump to document views.
            </div>
          </div>
        </div>
        <div className="panel-body">
          <section className="graph-console__search">
            <div className="graph-console__search-grid">
              <label className="graph-console__field" htmlFor="graph-search-gene">
                <div className="muted graph-console__label">Gene</div>
                <input id="graph-search-gene" className="graph-console__input" value={geneSymbol} onChange={(e) => setGeneSymbol(e.target.value)} placeholder="e.g. GLA" />
              </label>
              <label className="graph-console__field" htmlFor="graph-search-variant">
                <div className="muted graph-console__label">Variant</div>
                <input id="graph-search-variant" className="graph-console__input" value={variant} onChange={(e) => setVariant(e.target.value)} placeholder="e.g. GLA:c.92C>A" />
              </label>
              <label className="graph-console__field" htmlFor="graph-search-protein">
                <div className="muted graph-console__label">Protein</div>
                <input id="graph-search-protein" className="graph-console__input" value={proteinChange} onChange={(e) => setProteinChange(e.target.value)} placeholder="e.g. p.Arg31Ser" />
              </label>
              <label className="graph-console__field" htmlFor="graph-search-disease">
                <div className="muted graph-console__label">Disease</div>
                <input id="graph-search-disease" className="graph-console__input" value={diseaseName} onChange={(e) => setDiseaseName(e.target.value)} placeholder="e.g. Fabry disease" />
              </label>
            </div>
            <div className="graph-console__actions" style={{ marginTop: 12 }}>
              <button type="button" className="graph-console__btn graph-console__btn--primary" onClick={runSearch} disabled={searchLoading}>
                {searchLoading ? 'Searching…' : 'Search graph'}
              </button>
            </div>
          </section>

          <div className="graph-console__grid graph-console__grid--results" style={{ marginTop: 18 }}>
            <section>
              <h3 style={{ margin: 0, fontWeight: 800 }}>Nodes</h3>
              <div className="graph-console__canvas" role="region" aria-label="Graph nodes">
                {nodes.length === 0 ? <div className="muted">No graph data yet.</div> : null}
                <div className="graph-console__node-list">
                  {nodes.map((node) => {
                    const documentId = node.id?.startsWith('doc:') ? node.id.slice(4) : null;
                    return (
                      <div key={node.id} className="graph-console__node-card">
                        <div style={{ fontWeight: 800 }}>{node.label ?? node.id}</div>
                        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{node.type ?? 'node'}</div>
                        {documentId ? (
                          <div style={{ marginTop: 8 }}>
                            <Link to={`/documents/${encodeURIComponent(documentId)}`}>Open document</Link>
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

            <section>
              <h3 style={{ margin: 0, fontWeight: 800 }}>Edges</h3>
              <pre className="graph-console__pre" role="region" aria-label="Graph edges JSON" aria-live="polite">
                {prettyJson(edges)}
              </pre>
            </section>

            <section>
              <h3 style={{ margin: 0, fontWeight: 800 }}>Evidence records</h3>
              <pre className="graph-console__pre" role="region" aria-label="Evidence records JSON" aria-live="polite">
                {prettyJson(evidenceRecords)}
              </pre>
            </section>
          </div>

          <div className="graph-console__grid" style={{ marginTop: 18 }}>
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
