// The couple's evening in the browser, on real activities of the base (tests/e2e_server.py) and the local Supabase: the
// instigateur creates an account, composes, changes a step, keeps the evening; the passager joins by its link and
// sees only its clues.
import { expect, type Page, test } from '@playwright/test';

import type { ComposedSoiree, Night, SoireeStep } from '@/lib/api';

// The activities' images are the sites' own, loaded live as the couple's browser does: a slow site has some time.
const IMAGE_TIMEOUT = 30_000;

// React Native Web puts a step's <img> in the page only once its image has loaded: there, and decoded. A kept
// evening's images are the server's own copies (/images/…).
const imageShown = (page: Page, url: string) =>
  page.evaluate((src) => {
    const wanted = new URL(src, location.href).href;
    return [...document.images].some((i) => i.src === wanted && i.complete && i.naturalWidth > 0);
  }, url);

async function expectImagesAndTexts(page: Page, steps: SoireeStep[]) {
  for (const s of steps) {
    expect(s.image_url).toBeTruthy();
    expect(s.text).toBeTruthy();
    await expect.poll(() => imageShown(page, s.image_url!), { message: `image de « ${s.title} » (${s.image_url})`, timeout: IMAGE_TIMEOUT }).toBe(true);
    await expect(page.getByText(s.text!, { exact: true })).toBeVisible();
  }
}

const PASSWORD = `e2e-${Math.random().toString(36).slice(2)}`;
const email = (label: string) => `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@e2e.test`;

async function createAccount(page: Page, label: string, button = 'Créer notre compte') {
  await page.getByText('Créer un compte', { exact: true }).click();
  await page.getByLabel('Email').fill(email(label));
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByText(button, { exact: true }).click();
}

const posted = (page: Page, path: RegExp) =>
  page.waitForResponse((r) => r.request().method() === 'POST' && path.test(new URL(r.url()).pathname));

// An evening composed from the form: to laugh, having eaten. What the server answered, and what the page sent it.
async function compose(page: Page) {
  await page.getByText('Rire aux éclats').click();
  await page.getByText('Non, déjà mangé').click();
  const composing = posted(page, /^\/api\/soirees$/);
  await page.getByText('Tramer nos intrigues').click();
  const response = await composing;
  // The screen just opened: one composed before may stay under it, hidden.
  await expect(page.getByText('Trois intrigues se murmurent au salon').filter({ visible: true })).toBeVisible();
  return { composed: (await response.json()) as ComposedSoiree, sent: response.request().postDataJSON() as Night };
}

// A vote written to Supabase (table gouts): cast, changed or withdrawn.
const voted = (page: Page, method: 'POST' | 'DELETE') =>
  page.waitForResponse((r) => r.request().method() === method && new URL(r.url()).pathname === '/rest/v1/gouts');

const EMERALD = 'rgb(61, 183, 135)';
const NIGHT_INK = 'rgb(3, 20, 13)';

test('signed out, every screen leads to the account page', async ({ page }) => {
  for (const path of ['/', '/soiree', '/historique']) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/compte$/);
    await expect(page.getByText('Le mystère commence.')).toBeVisible();
  }
});

