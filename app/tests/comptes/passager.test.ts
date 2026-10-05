// The passager, invited to one evening by its link (join_evening), let go with a fresh link (reset_passager).
import { expect, test } from '@jest/globals';
import { deleteEvening, eveningsHistory, keptEvening, saveBookedSteps, saveRevealMode, signOut } from '@/lib/account';
import { eveningRole, joinEvening, myRole, resetPassager } from '@/lib/couple';

import { as, keep, newAccount, PAST } from './helpers';

test('the passager joins by the link and sees the evening; the instigateur sees who joined', async () => {
  const lea = await newAccount('instigatrice');
  const row = await keep();
  expect(await myRole()).toEqual({ role: 'instigateur', userId: lea.id });
  await expect(joinEvening(row.invite_code)).rejects.toThrow("C'est votre propre invitation : envoyez-la à votre passager.");

  const sam = await newAccount('passager');
  expect(await keptEvening(row.page_name)).toBeNull();
  await joinEvening(row.invite_code);
  await joinEvening(row.invite_code); // the link opened twice
  expect(await myRole()).toEqual({ role: 'passager', userId: sam.id });
  const seen = await keptEvening(row.page_name);
  expect(seen).toMatchObject({ id: row.id, passager: sam.id, passager_email: sam.email });
  expect(eveningRole(seen!, sam.id)).toBe('passager');
  expect((await eveningsHistory()).map((r) => r.id)).toEqual([row.id]);

  await as(lea);
  const kept = await keptEvening(row.page_name);
  expect(kept).toMatchObject({ passager: sam.id, passager_email: sam.email });
  expect(eveningRole(kept!, lea.id)).toBe('instigateur');
});

test('a link already taken, a wrong one, or no account: refused', async () => {
  await newAccount('instigateur');
  const row = await keep();
  await newAccount('premier');
  await joinEvening(row.invite_code);
  await newAccount('second');
  await expect(joinEvening(row.invite_code)).rejects.toThrow('Cette invitation a déjà été acceptée.');
  await expect(joinEvening('000000000000')).rejects.toThrow('Invitation introuvable : demandez un nouveau lien.');
  expect(await keptEvening(row.page_name)).toBeNull();
  await signOut();
  await expect(joinEvening(row.invite_code)).rejects.toThrow();
});

test('the passager only reads: books nothing, lifts nothing, deletes nothing', async () => {
  await newAccount('instigateur');
  const row = await keep(PAST);
  await newAccount('passager');
  await joinEvening(row.invite_code);
  await expect(saveBookedSteps(row.page_name, ['x:y'])).rejects.toThrow("Cette soirée n'est pas gardée sur votre compte.");
  await expect(saveRevealMode(row.id, 'veille')).rejects.toThrow("Cette soirée n'est pas gardée sur votre compte.");
  await expect(deleteEvening(row.id)).rejects.toThrow("Cette soirée n'a pas pu être supprimée.");
  await expect(resetPassager(row.id)).rejects.toThrow('Soirée introuvable.');
});

test('the passager let go: the evening hidden from them, the old link dead, a new one for another', async () => {
  const lea = await newAccount('instigatrice');
  const row = await keep();
  const sam = await newAccount('passager');
  await joinEvening(row.invite_code);

  await as(lea);
  await resetPassager(row.id);
  const fresh = await keptEvening(row.page_name);
  expect(fresh).toMatchObject({ passager: null, passager_email: null });
  expect(fresh!.invite_code).not.toBe(row.invite_code);

  await as(sam);
  expect(await keptEvening(row.page_name)).toBeNull();
  expect(await myRole()).toEqual({ role: 'instigateur', userId: sam.id });
  await expect(joinEvening(row.invite_code)).rejects.toThrow('Invitation introuvable : demandez un nouveau lien.');

  await newAccount('autre');
  await joinEvening(fresh!.invite_code);
  expect(await keptEvening(row.page_name)).not.toBeNull();
});

test('a passager composes an evening of their own, where the other is the passager', async () => {
  const lea = await newAccount('instigatrice');
  const first = await keep();
  const sam = await newAccount('passager');
  await joinEvening(first.invite_code);

  const second = await keep();
  expect(eveningRole(second, sam.id)).toBe('instigateur');
  await as(lea);
  await joinEvening(second.invite_code);
  const theirs = await keptEvening(second.page_name);
  expect(eveningRole(theirs!, lea.id)).toBe('passager');
  expect((await eveningsHistory()).map((r) => r.id).sort()).toEqual([first.id, second.id].sort());
});
