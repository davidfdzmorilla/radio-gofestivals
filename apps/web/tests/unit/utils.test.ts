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

describe('initials · caracteres fuera del plano básico', () => {
  it.each([
    ['𝗥𝗔𝗗𝗜𝗢 𝗧𝗘𝗖𝗛𝗡𝗢', '𝗥𝗧'],
    ['🎵 Radio Techno', '🎵R'],
    ['Radio 𝗧𝗘𝗖𝗛', 'R𝗧'],
    ['𝙏𝙚𝙘𝙝𝙣𝙤', '𝙏𝙚'],
  ])('%s -> %s sin partir ningún carácter', (name, expected) => {
    const out = initials(name);
    expect(out).toBe(expected);
    expect(out.isWellFormed()).toBe(true);
  });

  it('never returns a lone surrogate for any mix of emoji and text', () => {
    for (const name of ['🔥', '🔥🔥 Mix', 'A 🔥', '🇪🇸 Radio', '👨‍👩‍👧 Familia']) {
      expect(initials(name).isWellFormed()).toBe(true);
    }
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