test('the instigateur composes, changes a step and keeps the evening; the passager joins and sees only clues', async ({ page, browser }) => {
  await page.goto('/');
  await createAccount(page, 'instigateur');
  await expect(page.getByText('Bonjour, cher instigateur.')).toBeVisible();

  await page.getByText('Lancer une nouvelle intrigue').click();
  await page.getByText('Rire aux éclats').click();
  await page.getByText('Non, déjà mangé').click();
  const composing = posted(page, /^\/api\/soirees$/);
  await page.getByText('Tramer nos intrigues').click();
  const composed: ComposedSoiree = await (await composing).json();
  await expect(page.getByText('Trois intrigues se murmurent au salon')).toBeVisible();
  expect(composed.routes.length).toBeGreaterThan(1);
  for (const route of composed.routes) {
    for (const step of route.steps) await expect(page.getByText(step.title, { exact: true })).toBeVisible();
    await expectImagesAndTexts(page, route.steps);
  }

  // A step changed for another activity, never one already shown; route by route, from the last step back, as with
  // real activities some have no other that fits the evening's time, place and budget (the server then says so, 409).
  const shown = new Set(composed.routes.flatMap((r) => r.steps.map((s) => s.id)));
  const changes = page.getByText('↻ Changer', { exact: true });
  const tries = composed.routes.flatMap((r, index) => r.steps.map((_, position) => ({ index, position })).reverse());
  await expect(changes).toHaveCount(tries.length);
  let changed: ComposedSoiree | null = null;
  let at = { index: 0, position: 0 };
  for (const t of tries) {
    const changing = posted(page, new RegExp(`^/api/parcours/${composed.name}/${composed.routes[t.index].steps[t.position].redo}$`));
    await changes.nth(composed.routes.slice(0, t.index).reduce((n, r) => n + r.steps.length, 0) + t.position).click();
    const response = await changing;
    if (response.ok()) {
      [changed, at] = [await response.json(), t];
      break;
    }
    expect(response.status()).toBe(409);
  }
  expect(changed).not.toBeNull();
  const old = composed.routes[at.index].steps[at.position];
  const step = changed!.routes[at.index].steps[at.position];
  expect(shown.has(step.id)).toBe(false);
  await expect(page.getByText(step.title, { exact: true })).toBeVisible();
  await expect(page.getByText(old.title, { exact: true })).toHaveCount(0);
  await expectImagesAndTexts(page, [step]);

  // Kept: the organiser's page, with the whole route and the passager's link.
  const choosing = posted(page, /\/routes\/0\/choose$/);
  await page.getByText('Garder cette intrigue').first().click();
  const kept: ComposedSoiree = await (await choosing).json();
  const route = kept.routes[0];
  // Its images copied on the server when kept: the evening keeps them, whatever the sites do until then.
  for (const s of route.steps) expect(s.image_url).toMatch(/^\/images\/\w+\.(jpg|png|webp|gif)$/);
  await expect(page).toHaveURL(/\/revelation\?soiree=/);
  await expect(page.getByText(route.secret_title, { exact: true }).first()).toBeVisible();
  for (const s of route.steps) await expect(page.getByText(s.title, { exact: true })).toBeVisible();
  await expectImagesAndTexts(page, route.steps);
  const link = await page.getByText(/\/invitation\?code=[0-9a-f]{12}$/).textContent();
  const invitation = new URL(link!).pathname + new URL(link!).search;

  // The passager, in a browser of their own.
  const other = await browser.newContext();
  const passager = await other.newPage();
  await passager.goto(invitation);
  await expect(passager.getByText("Quelqu'un trame une soirée pour vous…")).toBeVisible();
  await createAccount(passager, 'passager', 'Créer mon compte passager');
  await expect(passager).toHaveURL(/\/$/);
  await expect(passager.getByText('Votre soirée secrète')).toBeVisible();
  await expect(passager.getByText(route.secret_title, { exact: true })).toBeVisible();
  // The step to come in its photo, veiled: the image is there (blurred), its title and description are not.
  await expect(passager.getByText('Une étape encore voilée').first()).toBeVisible();
  await expect.poll(async () => (await Promise.all(route.steps.map((s) => imageShown(passager, s.image_url!)))).some(Boolean), { timeout: IMAGE_TIMEOUT }).toBe(true);
  const hidden = async () => {
    for (const s of route.steps) {
      await expect(passager.getByText(s.title)).toHaveCount(0);
      await expect(passager.getByText(s.text!)).toHaveCount(0);
    }
  };
  await hidden();
  // Their page of the evening: the clues, the programme still sealed.
  await passager.goto(`/revelation?soiree=${kept.name}`);
  await expect(passager.getByText('Vos indices')).toBeVisible();
  await hidden();
  await other.close();

  // The instigateur's home now says the passager has joined, under the photo of the step to come.
  await page.goto('/');
  await expect(page.getByText(/Complices connectés/)).toBeVisible();
  await expect.poll(async () => (await Promise.all(route.steps.map((s) => imageShown(page, s.image_url!)))).some(Boolean), { timeout: IMAGE_TIMEOUT }).toBe(true);
});

test('a wrong password is refused in French, on the account page', async ({ page }) => {
  await page.goto('/compte');
  await page.getByLabel('Email').fill(email('oubli'));
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByText('Se connecter', { exact: true }).last().click();
  await expect(page.getByText('Email ou mot de passe incorrect.')).toBeVisible();
  await expect(page).toHaveURL(/\/compte$/);
});

test('a wrong invitation code is refused once the passager has an account', async ({ page }) => {
  await page.goto('/invitation?code=000000000000');
  await createAccount(page, 'egare', 'Créer mon compte passager');
  await expect(page.getByText('Invitation introuvable : demandez un nouveau lien.')).toBeVisible();
  await expect(page).toHaveURL(/\/invitation/);
});

