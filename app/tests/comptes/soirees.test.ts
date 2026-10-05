// The evenings an account keeps (soirees_choisies): its history, what it booked, how they are lifted, and deleted.
import { expect, test } from '@jest/globals';
import {
  bookedSteps, chooseEvening, deleteEvening, eveningsHistory, keptEvening, keptSecretTitle, saveBookedSteps,
  saveRevealMode, signOut, upcomingEvening, upcomingEvenings,
} from '@/lib/account';
import { supabase } from '@/lib/supabase';

import { as, FUTURE, keep, newAccount, PAST, pageName } from './helpers';

test('without an account, no evening is kept', async () => {
  await signOut();
  await expect(chooseEvening({
    pageName: pageName(), title: 'Soirée', secretTitle: 'Le Secret', pitch: '…', vibes: [], day: FUTURE,
  })).rejects.toThrow('Connectez-vous pour la garder dans votre historique.');
});

test('a kept evening is in the history with its secret name, once even when kept twice', async () => {
  await newAccount('historique');
  const page = pageName();
  const row = await keep(FUTURE, page);
  await keep(FUTURE, page);
  expect(row).toMatchObject({ page_name: page, secret_title: 'Le Pacte du Marais', day: FUTURE, passager: null, reveal_mode: 'etapes' });
  expect(row.invite_code).toMatch(/^[0-9a-f]{12}$/);
  expect((await eveningsHistory()).map((r) => r.page_name)).toEqual([page]);
  expect(await keptSecretTitle(page)).toBe('Le Pacte du Marais');
});

test('the evenings to come, the nearest first; the past ones are only in the history', async () => {
  await newAccount('a-venir');
  const later = await keep('2099-07-01');
  const sooner = await keep('2099-06-01');
  const past = await keep(PAST);
  expect((await upcomingEvenings('2026-10-04')).map((r) => r.id)).toEqual([sooner.id, later.id]);
  expect((await upcomingEvening('2026-10-04'))?.id).toBe(sooner.id);
  expect((await eveningsHistory()).map((r) => r.id).sort()).toEqual([later.id, sooner.id, past.id].sort());
});

test('the steps booked and the way the evening is lifted are kept on it', async () => {
  await newAccount('coulisses');
  const row = await keep();
  expect(await bookedSteps(row.page_name)).toEqual([]);
  await saveBookedSteps(row.page_name, ['wecandoo:atelier', 'fever:concert']);
  expect(await bookedSteps(row.page_name)).toEqual(['wecandoo:atelier', 'fever:concert']);
  await saveRevealMode(row.id, 'arrivee');
  expect((await keptEvening(row.page_name))?.reveal_mode).toBe('arrivee');
  await expect(saveRevealMode(row.id, 'tout-de-suite' as never)).rejects.toThrow();
});

test("another account sees nothing of an evening it neither keeps nor joined, and changes nothing", async () => {
  const lea = await newAccount('lea');
  const row = await keep();
  await newAccount('intrus');
  expect(await keptEvening(row.page_name)).toBeNull();
  expect(await eveningsHistory()).toEqual([]);
  await expect(saveBookedSteps(row.page_name, ['x:y'])).rejects.toThrow("Cette soirée n'est pas gardée sur votre compte.");
  await expect(saveRevealMode(row.id, 'veille')).rejects.toThrow("Cette soirée n'est pas gardée sur votre compte.");
  await expect(deleteEvening(row.id)).rejects.toThrow("Cette soirée n'a pas pu être supprimée.");
  // Nor keeps one in its name.
  const forged = await supabase.from('soirees_choisies').insert({
    user_id: lea.id, page_name: pageName(), title: 't', pitch: 'p',
  });
  expect(forged.error).not.toBeNull();
  await as(lea);
  expect(await keptEvening(row.page_name)).toMatchObject({ id: row.id, booked: [], reveal_mode: 'etapes' });
});

test('a past evening is deleted, one to come is not', async () => {
  await newAccount('archives');
  const past = await keep(PAST);
  const coming = await keep(FUTURE);
  await deleteEvening(past.id);
  await expect(deleteEvening(coming.id)).rejects.toThrow("Cette soirée n'a pas pu être supprimée.");
  expect((await eveningsHistory()).map((r) => r.id)).toEqual([coming.id]);
});
