// « Mon couple » in the browser, two accounts on two browsers, on the local Supabase: the duo formed by a code sent as a
// link; their profile asked first, one for two; the questions du jour from the day after their first evening lived,
// answered by one then the other — each reads the other's answer once their own is sealed —; and the complicity gauge
// of the home opening the page.
import { type Browser, type Page } from '@playwright/test';
import { expect, test } from './fixtures';

import { admin, userId } from './local-admin';

test.use({ viewport: { width: 375, height: 812 } });

const PASSWORD = `e2e-${Math.random().toString(36).slice(2)}`;
const email = (label: string) => `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@e2e.test`;

const addresses = new Map<Page, string>();

async function newAccount(browser: Browser, label: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  const address = email(label);
  addresses.set(page, address);
  await page.goto('/compte');
  await page.getByText('Créer un compte', { exact: true }).click();
  await page.getByLabel('Email').fill(address);
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByText('Créer notre compte', { exact: true }).click();
  await expect(page.getByText('Bonjour, cher instigateur.')).toBeVisible();
  return page;
}

test('a duo by a link, the day’s question sealed by each, the other’s answer read once one’s own is given', async ({ browser }) => {
  const lea = await newAccount(browser, 'lea');
  // The home's gauge opens « Mon couple ».
  await lea.getByTestId('jauge').click();
  await expect(lea).toHaveURL(/\/couple$/);
  await expect(lea.getByText('Former votre duo', { exact: true })).toBeVisible();
  await lea.getByText('Obtenir mon code', { exact: true }).click();
  const code = (await lea.getByTestId('code-duo').textContent())!.trim();
  expect(code).toMatch(/^[0-9a-f]{8}$/);

  // Sam opens the link: the code is filled in.
  const sam = await newAccount(browser, 'sam');
  await sam.goto(`/couple?duo=${code}`);
  await expect(sam.getByLabel('Le code de votre moitié')).toHaveValue(code);
  await sam.getByText('Rejoindre son duo', { exact: true }).click();
  const question = sam.getByTestId('question-du-jour');
  await expect(question).toBeVisible();
  await expect(sam.getByText(/^Vous et Lea\./)).toBeVisible();

  // Where a couple starts: its profile, either one's. And no question before their first evening, but the way to it.
  const invite = sam.getByTestId('profil-a-faire');
  await expect(invite.getByText(/Un seul profil suffit, le vôtre ou celui de Lea\./)).toBeVisible();
  await expect(question.getByText('Après votre premier rendez-vous', { exact: true })).toBeVisible();
  await expect(question.getByText('Organiser notre première soirée', { exact: true })).toBeVisible();
  await expect(sam.getByLabel('Votre réponse')).toHaveCount(0);
  await invite.getByText('Faire notre profil', { exact: true }).click();
  await expect(sam).toHaveURL(/\/profil$/);

  // Their first evening lived (past the row-level security: the server kept it days ago); Léa made the profile.
  const db = await admin();
  const leaId = await userId(addresses.get(lea)!);
  expect((await db.from('soirees_choisies').insert({
    user_id: leaId, page_name: `soiree-e2e-${Date.now()}`, title: 'Premier rendez-vous', secret_title: 'Le premier soir',
    pitch: '…', vibes: ['rire'], day: '2025-06-12', formule: 'duo', personnes: 2,
  })).error).toBeNull();
  expect((await db.from('couple_profiles').insert({ id: leaId, user_id: leaId, answers: { couple: 'complices' }, profile: { vibes: {} } })).error).toBeNull();
  await sam.goto('/couple');
  await expect(question.getByText('Le fil de vos questions suit votre profil de couple.', { exact: true })).toBeVisible();
  await expect(sam.getByTestId('profil-a-faire')).toHaveCount(0);
  const asked = (await sam.getByTestId('question-texte').textContent())!;
  // A new duo starts its journey with the lightest: the first question, « Pour rire ».
  await expect(question.getByText('Pour rire', { exact: true })).toBeVisible();
  expect(asked).toMatch(/titre de l'épisode d'aujourd'hui/);
  await sam.getByLabel('Votre réponse').fill('Le café en terrasse, ce matin.');
  await sam.getByText('Sceller ma réponse', { exact: true }).click();
  await expect(sam.getByText('« Le café en terrasse, ce matin. »')).toBeVisible();
  await expect(sam.getByText(/^Pas encore donnée\s:\selle apparaîtra ici dès que Lea/)).toBeVisible();

  // Léa: told on the home that Sam answered, the same question, Sam's answer hidden until hers is sealed.
  await lea.goto('/');
  await expect(lea.getByText('Sam a répondu à la question du jour', { exact: true })).toBeVisible();
  await lea.getByText('Sam a répondu à la question du jour', { exact: true }).click();
  // The same question (the home stays mounted under the page: its call says it too).
  await expect(lea.getByTestId('question-texte')).toHaveText(asked);
  await expect(lea.getByText('Sam a répondu. Scellez votre réponse pour lire la sienne.', { exact: true })).toBeVisible();
  await expect(lea.getByText('« Le café en terrasse, ce matin. »')).toHaveCount(0);
  await lea.getByLabel('Votre réponse').fill('Ton rire au téléphone.');
  await lea.getByText('Sceller ma réponse', { exact: true }).click();
  await expect(lea.getByText('« Le café en terrasse, ce matin. »')).toBeVisible();
  await expect(lea.getByText('La réponse de Sam', { exact: true })).toBeVisible();
  // Their first evening (10 points) and a pair of answers (1): the gauge.
  await expect(lea.getByTestId('jauge').getByText('11 points', { exact: true })).toBeVisible();

  // The home no longer calls to the question once answered.
  await lea.goto('/');
  await expect(lea.getByTestId('jauge')).toBeVisible();
  await expect(lea.getByText('La question du jour', { exact: true })).toHaveCount(0);
  await expect(lea.getByText('Sam a répondu à la question du jour', { exact: true })).toHaveCount(0);

  // Sam reads Léa's answer in turn.
  await sam.reload();
  await expect(sam.getByText('« Ton rire au téléphone. »')).toBeVisible();
});

test('leaving the duo, asked twice, brings back the way to form one', async ({ browser }) => {
  const one = await newAccount(browser, 'nina');
  await one.goto('/couple');
  await one.getByText('Obtenir mon code', { exact: true }).click();
  const code = (await one.getByTestId('code-duo').textContent())!.trim();
  const other = await newAccount(browser, 'yann');
  await other.goto('/couple');
  await other.getByLabel('Le code de votre moitié').fill(code);
  await other.getByText('Rejoindre son duo', { exact: true }).click();
  await expect(other.getByTestId('question-du-jour')).toBeVisible();
  await other.getByText('Quitter le duo', { exact: true }).click();
  await expect(other.getByText(/^Vos réponses avec Nina seront effacées/)).toBeVisible();
  await other.getByText('Quitter le duo', { exact: true }).last().click();
  await expect(other.getByText('Former votre duo', { exact: true })).toBeVisible();
  await one.reload();
  await expect(one.getByText('Former votre duo', { exact: true })).toBeVisible();
});
