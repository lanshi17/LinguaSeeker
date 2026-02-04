/**
 * Evidence Panel Component
 * Displays all evidence keywords, supports click to navigate, and filtering by type
 */
import React from 'react';
import { FileText, ArrowRight, Eye, EyeOff, CheckSquare, Square } from 'lucide-react';
import type { Evidence, EvidenceTypeValue } from '../../types';
import { EvidenceTypeColors, EvidenceType } from '../../types';
import { useDocumentStore } from '../../store/documentStore';
import './EvidencePanel.css';

interface EvidencePanelProps {
  evidences: Evidence[];
  activeEvidenceId: string | null;
  onEvidenceClick: (evidence: Evidence) => void;
  docTitle?: string;
}

// Evidence type display names (ACMG guidelines)
const typeNames: Record<EvidenceTypeValue, string> = {
  [EvidenceType.PVS]: 'Pathogenic Very Strong',
  [EvidenceType.PS]: 'Pathogenic Strong',
  [EvidenceType.PM]: 'Pathogenic Moderate',
  [EvidenceType.PP]: 'Pathogenic Supporting',
  [EvidenceType.BA]: 'Benign Stand-alone',
  [EvidenceType.BS]: 'Benign Strong',
  [EvidenceType.BP]: 'Benign Supporting',
};

export const EvidencePanel: React.FC<EvidencePanelProps> = ({
  evidences,
  activeEvidenceId,
  onEvidenceClick,
  docTitle,
}) => {
  const { 
    showEvidenceHighlight, 
    enabledEvidenceTypes, 
    toggleEvidenceHighlight,
    toggleEvidenceType,
    enableAllEvidenceTypes,
    disableAllEvidenceTypes,
  } = useDocumentStore();

  // Group by evidence type, only show enabled types
  const groupedEvidences = React.useMemo(() => {
    const groups: Record<string, Evidence[]> = {};
    evidences.forEach(evidence => {
      // 只包含启用的证据类型
      if (!enabledEvidenceTypes.includes(evidence.type)) return;
      
      if (!groups[evidence.type]) {
        groups[evidence.type] = [];
      }
      groups[evidence.type].push(evidence);
    });
    return groups;
  }, [evidences, enabledEvidenceTypes]);

  // Count enabled evidences
  const enabledCount = React.useMemo(() => {
    return evidences.filter(e => enabledEvidenceTypes.includes(e.type)).length;
  }, [evidences, enabledEvidenceTypes]);

  // Check if all enabled
  const allEnabled = enabledEvidenceTypes.length === Object.values(EvidenceType).length;
  // Check if all disabled
  const allDisabled = enabledEvidenceTypes.length === 0;

  return (
    <div className="evidence-panel">
      {/* Document info */}
      <div className="evidence-panel-header">
        <FileText size={20} />
        <div className="doc-info">
          <h3 className="doc-title">{docTitle || 'Document Analysis'}</h3>
          <p className="doc-stats">Showing {enabledCount} / {evidences.length} evidences</p>
        </div>
      </div>

      {/* Global toggle */}
      <div className="evidence-global-controls">
        <button 
          className={`control-btn ${showEvidenceHighlight ? 'active' : ''}`}
          onClick={toggleEvidenceHighlight}
          title={showEvidenceHighlight ? 'Turn off evidence highlighting' : 'Turn on evidence highlighting'}
        >
          {showEvidenceHighlight ? <Eye size={16} /> : <EyeOff size={16} />}
          <span>{showEvidenceHighlight ? 'Highlight On' : 'Highlight Off'}</span>
        </button>
      </div>

      {/* Type filter bar */}
      <div className="evidence-type-filters">
        <div className="filter-header">
          <span className="filter-title">Filter by Type</span>
          <div className="filter-actions">
            <button 
              className="filter-action-btn" 
              onClick={enableAllEvidenceTypes}
              disabled={allEnabled}
            >
              Select All
            </button>
            <button 
              className="filter-action-btn" 
              onClick={disableAllEvidenceTypes}
              disabled={allDisabled}
            >
              Deselect All
            </button>
          </div>
        </div>
        <div className="filter-tags">
          {Object.values(EvidenceType).map((type) => {
            const isEnabled = enabledEvidenceTypes.includes(type);
            const count = evidences.filter(e => e.type === type).length;
            return (
              <button
                key={type}
                className={`filter-tag ${isEnabled ? 'enabled' : 'disabled'}`}
                onClick={() => toggleEvidenceType(type)}
                style={{
                  '--type-color': EvidenceTypeColors[type],
                } as React.CSSProperties}
              >
                {isEnabled ? <CheckSquare size={12} /> : <Square size={12} />}
                <span className="tag-type">{type}</span>
                <span className="tag-count">{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Evidence list */}
      <div className="evidence-list">
        {Object.keys(groupedEvidences).length === 0 ? (
          <div className="evidence-empty">
            <p>No evidence types selected</p>
            <p className="evidence-empty-hint">Please select evidence types above</p>
          </div>
        ) : (
          Object.entries(groupedEvidences).map(([type, items]) => (
            <div key={type} className="evidence-group">
              <div 
                className="evidence-group-header"
                style={{ borderLeftColor: EvidenceTypeColors[type as EvidenceTypeValue] }}
              >
                <span 
                  className="evidence-type-badge"
                  style={{ 
                    backgroundColor: EvidenceTypeColors[type as EvidenceTypeValue] + '20',
                    color: EvidenceTypeColors[type as EvidenceTypeValue]
                  }}
                >
                  {type}
                </span>
                <span className="evidence-type-name">{typeNames[type as EvidenceTypeValue]}</span>
                <span className="evidence-count">{items.length}</span>
              </div>
              
              <div className="evidence-items">
                {items.map(evidence => (
                  <div
                    key={evidence.id}
                    className={`evidence-item ${activeEvidenceId === evidence.id ? 'active' : ''}`}
                    onClick={() => onEvidenceClick(evidence)}
                  >
                    <div className="evidence-keyword">
                      <span className="keyword-text">{evidence.keyword}</span>
                      <ArrowRight size={14} className="keyword-arrow" />
                    </div>
                    <p className="evidence-description">{evidence.description}</p>
                    <div className="evidence-meta">
                      <span className="confidence">Confidence: {(evidence.confidence * 100).toFixed(0)}%</span>
                      <span className="positions">{evidence.positions.length} citation(s)</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
