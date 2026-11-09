#!/usr/bin/env node
// Verifica en un entorno desplegado que sitemap, robots y redirects cumplen ADR 015.
//   node scripts/seo-check.mjs [https://radio.gofestivals.eu] [muestras-por-tipo] [--phase=t1]
// --phase=t1: despliegue previo al índice de sitemaps (un único /sitemap.xml ya filtrado).
// Sale con código 1 si algo falla. Solo hace GET/HEAD públicos.
const args = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const T1 = process.argv.includes('--phase=t1');
const BASE = (args[0] ?? 'https://radio.gofestivals.eu').replace(/\/$/, '');
const SAMPLES = Number(args[1] ?? 6);
const SITE = 'https://radio.gofestivals.eu';
const rebase = (u) => u.replace(SITE, BASE); // permite probar un servidor local con las URLs canónicas
let failures = 0;
const ok = (cond, msg) => {
  console.log(`${cond ? 'OK  ' : 'FAIL'} ${msg}`);
  if (!cond) failures += 1;
};
const get = (path, init = {}) => fetch(path.startsWith('http') ? rebase(path) : BASE + path, { redirect: 'manual', ...init });
const locs = (xml) => [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
const spread = (arr, n) => (arr.length <= n ? arr : Array.from({ length: n }, (_, i) => arr[Math.floor((i * arr.length) / n)]));
const kind = (u) => {
  const p = new URL(u).pathname.split('/').filter(Boolean).slice(1);
  if (p[0] === 'stations') return 'station';
  if (p[0] === 'genres' && p[1]) return 'genre';
  if (p[0] === 'countries' && p[2]) return 'combo';
  if (p[0] === 'countries' && p[1]) return 'country';
  return 'static';
};
const robotsOf = (html, headers) => {
  const meta = html.match(/<meta[^>]+name="robots"[^>]*content="([^"]*)"/i)?.[1] ?? html.match(/<meta[^>]+content="([^"]*)"[^>]*name="robots"/i)?.[1] ?? '';
  return `${meta} ${headers.get('x-robots-tag') ?? ''}`.toLowerCase();
};
const canonicalOf = (html) => html.match(/<link[^>]+rel="canonical"[^>]*href="([^"]*)"/i)?.[1];

// 1. robots.txt
const robots = await (await get('/robots.txt')).text();
if (!T1) ok((robots.match(/^Sitemap:/gim) ?? []).length === 1 && robots.includes(`${SITE}/sitemap.xml`), 'robots.txt: una sola línea Sitemap al índice');
if (!T1) ok(!/^Host:/im.test(robots), 'robots.txt: sin Host');

// 2. sitemap-v2 y redirects de idioma
const v2 = await get('/sitemap-v2.xml');
if (!T1) ok(v2.status === 301 && v2.headers.get('location')?.endsWith('/sitemap.xml'), `sitemap-v2.xml -> ${v2.status} ${v2.headers.get('location')}`);
for (const path of ['/countries/ro/deep-house', '/genres/techno', '/stations/radio-x']) {
  const r = await get(path);
  ok(r.status === 308 && /^\/?(https?:\/\/[^/]+)?\/(es|en)\//.test(r.headers.get('location') ?? ''), `${path} -> ${r.status} ${r.headers.get('location')}`);
}

// 2b. la portada negocia idioma (redirect temporal, sin caché) y x-default de la home apunta a ella
for (const [lang, expected] of [[undefined, '/es'], ['en-GB,en;q=0.9', '/en']]) {
  const r = await get('/', lang ? { headers: { 'accept-language': lang } } : {});
  const loc = new URL(r.headers.get('location') ?? '', SITE).pathname;
  ok([302, 307].includes(r.status) && loc === expected && /no-store|private|no-cache/.test(r.headers.get('cache-control') ?? ''), `/ (${lang ?? 'sin Accept-Language'}) -> ${r.status} ${loc}, cache-control="${r.headers.get('cache-control')}"`);
}
for (const l of ['es', 'en']) {
  const html = await (await get(`/${l}`)).text();
  const xdef = html.match(/<link[^>]+rel="alternate"[^>]*hreflang="x-default"[^>]*href="([^"]*)"/i)?.[1] ?? html.match(/<link[^>]+hreflang="x-default"[^>]*href="([^"]*)"/i)?.[1];
  ok(xdef === SITE, `/${l}: x-default de la portada = ${xdef}`);
}

// 3. índice y sitemaps hijos
const index = await (await get('/sitemap.xml')).text();
if (!T1) ok(index.includes('<sitemapindex'), '/sitemap.xml es un sitemapindex');
const children = T1 ? [`${SITE}/sitemap.xml`] : locs(index);
if (!T1) ok(children.length === 4, `índice con ${children.length} hijos`);
const all = [];
for (const child of children) {
  const res = await get(child);
  const xml = await res.text();
  const urls = locs(xml);
  ok(res.status === 200 && xml.includes('<urlset'), `${child}: ${res.status}, ${urls.length} URLs`);
  ok(urls.length <= 50000 && xml.length < 50 * 1024 * 1024, `${child}: dentro de los límites`);
  if (!T1) ok(!/changefreq|<priority>/.test(xml), `${child}: sin changefreq/priority`);
  ok(!urls.some((u) => u.includes('/festivals')), `${child}: sin festivales`);
  if (!T1) ok(urls.length === 0 || xml.includes('<lastmod>'), `${child}: con lastmod`);
  all.push(...urls);
}

// 4. muestra de cada tipo: 200, sin noindex, canonical autorreferente
const byKind = {};
for (const u of all) (byKind[kind(u)] ??= []).push(u);
for (const [k, urls] of Object.entries(byKind)) {
  for (const u of spread(urls, SAMPLES)) {
    const r = await get(u);
    const html = r.status === 200 ? await r.text() : '';
    const rb = robotsOf(html, r.headers);
    ok(r.status === 200 && !rb.includes('noindex') && canonicalOf(html) === u, `[${k}] ${u} -> ${r.status}, robots="${rb.trim()}", canonical ${canonicalOf(html) === u ? 'propio' : canonicalOf(html)}`);
  }
}

// 5. controles: deben ser noindex (y no estar en el sitemap)
const controls = ['/es/search', '/es/new', '/es/festivals', '/es/countries/se', '/es/stations/radio-medved'];
for (const path of controls) {
  const r = await get(path);
  const rb = robotsOf(r.status === 200 ? await r.text() : '', r.headers);
  ok(r.status === 200 && rb.includes('noindex'), `[control] ${path} -> ${r.status}, robots="${rb.trim()}"`);
  ok(!all.some((u) => new URL(u).pathname === path || new URL(u).pathname === path.replace('/es', '/en')), `[control] ${path} fuera del sitemap`);
}
const home = all.find((u) => new URL(u).pathname === '/es');
ok(Boolean(home), 'la portada está en el sitemap');
const idx = await (await get(T1 ? '/sitemap.xml' : '/sitemap-static.xml')).text();
ok(idx.includes(`hreflang="x-default" href="${SITE}"`), 'sitemap: x-default de la portada = /');

console.log(`\n${failures === 0 ? 'TODO OK' : `${failures} comprobación(es) fallida(s)`}`);
process.exit(failures === 0 ? 0 : 1);
