'use client';

import type { AnchorHTMLAttributes } from 'react';
import { trackEvent, type AnalyticsEvents } from '@/lib/analytics';

type Props = AnchorHTMLAttributes<HTMLAnchorElement> & {
  event: AnalyticsEvents['festival_outbound'];
};

/** Enlace normal que además mide el clic como `festival_outbound` (el resto del <a> no cambia). */
export function TrackedAnchor({ event, onClick, ...rest }: Props) {
  return (
    // eslint-disable-next-line jsx-a11y/anchor-has-content -- el contenido llega en rest.children
    <a
      {...rest}
      onClick={(e) => {
        trackEvent('festival_outbound', event);
        onClick?.(e);
      }}
    />
  );
}
