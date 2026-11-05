import { describe, expect, it } from 'vitest';
import robots from '@/app/robots';

describe('robots.txt', () => {
  const rule = (() => {
    const r = robots().rules;
    return Array.isArray(r) ? r[0]! : r;
  })();

  it('veta /api/ pero deja rastrear los logos de emisora (van en el JSON-LD)', () => {
    expect(rule.disallow).toContain('/api/');
    expect(rule.allow).toContain('/api/v1/stations/*/logo');
  });

  it('la regla de logo es más específica que el veto (gana en Googlebot)', () => {
    const allowLogo = (rule.allow as string[]).find((a) => a.includes('logo'))!;
    expect(allowLogo.length).toBeGreaterThan('/api/'.length);
  });
});
