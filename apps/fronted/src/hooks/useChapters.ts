/**
 * 章节解析与同步 Hook
 * 提取 Markdown 章节结构，支持跨语言对齐
 */
import { useMemo, useCallback } from 'react';

export interface Chapter {
  id: string;
  level: number;
  title: string;
  index: number;
  charOffset: number;
}

interface UseChaptersOptions {
  originalContent: string;
  translatedContent: string;
}

interface UseChaptersReturn {
  originalChapters: Chapter[];
  translatedChapters: Chapter[];
  chapterMap: Map<number, number>; // original index -> translated index
  reverseChapterMap: Map<number, number>; // translated index -> original index
  findChapterByOffset: (offset: number, chapters: Chapter[]) => Chapter | null;
}

const CHAPTER_REGEX = /^(#{1,6})\s+(.+)$/gm;

/**
 * 解析 Markdown 章节结构
 */
function parseChapters(content: string): Chapter[] {
  const chapters: Chapter[] = [];
  let match;
  
  while ((match = CHAPTER_REGEX.exec(content)) !== null) {
    const level = match[1].length;
    const title = match[2].trim();
    const charOffset = match.index;
    
    chapters.push({
      id: `ch-${chapters.length}`,
      level,
      title,
      index: chapters.length,
      charOffset,
    });
  }
  
  return chapters;
}

/**
 * 简单的章节标题相似度匹配（用于双语对齐）
 */
function calculateSimilarity(title1: string, title2: string): number {
  // 移除标点、数字，转小写
  const normalize = (s: string) => 
    s.toLowerCase().replace(/[^\w\u4e00-\u9fa5]/g, '');
  
  const t1 = normalize(title1);
  const t2 = normalize(title2);
  
  // 如果一方包含另一方
  if (t1.includes(t2) || t2.includes(t1)) return 0.8;
  
  // 计算共同字符比例
  const set1 = new Set(t1);
  const set2 = new Set(t2);
  const intersection = new Set([...set1].filter(x => set2.has(x)));
  const union = new Set([...set1, ...set2]);
  
  return intersection.size / union.size;
}

/**
 * 构建双语章节映射
 */
function buildChapterMap(
  originalChapters: Chapter[],
  translatedChapters: Chapter[]
): Map<number, number> {
  const map = new Map<number, number>();
  
  // 按顺序匹配相似度最高的章节
  let transIdx = 0;
  originalChapters.forEach((origCh, origIdx) => {
    let bestMatch = -1;
    let bestScore = 0;
    
    // 在翻译章节中查找最佳匹配（只在附近范围内查找）
    const searchRange = 3;
    const start = Math.max(0, transIdx - searchRange);
    const end = Math.min(translatedChapters.length, transIdx + searchRange + 1);
    
    for (let i = start; i < end; i++) {
      const score = calculateSimilarity(origCh.title, translatedChapters[i].title);
      if (score > bestScore && score > 0.3) {
        bestScore = score;
        bestMatch = i;
      }
    }
    
    if (bestMatch !== -1) {
      map.set(origIdx, bestMatch);
      transIdx = bestMatch + 1;
    } else {
      // 未找到匹配，按顺序映射
      map.set(origIdx, Math.min(origIdx, translatedChapters.length - 1));
    }
  });
  
  return map;
}

export function useChapters(options: UseChaptersOptions): UseChaptersReturn {
  const { originalContent, translatedContent } = options;
  
  const originalChapters = useMemo(() => 
    parseChapters(originalContent),
    [originalContent]
  );
  
  const translatedChapters = useMemo(() => 
    parseChapters(translatedContent),
    [translatedContent]
  );
  
  const chapterMap = useMemo(() => 
    buildChapterMap(originalChapters, translatedChapters),
    [originalChapters, translatedChapters]
  );
  
  // Build reverse map: translated index -> original index
  const reverseChapterMap = useMemo(() => {
    const reverseMap = new Map<number, number>();
    chapterMap.forEach((transIdx, origIdx) => {
      // If multiple original chapters map to same translated, keep the first one
      if (!reverseMap.has(transIdx)) {
        reverseMap.set(transIdx, origIdx);
      }
    });
    return reverseMap;
  }, [chapterMap]);
  
  const findChapterByOffset = useCallback((offset: number, chapters: Chapter[]): Chapter | null => {
    for (let i = chapters.length - 1; i >= 0; i--) {
      if (chapters[i].charOffset <= offset) {
        return chapters[i];
      }
    }
    return chapters[0] || null;
  }, []);
  
  return {
    originalChapters,
    translatedChapters,
    chapterMap,
    reverseChapterMap,
    findChapterByOffset,
  };
}
