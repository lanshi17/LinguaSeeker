/**
 * Graph Page
 * D3.js force-directed knowledge graph with search, filter, and export
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Search, Filter } from 'lucide-react';
import { ForceGraph } from '../../components/Graph/ForceGraph';
import { useDocumentStore } from '../../store/documentStore';
import { EvidenceType } from '../../types';
import type { GraphNode, GraphEdge } from '../../types';
import './GraphPage.css';

// Generate mock graph data
const generateMockGraph = (keyword: string): { nodes: GraphNode[]; edges: GraphEdge[] } => {
  const nodes: GraphNode[] = [
    { id: 'k1', label: keyword, type: 'keyword', x: 400, y: 300 },
    { id: 'g1', label: 'Gene:A', type: 'gene' },
    { id: 'g2', label: 'Gene:B', type: 'gene' },
    { id: 't1', label: 'Transcript:1', type: 'transcript' },
    { id: 'v1', label: 'Variant:c.123A>G', type: 'variant' },
    { id: 'e1', label: 'PVS1', type: 'evidence', evidenceType: EvidenceType.PVS },
    { id: 'e2', label: 'PS4', type: 'evidence', evidenceType: EvidenceType.PS },
    { id: 'e3', label: 'PM2', type: 'evidence', evidenceType: EvidenceType.PM },
    { id: 'd1', label: 'PMID:12345678', type: 'document' },
    { id: 'd2', label: 'PMID:23456789', type: 'document' },
  ];

  const edges: GraphEdge[] = [
    { id: 'edge1', source: 'k1', target: 'g1', weight: 1 },
    { id: 'edge2', source: 'k1', target: 'g2', weight: 0.8 },
    { id: 'edge3', source: 'g1', target: 't1', weight: 1 },
    { id: 'edge4', source: 't1', target: 'v1', weight: 0.9 },
    { id: 'edge5', source: 'v1', target: 'e1', weight: 1 },
    { id: 'edge6', source: 'v1', target: 'e2', weight: 0.8 },
    { id: 'edge7', source: 'g2', target: 'e3', weight: 0.7 },
    { id: 'edge8', source: 'e1', target: 'd1', weight: 1 },
    { id: 'edge9', source: 'e2', target: 'd2', weight: 1 },
  ];

  return { nodes, edges };
};

export const GraphPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { graphFilter, updateGraphFilter } = useDocumentStore();
  
  const keyword = searchParams.get('keyword') || '';
  const [searchInput, setSearchInput] = useState(keyword);
  const [loading, setLoading] = useState(false);
  const [showFilter, setShowFilter] = useState(false);

  // Graph data
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] }>({
    nodes: [],
    edges: [],
  });

  // Load graph data
  useEffect(() => {
    if (!keyword) return;
    
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      const data = generateMockGraph(keyword);
      setGraphData(data);
      setLoading(false);
    }, 800);
  }, [keyword]);

  // Filtered nodes
  const filteredNodes = useMemo(() => {
    return graphData.nodes.filter((node) => {
      if (graphFilter.entityTypes.length > 0 && !graphFilter.entityTypes.includes(node.type)) {
        return false;
      }
      if (node.type === 'evidence' && node.evidenceType) {
        if (graphFilter.evidenceTypes.length > 0 && 
            !graphFilter.evidenceTypes.includes(node.evidenceType)) {
          return false;
        }
      }
      return true;
    });
  }, [graphData.nodes, graphFilter]);

  // Filtered edges (only keep edges where both nodes are in filtered list)
  const filteredEdges = useMemo(() => {
    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    return graphData.edges.filter((e) => {
      // 处理 source 和 target 可能是对象或字符串的情况
      const sourceId = typeof e.source === 'object' ? e.source.id : e.source;
      const targetId = typeof e.target === 'object' ? e.target.id : e.target;
      return nodeIds.has(sourceId) && nodeIds.has(targetId);
    });
  }, [graphData.edges, filteredNodes]);

  /**
   * Handle search
   */
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchInput.trim()) return;
    setSearchParams({ keyword: searchInput.trim() });
  };

  /**
   * Handle node click - navigate to source
   */
  const handleNodeClick = useCallback((node: GraphNode) => {
    if (node.type === 'document' && node.label.startsWith('PMID:')) {
      const pmid = node.label.replace('PMID:', '').trim();
      navigate(`/analysis/${pmid}`);
    } else if (node.type === 'evidence') {
      // Navigate to document containing this evidence
      navigate('/analysis/demo');
    }
  }, [navigate]);

  /**
   * Toggle entity type filter
   */
  const toggleEntityType = (type: string) => {
    const types = graphFilter.entityTypes;
    if (types.includes(type)) {
      updateGraphFilter({ entityTypes: types.filter((t) => t !== type) });
    } else {
      updateGraphFilter({ entityTypes: [...types, type] });
    }
  };

  return (
    <div className="graph-page">
      {/* Top navigation */}
      <header className="graph-header">
        <button onClick={() => navigate('/')} className="nav-btn">
          <ArrowLeft size={18} /> Back
        </button>

        <form onSubmit={handleSearch} className="search-form">
          <div className="search-input-wrapper">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search genes, transcripts, variants..."
              className="search-input"
            />
          </div>
          <button type="submit" disabled={!searchInput.trim()} className="search-btn">
            Search
          </button>
        </form>

        <div className="header-actions">
          <button
            className={`filter-btn ${showFilter ? 'active' : ''}`}
            onClick={() => setShowFilter(!showFilter)}
          >
            <Filter size={16} /> Filter
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="graph-content">
        {loading ? (
          <div className="loading-state">
            <div className="spinner" />
            <p>Building knowledge graph...</p>
          </div>
        ) : filteredNodes.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <h3>{keyword ? 'No results found' : 'Enter keywords to search'}</h3>
            <p>Enter keywords like genes, transcripts, or variants to start exploring</p>
          </div>
        ) : (
          <ForceGraph
            nodes={filteredNodes}
            edges={filteredEdges}
            onNodeClick={handleNodeClick}
            width={window.innerWidth - 320}
            height={window.innerHeight - 100}
          />
        )}

        {/* Filter panel */}
        {showFilter && (
          <div className="filter-panel">
            <h4>Entity Types</h4>
            <div className="filter-options">
              {['keyword', 'gene', 'transcript', 'variant', 'evidence', 'document'].map(
                (type) => (
                  <label key={type} className="filter-option">
                    <input
                      type="checkbox"
                      checked={graphFilter.entityTypes.includes(type)}
                      onChange={() => toggleEntityType(type)}
                    />
                    <span>{type}</span>
                  </label>
                )
              )}
            </div>

            <h4>Evidence Types</h4>
            <div className="filter-options">
              {Object.keys(EvidenceType).map((type) => (
                <label key={type} className="filter-option">
                  <input
                    type="checkbox"
                    checked={graphFilter.evidenceTypes.includes(type)}
                    onChange={() => {
                      const types = graphFilter.evidenceTypes;
                      updateGraphFilter({
                        evidenceTypes: types.includes(type)
                          ? types.filter((t) => t !== type)
                          : [...types, type],
                      });
                    }}
                  />
                  <span>{type}</span>
                </label>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
