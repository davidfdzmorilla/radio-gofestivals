#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launch } from 'chrome-launcher';
import lighthouse from 'lighthouse';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPORTS_DIR = path.resolve(__dirname, '..', 'lighthouse-reports');
const BASE = process.env.LIGHTHOUSE_BASE ?? 'http://127.0.0.1:3000';

const ROUTES = [
  { name: 'home-es', path: '/es' },
  { name: 'home-en', path: '/en' },
  { name: 'genre-techno-es', path: '/es/genres/techno' },
];

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

async function runOne(chrome, url, name) {
  const options = {
    logLevel: 'error',
    output: ['html', 'json'],
    onlyCategories: ['performance', 'accessibility', 'seo', 'best-practices'],
    port: chrome.port,
  };
  const runnerResult = await lighthouse(url, options);
  const html = runnerResult.report[0];
  const json = runnerResult.report[1];
  fs.writeFileSync(path.join(REPORTS_DIR, `${name}.html`), html);
  fs.writeFileSync(path.join(REPORTS_DIR, `${name}.json`), json);
  const lhr = runnerResult.lhr;
  return {
    name,
    url,
    perf: Math.round((lhr.categories.performance.score ?? 0) * 100),
    seo: Math.round((lhr.categories.seo.score ?? 0) * 100),
    a11y: Math.round((lhr.categories.accessibility.score ?? 0) * 100),
    best: Math.round((lhr.categories['best-practices'].score ?? 0) * 100),
  };
}

async function main() {
  ensureDir(REPORTS_DIR);
  const chrome = await launch({ chromeFlags: ['--headless=new'] });
  const results = [];
  try {
    for (const r of ROUTES) {
      const url = `${BASE}${r.path}`;
      process.stderr.write(`→ ${url}\n`);
      results.push(await runOne(chrome, url, r.name));
    }
  } finally {
    await chrome.kill();
  }

  const pad = (s, n) => String(s).padEnd(n);
  const rows = [
    ['Ruta', 'Perf', 'SEO', 'A11y', 'Best'],
    ['---', '---', '---', '---', '---'],
    ...results.map((r) => [r.url.replace(BASE, ''), r.perf, r.seo, r.a11y, r.best]),
  ];
  process.stdout.write(
    rows
      .map((row) => '| ' + row.map((c, i) => pad(c, i === 0 ? 28 : 5)).join(' | ') + ' |')
      .join('\n') + '\n',
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
