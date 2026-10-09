// @ts-check
// Read-only CommonMark/GFM asset audit. Supply an existing marked module explicitly.
import { readFile, readdir, stat } from 'node:fs/promises';
import { resolve, dirname, join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

/** @typedef {{type: string, raw: string, href?: string, tokens?: Token[]}} Token */
/** @typedef {{parse: (text: string) => string, lexer: (text: string) => Token[], walkTokens: (tokens: Token[], callback: (token: Token) => void) => void}} Renderer */
/** @typedef {{file: string, line: number, kind: string, src: string, alt: string, rendered: boolean, resolved: string|null, bytes: number|null, format: string|null, status: string, failures: string[]}} Result */

/** @param {string} value */
function unescapeHtml(value) {
  return value.replace(/&(#x[\da-f]+|#\d+|amp|quot|apos|lt|gt);/gi, (_, entity) => {
    if (entity[0] === '#') return String.fromCodePoint(parseInt(entity.slice(entity[1].toLowerCase() === 'x' ? 2 : 1), entity[1].toLowerCase() === 'x' ? 16 : 10));
    return /** @type {Record<string, string>} */ ({amp: '&', quot: '"', apos: "'", lt: '<', gt: '>'})[entity.toLowerCase()];
  });
}

/** @param {string} tag @param {string} name */
function attribute(tag, name) {
  const match = tag.match(new RegExp(`\\b${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i'));
  return unescapeHtml(match?.[1] ?? match?.[2] ?? match?.[3] ?? '');
}

/** Signature checks, deliberately independent of the filename extension.
 * @param {Buffer} bytes */
function imageFormat(bytes) {
  if (bytes.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex'))) return 'png';
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'jpeg';
  if (/^GIF8[79]a/.test(bytes.toString('ascii', 0, 6))) return 'gif';
  if (bytes.toString('ascii', 0, 4) === 'RIFF' && bytes.toString('ascii', 8, 12) === 'WEBP') return 'webp';
  if (bytes.toString('ascii', 0, 2) === 'BM') return 'bmp';
  if (['49492a00', '4d4d002a'].includes(bytes.subarray(0, 4).toString('hex'))) return 'tiff';
  if (bytes.subarray(0, 4).toString('hex') === '00000100') return 'ico';
  if (bytes.toString('ascii', 4, 8) === 'ftyp' && ['avif', 'avis'].includes(bytes.toString('ascii', 8, 12))) return 'avif';
  // SVG has no binary signature. Unsupported markup is reported, never trusted by suffix.
  const xml = bytes.toString('utf8').replace(/^\uFEFF/, '').trim();
  if (/^(?:<\?xml[^>]*>\s*)?<svg\b/.test(xml) && !/<!DOCTYPE|<!ENTITY/i.test(xml)) {
    const parsed = spawnSync('python3', ['-c',
      'import sys, xml.etree.ElementTree as ET; root=ET.fromstring(sys.stdin.buffer.read()); sys.exit(root.tag != "{http://www.w3.org/2000/svg}svg")'],
    {input: bytes, maxBuffer: 1024 * 1024});
    if (parsed.status === 0) return 'svg';
  }
  return null;
}

/** @param {Result} row */
async function checkTarget(row) {
  if (row.kind === 'image' && !row.alt.trim()) row.failures.push('missing-alt');
  if (!row.src) row.failures.push('missing-destination');
  else if (/^(?:https?:)?\/\//i.test(row.src)) {
    row.status = row.failures.length ? 'FAIL' : 'NOT VERIFIED';
    return; // No network reads, even for a remote image.
  } else if (/^[a-z][a-z\d+.-]*:/i.test(row.src) && !row.src.startsWith('file:')) {
    row.failures.push('unsupported-scheme');
  } else {
    try {
      row.resolved = row.src.startsWith('file:') ? fileURLToPath(row.src)
        : resolve(dirname(row.file), decodeURIComponent(row.src.split(/[?#]/, 1)[0]));
      const info = await stat(row.resolved);
      row.bytes = info.size;
      if (!info.isFile()) row.failures.push('not-a-file');
      else if (!info.size) row.failures.push('empty-file');
      else if (row.kind === 'image') {
        row.format = imageFormat(await readFile(row.resolved));
        if (!row.format) row.failures.push('invalid-or-unsupported-image-signature');
      }
    } catch (error) {
      row.failures.push(error instanceof Error ? `target-error: ${error.message}` : 'target-error');
    }
  }
  row.status = row.failures.length ? 'FAIL' : 'PASS';
}

/** @param {string} file @param {Renderer} marked @returns {Promise<Result[]>} */
async function auditFile(file, marked) {
  const source = await readFile(file, 'utf8');
  // YAML is metadata, not rendered body; keep line count intact.
  const body = source.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, front => front.replace(/[^\n]/g, ''))
    // marked's core has no footnote extension: prevent footnotes becoming ordinary asset links.
    .replace(/^\[\^[^\]]+\]:[^\n]*(?:\n(?: {4}|\t)[^\n]*)*/gm, definition => definition.replace(/[^\n]/g, ''))
    .replace(/\[\^[^\]\n]+\]/g, citation => ' '.repeat(citation.length));
  const html = marked.parse(body);
  /** @type {Token[]} */ const images = [];
  /** @type {Token[]} */ const links = [];
  /** @type {Result[]} */ const rows = [];
  /** @type {Map<string, number>} */ const offsets = new Map();
  /** @param {string} raw */
  function lineOf(raw) {
    const start = body.indexOf(raw, offsets.get(raw) ?? 0);
    if (start < 0) return 1;
    offsets.set(raw, start + raw.length);
    return body.slice(0, start).split('\n').length;
  }
  /** @param {string} kind @param {string} src @param {string} alt @param {boolean} rendered @param {number} line @returns {Result} */
  const row = (kind, src, alt, rendered, line) => ({file, line, kind, src, alt, rendered, resolved: null, bytes: null, format: null, status: 'FAIL', failures: rendered ? [] : ['does-not-render']});
  marked.walkTokens(marked.lexer(body), token => {
    if (token.type === 'image') images.push(token);
    if (token.type === 'link') links.push(token);
    // Malformed image/link syntax survives as text. Ignore code spans/fences and escaped markers.
    if (token.type === 'text' && !token.tokens) {
      for (const match of token.raw.matchAll(/(?<!\\)!\[([^\]\n]*)\](?:\(([^\n]*)|\[[^\]\n]*\])?/g)) {
        rows.push(row('image', match[2]?.replace(/\).*$/, '') ?? '', match[1], false, lineOf(token.raw)));
      }
      for (const match of token.raw.matchAll(/(?<!!)(?<!\\)\[[^\]\n]+\]\(([^\n]+)\)/g)) {
        rows.push(row('asset', match[1], '', false, lineOf(token.raw)));
      }
    }
  });
  let imageIndex = 0;
  for (const match of html.matchAll(/<img\b[^>]*>/gi)) {
    const token = images[imageIndex++];
    rows.push(row('image', attribute(match[0], 'src'), attribute(match[0], 'alt'), true, lineOf(token?.raw ?? match[0])));
  }
  if (imageIndex < images.length) throw new Error(`${file}: renderer omitted parsed images`);
  let linkIndex = 0;
  for (const match of html.matchAll(/<a\b[^>]*>/gi)) {
    const token = links[linkIndex++];
    const href = attribute(match[0], 'href');
    if (/^(?:https?:|mailto:|#|\/\/)/i.test(href)) continue;
    rows.push(row('asset', href, '', true, lineOf(token?.raw ?? match[0])));
  }
  for (const result of rows) await checkTarget(result);
  return rows;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 4 || args[0] !== '--kb' || args[2] !== '--marked') {
    throw new Error('Usage: node check-assets.mjs --kb /absolute/instance --marked /absolute/marked.esm.js');
  }
  const kb = resolve(args[1]);
  /** @type {{marked: Renderer}} */ const module = await import(pathToFileURL(resolve(args[3])).href);
  /** @type {Result[]} */ const rows = [];
  for (const folder of ['notes', 'wiki']) {
    const directory = join(kb, folder);
    for (const name of (await readdir(directory)).filter(name => name.endsWith('.md')).sort()) {
      rows.push(...await auditFile(join(directory, name), module.marked));
    }
  }
  const images = rows.filter(row => row.kind === 'image');
  const failures = rows.filter(row => row.status === 'FAIL');
  const unverified = rows.filter(row => row.status === 'NOT VERIFIED');
  console.log(JSON.stringify({kb, renderer: resolve(args[3]), totals: {
    images: images.length, renderedImages: images.filter(row => row.rendered).length,
    passedImages: images.filter(row => row.status === 'PASS').length,
    notesImages: images.filter(row => dirname(row.file) === join(kb, 'notes')).length,
    wikiImages: images.filter(row => dirname(row.file) === join(kb, 'wiki')).length,
    assets: rows.length - images.length, failures: failures.length, unverified: unverified.length,
  }, failures, unverified, references: rows}, null, 2));
  process.exitCode = failures.length ? 1 : unverified.length ? 2 : 0;
}

main().catch(error => {
  console.error(JSON.stringify({status: 'NOT VERIFIED', error: error instanceof Error ? error.message : String(error)}));
  process.exitCode = 2;
});
