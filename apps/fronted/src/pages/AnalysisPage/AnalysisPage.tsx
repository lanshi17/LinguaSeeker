/**
 * Analysis Page
 * Triple-panel display: Original PDF / Markdown Translation / Evidence Panel
 * Supports state persistence and sharing
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Share2, AlertCircle } from 'lucide-react';
import { OptimizedTriplePanel } from '../../components/OptimizedTriplePanel/OptimizedTriplePanel';
import { useDocumentStore } from '../../store/documentStore';
import { getDocument } from '../../services/documentApi';
import { URLStateManager } from '../../utils/urlState';
import type { DocumentData } from '../../types';
import './AnalysisPage.css';

export const AnalysisPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { setDocument, setLoading, setError } = useDocumentStore();
  
  const [doc, setDoc] = useState<DocumentData | null>(null);
  const [loading, setLocalLoading] = useState(true);
  const [error, setLocalError] = useState<string | null>(null);
  const [shareCopied, setShareCopied] = useState(false);

  useEffect(() => {
    const fetchDocument = async () => {
      if (!id) {
        setLocalError('Document ID is required');
        setLocalLoading(false);
        return;
      }

      setLocalLoading(true);
      setLocalError(null);
      setLoading(true);

      try {
        const document = await getDocument(id);
        setDoc(document);
        setDocument(document);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load';
        setLocalError(message);
        setError(message);
      } finally {
        setLocalLoading(false);
        setLoading(false);
      }
    };

    fetchDocument();
  }, [id, setDocument, setLoading, setError]);

  /**
   * Share link
   */
  const handleShare = () => {
    if (!doc) return;
    const link = URLStateManager.generateShareLink({ 
      docId: doc.id,
      evidenceId: useDocumentStore.getState().selectedEvidenceId || undefined
    });
    navigator.clipboard.writeText(link);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="analysis-page loading">
        <Loader2 className="spinner" size={48} />
        <p>Analyzing document...</p>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="analysis-page error">
        <AlertCircle size={48} className="error-icon" />
        <h2>⚠️ {error || 'Failed to load document'}</h2>
        <button onClick={() => navigate('/')} className="back-btn">
          <ArrowLeft size={16} /> Back to Home
        </button>
      </div>
    );
  }

  return (
    <div className="analysis-page">
      <header className="analysis-header">
        <button onClick={() => navigate('/')} className="nav-btn">
          <ArrowLeft size={18} /> Back
        </button>
        
        <div className="doc-title-wrapper">
          <h1 className="doc-title">{doc.title}</h1>
          {doc.pmid && <span className="doc-pmid">PMID: {doc.pmid}</span>}
        </div>

        <div className="header-actions">
          <button onClick={handleShare} className="share-btn">
            <Share2 size={16} />
            {shareCopied ? 'Copied!' : 'Share'}
          </button>
        </div>
      </header>

      <main className="analysis-content">
        <OptimizedTriplePanel document={doc} onShare={handleShare} />
      </main>
    </div>
  );
};
