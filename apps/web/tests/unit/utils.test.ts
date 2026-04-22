import { describe, expect, it } from 'vitest';
import { cn, initials } from '@/lib/utils';

describe('cn', () => {
  it('merges simple classes', () => {
    expect(cn('a', 'b')).toBe('a b');
  });

  it('dedupes tailwind conflicts (last wins)', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
  });

  it('ignores falsy', () => {
    expect(cn('a', false, null, undefined, 'b')).toBe('a b');
  });
});

describe('initials', () => {
  it('returns first two letters for single word', () => {
    expect(initials('Techno')).toBe('TE');
  });

  it('combines initials of first two words', () => {
    expect(initials('Radio Underground')).toBe('RU');
  });

  it('handles empty string', () => {
    expect(initials('')).toBe('··');
    expect(initials('   ')).toBe('··');
  });

  it('uppercases', () => {
    expect(initials('deep vibes')).toBe('DV');
  });
});
