/**
 * Intersection Observer Hook
 * 精准追踪当前可见章节，支持节流优化
 */
import { useEffect, useRef, useState, useCallback, useMemo } from 'react';

interface UseIntersectionObserverOptions {
  root?: Element | null;
  rootMargin?: string;
  threshold?: number | number[];
  throttleMs?: number;
}

interface UseIntersectionObserverReturn {
  visibleIds: Set<string>;
  mostVisibleId: string | null;
  observe: (element: Element, id: string) => void;
  unobserve: (element: Element) => void;
}

export function useIntersectionObserver(
  options: UseIntersectionObserverOptions = {}
): UseIntersectionObserverReturn {
  const {
    root = null,
    rootMargin = '-10% 0px -60% 0px',
    threshold = [0, 0.25, 0.5, 0.75, 1],
    throttleMs = 100,
  } = options;
  
  const [visibleEntries, setVisibleEntries] = useState<Map<string, number>>(new Map());
  const observerRef = useRef<IntersectionObserver | null>(null);
  const elementToIdMap = useRef<Map<Element, string>>(new Map());
  const throttleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingEntries = useRef<IntersectionObserverEntry[]>([]);
  
  const processEntries = useCallback(() => {
    const entries = pendingEntries.current;
    pendingEntries.current = [];
    
    setVisibleEntries(prev => {
      const next = new Map(prev);
      
      entries.forEach(entry => {
        const id = elementToIdMap.current.get(entry.target);
        if (!id) return;
        
        if (entry.isIntersecting) {
          const visibilityScore = entry.intersectionRatio * entry.intersectionRect.height;
          next.set(id, visibilityScore);
        } else {
          next.delete(id);
        }
      });
      
      return next;
    });
  }, []);
  
  const throttledProcess = useCallback(() => {
    if (throttleTimer.current) return;
    
    throttleTimer.current = setTimeout(() => {
      processEntries();
      throttleTimer.current = null;
    }, throttleMs);
  }, [processEntries, throttleMs]);
  
  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        pendingEntries.current.push(...entries);
        throttledProcess();
      },
      { root, rootMargin, threshold }
    );
    
    return () => {
      observerRef.current?.disconnect();
      if (throttleTimer.current) {
        clearTimeout(throttleTimer.current);
      }
    };
  }, [root, rootMargin, threshold, throttledProcess]);
  
  const observe = useCallback((element: Element, id: string) => {
    elementToIdMap.current.set(element, id);
    observerRef.current?.observe(element);
  }, []);
  
  const unobserve = useCallback((element: Element) => {
    elementToIdMap.current.delete(element);
    observerRef.current?.unobserve(element);
  }, []);
  
  const mostVisibleId = useMemo(() => {
    let maxScore = 0;
    let maxId: string | null = null;
    
    visibleEntries.forEach((score, id) => {
      if (score > maxScore) {
        maxScore = score;
        maxId = id;
      }
    });
    
    return maxId;
  }, [visibleEntries]);
  
  const visibleIds = useMemo(() => 
    new Set(visibleEntries.keys()),
    [visibleEntries]
  );
  
  return {
    visibleIds,
    mostVisibleId,
    observe,
    unobserve,
  };
}
