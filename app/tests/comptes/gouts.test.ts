// The couple's tastes (gouts): a vote on a step kept on the account, changed, withdrawn; each account its own, gone
// with it.
import { expect, test } from '@jest/globals';
import { deleteMyAccount, myTastes, saveTaste, signOut, votesOf } from '@/lib/account';
import { supabase } from '@/lib/supabase';

import { admin, as, newAccount } from './helpers';

const ESCAPE = { id: 'fever:12', title: 'Escape game des pirates' };
const QUIZ = { id: 'osm_loisirs:node:5', title: 'Quiz au pub' };

test('a vote is kept, changed, then withdrawn: one per activity, the latest first', async () => {
  await newAccount('gouts');
  expect(await myTastes()).toEqual([]);
  await saveTaste(ESCAPE, 1);
  await saveTaste(QUIZ, -1);
  expect(votesOf(await myTastes())).toEqual({ [ESCAPE.id]: 1, [QUIZ.id]: -1 });
  await saveTaste(ESCAPE, -1);
  const rows = await myTastes();
  expect(rows.map((r) => [r.activity_id, r.vote, r.title])).toEqual([[ESCAPE.id, -1, ESCAPE.title], [QUIZ.id, -1, QUIZ.title]]);
  await saveTaste(QUIZ, null);
  expect(votesOf(await myTastes())).toEqual({ [ESCAPE.id]: -1 });
});

test('without an account, no vote is kept', async () => {
  await signOut();
  await expect(saveTaste(ESCAPE, 1)).rejects.toThrow('Connectez-vous pour garder vos goûts.');
  expect(await myTastes()).toEqual([]);
});

test('a vote is +1 or -1, nothing else', async () => {
  const account = await newAccount('vote-faux');
  const { error } = await supabase.from('gouts').insert({ user_id: account.id, activity_id: ESCAPE.id, vote: 2 });
  expect(error).not.toBeNull();
  expect(await myTastes()).toEqual([]);
});

test("one account never reads, changes nor casts another's votes", async () => {
  const lea = await newAccount('lea-gouts');
  await saveTaste(ESCAPE, 1);
  await newAccount('sam-gouts');
  expect(await myTastes()).toEqual([]);
  await supabase.from('gouts').update({ vote: -1 }).eq('user_id', lea.id);
  await supabase.from('gouts').delete().eq('user_id', lea.id);
  const forged = await supabase.from('gouts').insert({ user_id: lea.id, activity_id: QUIZ.id, vote: -1 });
  expect(forged.error).not.toBeNull();
  await as(lea);
  expect(votesOf(await myTastes())).toEqual({ [ESCAPE.id]: 1 });
});

test('the votes go with the account', async () => {
  const account = await newAccount('gouts-partis');
  await saveTaste(ESCAPE, 1);
  await deleteMyAccount();
  const { data } = await admin.from('gouts').select('activity_id').eq('user_id', account.id);
  expect(data).toEqual([]);
});
