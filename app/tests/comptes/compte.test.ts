// Creating an account, signing in and out, and the couple's profile kept on it (couple_profiles).
import { expect, test } from '@jest/globals';
import { accountProfile, currentUser, saveAccountProfile, signIn, signOut, signUp } from '@/lib/account';
import type { Profile } from '@/lib/api';
import { supabase } from '@/lib/supabase';

import { admin, as, newAccount } from './helpers';

const profile = (persona: string) => ({
  vibes: ['rire', 'romantique'], weights: { rire: 3, romantique: 2 }, persona: { name: persona, text: '…' },
  audace: 0.5, avoid: ['frisson'], prefer: [], genres: ['jazz'], budget: 120, first_day: null, names: 'Léa & Sam',
}) as unknown as Profile;

test('an account is created and signed in at once, its email kept', async () => {
  const account = await newAccount('creation');
  const user = await currentUser();
  expect(user?.id).toBe(account.id);
  expect(user?.email).toBe(account.email);
});

test('an email already taken, a wrong password, a short one: refused, with the reason', async () => {
  const account = await newAccount('refus');
  await signOut();
  await expect(signUp(account.email, 'un-autre-secret')).rejects.toThrow(/already registered/i);
  await expect(signIn(account.email, 'pas-le-bon')).rejects.toThrow(/invalid login credentials/i);
  await expect(signIn('personne-ici@example.com', 'secret-123')).rejects.toThrow(/invalid login credentials/i);
  await expect(signUp('court@example.com', '12345')).rejects.toThrow(/at least 6 characters/i);
  await expect(signUp('pas-un-email', 'secret-123')).rejects.toThrow(/email/i);
  expect(await currentUser()).toBeNull();
});

test('signed out, then in again with the same password', async () => {
  const account = await newAccount('retour');
  await signOut();
  expect(await currentUser()).toBeNull();
  await signIn(account.email, account.password);
  expect((await currentUser())?.id).toBe(account.id);
});

test('the profile is kept on the account, then updated, one row only', async () => {
  const account = await newAccount('profil');
  expect(await accountProfile()).toBeNull();
  await saveAccountProfile({ couple: 'longue' }, profile('Les Romantiques'));
  await saveAccountProfile({ couple: 'debut' }, profile('Les Complices'));
  const saved = await accountProfile();
  expect(saved?.id).toBe(account.id);
  expect(saved?.answers).toEqual({ couple: 'debut' });
  expect(saved?.profile.persona.name).toBe('Les Complices');
  const { data } = await admin.from('couple_profiles').select('id').eq('user_id', account.id);
  expect(data).toHaveLength(1);
});

test('without an account, the profile is not saved anywhere', async () => {
  await signOut();
  await saveAccountProfile({ couple: 'longue' }, profile('Les Romantiques'));
  expect(await accountProfile()).toBeNull();
});

test("one account never reads nor overwrites another's profile", async () => {
  const lea = await newAccount('lea');
  await saveAccountProfile({ couple: 'longue' }, profile('Les Romantiques'));
  const sam = await newAccount('sam');
  expect(await accountProfile()).toBeNull();
  const read = await supabase.from('couple_profiles').select('id').eq('user_id', lea.id);
  expect(read.data).toEqual([]);
  await supabase.from('couple_profiles').update({ answers: { pirate: true } }).eq('id', lea.id);
  const forged = await supabase.from('couple_profiles').insert({ id: `${lea.id}-bis`, user_id: lea.id, answers: {}, profile: {} });
  expect(forged.error).not.toBeNull();
  await as(lea);
  expect((await accountProfile())?.answers).toEqual({ couple: 'longue' });
  expect(sam.id).not.toBe(lea.id);
});
