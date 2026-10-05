// An account deleted: everything of it goes (profile, evenings, pages, photos); the evenings it joined stay theirs.
import { expect, test } from '@jest/globals';
import { deleteMyAccount, keptEvening, saveAccountProfile, signIn } from '@/lib/account';
import type { Profile } from '@/lib/api';
import { joinEvening } from '@/lib/couple';
import { sealPage } from '@/lib/souvenirs';
import { currentUser } from '@/lib/supabase';

import { admin, as, keep, newAccount, PAST, PHOTO } from './helpers';

async function photos(soireeId: string) {
  const { data: folders } = await admin.storage.from('souvenirs').list(soireeId);
  const files = await Promise.all((folders ?? []).map((f) => admin.storage.from('souvenirs').list(`${soireeId}/${f.name}`)));
  return files.flatMap(({ data }) => data ?? []);
}

test("the instigateur's account deleted takes its evenings, their pages and photos, and its profile", async () => {
  const lea = await newAccount('instigatrice');
  await saveAccountProfile({ couple: 'longue' }, { vibes: ['rire'] } as unknown as Profile);
  const row = await keep(PAST);
  await sealPage(row.id, 'Souvenir', PHOTO);
  const sam = await newAccount('passager');
  await joinEvening(row.invite_code);
  await sealPage(row.id, 'Le mien', PHOTO);
  expect(await photos(row.id)).toHaveLength(2);

  await as(lea);
  await deleteMyAccount();
  expect(await currentUser()).toBeNull();
  await expect(signIn(lea.email, lea.password)).rejects.toThrow('Email ou mot de passe incorrect.');
  expect((await admin.auth.admin.getUserById(lea.id)).data.user).toBeNull();
  expect((await admin.from('couple_profiles').select('id').eq('user_id', lea.id)).data).toEqual([]);
  expect((await admin.from('soirees_choisies').select('id').eq('id', row.id)).data).toEqual([]);
  expect((await admin.from('souvenirs').select('author').eq('soiree_id', row.id)).data).toEqual([]);
  expect(await photos(row.id)).toEqual([]);
  // The passager's account stays.
  await as(sam);
  expect(await keptEvening(row.page_name)).toBeNull();
});

test("the passager's account deleted: the evening stays its instigateur's, without passager nor the passager's page", async () => {
  const lea = await newAccount('instigatrice');
  const row = await keep(PAST);
  await sealPage(row.id, 'Souvenir', PHOTO);
  await newAccount('passager');
  await joinEvening(row.invite_code);
  await sealPage(row.id, 'Le mien', PHOTO);

  await deleteMyAccount();
  await as(lea);
  expect(await keptEvening(row.page_name)).toMatchObject({ id: row.id, passager: null });
  const { data: pages } = await admin.from('souvenirs').select('author').eq('soiree_id', row.id);
  expect(pages).toEqual([{ author: lea.id }]);
  expect((await photos(row.id)).length).toBe(1);
});
