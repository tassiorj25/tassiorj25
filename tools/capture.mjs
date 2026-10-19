#!/usr/bin/env node
/**
 * Blueprint evidence capture.
 *
 * Measures a public page instead of guessing about it: real getComputedStyle
 * values, a DOM skeleton with measured boxes, the shape (never the content) of
 * JSON responses, and an asset inventory. Every raw file it writes is
 * registered in the evidence ledger, so downstream specs can cite it.
 *
 * Boundaries this tool enforces, not just documents:
 *   - robots.txt decides. A Disallow match refuses the page, with no override.
 *   - No credential handling at all. Public pages only.
 *   - You pass the page list. There is no crawler and no bulk download.
 *   - JSON bodies are reduced to key/type schemas before anything is written,
 *     so payload content never lands on disk.
 *
 * Usage:
 *   node tools/capture.mjs --out blueprint/evidence <url> [<url>...]
 *   node tools/capture.mjs --out blueprint/evidence --viewports 390,768,1440 <url>
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { jsonShape, robotsVerdict } from './capture-rules.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const LEDGER = join(HERE, 'ledger.py');

const STYLE_PROPS = [
  'color', 'background-color', 'font-family', 'font-size', 'font-weight',
  'line-height', 'letter-spacing', 'text-transform', 'border-radius',
  'border-top-width', 'border-top-color', 'border-top-style', 'box-shadow',
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'margin-top', 'margin-bottom', 'gap', 'display', 'flex-direction',
  'justify-content', 'align-items', 'grid-template-columns', 'opacity',
  'max-width', 'text-align',
];

const MAX_ELEMENTS = 1200;
const MAX_TEXT_STRINGS = 600;

function parseArgs(argv) {
  const opts = {
    out: 'blueprint/evidence',
    viewports: [390, 1440],
    delay: 1500,
    maxPages: 12,
    timeout: 30000,
    urls: [],
    ua: 'BlueprintBot/1.0 (+evidence capture; respects robots.txt)',
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') opts.out = argv[++i];
    else if (a === '--viewports') opts.viewports = argv[++i].split(',').map((v) => parseInt(v.trim(), 10));
    else if (a === '--delay') opts.delay = parseInt(argv[++i], 10);
    else if (a === '--max-pages') opts.maxPages = parseInt(argv[++i], 10);
    else if (a === '--timeout') opts.timeout = parseInt(argv[++i], 10);
    else if (a === '--user-agent') opts.ua = argv[++i];
    else if (a === '-h' || a === '--help') { opts.help = true; }
    else if (a.startsWith('-')) throw new Error(`unknown flag ${a}`);
    else opts.urls.push(a);
  }
  return opts;
}

function writeJson(path, data) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(data, null, 2) + '\n', 'utf-8');
  return path;
}

function register(outDir, kind, source, method, dataPath, viewport = '', note = '') {
  const args = ['--dir', outDir, 'add', '--kind', kind, '--source', source, '--method', method, '--data', dataPath];
  if (viewport) args.push('--viewport', viewport);
  if (note) args.push('--note', note);
  return execFileSync('python3', [LEDGER, ...args], { encoding: 'utf-8' }).trim();
}

const PAGE_PROBE = ({ styleProps, maxElements, maxTextStrings }) => {
  const isVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity) > 0.01;
  };
  const elements = [];
  const frequency = {};
  const texts = new Set();
  const all = Array.from(document.querySelectorAll('body *'));
  for (const el of all) {
    if (elements.length >= maxElements) break;
    if (!isVisible(el)) continue;
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    const styles = {};
    for (const p of styleProps) {
      const v = cs.getPropertyValue(p).trim();
      if (!v || v === 'none' || v === 'normal' || v === 'auto' || v === '0px') continue;
      styles[p] = v;
      (frequency[p] ||= {});
      frequency[p][v] = (frequency[p][v] || 0) + 1;
    }
    const ownText = Array.from(el.childNodes)
      .filter((n) => n.nodeType === 3)
      .map((n) => n.textContent.trim())
      .join(' ')
      .trim();
    if (ownText && ownText.length > 3 && texts.size < maxTextStrings) texts.add(ownText.slice(0, 300));
    elements.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || null,
      type: el.getAttribute('type') || null,
      aria: el.getAttribute('aria-label') || null,
      classes: (el.getAttribute('class') || '').split(/\s+/).filter(Boolean).slice(0, 6),
      depth: (() => { let d = 0, n = el; while ((n = n.parentElement)) d++; return d; })(),
      box: {
        x: Math.round(rect.x), y: Math.round(rect.y),
        w: Math.round(rect.width), h: Math.round(rect.height),
      },
      textLength: ownText.length,
      styles,
    });
  }
  const assets = [];
  for (const img of Array.from(document.images).slice(0, 200)) {
    assets.push({ kind: 'image', url: img.currentSrc || img.src, w: img.naturalWidth, h: img.naturalHeight, alt: img.alt || null });
  }
  for (const link of Array.from(document.querySelectorAll('link[rel~="icon"], link[rel="stylesheet"]')).slice(0, 60)) {
    assets.push({ kind: link.rel, url: link.href });
  }
  const fonts = [];
  try {
    document.fonts.forEach((f) => fonts.push({ family: f.family, weight: f.weight, style: f.style, status: f.status }));
  } catch { /* FontFaceSet unavailable */ }
  return {
    url: location.href,
    title: document.title,
    viewport: { w: window.innerWidth, h: window.innerHeight },
    documentHeight: document.documentElement.scrollHeight,
    elementCount: all.length,
    measuredElements: elements.length,
    frequency,
    elements,
    assets,
    fonts,
    texts: Array.from(texts),
    landmarks: Array.from(document.querySelectorAll('header,nav,main,footer,aside,section[aria-label],[role=banner],[role=navigation],[role=main]'))
      .slice(0, 40)
      .map((el) => ({ tag: el.tagName.toLowerCase(), role: el.getAttribute('role') || null, label: el.getAttribute('aria-label') || null })),
  };
};

