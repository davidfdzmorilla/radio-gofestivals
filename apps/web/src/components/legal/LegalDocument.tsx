import { getTranslations } from 'next-intl/server';

type Section = {
  heading: string;
  paragraphs: string[];
};

export type LegalDocumentContent = {
  lastUpdated: string;
  sections: Section[];
};

type Props = {
  title: string;
  content: LegalDocumentContent;
  locale: 'es' | 'en';
};

/**
 * Generic legal page renderer. The document structure (h1 title, last
 * updated line, h2 sections, paragraphs) is shared between privacy and
 * cookies, so the page-level components stay one-line wrappers.
 */
export async function LegalDocument({ title, content, locale }: Props) {
  const t = await getTranslations({ locale, namespace: 'legal' });
  return (
    <article className="mx-auto max-w-3xl space-y-8 px-4 py-12">
      <header className="space-y-2">
        <h1 className="font-display text-3xl font-semibold text-fg-0 sm:text-4xl">
          {title}
        </h1>
        <p className="font-mono text-[11px] uppercase tracking-widest text-fg-2">
          {t('lastUpdated', { date: content.lastUpdated })}
        </p>
      </header>
      {content.sections.map((section) => (
        <section key={section.heading} className="space-y-3">
          <h2 className="font-display text-xl font-semibold text-fg-0">
            {section.heading}
          </h2>
          {section.paragraphs.map((paragraph, i) => (
            <p
              key={`${section.heading}-${i}`}
              className="text-base leading-relaxed text-fg-1"
            >
              {paragraph}
            </p>
          ))}
        </section>
      ))}
    </article>
  );
}
