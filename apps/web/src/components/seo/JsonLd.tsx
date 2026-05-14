type JsonLdData = Record<string, unknown>;

/**
 * Renders a schema.org JSON-LD <script>. Server component — emits no client JS.
 * `<` is escaped so the payload can never break out of the <script> element.
 */
export function JsonLd({ data }: { data: JsonLdData }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, '\\u003c'),
      }}
    />
  );
}
