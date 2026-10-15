// The duo's games and what the gauge unlocks, in the browser on the local Supabase: the week's défi ticked by both and
// its badge, the week's quiz answered and guessed; an account whose complicity climbed sees a secret option more and
// the special intrigue in the evening form, then the « Minuit » theme; and on the evening's day, a card under each step.
import { type Browser, type Page } from '@playwright/test';
import { expect, test } from './fixtures';

import type { ComposedSoiree } from '@/lib/api';

import { admin, userId } from './local-admin';

test.use({ viewport: { width: 375, height: 812 } });

const PASSWORD = `e2e-${Math.random().toString(36).slice(2)}`;
const email = (label: string) => `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@e2e.test`;

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

// Two accounts paired by a code, both on « Mon couple ».
async function pair(browser: Browser) {
  const { page: lea } = await newAccount(browser, 'lea');
  await lea.goto('/couple');
  await lea.getByText('Obtenir mon code', { exact: true }).click();
  const code = (await lea.getByTestId('code-duo').textContent())!.trim();
  const { page: sam } = await newAccount(browser, 'sam');
  await sam.goto(`/couple?duo=${code}`);
  await sam.getByText('Rejoindre son duo', { exact: true }).click();
  await expect(sam.getByTestId('defi-de-la-semaine')).toBeVisible();
  await lea.reload();
  return { lea, sam };
}

// Past the row-level security of the local Supabase (never the project's): evenings lived written for an account.
async function livedEvenings(address: string, count: number) {
  const user = await userId(address);
  const rows = Array.from({ length: count }, (_, i) => ({
    user_id: user, page_name: `soiree-e2e-${Date.now()}-${i}`, title: 'Soirée passée', secret_title: 'Un souvenir',
    pitch: '…', vibes: ['rire'], day: `2025-0${(i % 9) + 1}-12`, formule: 'duo', personnes: 2,
  }));
  const { error } = await (await admin()).from('soirees_choisies').insert(rows);
  expect(error).toBeNull();
}

test('the week’s défi ticked by both, its badge; the week’s quiz answered for oneself and guessed', async ({ browser }) => {
  const { lea, sam } = await pair(browser);
  const defi = sam.getByTestId('defi-de-la-semaine');
  await defi.getByText('C’est fait', { exact: true }).click();
  await expect(defi.getByText(/^Fait de votre côté\. Il comptera dès que Lea l’aura coché\./)).toBeVisible();
  await lea.reload();
  const hers = lea.getByTestId('defi-de-la-semaine');
  await expect(hers.getByText('Sam l’a relevé. À vous !', { exact: true })).toBeVisible();
  await hers.getByText('C’est fait', { exact: true }).click();
  await expect(hers.getByText('Défi relevé à deux. Rendez-vous lundi pour le suivant.', { exact: true })).toBeVisible();
  await expect(hers.getByText('Premier pas', { exact: true })).toBeVisible();
  await expect(lea.getByTestId('jauge').getByText('4 points', { exact: true })).toBeVisible();

  // The quiz: Léa answers the first question for herself and guesses Sam's.
  const quiz = lea.getByTestId('quiz-de-la-semaine');
  await expect(quiz.getByText('0 sur 8', { exact: true })).toBeVisible();
  const mine = quiz.getByRole('radiogroup', { name: 'Pour vous' }).getByRole('radio');
  const guess = quiz.getByRole('radiogroup', { name: 'Pour Sam, à votre avis' }).getByRole('radio');
  const first = (await mine.nth(1).textContent())!;
  await mine.nth(1).click();
  await guess.nth(2).click();
  await quiz.getByText('Valider', { exact: true }).click();
  await expect(quiz.getByText('1 sur 8', { exact: true })).toBeVisible();

  // Sam: told Léa answered; answers 2 for himself (Léa guessed right), guesses 1 for her (right too).
  await sam.reload();
  const his = sam.getByTestId('quiz-de-la-semaine');
  await expect(his.getByText('Lea a déjà répondu à celle-ci.', { exact: true })).toBeVisible();
  await his.getByRole('radiogroup', { name: 'Pour vous' }).getByRole('radio').nth(2).click();
  await his.getByRole('radiogroup', { name: 'Pour Lea, à votre avis' }).getByRole('radio').nth(1).click();
  await his.getByText('Valider', { exact: true }).click();
  await expect(his.getByText('Vos bonnes devinettes : 1 · celles de Lea : 1', { exact: true })).toBeVisible();
  // (A space before « : » and « ! » is a non-breaking one on the page: themed-text.tsx.)
  await expect(his.getByText(new RegExp(`Lea\\s:\\s${first}\\s\\(deviné\\s!\\)`))).toBeVisible();

  // The seven others answered by both, each the first answer and the first guess: the quiz's verdict.
  for (const [page, other] of [[lea, 'Sam'], [sam, 'Lea']] as const) {
    await page.reload();
    const box = page.getByTestId('quiz-de-la-semaine');
    for (let n = 2; n <= 8; n++) {
      await box.getByRole('radiogroup', { name: 'Pour vous' }).getByRole('radio').first().click();
      await box.getByRole('radiogroup', { name: `Pour ${other}, à votre avis` }).getByRole('radio').first().click();
      await box.getByText('Valider', { exact: true }).click();
      await expect(box.getByText(`${n} sur 8`, { exact: true })).toBeVisible();
    }
  }
  // Sixteen guesses, fourteen right: telepathy.
  await sam.reload();
  await expect(sam.getByTestId('verdict')).toHaveText(/^Télépathes/);
});

