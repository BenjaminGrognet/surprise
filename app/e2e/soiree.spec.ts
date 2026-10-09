// The couple's evening in the browser, on real activities of the base (tests/e2e_server.py) and the local Supabase: the
// instigateur creates an account, composes, changes a step, keeps the evening; the passager joins by its link and
// sees only its clues. And a band's (Secret Squad): its own look, its number, its guests and complices by two links.
import { readFileSync } from 'node:fs';

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

// A step's picture on the page (StepImage), shown: its photo, or the app's own of its kind in its place.
const pictured = (page: Page, id: string) =>
  page.evaluate(
    (id) => [...document.querySelectorAll(`[data-testid="photo:${id}"] img, [data-testid="image-de-secours:${id}"] img`)]
      .some((i) => (i as HTMLImageElement).complete && (i as HTMLImageElement).naturalWidth > 0),
    id,
  );

// Each step with its own text and a picture: the site's photo, or, when the site does not give it (an activity without
// one, a photo gone or refused: asked again, reported), the app's own picture of its kind; never a blank.
async function expectImagesAndTexts(page: Page, steps: SoireeStep[]) {
  for (const s of steps) {
    expect(s.text).toBeTruthy();
    await expect(page.getByText(s.text!, { exact: true })).toBeVisible();
    await expect.poll(() => pictured(page, s.id), { message: `image de « ${s.title} » (${s.image_url})`, timeout: IMAGE_TIMEOUT }).toBe(true);
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

// The first choice of a new evening: for two (Secret Date), or for a band (Secret Squad).
const forTwo = (page: Page) => page.getByText('Une soirée à deux', { exact: true }).click();

// An evening composed from the form: to laugh, having eaten. What the server answered, and what the page sent it.
async function compose(page: Page, pick = true) {
  if (pick) await forTwo(page);
  await page.getByText('Rire aux éclats').click();
  await page.getByText('Non, déjà mangé').click();
  const composing = posted(page, /^\/api\/soirees$/);
  await page.getByText('Tramer nos intrigues').click();
  const response = await composing;
  // The screen just opened: one composed before may stay under it, hidden.
  await expect(page.getByText('Trois intrigues se murmurent au salon').filter({ visible: true })).toBeVisible();
  return { composed: (await response.json()) as ComposedSoiree, sent: response.request().postDataJSON() as Night };
}

// The wait while the evening is composed, said the formula's way: the composition is held until its title shows, and
// its lines are not the other formula's.
async function waitingSaid(page: Page, title: string, notTitle: string) {
  await page.route('**/api/soirees', async (route) => {
    await expect(page.getByText(title, { exact: true })).toBeVisible();
    await expect(page.getByText(notTitle, { exact: true })).toHaveCount(0);
    await route.continue();
  }, { times: 1 });
}
const DATE_WAIT = 'La nuit tisse des secrets aux reflets d’émeraude…';
const SQUAD_WAIT = 'Sous la boule à facettes, la nuit trame votre virée…';

// A vote written to Supabase (table gouts): cast, changed or withdrawn.
const voted = (page: Page, method: 'POST' | 'DELETE') =>
  page.waitForResponse((r) => r.request().method() === method && new URL(r.url()).pathname === '/rest/v1/gouts');

// How far the page is scrolled, whichever element scrolls it (react-native-web's ScrollView is a div of its own).
const scrolled = (page: Page) =>
  page.evaluate(() => Math.max(window.scrollY, ...[...document.querySelectorAll('*')].map((e) => e.scrollTop)));

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
  await forTwo(page);
  await page.getByText('Rire aux éclats').click();
  // Dinner or not: cutlery, or a plate crossed out.
  const eaten = page.getByRole('checkbox', { name: 'Non, déjà mangé' });
  await expect(eaten.locator('svg circle')).toHaveCount(2);
  await expect(eaten.locator('svg path')).toHaveCount(1);
  await eaten.click();
  // No question on the start; the end said with its hour and the evening's length, no "Sans choix".
  await expect(page.getByText("L'heure du rendez-vous")).toHaveCount(0);
  await expect(page.getByText("Jusqu'à quelle heure ?")).toBeVisible();
  await expect(page.getByText('Fin vers 0 h 30 · 5 h 30', { exact: true })).toBeVisible();
  await expect(page.getByText(/Sans choix : (l'heure|ce que vos envies)/)).toHaveCount(0);
  await waitingSaid(page, DATE_WAIT, SQUAD_WAIT);
  const composing = posted(page, /^\/api\/soirees$/);
  await page.getByText('Tramer nos intrigues').click();
  expect(await scrolled(page)).toBeGreaterThan(0);
  const composed: ComposedSoiree = await (await composing).json();
  await expect(page.getByText('Trois intrigues se murmurent au salon')).toBeVisible();
  // The three routes open at the top of the page, not where the form was left.
  expect(await scrolled(page)).toBe(0);
  await expect(page.getByText(/votre passager n'en verra que les indices/)).toBeVisible();
  expect(composed).toMatchObject({ formule: 'duo', personnes: 2 });
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
  // Its images copied on the server when kept, as far as the sites give them: the evening keeps them, whatever the
  // sites do until then (one that cannot be had stays the site's; the page then shows another, or its own picture).
  expect(route.steps.filter((s) => /^\/images\/\w+\.(jpg|png|webp|gif)$/.test(s.image_url ?? '')).length).toBeGreaterThan(0);
  await expect(page).toHaveURL(/\/revelation\?soiree=/);
  await expect(page.getByText(route.secret_title, { exact: true }).first()).toBeVisible();
  for (const s of route.steps) await expect(page.getByText(s.title, { exact: true })).toBeVisible();
  await expectImagesAndTexts(page, route.steps);
  const link = await page.getByText(/\/invitation\?code=[0-9a-f]{12}$/).textContent();
  const invitation = new URL(link!).pathname + new URL(link!).search;
  // Or by email: the server writes to the address in the evening's name (surprise.courriers); here, on its way.
  const friend = email('ami');
  await page.getByLabel("Email de l'invité").fill(friend);
  await page.getByText('Envoyer', { exact: true }).click();
  await expect(page.getByText(`Invitation en route vers ${friend}…`)).toBeVisible();
  await page.getByLabel("Email de l'invité").fill('pas-un-email');
  await page.getByText('Envoyer', { exact: true }).click();
  await expect(page.getByText("Cet email n'est pas valide.")).toBeVisible();

  // Behind the scenes, the passager's week as their phone will tell it: the sealed letter a week before, each step's
  // mystery word turned into its name as its veil lifts.
  await page.getByText('Les Coulisses', { exact: true }).click();
  const week = page.getByTestId('semaine-passager');
  await expect(week.getByText('La semaine de votre passager')).toBeVisible();
  const whole = week.getByText(/^Toute la semaine \(\d+\)$/);
  if (await whole.count()) await whole.click();
  await expect(week.getByText('J-7 · Le pli scellé', { exact: true })).toBeVisible();
  await expect(week.getByText(`« ${route.secret_title} » commence`)).toBeVisible();
  for (const s of route.steps) await expect(week.getByText(`prend un nom : ${s.title}, à`)).toBeVisible();
  await expect(week.getByText('Le lendemain · Le Livre des Secrets', { exact: true })).toBeVisible();

  // The invitation on paper: the evening's name and its code to scan, printed from a window of its own.
  await page.getByText("Ou un carton d'invitation à imprimer…").click();
  const carton = page.getByTestId('carton-invitation');
  await expect(carton.getByText(route.secret_title, { exact: true })).toBeVisible();
  await expect(carton.locator('svg path')).toHaveCount(1);
  const printing = page.waitForEvent('popup');
  await carton.getByText('Imprimer le carton').click();
  const printed = await printing;
  await expect(printed.locator('h1')).toHaveText(route.secret_title);
  await expect(printed.getByText('Scannez pour recevoir')).toBeVisible();
  await expect(printed.getByText(link!, { exact: true })).toBeVisible();
  await expect(printed.locator(`svg[aria-label="QR code de l'invitation"] path`)).toHaveCount(1);
  for (const s of route.steps) await expect(printed.getByText(s.title)).toHaveCount(0);
  await printed.close();

  // The evening's postcard, for a story: its name and a mystery word, no step; downloaded at 1080 x 1920.
  const card = page.getByTestId('carte-postale');
  await expect(card.getByText(route.secret_title, { exact: true })).toBeVisible();
  await expect(card.getByText(/^« .+ »$/).first()).toBeVisible();
  for (const s of route.steps) await expect(card.getByText(s.title)).toHaveCount(0);
  const downloading = page.waitForEvent('download');
  await card.getByText('Télécharger la carte').click();
  const image = readFileSync((await (await downloading).path())!);
  expect(image.subarray(1, 4).toString()).toBe('PNG');
  expect([image.readUInt32BE(16), image.readUInt32BE(20)]).toEqual([1080, 1920]);

  // Home by the tab bar: the page left under the form, read again, opens on the evening just kept.
  await page.getByRole('tab', { name: 'Accueil' }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText(route.secret_title, { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Le prochain secret reste encore à écrire…')).toHaveCount(0);

  // The passager, in a browser of their own.
  const other = await browser.newContext();
  const passager = await other.newPage();
  await passager.goto(invitation);
  await expect(passager.getByText("Quelqu'un trame une soirée pour vous…")).toBeVisible();
  await createAccount(passager, 'passager', 'Créer mon compte passager');
  await expect(passager).toHaveURL(/\/$/);
  await expect(passager.getByText('Votre soirée secrète')).toBeVisible();
  await expect(passager.getByText(route.secret_title, { exact: true })).toBeVisible();
  // The step to come in its picture, veiled: the image is there (blurred), its title and description are not.
  await expect(passager.getByText('Une étape encore voilée').first()).toBeVisible();
  await expect.poll(async () => (await Promise.all(route.steps.map((s) => pictured(passager, s.id)))).some(Boolean), { timeout: IMAGE_TIMEOUT }).toBe(true);
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
  // Each clue under its chapter of the week; the meeting time theirs from the start.
  await expect(passager.getByText('Le rendez-vous', { exact: true })).toBeVisible();
  await hidden();
  // Surprised by one evening, composing one of their own: their home shows the next of each, the surprise still veiled.
  await passager.goto('/');
  await passager.getByText('À votre tour de surprendre').click();
  // Composing, they are this evening's instigateur: the page says so, not the roles of the evening they are surprised by.
  await forTwo(passager);
  await expect(passager.getByText('Quelle intrigue vous tente ?')).toBeVisible();
  await expect(passager.getByText(/Vous êtes l'instigateur de cette soirée/)).toBeVisible();
  const { composed: theirs } = await compose(passager, false);
  await expect(passager.getByText(/votre passager n'en verra que les indices/)).toBeVisible();
  await expect(passager.getByText(/votre instigateur qui n'en verra/)).toHaveCount(0);
  const keeping = posted(passager, /\/routes\/0\/choose$/);
  await passager.getByText('Garder cette intrigue').first().click();
  const own: ComposedSoiree = await (await keeping).json();
  await expect(passager).toHaveURL(/\/revelation\?soiree=/);
  expect(theirs.name).not.toBe(kept.name);
  await passager.getByRole('tab', { name: 'Accueil' }).click();
  await expect(passager.getByText(route.secret_title, { exact: true })).toBeVisible();
  await expect(passager.getByText(own.routes[0].secret_title, { exact: true }).first()).toBeVisible();
  for (const s of route.steps) await expect(passager.getByText(s.title)).toHaveCount(0);
  await other.close();

  // The instigateur's home now says the passager has joined, under the photo of the step to come.
  await page.goto('/');
  await expect(page.getByText(/Complices connectés/)).toBeVisible();
  await expect.poll(async () => (await Promise.all(route.steps.map((s) => pictured(page, s.id)))).some(Boolean), { timeout: IMAGE_TIMEOUT }).toBe(true);
});

test("the profile's answers are read whole on a phone: a description goes on a second line, never cut", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 760 });
  await page.goto('/');
  await createAccount(page, 'profil');
  await page.getByText('Faire notre profil de couple').click();
  await page.getByText('Complices', { exact: true }).click();
  await expect(page.getByText('Votre soirée idéale commence par…')).toBeVisible();
  for (const desc of ['Un moment hors du temps', 'Musées, monuments, secrets', 'Créer, cuisiner, façonner']) {
    const text = page.getByText(desc, { exact: true });
    await expect(text).toBeVisible();
    expect(await text.evaluate((e) => getComputedStyle(e).textOverflow !== 'ellipsis' && e.scrollWidth <= e.clientWidth)).toBe(true);
  }
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

test("a photo the sites do not give is asked again, reported, and the step shows another or the app's own picture", async ({ page, baseURL }) => {
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
  await forTwo(page);
  await page.getByText('Rire aux éclats').click();
  await page.getByText('Non, déjà mangé').click();
  const composing = posted(page, /^\/api\/soirees$/);
  await page.getByText('Tramer nos intrigues').click();
  const composed: ComposedSoiree = await (await composing).json();
  const steps = composed.routes.flatMap((r) => r.steps);
  // An activity of an evening kept before (the test above) comes with its copy on the server: that one shows.
  const sites = steps.filter((s) => s.image_url && !s.image_url.startsWith('/'));
  for (const s of steps.filter((s) => s.image_url?.startsWith('/')))
    await expect.poll(() => imageShown(page, s.image_url!), { message: `copie de « ${s.title} »` }).toBe(true);
  // The others: their photo asked twice, then reported to the server, which answers with another it copied here (the
  // official site's) or none, the step then in the app's own picture of its kind; at once for an activity without one.
  expect(sites.length).toBeGreaterThan(0);
  await expect.poll(() => new Set(reported).size, { timeout: IMAGE_TIMEOUT }).toBe(new Set(sites.map((s) => s.id)).size);
  for (const s of sites) expect(asked.get(s.image_url!) ?? 0).toBeGreaterThanOrEqual(2);
  for (const s of steps) {
    await expect(page.getByText(s.title, { exact: true })).toBeVisible();
    await expect.poll(() => pictured(page, s.id), { message: `image de « ${s.title} »`, timeout: IMAGE_TIMEOUT }).toBe(true);
  }
  await expect(page.getByTestId(/^image-de-secours:/).first()).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => [...document.images].filter((i) => i.complete && i.naturalWidth > 0 && i.src.includes('/bannieres/')).length))
    .toBeGreaterThan(0);
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

const NEON = 'rgb(63, 224, 230)';
const SECRET = '255, 43, 214'; // the fuchsia neon of a band's secret options

test('a band’s evening: its own look, no profile, eight of them, its guests by one link and its complices by another', async ({ page, browser }) => {
  await page.goto('/');
  await createAccount(page, 'cerveau');
  await page.getByText('Lancer une nouvelle intrigue').click();
  // The first choice, each formula in its own look.
  await expect(page.getByText('Quelle soirée tramer ?')).toBeVisible();
  await expect(page.getByText('Secret Date', { exact: true }).last()).toBeVisible();
  await page.getByText('Une soirée entre potes', { exact: true }).click();
  await expect(page).toHaveURL(/formule=squad/);

  // The band's form: its neon, its number, its wishes and occasions; no night out.
  const title = page.getByText('Quelle virée pour la bande ?');
  await expect(title).toBeVisible();
  // Its headings in poster capitals, lit, where a couple's are in a serif.
  const look = await title.evaluate((t) => {
    const css = getComputedStyle(t);
    return { font: css.fontFamily, transform: css.textTransform, glow: css.textShadow, color: css.color };
  });
  expect(look).toMatchObject({ font: expect.stringContaining('Anton'), transform: 'uppercase', color: NEON });
  expect(look.glow).not.toBe('none');
  // The dinner asked right after the mood, before the secret options (the couple's form is the same).
  const top = async (text: string, exact = false) => (await page.getByText(text, { exact }).boundingBox())!.y;
  const diner = await top('Le dîner fait-il partie du complot');
  expect(diner).toBeGreaterThan(await top("L'humeur du soir"));
  // Exact: the mood's hint names the secret options too.
  expect(diner).toBeLessThan(await top('Les options secrètes', true));
  // Its secret options outlined in a second neon, fuchsia.
  const borders = await page.getByRole('checkbox').evaluateAll((boxes) => boxes.map((box) => getComputedStyle(box).borderColor));
  expect(borders.filter((border) => border.includes(SECRET)).length).toBeGreaterThan(0);
  // No profile asked nor applied: nothing of the couple's quiz, nor a wish that would take its vibes.
  await expect(page.getByText(/profil|Faire le quiz/).filter({ visible: true })).toHaveCount(0);
  await expect(page.getByText('Fidèles à la bande', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Secret Squad', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Et quand la nuit tombe ?')).toHaveCount(0);
  await expect(page.getByText('Romantique', { exact: true })).toHaveCount(0);
  // From two (a friend, no date) to ten.
  await expect(page.getByText('Vous compris, de 2 à 10.')).toBeVisible();
  const fewer = page.getByRole('button', { name: 'Une personne de moins' });
  for (let i = 0; i < 4; i++) await fewer.click();
  await expect(page.getByLabel('2 personnes', { exact: true })).toBeVisible();
  await expect(fewer).toBeDisabled();
  for (let i = 0; i < 6; i++) await page.getByRole('button', { name: 'Une personne de plus' }).click();
  await expect(page.getByText(/À partir de 8, moins de lieux/)).toBeVisible();
  // Several moods, the middle one chosen until then: three wishes in all with the secret options.
  const mood = (name: string) => page.getByRole('checkbox', { name, exact: true });
  await expect(mood('Se défier entre potes')).toBeChecked();
  await mood('Rire aux larmes').click();
  await expect(mood('Se défier entre potes')).toBeChecked();
  await expect(mood('Rire aux larmes')).toBeChecked();
  // Two moods and still two secret options, as a couple slips two beside its mood: four wishes for a band.
  await expect(page.getByText("Jusqu'à 2, glissées dans le programme.")).toBeVisible();
  await mood('Trinquer').click();
  await expect(page.getByText("Jusqu'à 1, glissées dans le programme.")).toBeVisible();
  await mood('Chanter à tue-tête').click();
  await expect(page.getByText('Vos humeurs prennent les 4 envies : retirez-en une pour en glisser.')).toBeVisible();
  await expect(mood('Faire la fête')).toBeDisabled();
  await mood('Trinquer').click();
  await mood('Chanter à tue-tête').click();
  await expect(mood('Faire la fête')).toBeEnabled();
  await mood('Frissonner').click();
  await mood('Se régaler').click();
  await expect(mood('Vibrer en musique')).toBeDisabled();
  await page.getByText('Un EVJF ou un EVG', { exact: true }).click();
  await page.getByText('Non, déjà mangé').click();
  // What the band never wants, asked with the order in place of a profile's refusals.
  await expect(page.getByText('Ce que la bande ne veut pas')).toBeVisible();
  await page.getByText("L'alcool", { exact: true }).click();
  const button = page.getByText('Tramer la virée à 8', { exact: true });
  expect(await button.evaluate((label) => getComputedStyle(label.parentElement!).backgroundColor)).toBe(NEON);
  await waitingSaid(page, SQUAD_WAIT, DATE_WAIT);
  const composing = posted(page, /^\/api\/soirees$/);
  await button.click();
  const response = await composing;
  const composed: ComposedSoiree = await response.json();
  expect(response.request().postDataJSON()).toMatchObject({
    formule: 'squad', personnes: 8, occasion: 'evjf', envies: ['jouer', 'rire', 'frissons', 'gourmand'], decoucher: false, profile: null, eviter: ['alcool'], votes: {},
  });
  expect(composed).toMatchObject({ formule: 'squad', personnes: 8 });
  expect(composed.routes.length).toBeGreaterThan(0);
  await expect(page.getByText('Trois virées pour la bande')).toBeVisible();
  // The way between two steps: on foot or by metro, its icon in a round badge, a link to the itinerary.
  if (composed.routes[0].steps.length > 1) {
    await expect(page.getByRole('link', { name: /^(À pied|En métro), \d+ min, / }).first()).toBeVisible();
  }
  // A band's steps are not voted on: the couple's tastes are not the band's.
  await expect(page.getByRole('checkbox', { name: 'On aime ce genre' })).toHaveCount(0);
  // Each one's share, never the couple's price.
  await expect(page.getByText(/€\/pers\.$/).first()).toBeVisible();
  await expectImagesAndTexts(page, composed.routes[0].steps);

  // Kept: the band's two links and its places.
  const choosing = posted(page, /\/routes\/0\/choose$/);
  await page.getByText('Garder cette intrigue').first().click();
  const kept: ComposedSoiree = await (await choosing).json();
  const route = kept.routes[0];
  await expect(page).toHaveURL(/\/revelation\?soiree=/);
  await expect(page.getByText('Votre bande pour cette soirée')).toBeVisible();
  await expect(page.getByText('Encore 7 places dans la bande')).toBeVisible();
  const links = await page.getByText(/\/invitation\?code=[0-9a-f]{12}$/).allTextContents();
  expect(links).toHaveLength(2);
  const [guests, complices] = links.map((link) => new URL(link).pathname + new URL(link).search);

  // A friend by the guests' link: the clues only, in the band's look.
  const friendContext = await browser.newContext();
  const friend = await friendContext.newPage();
  await friend.goto(guests);
  await createAccount(friend, 'pote', 'Créer mon compte passager');
  await expect(friend).toHaveURL(/\/$/);
  await expect(friend.getByText(route.secret_title, { exact: true })).toBeVisible();
  await friend.goto(`/revelation?soiree=${kept.name}`);
  await expect(friend.getByText('Squad · Invité', { exact: true })).toBeVisible();
  await expect(friend.getByText('Vos indices')).toBeVisible();
  for (const s of route.steps) await expect(friend.getByText(s.title)).toHaveCount(0);
  await friendContext.close();

  // A witness by the complices' link: the whole evening, as its organiser sees it.
  const witnessContext = await browser.newContext();
  const witness = await witnessContext.newPage();
  await witness.goto(complices);
  await createAccount(witness, 'temoin', 'Créer mon compte passager');
  await expect(witness).toHaveURL(/\/$/);
  await witness.goto(`/revelation?soiree=${kept.name}`);
  for (const s of route.steps) await expect(witness.getByText(s.title, { exact: true })).toBeVisible();
  await witnessContext.close();

  // The instigateur's home: the evening in the band's look, three of eight in.
  await page.goto('/');
  await expect(page.getByText('Squad', { exact: true })).toBeVisible();
  await expect(page.getByText(/3 sur 8 dans la bande/)).toBeVisible();
});
