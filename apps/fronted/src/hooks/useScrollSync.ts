/**
 * Simplified scroll sync hook
 * Chapter-level sync only, no intra-chapter progress sync to avoid dragging issues
 */
import { useRef, useCallback, useState } from 'react';
import type { Chapter } from './useChapters';

export interface ScrollState {
  chapterIndex: number;
}

interface UseScrollSyncOptions {
  originalChapters: Chapter[];
  translatedChapters: Chapter[];
  chapterMap: Map<number, number>; // original -> translated
  reverseChapterMap: Map<number, number>; // translated -> original
  onSync?: (source: 'original' | 'translated', state: ScrollState) => void;
}

interface UseScrollSyncReturn {
  originalState: ScrollState;
  translatedState: ScrollState;
  setOriginalRef: (el: HTMLElement | null) => void;
  setTranslatedRef: (el: HTMLElement | null) => void;
  handleOriginalScroll: () => void;
  handleTranslatedScroll: () => void;
  syncToChapter: (chapterIndex: number, target: 'original' | 'translated') => void;
  setChapterState: (chapterIndex: number, target: 'original' | 'translated') => void;
  isSyncing: () => boolean;
  pauseSync: () => void;
  resumeSync: () => void;
}

// Throttle function
function createThrottle<T extends () => void>(fn: T, ms: number): () => void {
  let lastTime = 0;
  return () => {
    const now = Date.now();
    if (now - lastTime >= ms) {
      lastTime = now;
      fn();
    }
  };
}

/**
 * Calculate current chapter index
 */
function calculateCurrentChapter(container: HTMLElement): number {
  const chapterElements = container.querySelectorAll('[data-chapter-id]');
  if (chapterElements.length === 0) return 0;
  
  const containerRect = container.getBoundingClientRect();
  const viewportCenter = containerRect.top + containerRect.height / 3;
  
  let currentIndex = 0;
  let minDistance = Infinity;
  
  chapterElements.forEach((el, index) => {
    const rect = el.getBoundingClientRect();
    const elCenter = rect.top + rect.height / 2;
    const distance = Math.abs(elCenter - viewportCenter);
    
    if (distance < minDistance) {
      minDistance = distance;
      currentIndex = index;
    }
  });
  
  return currentIndex;
}

