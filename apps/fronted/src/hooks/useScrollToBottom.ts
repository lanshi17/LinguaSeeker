import { useEffect, useRef, DependencyList } from 'react';

/**
 * Hook for auto-scrolling a container to the bottom with smooth animation.
 * Useful for chat interfaces, log viewers, and message feeds.
 *
 * @param deps - Dependency array that triggers scroll on change (e.g., messages array)
 * @returns ref - Ref to attach to the scroll container element
 *
 * @example
 * const scrollRef = useScrollToBottom([messages]);
 * return <div ref={scrollRef} className="messages-container" />;
 */
export function useScrollToBottom(deps: DependencyList) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    containerRef.current?.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: 'smooth'
    });
  }, deps);

  return containerRef;
}