test('the gauge unlocks a secret option more, the special intrigue, then the « Minuit » theme', async ({ browser }) => {
  const { page, address } = await newAccount(browser, 'complices');
  await page.goto('/soiree?formule=duo');
  await expect(page.getByText(/Une ou plusieurs\s:\s3 envies en tout/)).toBeVisible();
  await expect(page.getByText('L\'intrigue spéciale', { exact: true })).toHaveCount(0);

  // Four evenings lived: 40 points, « Étoiles filantes ».
  await livedEvenings(address, 4);
  await page.reload();
  await expect(page.getByText(/Une ou plusieurs\s:\s4 envies en tout/)).toBeVisible();
  await expect(page.getByText('L\'intrigue spéciale', { exact: true })).toBeVisible();
  await expect(page.getByText('Jusqu\'à 3, glissées dans le programme.', { exact: true })).toBeVisible();

  // Eight: « Constellation », the theme to choose on « Mon couple », the whole app in its night.
  await livedEvenings(address, 4);
  await page.goto('/couple');
  await expect(page.getByText('Constellation', { exact: true })).toBeVisible();
  await expect(page.getByText('Débloqué à « Constellation »', { exact: true })).toBeVisible();
  const night = () => page.getByTestId('jauge').evaluate((e) => getComputedStyle(e).backgroundColor);
  const emerald = await night();
  await page.getByText('Passer au thème « Minuit »', { exact: true }).click();
  await expect.poll(night).toBe('rgb(11, 18, 38)');
  expect(emerald).not.toBe('rgb(11, 18, 38)');
  // Kept on this device.
  await page.reload();
  await expect.poll(night).toBe('rgb(11, 18, 38)');
  await page.getByText('Revenir au thème émeraude', { exact: true }).click();
  await expect.poll(night).toBe(emerald);
});

test('on the evening’s day, each step has its card of the evening, another at a touch', async ({ browser }) => {
  const { page } = await newAccount(browser, 'ce-soir');
  const today = await page.evaluate(() => new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' }));
  await page.goto(`/soiree?formule=duo&envies=rire&jour=${today}`);
  await page.getByText('Non, déjà mangé').click();
  const composing = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/soirees');
  await page.getByText('Tramer nos intrigues').click();
  const composed: ComposedSoiree = await (await composing).json();
  expect(composed.routes[0].day).toBe(today);
  await page.getByText('Garder cette intrigue').first().click();
  await expect(page).toHaveURL(/\/revelation\?soiree=/);
  const card = page.getByTestId('carte-du-soir:0');
  await expect(card).toBeVisible();
  const before = await card.textContent();
  await card.getByText('Une autre carte', { exact: true }).click();
  await expect.poll(() => card.textContent()).not.toBe(before);
});
