// The dates and occasions in the browser, on real activities of the base (tests/e2e_server.py) and the local Supabase:
// intrigues ready for a date that counts, opened from the home and moved to another day — the same evening, a step
// drawn again only where it cannot be that day —; the duo's dates noted on « Mon couple »; a season coming and an
// evening lived a year ago, called to from the home.
import { type Browser, type Page } from '@playwright/test';
import { expect, test } from './fixtures';

import type { ComposedSoiree } from '@/lib/api';

import { admin, userId } from './local-admin';

test.use({ viewport: { width: 375, height: 812 } });

const PASSWORD = `e2e-${Math.random().toString(36).slice(2)}`;
const email = (label: string) => `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@e2e.test`;
const parisDay = (offset = 0) => {
  const d = new Date(Date.now() + offset * 86_400_000);
  return d.toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' });
};

async function newAccount(browser: Browser, label: string): Promise<{ page: Page; address: string }> {
  const page = await (await browser.newContext({ locale: 'fr-FR', timezoneId: 'Europe/Paris' })).newPage();
  const address = email(label);
  await page.goto('/compte');
  await page.getByText('Créer un compte', { exact: true }).click();
  await page.getByLabel('Email').fill(address);
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByText('Créer notre compte', { exact: true }).click();
  await expect(page.getByText('Bonjour, cher instigateur.')).toBeVisible();
  return { page, address };
}

test('intrigues ready for a date open from the home, and move to another day as the same evening', async ({ browser }) => {
  const { page, address } = await newAccount(browser, 'prete');
  // Three intrigues composed (here by the form, by the server's reminders in life), then said ready for a date.
  await page.goto('/soiree?formule=duo&envies=rire');
  await page.getByText('Non, déjà mangé').click();
  const composing = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/soirees');
  await page.getByText('Tramer nos intrigues').click();
  const composed: ComposedSoiree = await (await composing).json();
  const day = composed.routes[0].day;
  const ready = { user_id: await userId(address), cle: `date:e2e:${day}`, page_name: composed.name, day, label: '« Notre rencontre »' };
  expect((await (await admin()).from('intrigues_pretes').insert(ready)).error).toBeNull();

  await page.goto('/');
  await page.getByText('Trois intrigues prêtes : « Notre rencontre »', { exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`soiree=${composed.name}`));
  await expect(page.getByText('Trois intrigues se murmurent au salon').filter({ visible: true })).toBeVisible();

  // A week later: the same evening, step by step where it can be.
  const box = page.getByTestId('decaler');
  await box.getByText('Décaler la date', { exact: true }).click();
  const later = new Date(`${day}T12:00:00`);
  later.setDate(later.getDate() + 7);
  const laterDay = later.toLocaleDateString('sv-SE');
  await box.locator('input[type="date"]').fill(laterDay);
  const moving = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/jour'));
  await box.getByText('Décaler la soirée', { exact: true }).click();
  const moved: ComposedSoiree & { changed: number } = await (await moving).json();
  expect(moved.name).not.toBe(composed.name);
  expect(moved.routes.every((r) => r.day === laterDay)).toBe(true);
  await expect(page).toHaveURL(new RegExp(`soiree=${moved.name}`));
  await expect(page.getByTestId('decaler').getByText(/^Décalée au /)).toBeVisible();
  // The steps kept are the same activities, at the same hour.
  const before = new Map(composed.routes.flatMap((r) => r.steps.map((s) => [s.id, s.start.slice(11, 16)] as const)));
  const same = moved.routes.flatMap((r) => r.steps).filter((s) => before.get(s.id) === s.start.slice(11, 16)).length;
  expect(same).toBeGreaterThan(0);
  for (const s of moved.routes[0].steps) await expect(page.getByText(s.title, { exact: true }).first()).toBeVisible();
});

test('the duo notes its dates that count on « Mon couple »', async ({ browser }) => {
  const { page: lea } = await newAccount(browser, 'lea');
  await lea.goto('/couple');
  await lea.getByText('Obtenir mon code', { exact: true }).click();
  const code = (await lea.getByTestId('code-duo').textContent())!.trim();
  const { page: sam } = await newAccount(browser, 'sam');
  await sam.goto(`/couple?duo=${code}`);
  await sam.getByText('Rejoindre son duo', { exact: true }).click();
  const dates = sam.getByTestId('dates-qui-comptent');
  await dates.getByText('+ Ajouter une date', { exact: true }).click();
  await dates.getByText('Un anniversaire', { exact: true }).click();
  await dates.getByText('Celui de Lea', { exact: true }).click();
  await dates.getByLabel('Le jour et le mois').fill('31/02');
  await dates.getByText('Noter cette date', { exact: true }).click();
  await expect(dates.getByText(/^Cette date n'existe pas/)).toBeVisible();
  await dates.getByLabel('Le jour et le mois').fill('03/02');
  await dates.getByText('Noter cette date', { exact: true }).click();
  await expect(dates.getByText('3 février · l’anniversaire de Lea', { exact: true })).toBeVisible();
  // Léa sees it as hers.
  await lea.reload();
  await expect(lea.getByTestId('dates-qui-comptent').getByText('3 février · votre anniversaire', { exact: true })).toBeVisible();
  await lea.getByTestId('dates-qui-comptent').getByText('Retirer', { exact: true }).click();
  await expect(lea.getByTestId('dates-qui-comptent').getByText('3 février · votre anniversaire', { exact: true })).toHaveCount(0);
});

test('a season coming and an evening lived a year ago are called to from the home', async ({ browser }) => {
  const { page, address } = await newAccount(browser, 'occasions');
  const db = await admin();
  const season = `e2e-${Date.now()}`;
  const start = parisDay(5);
  await db.from('saisons').insert({ id: season, nom: 'La Nuit des tests', texte: 'Une nuit pour les tests.', deroule: 'Un verre, puis un test.', envies: ['curieux'] });
  await db.from('saison_dates').insert({ saison_id: season, debut: start });
  const lived = new Date(`${parisDay()}T12:00:00`);
  lived.setFullYear(lived.getFullYear() - 1);
  const user = await userId(address);
  await db.from('soirees_choisies').insert({
    user_id: user, page_name: `soiree-e2e-un-an-${Date.now()}`, title: 'Rires au Marais', secret_title: 'Le Pacte du Marais',
    pitch: '…', vibes: ['rire'], day: lived.toLocaleDateString('sv-SE'), formule: 'duo', personnes: 2,
  });
  try {
    await page.reload();
    await expect(page.getByText('Il y a un an', { exact: true })).toBeVisible();
    await expect(page.getByText('Le Pacte du Marais', { exact: true })).toBeVisible();
    const seasonCall = page.getByText(/^La Nuit des tests, /);
    await expect(seasonCall).toBeVisible();
    await seasonCall.click();
    await expect(page).toHaveURL(new RegExp(`envies=curieux.*jour=${start}|jour=${start}.*envies=curieux`));
    await page.goto('/');
    await page.getByText('On remet ça ?', { exact: true }).click();
    await expect(page).toHaveURL(/\/soiree\?.*envies=rire/);
  } finally {
    await db.from('saisons').delete().eq('id', season);
  }
});
