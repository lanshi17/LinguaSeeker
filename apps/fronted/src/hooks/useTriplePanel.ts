/**
 * 三屏联动 Hook
 * 管理三屏滚动同步和防循环触发
 */
import { useState, useRef, useCallback, useEffect } from 'react';
import type { TriplePanelState, Evidence } from '../types';
import { URLStateManager } from '../utils/helpers/urlState';

interface UseTriplePanelOptions {
  docId: string;
  onStateChange?: (state: TriplePanelState) => void;
}

export function useTriplePanel(options: UseTriplePanelOptions) {
  const { docId, onStateChange } = options;
  
  // 状态
  const [state, setState] = useState<TriplePanelState>({
    activeEvidenceId: null,
    scrollRatio: 0,
    highlightedPosition: null,
    pdfPage: 1,
  });

  // 防止循环触发的锁
  const isScrolling = useRef(false);
  const scrollTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const originalPanelRef = useRef<HTMLDivElement>(null);
  const translatedPanelRef = useRef<HTMLDivElement>(null);

  // 同步状态到URL
  useEffect(() => {
    const params = URLStateManager.stateToParams(docId, state);
    URLStateManager.syncToURL(params);
    onStateChange?.(state);
  }, [state, docId, onStateChange]);

  /**
   * 处理滚动事件（带防循环保护）
   */
  const handleScroll = useCallback((source: 'original' | 'translated', ratio: number) => {
    if (isScrolling.current) return;
    
    isScrolling.current = true;
    setState(prev => ({ ...prev, scrollRatio: ratio }));

    // 同步另一侧滚动
    const targetRef = source === 'original' ? translatedPanelRef : originalPanelRef;
    const targetEl = targetRef.current;
    
    if (targetEl) {
      const maxScroll = targetEl.scrollHeight - targetEl.clientHeight;
      targetEl.scrollTop = ratio * maxScroll;
    }

    // 释放锁
    if (scrollTimeout.current) {
      clearTimeout(scrollTimeout.current);
    }
    scrollTimeout.current = setTimeout(() => {
      isScrolling.current = false;
    }, 50);
  }, []);

  /**
   * 激活证据并滚动到对应位置
   */
  const activateEvidence = useCallback((evidence: Evidence) => {
    const position = evidence.positions[0];
    if (!position) return;

    setState(prev => ({
      ...prev,
      activeEvidenceId: evidence.id,
      highlightedPosition: position,
    }));

    // 滚动到对应位置
    const scrollToPosition = (panelRef: React.RefObject<HTMLDivElement | null>) => {
      const panel = panelRef.current;
      if (!panel) return;

      // 查找目标元素（通过data属性标记）
      const targetEl = panel.querySelector(
        `[data-position-id="${position.id}"]`
      ) as HTMLElement;
      
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // 添加高亮效果
        targetEl.classList.add('evidence-highlight');
        setTimeout(() => targetEl.classList.remove('evidence-highlight'), 2000);
      }
    };

    scrollToPosition(originalPanelRef);
    scrollToPosition(translatedPanelRef);
  }, []);

  /**
   * 从URL恢复状态
   */
  const restoreFromURL = useCallback((evidences: Evidence[]) => {
    const params = URLStateManager.parseFromURL();
    
    if (params.evidenceId) {
      const evidence = evidences.find(e => e.id === params.evidenceId);
      if (evidence) {
        setState(prev => ({
          ...prev,
          activeEvidenceId: params.evidenceId || null,
        }));
      }
    }
  }, []);

  return {
    state,
    setState,
    originalPanelRef,
    translatedPanelRef,
    handleScroll,
    activateEvidence,
    restoreFromURL,
    isScrolling: isScrolling.current,
  };
}
