// The app at a phone's size, quick and easy to hold: the entry page's form above the fold and its files kept by the
// browser, the evening form opened at once and showing what it still needs, the buttons that say when they are at
// work, links one can hit with a finger. On real activities of the base and the local Supabase, as soiree.spec.ts.
import { expect, type Page, test } from '@playwright/test';

test.use({ viewport: { width: 375, height: 812 } });

const PASSWORD = `e2e-${Math.random().toString(36).slice(2)}`;
const email = (label: string) => `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@e2e.test`;

async function createAccount(page: Page, label: string) {
  await page.getByText('Créer un compte', { exact: true }).click();
  await page.getByLabel('Email').fill(email(label));
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByText('Créer notre compte', { exact: true }).click();
  await expect(page.getByText('Bonjour, cher instigateur.')).toBeVisible();
}

// Whether the element lies whole within the window, as it is scrolled.
const inView = (page: Page, testId: string) =>
  page.getByTestId(testId).evaluate((e) => {
    const box = e.getBoundingClientRect();
    return box.top >= 0 && box.top < window.innerHeight;
  });

test('the entry page: its form above the fold on a phone, its fonts and pictures kept by the browser', async ({ page }) => {
  const files: { url: string; size: number; cache: string }[] = [];
  page.on('response', async (r) => {
    if (new URL(r.url()).pathname.startsWith('/assets/')) {
      files.push({ url: r.url(), size: Number(r.headers()['content-length'] ?? (await r.body()).length), cache: r.headers()['cache-control'] ?? '' });
    }
  });
  await page.goto('/compte');
  await expect(page.getByText('Le mystère commence.')).toBeVisible();
  // Email, password and the button, without scrolling.
  const button = page.getByRole('button', { name: 'Se connecter' }).last();
  const box = await button.boundingBox();
  expect(box && box.y + box.height).toBeLessThanOrEqual(812);
  await expect(page.getByLabel('Email')).toBeInViewport();
  // The emblem is its small copy, not the 1.6 MB icon.
  await expect.poll(() => files.some((f) => f.url.includes('logo-secretdate'))).toBe(true);
  const logo = files.find((f) => f.url.includes('logo-secretdate'));
  expect(logo?.url).toContain('logo-secretdate-256');
  expect(logo!.size).toBeLessThan(60_000);
  // Fonts and pictures carry their content's hash: kept, never asked again.
  const fonts = files.filter((f) => f.url.endsWith('.ttf'));
  expect(fonts.length).toBeGreaterThan(0);
  for (const f of [...fonts, logo!]) expect(f.cache).toContain('immutable');
});

test('signing in says it is at work, and takes no second press', async ({ page }) => {
  await page.goto('/compte');
  // Supabase holds its answer a moment: the button turns meanwhile.
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route('**/auth/v1/token**', async (route) => {
    await held;
    await route.continue();
  }, { times: 1 });
  await page.getByLabel('Email').fill(email('connexion'));
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByRole('button', { name: 'Se connecter' }).last().click();
  const busy = page.getByRole('button', { name: 'Connexion…' });
  await expect(busy).toBeVisible();
  await expect(busy).toHaveAttribute('aria-busy', 'true');
  await expect(busy).toBeDisabled();
  release();
  // An unknown account: refused, and the button is itself again.
  await expect(page.getByRole('button', { name: 'Se connecter' }).last()).toBeEnabled();
});

test('the evening form opens at once, shows what it still needs, and keeping an evening says it is at work', async ({ page }) => {
  await page.goto('/');
  await createAccount(page, 'fluidite');
  const asked: string[] = [];
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (url.pathname === '/api/soiree' || url.pathname === '/api/quiz') asked.push(url.pathname + url.search);
  });

  // The home asked the form's options ahead: the formula chosen, the form is there, no wait in between.
  await page.getByText('Lancer une nouvelle intrigue').click();
  await page.getByText('Une soirée entre potes', { exact: true }).click();
  await expect(page.getByText('Quelle virée pour la bande ?')).toBeVisible();
  await page.getByText('← Plutôt une soirée à deux').click();
  await expect(page.getByText('Quelle intrigue vous tente ?')).toBeVisible();
  await expect(page.getByText('On prépare le salon…')).toHaveCount(0);
  // Each of them asked once, whatever the comings and goings.
  expect(new Set(asked).size).toBe(asked.length);

  // Dinner not said: the button is not a dead end, it brings the question into view and lights it.
  await page.getByText('Rire aux éclats').click();
  const cta = page.getByRole('button', { name: 'Dîner ou pas ? Dites-le-nous' });
  await cta.scrollIntoViewIfNeeded();
  await expect(cta).toBeEnabled();
  await cta.click();
  await expect(page.getByTestId('question-attendue')).toContainText('Le dîner fait-il partie du complot ?');
  await expect.poll(() => inView(page, 'question-attendue')).toBe(true);
  await page.getByText('Non, déjà mangé').click();
  await expect(page.getByTestId('question-attendue')).toHaveCount(0);

  // No mood left: the same, on the moods.
  await page.getByText('Fidèles à nous-mêmes').click();
  await page.getByText('Rire aux éclats').click();
  await page.getByRole('button', { name: 'Une humeur ? Choisissez-la' }).click();
  await expect(page.getByTestId('question-attendue')).toContainText("L'humeur du soir");
  await page.getByText('Rire aux éclats').click();

  await page.getByText('Tramer nos intrigues').click();
  await expect(page.getByText('Trois intrigues se murmurent au salon').filter({ visible: true })).toBeVisible();

  // The small links of a step leave room for a finger.
  const change = page.getByRole('button', { name: '↻ Changer' }).first();
  expect((await change.boundingBox())!.height).toBeGreaterThanOrEqual(26);

  // Keeping takes the server a few seconds (it copies the images): the button turns, the others wait.
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route('**/api/parcours/*/routes/*/choose', async (route) => {
    await held;
    await route.continue();
  }, { times: 1 });
  await page.getByText('Garder cette intrigue').first().click();
  const sealing = page.getByRole('button', { name: 'On scelle l’intrigue…' });
  await expect(sealing).toBeVisible();
  await expect(sealing).toBeDisabled();
  for (const other of await page.getByRole('button', { name: 'Garder cette intrigue' }).all()) await expect(other).toBeDisabled();
  release();
  await expect(page).toHaveURL(/\/revelation\?soiree=/);
});
