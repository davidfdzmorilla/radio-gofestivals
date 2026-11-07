'use client';

import Image from 'next/image';
import { useState } from 'react';
import { readableTextOn } from '@/lib/color';

interface Props {
  /** Ya validada con `festivalImageSrc` (host permitido); null = sin imagen. */
  src: string | null;
  alt: string;
  /** Iniciales y color del recuadro de respaldo. */
  fallbackText: string;
  fallbackColor: string;
  priority?: boolean;
  /** `card`: miniatura junto al texto; `hero`: portada de la ficha (por defecto). */
  variant?: 'hero' | 'card';
  /** Dentro de un enlace que ya lleva el nombre: la imagen no se anuncia. */
  decorative?: boolean;
}

/**
 * Imagen del festival con respaldo: si no hay imagen o no carga (el bucket de
 * gofestivals puede estar caído), se pinta el recuadro de color con las iniciales,
 * igual que las portadas de las emisoras.
 */
export function FestivalImage({
  src,
  alt,
  fallbackText,
  fallbackColor,
  priority = false,
  variant = 'hero',
  decorative = false,
}: Props) {
  const [failed, setFailed] = useState(false);
  const card = variant === 'card';
  return (
    <div
      aria-hidden={decorative || undefined}
      className={
        card
          ? 'relative aspect-[4/3] w-24 shrink-0 overflow-hidden rounded-lg bg-bg-3 sm:w-28'
          : 'relative aspect-[16/9] w-full overflow-hidden rounded-2xl bg-bg-2 shadow-sticker-lg sm:w-[420px] sm:shrink-0'
      }
    >
      {src && !failed ? (
        <Image
          src={src}
          alt={decorative ? '' : alt}
          fill
          priority={priority}
          sizes={card ? '112px' : '(min-width: 640px) 420px, 100vw'}
          className="object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <div
          role={decorative ? undefined : 'img'}
          aria-label={decorative ? undefined : alt}
          className={`flex h-full w-full items-center justify-center font-display font-semibold ${card ? 'text-2xl' : 'text-6xl'}`}
          style={{ backgroundColor: fallbackColor, color: readableTextOn(fallbackColor) }}
        >
          {fallbackText}
        </div>
      )}
    </div>
  );
}