export function useScrollSync(options: UseScrollSyncOptions): UseScrollSyncReturn {
  const {
    originalChapters,
    translatedChapters,
    chapterMap,
    reverseChapterMap,
    onSync,
  } = options;
  
  const originalRef = useRef<HTMLElement | null>(null);
  const translatedRef = useRef<HTMLElement | null>(null);
  const isSyncing = useRef(false);
  const isPaused = useRef(false);
  const lastSyncedChapter = useRef<number>(-1);
  
  const [originalState, setOriginalState] = useState<ScrollState>({ chapterIndex: 0 });
  const [translatedState, setTranslatedState] = useState<ScrollState>({ chapterIndex: 0 });
  
  // Perform chapter sync (only when chapter changes)
  const performSync = useCallback((
    sourceChapterIndex: number,
    source: 'original' | 'translated'
  ) => {
    // Avoid duplicate sync for same chapter
    if (sourceChapterIndex === lastSyncedChapter.current && isSyncing.current) {
      return;
    }
    lastSyncedChapter.current = sourceChapterIndex;
    
    const isSourceOriginal = source === 'original';
    const targetRef = isSourceOriginal ? translatedRef : originalRef;
    const targetChapters = isSourceOriginal ? translatedChapters : originalChapters;
    const setTargetState = isSourceOriginal ? setTranslatedState : setOriginalState;
    
    if (!targetRef.current) return;
    
    // Find corresponding chapter
    const mappedChapterIndex = isSourceOriginal
      ? (chapterMap.get(sourceChapterIndex) ?? sourceChapterIndex)
      : (reverseChapterMap.get(sourceChapterIndex) ?? sourceChapterIndex);
    
    // Boundary check
    const safeIndex = Math.max(0, Math.min(mappedChapterIndex, targetChapters.length - 1));
    const targetChapter = targetChapters[safeIndex];
    
    if (!targetChapter) return;
    
    // Find target chapter element
    const targetElement = targetRef.current.querySelector(
      `[data-chapter-id="${targetChapter.id}"]`
    ) as HTMLElement | null;
    
    if (!targetElement) return;
    
    // Set sync lock
    isSyncing.current = true;
    
    // Only sync to chapter start, no internal progress sync
    targetRef.current.scrollTo({
      top: targetElement.offsetTop,
      behavior: 'smooth',
    });
    
    // Update target state
    setTargetState({ chapterIndex: safeIndex });
    
    // Release sync lock
    setTimeout(() => {
      isSyncing.current = false;
    }, 300);
  }, [chapterMap, originalChapters, translatedChapters]);
  
  // Handle original panel scroll (throttled) - only detect chapter changes
  const handleOriginalScrollRaw = useCallback(() => {
    if (isSyncing.current || isPaused.current || !originalRef.current) return;
    
    const chapterIndex = calculateCurrentChapter(originalRef.current);
    
    // Only update state and sync when chapter changes
    if (chapterIndex !== originalState.chapterIndex) {
      const newState = { chapterIndex };
      setOriginalState(newState);
      onSync?.('original', newState);
      performSync(chapterIndex, 'original');
    }
  }, [originalState.chapterIndex, onSync, performSync]);
  
  // Handle translated panel scroll (throttled)
  const handleTranslatedScrollRaw = useCallback(() => {
    if (isSyncing.current || isPaused.current || !translatedRef.current) return;
    
    const chapterIndex = calculateCurrentChapter(translatedRef.current);
    
    if (chapterIndex !== translatedState.chapterIndex) {
      const newState = { chapterIndex };
      setTranslatedState(newState);
      onSync?.('translated', newState);
      performSync(chapterIndex, 'translated');
    }
  }, [translatedState.chapterIndex, onSync, performSync]);
  
  // Apply throttling - use longer throttle time
  const handleOriginalScroll = useRef(createThrottle(handleOriginalScrollRaw, 150)).current;
  const handleTranslatedScroll = useRef(createThrottle(handleTranslatedScrollRaw, 150)).current;
  
  // Jump to specified chapter (for evidence navigation) - no sync trigger to avoid bounce-back
  const syncToChapter = useCallback((chapterIndex: number, target: 'original' | 'translated') => {
    const isOriginal = target === 'original';
    const chapters = isOriginal ? originalChapters : translatedChapters;
    const ref = isOriginal ? originalRef : translatedRef;
    const setState = isOriginal ? setOriginalState : setTranslatedState;
    
    const safeIndex = Math.max(0, Math.min(chapterIndex, chapters.length - 1));
    const chapter = chapters[safeIndex];
    
    if (!chapter || !ref.current) return;
    
    const element = ref.current.querySelector(`[data-chapter-id="${chapter.id}"]`) as HTMLElement | null;
    if (!element) return;
    
    // Set temporary lock to prevent scroll listener from syncing back
    isSyncing.current = true;
    
    // Update state first, mark current chapter
    setState({ chapterIndex: safeIndex });
    
    // Calculate scroll position relative to the scroll container
    // element.offsetTop gives position relative to offsetParent, we need to account for the container's own offset
    let scrollTop = element.offsetTop;
    
    // If the element's offsetParent is not the scroll container itself, we need to adjust
    let offsetParent = element.offsetParent as HTMLElement;
    while (offsetParent && offsetParent !== ref.current) {
      scrollTop += offsetParent.offsetTop;
      offsetParent = offsetParent.offsetParent as HTMLElement;
    }
    
    // Add small offset to ensure chapter title is visible below any sticky headers
    scrollTop = Math.max(0, scrollTop - 16);
    
    // Execute scroll
    ref.current.scrollTo({
      top: scrollTop,
      behavior: 'smooth',
    });
    
    // Extend lock time to ensure scroll animation completes
    setTimeout(() => {
      isSyncing.current = false;
    }, 500);
  }, [originalChapters, translatedChapters]);
  
  // Pause sync (used during evidence navigation)
  const pauseSync = useCallback(() => {
    isPaused.current = true;
  }, []);
  
  // Resume sync
  const resumeSync = useCallback(() => {
    isPaused.current = false;
  }, []);
  
  // Manually set chapter state (used to update outline after evidence navigation)
  const setChapterState = useCallback((chapterIndex: number, target: 'original' | 'translated') => {
    const isOriginal = target === 'original';
    const setState = isOriginal ? setOriginalState : setTranslatedState;
    const chapters = isOriginal ? originalChapters : translatedChapters;
    
    const safeIndex = Math.max(0, Math.min(chapterIndex, chapters.length - 1));
    setState({ chapterIndex: safeIndex });
    
    // Also update mapped chapter on other side
    if (isOriginal && chapterMap.has(safeIndex)) {
      const mappedIndex = chapterMap.get(safeIndex);
      if (mappedIndex !== undefined) {
        setTranslatedState({ chapterIndex: mappedIndex });
      }
    } else if (!isOriginal) {
      // Reverse lookup mapping
      const reverseMap = Array.from(chapterMap.entries()).find(([, v]) => v === safeIndex);
      if (reverseMap) {
        setOriginalState({ chapterIndex: reverseMap[0] });
      }
    }
  }, [originalChapters, translatedChapters, chapterMap]);
  
  // Helper functions to set refs
  const setOriginalRef = useCallback((el: HTMLElement | null) => {
    originalRef.current = el;
  }, []);
  
  const setTranslatedRef = useCallback((el: HTMLElement | null) => {
    translatedRef.current = el;
  }, []);
  
  return {
    originalState,
    translatedState,
    setOriginalRef,
    setTranslatedRef,
    handleOriginalScroll,
    handleTranslatedScroll,
    syncToChapter,
    setChapterState,
    isSyncing: () => isSyncing.current,
    pauseSync,
    resumeSync,
  };
}
