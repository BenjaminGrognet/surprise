// Out of the routine in the browser, on real activities of the base (tests/e2e_server.py) and the local Supabase: the
// programme « 4 semaines pour se retrouver » begun on « Mon couple » and its défi ticked by each; « Ce soir », an
// evening asked from the home around where the phone is; the morning after's review on the Livre's page.
import { type Browser, type BrowserContextOptions, type Page } from '@playwright/test';
import { expect, test } from './fixtures';

import type { ComposedSoiree } from '@/lib/api';

import { admin, userId } from './local-admin';

test.use({ viewport: { width: 375, height: 812 } });

const PASSWORD = `e2e-${Math.random().toString(36).slice(2)}`;
const email = (label: string) => `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@e2e.test`;

async function newAccount(browser: Browser, label: string, options: BrowserContextOptions = {}): Promise<{ page: Page; address: string }> {
  const page = await (await browser.newContext({ locale: 'fr-FR', timezoneId: 'Europe/Paris', ...options })).newPage();
  const address = email(label);
  await page.goto('/compte');
  await page.getByText('Créer un compte', { exact: true }).click();
  await page.getByLabel('Email').fill(address);
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByText('Créer notre compte', { exact: true }).click();
  await expect(page.getByText('Bonjour, cher instigateur.')).toBeVisible();
  return { page, address };
}

test('the programme begun on « Mon couple », its week’s evening composed, its défi ticked by each', async ({ browser }) => {
  const { page: lea } = await newAccount(browser, 'lea');
  await lea.goto('/couple');
  await lea.getByText('Obtenir mon code', { exact: true }).click();
  const code = (await lea.getByTestId('code-duo').textContent())!.trim();
  const { page: sam } = await newAccount(browser, 'sam');
  await sam.goto(`/couple?duo=${code}`);
  await sam.getByText('Rejoindre son duo', { exact: true }).click();

  const programme = sam.getByTestId('programme');
  await expect(programme.getByText('4 semaines pour se retrouver', { exact: true })).toBeVisible();
  await programme.getByText('Commencer le programme', { exact: true }).click();
  await expect(programme.getByText('Semaine 1 sur 4', { exact: true })).toBeVisible();
  await expect(programme.getByText('Se retrouver', { exact: true })).toBeVisible();
  await programme.getByText('Défi relevé', { exact: true }).click();
  await expect(programme.getByText('Fait de votre côté : à Lea maintenant.', { exact: true })).toBeVisible();

  await lea.reload();
  const hers = lea.getByTestId('programme');
  await expect(hers.getByText('Sam l’a relevé. À vous !', { exact: true })).toBeVisible();
  await hers.getByText('Défi relevé', { exact: true }).click();
  await expect(hers.getByText('Relevé à deux.', { exact: true })).toBeVisible();
  // The week's evening: the form set on its wishes.
  await hers.getByText('Composer la soirée de la semaine →', { exact: true }).click();
  await expect(lea).toHaveURL(/\/soiree\?.*envies=nous(%2C|,)cocooning/);
});

test('« Ce soir » from the home: an evening around where the phone is, for the hours to come', async ({ browser }) => {
  const { page } = await newAccount(browser, 'cesoir', { permissions: ['geolocation'], geolocation: { latitude: 48.8532, longitude: 2.3692 } });
  await page.getByText('Ce soir, maintenant', { exact: true }).click();
  await expect(page).toHaveURL(/maintenant=1/);
  await expect(page.getByText(/^Autour de vous, de dans une demi-heure/)).toBeVisible();
  // Neither the day, nor the end, nor a night away: a mood, dinner or not.
  await expect(page.getByText('Le jour J', { exact: true })).toHaveCount(0);
  await expect(page.getByText("Jusqu'à quelle heure ?", { exact: true })).toHaveCount(0);
  await page.getByText('Non, déjà mangé').click();
  await page.getByText('Cocooning', { exact: true }).click();
  const composing = page.waitForRequest((r) => r.method() === 'POST' && new URL(r.url()).pathname === '/api/soirees');
  await page.getByText('Tramer nos intrigues').click();
  const body = (await composing).postDataJSON();
  expect(body).toMatchObject({ maintenant: true, origin: { lat: 48.8532, lon: 2.3692 }, decoucher: false, end: null });
  expect(body.day).toBe(new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' }));
});

test('« Ce soir » without the position: anywhere in Paris, or another day', async ({ browser }) => {
  const { page: other } = await newAccount(browser, 'cesoir-sans');
  await other.goto('/soiree?formule=duo&maintenant=1');
  await expect(other.getByText(/^Sans votre position, la soirée se trame dans tout Paris/)).toBeVisible();
  await other.getByText('Plutôt un autre jour →', { exact: true }).click();
  await expect(other.getByText('Le jour J', { exact: true })).toBeVisible();
});

test('the morning after: the review on the Livre’s page, the favourite moment said', async ({ browser }) => {
  const { page, address } = await newAccount(browser, 'bilan');
  await page.goto('/soiree?formule=duo&envies=rire');
  await page.getByText('Non, déjà mangé').click();
  const composing = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/soirees');
  await page.getByText('Tramer nos intrigues').click();
  const composed: ComposedSoiree = await (await composing).json();
  // The evening kept, lived yesterday.
  const yesterday = new Date(Date.now() - 86_400_000).toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' });
  const kept = await (await admin()).from('soirees_choisies').insert({
    user_id: await userId(address), page_name: composed.name, title: composed.routes[0].title,
    secret_title: 'Le Pacte', pitch: '…', vibes: ['rire'], day: yesterday, formule: 'duo', personnes: 2,
  });
  expect(kept.error).toBeNull();

  await page.goto(`/livre?soiree=${composed.name}`);
  const review = page.getByTestId('bilan');
  await expect(review.getByText('Le bilan du lendemain', { exact: true })).toBeVisible();
  const [first, second] = composed.routes[0].steps;
  await review.getByLabel('Votre moment préféré').getByText(first.title, { exact: true }).click();
  await review.getByLabel('À refaire').getByText(second.title, { exact: true }).click();
  await review.getByText('Donner mon bilan', { exact: true }).click();
  await expect(review.getByText(`Votre moment préféré : ${first.title}`, { exact: true })).toBeVisible();
  await expect(review.getByText(/^Le moment préféré de votre complice apparaîtra ici/)).toBeVisible();
});
