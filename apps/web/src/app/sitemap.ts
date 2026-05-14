import type { MetadataRoute } from 'next';
import { buildSitemapEntries } from '@/lib/sitemap-data';

// Next.js statically analyses this export and requires a literal number.
export const revalidate = 86_400;

export default function sitemap(): Promise<MetadataRoute.Sitemap> {
  return buildSitemapEntries();
}
