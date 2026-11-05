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
}

/**
 * Imagen del festival con respaldo: si no hay imagen o no carga (el bucket de
 * gofestivals puede estar caído), se pinta el recuadro de color con las iniciales,
 * igual que las portadas de las emisoras.
 */
export function FestivalImage({ src, alt, fallbackText, fallbackColor, priority = false }: Props) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="relative aspect-[16/9] w-full overflow-hidden rounded-2xl bg-bg-2 shadow-sticker-lg sm:w-[420px] sm:shrink-0">
      {src && !failed ? (
        <Image
          src={src}
          alt={alt}
          fill
          priority={priority}
          sizes="(min-width: 640px) 420px, 100vw"
          className="object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <div
          role="img"
          aria-label={alt}
          className="flex h-full w-full items-center justify-center font-display text-6xl font-semibold"
          style={{ backgroundColor: fallbackColor, color: readableTextOn(fallbackColor) }}
        >
          {fallbackText}
        </div>
      )}
    </div>
  );
}
