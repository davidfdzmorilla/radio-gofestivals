/** Texto introductorio de una página de listado: 1–3 párrafos generados con datos reales. */
export function PageIntro({ paragraphs }: { paragraphs: Array<string | null | undefined> }) {
  const items = paragraphs.filter((p): p is string => Boolean(p && p.trim()));
  if (items.length === 0) return null;
  return (
    <div className="max-w-2xl space-y-3 text-base leading-relaxed text-fg-1">
      {items.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </div>
  );
}
