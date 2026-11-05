'use client';

import { useState } from 'react';
import { readableTextOn } from '@/lib/color';
import { stationLogoUrl, type LogoSize } from '@/lib/logo';
import { cn, initials } from '@/lib/utils';

interface Props {
  slug: string;
  name: string;
  /** `logo_hash` del API; null/undefined = la emisora no tiene logo propio. */
  logoHash: string | null | undefined;
  /** Color del recuadro de respaldo (el del género principal). */
  color: string;
  /** `sm` (112 px) para recuadros de hasta ~64 px; `lg` (256 px) para los grandes. */
  size: LogoSize;
  /** Tamaño, forma y sombra del recuadro. */
  className: string;
  /** Tamaño de las iniciales del respaldo. */
  textClassName: string;
  /** Margen interior del logo, para que no toque el borde. */
  paddingClassName?: string;
}

/**
 * Portada de una emisora: su logo real sobre un recuadro claro (se ve cualquier
 * logo, también los oscuros o transparentes) o, si no tiene o no carga, el recuadro
 * de color con las iniciales de siempre. La imagen es decorativa: el nombre ya está
 * junto a ella.
 */
export function StationCover({
  slug,
  name,
  logoHash,
  color,
  size,
  className,
  textClassName,
  paddingClassName = 'p-1.5',
}: Props) {
  const [failed, setFailed] = useState(false);
  const showLogo = Boolean(logoHash) && !failed;
  return (
    <div
      className={cn(
        'relative flex shrink-0 items-center justify-center overflow-hidden',
        className,
      )}
      style={showLogo ? undefined : { backgroundColor: color, color: readableTextOn(color) }}
    >
      {showLogo && logoHash ? (
        // Un <img> normal a propósito: ya es un WebP de nuestro propio dominio, no hay
        // nada que optimizar y `next/image` solo añadiría un salto por el optimizador.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={stationLogoUrl(slug, logoHash, size)}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className={cn('h-full w-full bg-fg-0 object-contain', paddingClassName)}
        />
      ) : (
        <span className={cn('font-display font-bold', textClassName)}>{initials(name)}</span>
      )}
    </div>
  );
}
