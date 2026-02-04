/**
 * 三屏联动组件
 * 左屏: PDF 原文 | 中屏: Markdown 译文 | 右屏: 证据列表
 * 支持同步滚动、点击跳转、URL状态持久化
 */
import React, { useEffect, useRef, useCallback } from 'react';
import { useDocumentStore } from '../../store/documentStore';
import { MarkdownViewer } from '../MarkdownViewer/MarkdownViewer';
import { EvidencePanel } from '../EvidencePanel/EvidencePanel';
import { PDFViewer } from '../PDFViewer/PDFViewer';
import { URLStateManager } from '../../utils/urlState';
import type { DocumentData, Evidence } from '../../types';
import './TriplePanel.css';

interface TriplePanelProps {
  document: DocumentData;
  onShare?: () => void;
}

export const TriplePanel: React.FC<TriplePanelProps> = ({ document, onShare }) => {
  const {
    selectedEvidenceId,
    highlightedPosition,
    pdfCurrentPage,
    selectEvidence,
    setPdfPage,
    setMarkdownScroll,
  } = useDocumentStore();

  const originalPanelRef = useRef<HTMLDivElement>(null);
  const translatedPanelRef = useRef<HTMLDivElement>(null);
  const isScrolling = useRef(false);
  const scrollTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 同步状态到 URL
  useEffect(() => {
    const params = URLStateManager.stateToParams(document.id, {
      activeEvidenceId: selectedEvidenceId,
      scrollRatio: 0,
      highlightedPosition,
      pdfPage: pdfCurrentPage,
    });
    URLStateManager.syncToURL(params);
  }, [document.id, selectedEvidenceId, highlightedPosition]);

  // 从 URL 恢复状态
  useEffect(() => {
    const params = URLStateManager.parseFromURL();
    if (params.evidenceId) {
      const evidence = document.evidences.find((e) => e.id === params.evidenceId);
      if (evidence) {
        selectEvidence(evidence.id, evidence.positions[0]);
      }
    }
  }, [document.evidences, selectEvidence]);

  /**
   * 处理证据点击 - 三屏同步跳转
   */
  const handleEvidenceClick = useCallback(
    (evidence: Evidence) => {
      const position = evidence.positions[0];
      if (!position) return;

      selectEvidence(evidence.id, position);

      // 1. PDF 跳转到对应页
      if (position.paragraphIndex > 0) {
        setPdfPage(Math.min(position.paragraphIndex, 10)); // 简化映射
      }

      // 2. Markdown 滚动到对应位置
      const scrollToPosition = (panelRef: React.RefObject<HTMLDivElement | null>) => {
        const panel = panelRef.current;
        if (!panel) return;

        const targetEl = panel.querySelector(`[data-position-id="${position.id}"]`) as HTMLElement;
        if (targetEl) {
          targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
          targetEl.classList.add('evidence-highlight-pulse');
          setTimeout(() => targetEl.classList.remove('evidence-highlight-pulse'), 2000);
        }
      };

      scrollToPosition(originalPanelRef);
      scrollToPosition(translatedPanelRef);
    },
    [selectEvidence, setPdfPage]
  );

  /**
   * Markdown 滚动同步（防循环）
   */
  const handleMarkdownScroll = useCallback(
    (source: 'original' | 'translated', ratio: number) => {
      if (isScrolling.current) return;

      isScrolling.current = true;
      setMarkdownScroll(ratio);

      // 同步另一侧
      const targetRef = source === 'original' ? translatedPanelRef : originalPanelRef;
      const targetEl = targetRef.current;
      if (targetEl) {
        const maxScroll = targetEl.scrollHeight - targetEl.clientHeight;
        targetEl.scrollTop = ratio * maxScroll;
      }

      // 释放锁
      if (scrollTimeout.current) clearTimeout(scrollTimeout.current);
      scrollTimeout.current = setTimeout(() => {
        isScrolling.current = false;
      }, 50);
    },
    [setMarkdownScroll]
  );

  // 判断是否为双语 PDF（如果有 PDF URL）
  const hasPDF = document.originalMarkdown.includes('data:application/pdf') || 
                 document.id === 'demo'; // demo 暂时没有 PDF

  return (
    <div className="triple-panel">
      {/* 左屏 - PDF 原文或 Markdown 原文 */}
      <div className="panel panel-original">
        <div className="panel-header">
          <span className="panel-title">原文</span>
          <span className="panel-badge">{hasPDF ? 'PDF' : 'Markdown'}</span>
        </div>
        <div className="panel-content">
          {hasPDF && document.pdfUrl ? (
            <PDFViewer
              pdfUrl={document.pdfUrl}
              evidences={document.evidences}
              highlightedPosition={highlightedPosition}
              currentPage={pdfCurrentPage}
              onPageChange={setPdfPage}
              panelRef={originalPanelRef}
            />
          ) : (
            <MarkdownViewer
              content={document.originalMarkdown}
              evidences={document.evidences}
              highlightedPosition={highlightedPosition}
              panelRef={originalPanelRef}
              onScroll={(ratio) => handleMarkdownScroll('original', ratio)}
            />
          )}
        </div>
      </div>

      {/* 中屏 - Markdown 英文译文 */}
      <div className="panel panel-translated">
        <div className="panel-header">
          <span className="panel-title">英文译文</span>
          <span className="panel-badge">Markdown</span>
        </div>
        <div className="panel-content">
          <MarkdownViewer
            content={document.translatedMarkdown}
            evidences={document.evidences}
            highlightedPosition={highlightedPosition}
            panelRef={translatedPanelRef}
            onScroll={(ratio) => handleMarkdownScroll('translated', ratio)}
          />
        </div>
      </div>

      {/* 右屏 - 证据面板 */}
      <div className="panel panel-evidence">
        <EvidencePanel
          evidences={document.evidences}
          activeEvidenceId={selectedEvidenceId}
          onEvidenceClick={handleEvidenceClick}
          docTitle={document.title}
        />
      </div>

      {/* 分享按钮 */}
      {onShare && (
        <button className="share-button" onClick={onShare} title="复制分享链接">
          🔗
        </button>
      )}
    </div>
  );
};