test("a photo the sites do not give is asked again, reported, and the step shows the app's own picture", async ({ page, baseURL }) => {
  // Every image from elsewhere refused, as a site down or a link gone would.
  const asked = new Map<string, number>();
  await page.route('**/*', (r) => {
    const url = r.request().url();
    if (r.request().resourceType() !== 'image' || new URL(url).origin === new URL(baseURL!).origin) return r.fallback();
    asked.set(url, (asked.get(url) ?? 0) + 1);
    return r.abort();
  });
  const reported: string[] = [];
  page.on('request', (r) => {
    if (r.method() === 'POST' && new URL(r.url()).pathname === '/api/images/broken') reported.push(r.postDataJSON().id);
  });
  await page.goto('/');
  await createAccount(page, 'sans-images');
  await page.getByText('Lancer une nouvelle intrigue').click();
  await page.getByText('Rire aux éclats').click();
  await page.getByText('Non, déjà mangé').click();
  const composing = posted(page, /^\/api\/soirees$/);
  await page.getByText('Tramer nos intrigues').click();
  const composed: ComposedSoiree = await (await composing).json();
  const steps = composed.routes.flatMap((r) => r.steps);
  // An activity of an evening kept before (the test above) comes with its copy on the server: that one shows.
  const sites = steps.filter((s) => !s.image_url!.startsWith('/'));
  for (const s of steps.filter((s) => s.image_url!.startsWith('/')))
    await expect.poll(() => imageShown(page, s.image_url!), { message: `copie de « ${s.title} »` }).toBe(true);
  // The others: their picture of the app's own, shown, after their photo was asked twice and reported to the server.
  expect(sites.length).toBeGreaterThan(0);
  await expect(page.getByTestId('image-de-secours')).toHaveCount(sites.length, { timeout: IMAGE_TIMEOUT });
  await expect.poll(() => new Set(reported).size).toBe(new Set(sites.map((s) => s.id)).size);
  for (const s of sites) expect(asked.get(s.image_url!) ?? 0).toBeGreaterThanOrEqual(2);
  for (const s of steps) await expect(page.getByText(s.title, { exact: true })).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => [...document.images].filter((i) => i.complete && i.naturalWidth > 0 && i.src.includes('/bannieres/')).length))
    .toBeGreaterThanOrEqual(sites.length);
});

test('the tab bar: every icon in emerald, only the tab one is on lit like the jewel', async ({ page }) => {
  await page.goto('/');
  await createAccount(page, 'onglets');
  await expect(page.getByText('Bonjour, cher instigateur.')).toBeVisible();
  const tabs = ['Accueil', 'Mes soirées', 'Nouvelle intrigue', 'Pas encore de soirée', 'Mon compte'];
  const look = (name: string) =>
    page.getByRole('tab', { name, exact: true }).evaluate((tab) => ({
      disc: getComputedStyle(tab).backgroundColor,
      ink: getComputedStyle(tab.querySelector('path')!).stroke,
      selected: tab.getAttribute('aria-selected'),
    }));
  for (const [path, lit] of [['/', 'Accueil'], ['/historique', 'Mes soirées'], ['/soiree', 'Nouvelle intrigue'], ['/compte', 'Mon compte']]) {
    await page.goto(path);
    await expect(page.getByRole('tab', { name: lit, exact: true })).toHaveAttribute('aria-selected', 'true');
    for (const name of tabs) {
      expect(await look(name), `${name} sur ${path}`).toEqual(
        name === lit ? { disc: EMERALD, ink: NIGHT_INK, selected: 'true' } : { disc: 'rgba(0, 0, 0, 0)', ink: EMERALD, selected: 'false' },
      );
    }
  }
});

test('the instigateur votes on steps: kept on the account, sent with the next evening, which leaves out the one voted down', async ({ page }) => {
  await page.goto('/');
  await createAccount(page, 'gouts');
  await page.getByText('Lancer une nouvelle intrigue').click();
  const { composed, sent } = await compose(page);
  expect(sent.votes).toEqual({});
  // The thumbs of each step, in the routes' order (the night is not voted on).
  const steps = composed.routes.flatMap((r) => r.steps);
  const ups = page.getByRole('checkbox', { name: 'On aime ce genre', exact: true });
  const downs = page.getByRole('checkbox', { name: 'Pas pour nous', exact: true });
  await expect(ups).toHaveCount(steps.length);
  await expect(downs).toHaveCount(steps.length);
  const [down, up] = steps;

  let saving = voted(page, 'POST');
  await downs.nth(0).click();
  await saving;
  await expect(downs.nth(0)).toBeChecked();
  saving = voted(page, 'POST');
  await ups.nth(1).click();
  await saving;
  await expect(ups.nth(1)).toBeChecked();
  await expect(downs.nth(1)).not.toBeChecked();

  // On the account: both, the latest first; one withdrawn.
  await page.getByRole('tab', { name: 'Mon compte', exact: true }).click();
  await expect(page.getByText('Nos goûts')).toBeVisible();
  const tastes = page.getByTestId('nos-gouts');
  await expect(tastes.getByText(down.title, { exact: true })).toBeVisible();
  await expect(tastes.getByText(up.title, { exact: true })).toBeVisible();
  const withdrawing = voted(page, 'DELETE');
  await tastes.getByText('Retirer', { exact: true }).first().click();
  await withdrawing;
  await expect(tastes.getByText(up.title, { exact: true })).toHaveCount(0);
  await expect(tastes.getByText(down.title, { exact: true })).toBeVisible();

  // The next evening is sent the vote left, and never proposes the step voted down.
  await page.getByRole('tab', { name: 'Nouvelle intrigue', exact: true }).click();
  const next = await compose(page);
  expect(next.sent.votes).toEqual({ [down.id]: -1 });
  expect(next.composed.routes.flatMap((r) => r.steps).map((s) => s.id)).not.toContain(down.id);
});
