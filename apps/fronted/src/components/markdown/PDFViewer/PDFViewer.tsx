/**
 * PDF 查看器组件
 * 集成 PDF.js 渲染原文，支持高亮证据位置
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as pdfjs from 'pdfjs-dist';
import type { Evidence, TextPosition } from '../../../types';
import './PDFViewer.css';

// 设置 PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

interface PDFViewerProps {
  pdfUrl: string;
  evidences: Evidence[];
  highlightedPosition: TextPosition | null;
  currentPage: number;
  onPageChange: (page: number) => void;
  panelRef?: React.RefObject<HTMLDivElement | null>;
  onScroll?: (ratio: number) => void;
}

export const PDFViewer: React.FC<PDFViewerProps> = ({
  pdfUrl,
  evidences,
  highlightedPosition,
  currentPage,
  onPageChange,
  panelRef,
  onScroll,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [pdfDoc, setPdfDoc] = useState<pdfjs.PDFDocumentProxy | null>(null);
  const [scale, setScale] = useState(1.5);
  const [numPages, setNumPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 加载 PDF
  useEffect(() => {
    const loadPDF = async () => {
      try {
        setLoading(true);
        const loadingTask = pdfjs.getDocument(pdfUrl);
        const pdf = await loadingTask.promise;
        setPdfDoc(pdf);
        setNumPages(pdf.numPages);
        setLoading(false);
      } catch (err) {
        setError('PDF 加载失败');
        setLoading(false);
        console.error('PDF load error:', err);
      }
    };

    if (pdfUrl) {
      loadPDF();
    }
  }, [pdfUrl]);

  // 渲染页面
  useEffect(() => {
    const renderPage = async () => {
      if (!pdfDoc || !canvasRef.current) return;

      const page = await pdfDoc.getPage(currentPage);
      const viewport = page.getViewport({ scale });
      
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');
      if (!context) return;

      canvas.height = viewport.height;
      canvas.width = viewport.width;

      const renderContext = {
        canvasContext: context,
        viewport: viewport,
        canvas: canvas,
      };

      await page.render(renderContext as any).promise;
    };

    renderPage();
  }, [pdfDoc, currentPage, scale]);

  // 处理滚动
  const handleScroll = useCallback(() => {
    if (!containerRef.current || !onScroll) return;
    const el = containerRef.current;
    const ratio = el.scrollTop / (el.scrollHeight - el.clientHeight);
    onScroll(ratio);
  }, [onScroll]);

  // 缩略控制
  const zoomIn = () => setScale((s) => Math.min(s + 0.25, 3));
  const zoomOut = () => setScale((s) => Math.max(s - 0.25, 0.5));
  const resetZoom = () => setScale(1.5);

  if (loading) {
    return (
      <div className="pdf-viewer loading">
        <div className="spinner" />
        <p>加载 PDF...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pdf-viewer error">
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="pdf-viewer" ref={panelRef}>
      {/* 工具栏 */}
      <div className="pdf-toolbar">
        <div className="page-controls">
          <button
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            disabled={currentPage <= 1}
          >
            ←
          </button>
          <span className="page-info">
            {currentPage} / {numPages}
          </span>
          <button
            onClick={() => onPageChange(Math.min(numPages, currentPage + 1))}
            disabled={currentPage >= numPages}
          >
            →
          </button>
        </div>
        <div className="zoom-controls">
          <button onClick={zoomOut}>-</button>
          <span>{Math.round(scale * 100)}%</span>
          <button onClick={zoomIn}>+</button>
          <button onClick={resetZoom}>重置</button>
        </div>
      </div>

      {/* 画布容器 */}
      <div
        className="pdf-container"
        ref={containerRef}
        onScroll={handleScroll}
      >
        <canvas ref={canvasRef} className="pdf-canvas" />
        
        {/* 证据高亮层 */}
        <div className="highlight-layer">
          {evidences.map((ev) =>
            ev.positions.map((pos, idx) => (
              <div
                key={`${ev.id}-${idx}`}
                className={`evidence-highlight ${ev.type} ${
                  highlightedPosition?.id === pos.id ? 'active' : ''
                }`}
                style={{
                  // 根据后端返回的位置数据定位
                  // 这里需要根据实际 PDF 坐标映射
                  top: `${pos.paragraphIndex * 50}px`,
                  left: '10%',
                  width: '80%',
                  height: '30px',
                }}
                title={`${ev.type}: ${ev.description}`}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
};
