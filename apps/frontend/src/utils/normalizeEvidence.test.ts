import { describe, expect, it } from 'vitest';

import { normalizeEvidence } from './normalizeEvidence';

describe('normalizeEvidence', () => {
  it('decodes segments array payload', () => {
    const vm = normalizeEvidence({
      source_lang: 'en',
      target_lang: 'zh',
      segments: [{ id: 's1', source_text: 'A', translated_text: '甲' }]
    });
    expect(vm.segments.length).toBe(1);
    expect(vm.segments[0].sourceText).toBe('A');
    expect(vm.segments[0].targetText).toBe('甲');
    expect(vm.warning).toBeUndefined();
  });

  it('decodes bilingual raw text payload without fallback warning', () => {
    const vm = normalizeEvidence({
      source_text: 'p1\n\n p2',
      translated_text: 't1\n\n t2'
    });
    expect(vm.segments.length).toBe(2);
    expect(vm.warning).toBeUndefined();
  });

  it('falls back for unknown object', () => {
    const vm = normalizeEvidence({ hello: 1 });
    expect(vm.segments.length).toBe(0);
    expect(vm.warning).toBeTruthy();
  });

  it('falls back for non-object', () => {
    const vm = normalizeEvidence('x');
    expect(vm.segments.length).toBe(0);
    expect(vm.warning).toBeTruthy();
  });
});
