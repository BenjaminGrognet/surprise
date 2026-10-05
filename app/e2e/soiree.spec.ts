// The couple's evening in the browser, on the test catalogue (tests/e2e_server.py) and the local Supabase: the
// instigateur creates an account, composes, changes a step, keeps the evening; the passager joins by its link and
// sees only its clues.
import { expect, type Page, test } from '@playwright/test';

import type { ComposedSoiree } from '@/lib/api';

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
  for (const route of composed.routes) for (const step of route.steps) await expect(page.getByText(step.title, { exact: true })).toBeVisible();

  // A step of the first route, changed for another activity, never one already shown; from the last step back, as
  // some have no other activity that fits (the server then says so, 409).
  const shown = new Set(composed.routes.flatMap((r) => r.steps.map((s) => s.id)));
  const changes = page.getByText('↻ Changer', { exact: true });
  await expect(changes).toHaveCount(composed.routes.reduce((n, r) => n + r.steps.length, 0));
  let changed: ComposedSoiree | null = null;
  let position = composed.routes[0].steps.length;
  while (!changed && position-- > 0) {
    const changing = posted(page, new RegExp(`^/api/parcours/${composed.name}/${composed.routes[0].steps[position].redo}$`));
    await changes.nth(position).click();
    const response = await changing;
    if (response.ok()) changed = await response.json();
    else expect(response.status()).toBe(409);
  }
  expect(changed).not.toBeNull();
  const old = composed.routes[0].steps[position];
  const step = changed!.routes[0].steps[position];
  expect(shown.has(step.id)).toBe(false);
  await expect(page.getByText(step.title, { exact: true })).toBeVisible();
  await expect(page.getByText(old.title, { exact: true })).toHaveCount(0);

  // Kept: the organiser's page, with the whole route and the passager's link.
  const choosing = posted(page, /\/routes\/0\/choose$/);
  await page.getByText('Garder cette intrigue').first().click();
  const kept: ComposedSoiree = await (await choosing).json();
  const route = kept.routes[0];
  await expect(page).toHaveURL(/\/revelation\?soiree=/);
  await expect(page.getByText(route.secret_title, { exact: true }).first()).toBeVisible();
  for (const s of route.steps) await expect(page.getByText(s.title, { exact: true })).toBeVisible();
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
  await expect(passager.getByText('Une étape encore voilée').first()).toBeVisible();
  for (const s of route.steps) await expect(passager.getByText(s.title)).toHaveCount(0);
  await other.close();

  // The instigateur's home now says the passager has joined.
  await page.goto('/');
  await expect(page.getByText(/Complices connectés/)).toBeVisible();
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
