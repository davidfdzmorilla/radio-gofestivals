import { act, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GoogleAnalytics } from '@/components/analytics/GoogleAnalytics';
import { ConsentChoiceClient } from '@/components/consent/ConsentChoiceClient';
import { CONSENT_CHANGED_EVENT, validGaId } from '@/lib/analytics';

// next/script inyecta tags reales; aquí basta ver qué se pediría.
vi.mock('next/script', () => ({
  default: ({ src, id, children }: { src?: string; id?: string; children?: string }) => (
    <script data-testid={id ?? 'gtag-src'} data-src={src}>
      {children}
    </script>
  ),
}));

const GA = 'G-ABC123XYZ9';

function setConsent(value: 'accepted' | 'rejected' | null) {
  document.cookie = value
    ? `rgf_consent=${value}; Path=/`
    : 'rgf_consent=; Max-Age=0; Path=/';
}

beforeEach(() => setConsent(null));
afterEach(() => setConsent(null));

describe('validGaId', () => {
  it.each([
    ['G-G196JWJWLC', 'G-G196JWJWLC'],
    ['  G-ABC123XYZ9 ', 'G-ABC123XYZ9'],
  ])('accepts %j', (raw, out) => expect(validGaId(raw)).toBe(out));

  it.each([[undefined], [null], [''], ['UA-12345-1'], ['G-'], ["G-ABC123'; alert(1)//"], ['g-abc123xyz9']])(
    'rejects %j',
    (raw) => expect(validGaId(raw)).toBeNull(),
  );
});

