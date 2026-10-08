// The emails beside the notifications, in the browser: the account's choice, and the link at the foot of an email,
// signed by the server (MAIL_SECRET), which stops them for its address, signed in or not. The invitation sent by email
// from a kept evening is in soiree.spec.ts.
import { createHmac } from 'node:crypto';

import { expect, type Page, test } from '@playwright/test';

import { MAIL_SECRET } from './mail-secret';

const PASSWORD = `e2e-${Math.random().toString(36).slice(2)}`;
const address = (label: string) => `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@e2e.test`;
// As surprise.courriers.token: the address's signature.
const signed = (email: string) => createHmac('sha256', MAIL_SECRET).update(email.toLowerCase()).digest('hex').slice(0, 32);

async function createAccount(page: Page, email: string) {
  await page.goto('/compte');
  await page.getByText('Créer un compte', { exact: true }).click();
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByText('Créer notre compte', { exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
}

test('the account chooses its emails: on until it says no, kept', async ({ page }) => {
  await createAccount(page, address('emails'));
  await page.goto('/compte');
  await expect(page.getByText(/Les moments clés de vos soirées vous arrivent aussi par email/)).toBeVisible();
  // Beside it, what the partner links are (surprise.affiliation).
  await expect(page.getByText(/Certains liens «\sRéserver\s» mènent aux sites partenaires de Secret Date/)).toBeVisible();
  await page.getByText('Ne plus recevoir les emails', { exact: true }).click();
  await expect(page.getByText('Vous ne recevez plus nos emails, seulement les notifications.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('Recevoir les emails', { exact: true })).toBeVisible();
  await page.getByText('Recevoir les emails', { exact: true }).click();
  await expect(page.getByText(/Les moments clés de vos soirées vous arrivent aussi par email/)).toBeVisible();
});

test('an email’s link stops them at once; a link not signed by the server, never', async ({ page }) => {
  const email = address('stop');
  await createAccount(page, email);
  await page.goto(`/compte?stop=${encodeURIComponent(email)}&t=faux`);
  await expect(page.getByText('Lien invalide', { exact: true })).toBeVisible();
  await page.goto(`/compte?stop=${encodeURIComponent(email)}&t=${signed(email)}`);
  await expect(page.getByText('C’est noté.', { exact: true })).toBeVisible();
  await expect(page.getByText(`${email} ne recevra plus nos emails.`, { exact: false })).toBeVisible();
  // The account's choice follows.
  await page.goto('/compte');
  await expect(page.getByText('Vous ne recevez plus nos emails, seulement les notifications.')).toBeVisible();
});
