/**
 * URL状态持久化工具
 * 用于保存和恢复视图状态到URL参数
 */
import type { ViewStateParams, TriplePanelState } from '../types';

export const URLStateManager = {
  /**
   * 从URL解析状态
   */
  parseFromURL(): ViewStateParams {
    const params = new URLSearchParams(window.location.search);
    return {
      docId: params.get('docId') || undefined,
      evidenceId: params.get('evidenceId') || undefined,
      position: params.get('position') || undefined,
      panel: (params.get('panel') as 'original' | 'translated') || undefined,
    };
  },

  /**
   * 将状态同步到URL（不刷新页面）
   */
  syncToURL(state: ViewStateParams): void {
    const params = new URLSearchParams();
    
    if (state.docId) params.set('docId', state.docId);
    if (state.evidenceId) params.set('evidenceId', state.evidenceId);
    if (state.position) params.set('position', state.position);
    if (state.panel) params.set('panel', state.panel);

    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', newUrl);
  },

  /**
   * 生成分享链接
   */
  generateShareLink(state: ViewStateParams): string {
    const params = new URLSearchParams();
    
    if (state.docId) params.set('docId', state.docId);
    if (state.evidenceId) params.set('evidenceId', state.evidenceId);
    if (state.position) params.set('position', state.position);
    if (state.panel) params.set('panel', state.panel);

    return `${window.location.origin}${window.location.pathname}?${params.toString()}`;
  },

  /**
   * 从状态对象生成URL参数
   */
  stateToParams(
    docId: string,
    panelState: TriplePanelState
  ): ViewStateParams {
    return {
      docId,
      evidenceId: panelState.activeEvidenceId || undefined,
      position: panelState.highlightedPosition 
        ? `${panelState.highlightedPosition.paragraphIndex}:${panelState.highlightedPosition.startOffset}` 
        : undefined,
    };
  },
};