describe('GoogleAnalytics', () => {
  it('loads nothing before the user has chosen', () => {
    const { container } = render(<GoogleAnalytics gaId={GA} />);
    expect(container.querySelector('script')).toBeNull();
  });

  it('loads nothing when the user rejected', () => {
    setConsent('rejected');
    const { container } = render(<GoogleAnalytics gaId={GA} />);
    expect(container.querySelector('script')).toBeNull();
  });

  it('loads gtag.js and the init once the user has accepted, without ad signals', () => {
    setConsent('accepted');
    const { getByTestId } = render(<GoogleAnalytics gaId={GA} />);
    expect(getByTestId('gtag-src').getAttribute('data-src')).toBe(
      `https://www.googletagmanager.com/gtag/js?id=${GA}`,
    );
    const init = getByTestId('ga-init').textContent ?? '';
    expect(init).toContain(`gtag('config', '${GA}'`);
    expect(init).toContain('allow_google_signals: false');
    expect(init).toContain('allow_ad_personalization_signals: false');
  });

  it('opens the session with the landing page and referrer when the user navigated before accepting', () => {
    const w = window as unknown as { __rgfLanding?: unknown; dataLayer?: unknown[] };
    setConsent('accepted');
    const { getByTestId } = render(<GoogleAnalytics gaId={GA} />);
    // el efecto de montaje fija la entrada = página actual: simulamos que venía de otra página
    w.__rgfLanding = { location: 'https://radio.gofestivals.eu/es/genres/techno?utm_source=test', referrer: 'https://www.google.com/' };
    w.dataLayer = [];
    new Function(getByTestId('ga-init').textContent ?? '')();
    const calls = (w.dataLayer as unknown[][]).map((a) => Array.from(a as ArrayLike<unknown>));
    const config = calls.find((c) => c[0] === 'config')!;
    expect((config[2] as Record<string, unknown>).send_page_view).toBe(false);
    const views = calls.filter((c) => c[0] === 'event' && c[1] === 'page_view').map((c) => c[2]);
    expect(views).toEqual([
      { page_location: 'https://radio.gofestivals.eu/es/genres/techno?utm_source=test', page_referrer: 'https://www.google.com/' },
      { page_location: window.location.href, page_referrer: 'https://radio.gofestivals.eu/es/genres/techno?utm_source=test' },
    ]);
    delete w.__rgfLanding;
  });

  it('enables DebugView only when the landing URL carries ga_debug=1', () => {
    const w = window as unknown as { __rgfLanding?: unknown; dataLayer?: unknown[] };
    setConsent('accepted');
    const { getByTestId } = render(<GoogleAnalytics gaId={GA} />);
    const run = (location: string) => {
      w.__rgfLanding = { location, referrer: '' };
      w.dataLayer = [];
      new Function(getByTestId('ga-init').textContent ?? '')();
      const calls = (w.dataLayer as unknown[][]).map((a) => Array.from(a as ArrayLike<unknown>));
      return (calls.find((c) => c[0] === 'config')![2] as Record<string, unknown>).debug_mode;
    };
    expect(run('https://radio.gofestivals.eu/es?utm_source=test&ga_debug=1')).toBe(true);
    expect(run('https://radio.gofestivals.eu/es?utm_source=test')).toBe(false);
    delete w.__rgfLanding;
  });

  it('keeps the automatic page_view when the user accepts on the landing page itself', () => {
    const w = window as unknown as { __rgfLanding?: unknown; dataLayer?: unknown[] };
    setConsent('accepted');
    const { getByTestId } = render(<GoogleAnalytics gaId={GA} />);
    w.dataLayer = [];
    new Function(getByTestId('ga-init').textContent ?? '')();
    const calls = (w.dataLayer as unknown[][]).map((a) => Array.from(a as ArrayLike<unknown>));
    expect((calls.find((c) => c[0] === 'config')![2] as Record<string, unknown>).send_page_view).toBe(true);
    expect(calls.some((c) => c[0] === 'event' && c[1] === 'page_view')).toBe(false);
    delete w.__rgfLanding;
  });

  it('remembers the landing in memory only (nothing in storage)', () => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    delete (window as unknown as { __rgfLanding?: unknown }).__rgfLanding;
    render(<GoogleAnalytics gaId={GA} />);
    expect((window as unknown as { __rgfLanding?: { location: string } }).__rgfLanding?.location).toBe(window.location.href);
    expect(window.sessionStorage.length + window.localStorage.length).toBe(0);
  });

  it('loads nothing without a valid measurement id, even with consent', () => {
    setConsent('accepted');
    for (const bad of [undefined, null, '', "G-X'; alert(1)//"]) {
      const { container, unmount } = render(<GoogleAnalytics gaId={bad} />);
      expect(container.querySelector('script')).toBeNull();
      unmount();
    }
  });

  it('starts loading when the consent changes in the same page, without a reload', () => {
    const { container } = render(<GoogleAnalytics gaId={GA} />);
    expect(container.querySelector('script')).toBeNull();
    act(() => {
      setConsent('accepted');
      window.dispatchEvent(new Event(CONSENT_CHANGED_EVENT));
    });
    expect(container.querySelector('script')).not.toBeNull();
  });
});

describe('ConsentChoiceClient → analytics', () => {
  const labels = {
    title: 't', body: 'b', accept: 'Aceptar', reject: 'Rechazar', moreInfo: 'm', privacyHref: '/p',
  };

  it('accepting writes the cookie and notifies the analytics loader', () => {
    const seen = vi.fn();
    window.addEventListener(CONSENT_CHANGED_EVENT, seen);
    const { getByText } = render(<ConsentChoiceClient labels={labels} />);
    fireEvent.click(getByText('Aceptar'));
    expect(document.cookie).toContain('rgf_consent=accepted');
    expect(seen).toHaveBeenCalledTimes(1);
    window.removeEventListener(CONSENT_CHANGED_EVENT, seen);
  });

  it('rejecting writes the cookie and the loader still does not load', () => {
    const { getByText } = render(
      <>
        <ConsentChoiceClient labels={labels} />
        <GoogleAnalytics gaId={GA} />
      </>,
    );
    fireEvent.click(getByText('Rechazar'));
    expect(document.cookie).toContain('rgf_consent=rejected');
    expect(document.querySelector('script')).toBeNull();
  });
});
