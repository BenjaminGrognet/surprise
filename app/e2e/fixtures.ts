// The browser tests' `test`, with a picture of every page they show: each page of each account, a moment after it
// moves to a new address, then as the test leaves it — its top, and, when it is longer than the screen, its bottom
// too (scrolled down, then back) — in e2e-snapshots/<spec>/<test>/, emptied before each run (e2e/snapshots-setup.ts)
// and gathered in e2e-snapshots/index.html once it ends.
import fs from 'node:fs';
import path from 'node:path';

import { test as base, type BrowserContext, type Page } from '@playwright/test';

export { expect } from '@playwright/test';

export const SNAPSHOTS = path.resolve(__dirname, '..', 'e2e-snapshots');
// Long enough for a screen to load what it shows.
const SETTLE_MS = 1200;

export const slug = (text: string) =>
  text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'accueil';

export const test = base.extend<{ snapshots: void }>({
  snapshots: [
    async ({ browser, context }, use, testInfo) => {
      const dir = path.join(SNAPSHOTS, slug(path.basename(testInfo.file, '.spec.ts')), slug(testInfo.title));
      const pages: Page[] = [];
      const timers = new Map<Page, ReturnType<typeof setTimeout>>();
      const shots: Promise<unknown>[] = [];
      let count = 0;
      let done = false;

      // One page's pictures one after the other, never two scrolls at once.
      const queues = new Map<Page, Promise<unknown>>();
      const shoot = (page: Page, label: string) => {
        if (page.isClosed()) return;
        const where = new URL(page.url());
        const name = `${String(++count).padStart(2, '0')}-compte${pages.indexOf(page) + 1}-${slug(where.pathname + where.search)}${label}`;
        const shot = (queues.get(page) ?? Promise.resolve()).then(() => both(page, name)).catch(() => {});
        queues.set(page, shot);
        shots.push(shot);
      };
      const both = async (page: Page, name: string) => {
        const top = await page.screenshot();
        // The page's scroller (the app scrolls in a view, not the window): the tallest that overflows.
        const scrolled = await page.evaluate(() => {
          const scrollers = [document.scrollingElement, ...document.querySelectorAll('div')].filter((el): el is Element =>
            !!el && el.scrollHeight > el.clientHeight + 40
            && (el === document.scrollingElement || /(auto|scroll)/.test(getComputedStyle(el).overflowY)));
          const el = scrollers.sort((a, b) => b.clientHeight - a.clientHeight)[0];
          if (!el) return false;
          (window as unknown as { __snapshot: [Element, number] }).__snapshot = [el, el.scrollTop];
          el.scrollTop = el.scrollHeight;
          return true;
        });
        fs.mkdirSync(dir, { recursive: true });
        if (!scrolled) return fs.writeFileSync(path.join(dir, `${name}.png`), top);
        fs.writeFileSync(path.join(dir, `${name}-1-haut.png`), top);
        await page.waitForTimeout(300); // the images below the fold
        await page.screenshot({ path: path.join(dir, `${name}-2-bas.png`) });
        await page.evaluate(() => {
          const [el, before] = (window as unknown as { __snapshot: [Element, number] }).__snapshot;
          el.scrollTop = before;
        });
      };
      const watch = (page: Page) => {
        pages.push(page);
        page.on('framenavigated', (frame) => {
          if (done || frame !== page.mainFrame() || frame.url() === 'about:blank') return;
          clearTimeout(timers.get(page));
          timers.set(page, setTimeout(() => shoot(page, ''), SETTLE_MS));
        });
      };
      const hook = (ctx: BrowserContext) => {
        ctx.pages().forEach(watch);
        ctx.on('page', watch);
      };

      // The tests open an account per context (browser.newContext): each one watched too.
      hook(context);
      const newContext = browser.newContext.bind(browser);
      browser.newContext = async (options) => {
        const ctx = await newContext(options);
        hook(ctx);
        return ctx;
      };
      try {
        await use();
      } finally {
        browser.newContext = newContext;
        done = true;
        timers.forEach(clearTimeout);
        for (const page of pages) if (!page.isClosed() && page.url() !== 'about:blank') shoot(page, testInfo.status === 'passed' ? '-fin' : '-echec');
        await Promise.all(shots);
      }
    },
    { auto: true },
  ],
});
