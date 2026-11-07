/**
 * Google Analytics 4 (ADR 013). El ID de medición es público (va en cada página), pero se
 * configura por entorno: sin `NEXT_PUBLIC_GA_MEASUREMENT_ID` válido no se carga nada.
 */

/** Evento que dispara el banner de consentimiento al elegir, para cargar GA sin recargar. */
export const CONSENT_CHANGED_EVENT = 'rgf:consent-changed';

const MEASUREMENT_ID = /^G-[A-Z0-9]{6,14}$/;

/** Devuelve el ID si tiene forma de ID de medición de GA4; si no, null (analítica desactivada). */
export function validGaId(raw: string | null | undefined): string | null {
  const id = raw?.trim();
  return id && MEASUREMENT_ID.test(id) ? id : null;
}

export const GA_MEASUREMENT_ID = validGaId(process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID);
