import { useEffect, useRef } from 'react';

/**
 * Hook for auto-scrolling a container to the bottom with smooth animation.
 * Useful for chat interfaces, log viewers, and message feeds.
 *
 * @param trigger - A value that triggers scroll when it changes (e.g., messages.length)
 * @returns ref - Ref to attach to the scroll container element
 *
 * @example
 * const scrollRef = useScrollToBottom(messages.length);
 * return <div ref={scrollRef} className="messages-container" />;
 */
export function useScrollToBottom(trigger: unknown) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    containerRef.current?.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: 'smooth'
    });
  }, [trigger]);

  return containerRef;
}
