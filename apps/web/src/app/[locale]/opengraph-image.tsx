import { ImageResponse } from 'next/og';
import { getTranslations } from 'next-intl/server';

// Imagen social por defecto de todo el sitio. Las rutas con imagen propia
// (emisoras, géneros, festivales) la sobrescriben; el resto (home, trending,
// países, combos, nuevas…) hereda esta en vez de compartirse sin imagen.
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';
export const alt = 'radio.gofestivals';

export default async function OpengraphImage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'home' });

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          gap: 24,
          padding: '0 96px',
          backgroundColor: '#14130f',
          backgroundImage: 'linear-gradient(135deg, #14130f 55%, #2a1640 100%)',
        }}
      >
        <div
          style={{ width: 120, height: 16, borderRadius: 999, backgroundColor: '#e62de9' }}
        />
        <div style={{ color: '#fafaf9', fontSize: 104, fontWeight: 700, lineHeight: 1.05 }}>
          {t('title')}
        </div>
        <div
          style={{
            color: '#8a877f',
            fontSize: 38,
            textTransform: 'uppercase',
            letterSpacing: 4,
          }}
        >
          {t('tagline')}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            marginTop: 28,
            color: '#1cc1f9',
            fontSize: 28,
          }}
        >
          <div
            style={{ width: 14, height: 14, borderRadius: 999, backgroundColor: '#e62de9' }}
          />
          radio.gofestivals.eu
        </div>
      </div>
    ),
    size,
  );
}
