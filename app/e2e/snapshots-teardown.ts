// After the browser tests: their pictures of the pages gathered in one page, e2e-snapshots/index.html, by spec and
// test, in the order they were taken.
import fs from 'node:fs';
import path from 'node:path';

import { SNAPSHOTS } from './fixtures';

const escape = (text: string) => text.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
const dirs = (dir: string) => fs.readdirSync(dir, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name).sort();

export default function teardown() {
  if (!fs.existsSync(SNAPSHOTS)) return;
  const sections = dirs(SNAPSHOTS).map((spec) => {
    const tests = dirs(path.join(SNAPSHOTS, spec)).map((name) => {
      const shots = fs.readdirSync(path.join(SNAPSHOTS, spec, name)).filter((f) => f.endsWith('.png')).sort();
      const figures = shots.map((f) => {
        const src = `${spec}/${name}/${f}`;
        return `<figure><a href="${escape(src)}"><img loading="lazy" src="${escape(src)}"></a><figcaption>${escape(f.replace(/\.png$/, ''))}</figcaption></figure>`;
      });
      return `<h3>${escape(name)}</h3><div class="shots">${figures.join('')}</div>`;
    });
    return `<h2>${escape(spec)}</h2>${tests.join('')}`;
  });
  fs.writeFileSync(path.join(SNAPSHOTS, 'index.html'), `<!doctype html><meta charset="utf-8"><title>Pages des tests</title>
<style>body{font:14px system-ui;background:#111;color:#eee;margin:16px}h2{margin-top:32px}h3{color:#bbb;font-weight:500}
.shots{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0;width:200px}img{width:200px;border:1px solid #333}
figcaption{font-size:11px;color:#999;word-break:break-all}</style>
<h1>Pages des tests (${new Date().toLocaleString('fr-FR')})</h1>${sections.join('')}`);
}