async function capturePage(context, url, outDir, viewports, timeout, delay) {
  const results = [];
  const network = [];
  const page = await context.newPage();

  page.on('response', async (res) => {
    try {
      const req = res.request();
      const u = new URL(res.url());
      const ct = (res.headers()['content-type'] || '').split(';')[0];
      const record = {
        method: req.method(),
        host: u.host,
        path: u.pathname,
        queryKeys: Array.from(u.searchParams.keys()),
        status: res.status(),
        contentType: ct,
        resourceType: req.resourceType(),
      };
      if (ct === 'application/json' && ['fetch', 'xhr'].includes(req.resourceType())) {
        try {
          const body = await res.json();
          record.shape = jsonShape(body);
        } catch { record.shape = 'unparsed'; }
      }
      network.push(record);
    } catch { /* response gone */ }
  });

  const ids = [];
  for (const width of viewports) {
    await page.setViewportSize({ width, height: Math.round(width * 0.75) + 300 });
    const resp = await page.goto(url, { waitUntil: 'networkidle', timeout }).catch(async (e) => {
      // networkidle can never settle on pages with long-polling; fall back.
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout });
      return { status: () => 0, _fallback: String(e.message).slice(0, 120) };
    });
    await page.waitForTimeout(600);

    const probe = await page.evaluate(PAGE_PROBE, {
      styleProps: STYLE_PROPS, maxElements: MAX_ELEMENTS, maxTextStrings: MAX_TEXT_STRINGS,
    });
    probe.httpStatus = typeof resp?.status === 'function' ? resp.status() : null;

    const slug = `${new URL(url).pathname.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '') || 'root'}-${width}`;
    const stylePath = writeJson(join(outDir, 'raw', `styles-${slug}.json`), {
      url: probe.url, viewport: probe.viewport, httpStatus: probe.httpStatus,
      frequency: probe.frequency, fonts: probe.fonts,
    });
    ids.push(register(outDir, 'computed-style', url, 'playwright/getComputedStyle', stylePath, String(width)));

    const domPath = writeJson(join(outDir, 'raw', `dom-${slug}.json`), {
      url: probe.url, title: probe.title, viewport: probe.viewport,
      documentHeight: probe.documentHeight, elementCount: probe.elementCount,
      measuredElements: probe.measuredElements, landmarks: probe.landmarks,
      elements: probe.elements,
    });
    ids.push(register(outDir, 'dom-skeleton', url, 'playwright/getBoundingClientRect', domPath, String(width)));

    const textPath = writeJson(join(outDir, 'raw', `text-${slug}.json`), {
      url: probe.url,
      note: 'Reference corpus for the originality sweep. Never ship these strings.',
      strings: probe.texts,
    });
    ids.push(register(outDir, 'text-corpus', url, 'playwright/textNodes', textPath, String(width),
      'reference only — input to sweep.py, never shipped'));

    const assetPath = writeJson(join(outDir, 'raw', `assets-${slug}.json`), {
      url: probe.url,
      note: 'Inventory only. Blueprint records that an asset exists; it does not download it.',
      assets: probe.assets,
    });
    ids.push(register(outDir, 'asset-inventory', url, 'playwright/DOM', assetPath, String(width)));

    const shotRel = join('raw', `shot-${slug}.png`);
    mkdirSync(join(outDir, 'raw'), { recursive: true });
    await page.screenshot({ path: join(outDir, shotRel), fullPage: true });
    ids.push(register(outDir, 'screenshot', url, 'playwright/screenshot(fullPage)', join(outDir, shotRel), String(width),
      'layout reference only'));

    results.push({ width, measuredElements: probe.measuredElements, title: probe.title });
    if (delay) await page.waitForTimeout(delay);
  }

  if (network.length) {
    const slug = new URL(url).pathname.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '') || 'root';
    const netPath = writeJson(join(outDir, 'raw', `network-${slug}.json`), {
      url,
      note: 'Key/type schemas only. Response bodies are reduced to shapes before writing.',
      requests: network,
    });
    ids.push(register(outDir, 'network-schema', url, 'playwright/response.json→jsonShape', netPath));
  }

  await page.close();
  return { url, viewports: results, evidence: ids, requests: network.length };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const needsHelp = opts.help || opts.urls.length === 0;
  if (needsHelp) {
    console.log(`Blueprint evidence capture

  node tools/capture.mjs --out <evidence-dir> [options] <url> [<url>...]

  --out <dir>          evidence directory (default blueprint/evidence)
  --viewports a,b,c    viewport widths in px (default 390,1440)
  --delay <ms>         pause between captures (default 1500)
  --max-pages <n>      refuse more than n URLs (default 12)
  --timeout <ms>       navigation timeout (default 30000)

Only public pages. robots.txt is enforced and cannot be overridden.`);
    return opts.help ? 0 : 2;  // asked for help: fine. No URLs: a usage error.
  }
  if (opts.urls.length > opts.maxPages) {
    console.error(`refusing ${opts.urls.length} URLs; --max-pages is ${opts.maxPages}. Capture the core loop, not the whole site.`);
    return 2;
  }

  const outDir = resolve(opts.out);
  mkdirSync(outDir, { recursive: true });
  try {
    execFileSync('python3', [LEDGER, '--dir', outDir, 'init', '--target', opts.urls[0]], { stdio: 'pipe' });
  } catch {
    // ledger already exists; capture appends to it
  }

  const browser = await chromium.launch();
  const context = await browser.newContext({ userAgent: opts.ua, ignoreHTTPSErrors: false });

  const summary = { target: opts.urls[0], captured: [], refused: [] };
  const robotsCache = new Map();

  for (const url of opts.urls) {
    let u;
    try { u = new URL(url); } catch { summary.refused.push({ url, reason: 'not a valid URL' }); continue; }
    if (!/^https?:$/.test(u.protocol)) { summary.refused.push({ url, reason: `unsupported protocol ${u.protocol}` }); continue; }

    if (!robotsCache.has(u.origin)) {
      const robotsUrl = `${u.origin}/robots.txt`;
      try {
        const r = await context.request.get(robotsUrl, { timeout: 15000 });
        if (r.status() === 404 || r.status() === 410) robotsCache.set(u.origin, { txt: '', state: 'absent' });
        else if (r.ok()) robotsCache.set(u.origin, { txt: await r.text(), state: 'fetched' });
        else robotsCache.set(u.origin, { txt: null, state: `http ${r.status()}` });
      } catch (e) {
        robotsCache.set(u.origin, { txt: null, state: `unreachable (${String(e.message).slice(0, 60)})` });
      }
      const rc = robotsCache.get(u.origin);
      if (rc.txt !== null) {
        const rpath = join(outDir, 'raw', `robots-${u.host.replace(/[^a-z0-9]+/gi, '-')}.txt`);
        mkdirSync(dirname(rpath), { recursive: true });
        writeFileSync(rpath, rc.txt, 'utf-8');
        register(outDir, 'robots', robotsUrl, 'http GET', rpath, '', `state: ${rc.state}`);
      }
    }

    const rc = robotsCache.get(u.origin);
    if (rc.txt === null) {
      summary.refused.push({ url, reason: `robots.txt ${rc.state} — refusing rather than assuming permission` });
      console.error(`REFUSED ${url}\n  robots.txt ${rc.state}; Blueprint fails closed.`);
      continue;
    }
    const verdict = robotsVerdict(rc.txt, u.pathname + (u.search || ''));
    if (!verdict.allowed) {
      summary.refused.push({ url, reason: `robots.txt ${verdict.rule}` });
      console.error(`REFUSED ${url}\n  robots.txt says ${verdict.rule}. There is no override for this.`);
      continue;
    }

    console.log(`capturing ${url} at ${opts.viewports.join('px, ')}px …`);
    try {
      const res = await capturePage(context, url, outDir, opts.viewports, opts.timeout, opts.delay);
      summary.captured.push(res);
      console.log(`  ${res.evidence.length} evidence entries (${res.evidence[0]}…${res.evidence[res.evidence.length - 1]}), ${res.requests} requests observed`);
    } catch (e) {
      summary.refused.push({ url, reason: `capture failed: ${String(e.message).slice(0, 200)}` });
      console.error(`  FAILED ${url}: ${e.message}`);
    }
  }

  await context.close();
  await browser.close();

  writeJson(join(outDir, 'capture-summary.json'), summary);
  console.log(`\ncaptured ${summary.captured.length} page(s), refused ${summary.refused.length}`);
  console.log(`evidence: ${outDir}`);
  console.log(`verify with: python3 tools/ledger.py --dir ${opts.out} verify`);
  return summary.captured.length === 0 ? 1 : 0;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  main().then((code) => process.exit(code)).catch((e) => { console.error(e); process.exit(1); });
}
