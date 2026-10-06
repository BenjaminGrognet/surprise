// Secret Squad: a band's evening, its guests invited by two links — the passagers', who only get the clues, and the
// complices', in on the secret — while it has places (supabase/migrations/…_secret_squad.sql).
import { expect, test } from '@jest/globals';
import { chooseEvening, deleteEvening, keptEvening, saveBookedSteps, saveRevealMode, signOut } from '@/lib/account';
import { eveningRole, guests, joinEvening, myRole, organises, placesLeft, removeGuest, resetPassager } from '@/lib/couple';
import { book, sealPage } from '@/lib/souvenirs';

import { as, FUTURE, newAccount, PAST, pageName } from './helpers';

// A band's evening kept by the account signed in, for `personnes` (its instigateur counted); its row.
async function keepBand(personnes = 4, day: string = FUTURE) {
  const page = pageName();
  await chooseEvening({
    pageName: page, title: 'Quiz et karaoké à Pigalle', secretTitle: 'La Virée de Pigalle', pitch: 'Un soir en bande.',
    vibes: ['Fous rires'], day, formule: 'squad', personnes,
  });
  const row = await keptEvening(page);
  if (!row) throw new Error(`${page} : pas gardée`);
  return row;
}

test('a band joins by the passagers link until it is complete; each of them only gets the clues', async () => {
  const lea = await newAccount('cerveau');
  const row = await keepBand(4);
  expect(row).toMatchObject({ formule: 'squad', personnes: 4, invites: [] });
  expect(row.codes?.complice_code).toMatch(/^[0-9a-f]{12}$/);
  expect(row.codes!.complice_code).not.toBe(row.invite_code);
  await expect(joinEvening(row.invite_code)).rejects.toThrow("C'est votre propre invitation : envoyez-la à votre bande.");

  const band = [];
  for (const label of ['un', 'deux', 'trois']) {
    band.push(await newAccount(`bande-${label}`));
    expect(await joinEvening(row.invite_code)).toBe('passager');
    const seen = await keptEvening(row.page_name);
    expect(eveningRole(seen!, band[band.length - 1].id)).toBe('passager');
    expect(await myRole()).toMatchObject({ role: 'passager' });
    // The complices' link is never theirs to read: it would lift the veil.
    expect(seen!.codes).toBeNull();
  }
  // The band sees itself: who else is coming.
  expect(guests((await keptEvening(row.page_name))!).map((g) => g.user_id).sort()).toEqual(band.map((a) => a.id).sort());

  await newAccount('de-trop');
  await expect(joinEvening(row.invite_code)).rejects.toThrow("La bande est au complet : demandez une place de plus à l'organisateur.");
  expect(await keptEvening(row.page_name)).toBeNull();

  await as(lea);
  const full = await keptEvening(row.page_name);
  expect(guests(full!, 'passager')).toHaveLength(3);
  expect(placesLeft(full!)).toBe(0);
});

test('a complice joins by their own link: the whole evening, its bookings, never its owner’s controls', async () => {
  const lea = await newAccount('cerveau');
  const row = await keepBand(5, PAST);
  const code = row.codes!.complice_code;
  const guest = await newAccount('invitee');
  await joinEvening(row.invite_code);

  const tom = await newAccount('temoin');
  expect(await joinEvening(code)).toBe('complice');
  expect(await joinEvening(code)).toBe('complice'); // the link opened twice
  const seen = await keptEvening(row.page_name);
  // On the secret's side, as its instigateur: the organiser's view, and the complices' link to pass on.
  expect(eveningRole(seen!, tom.id)).toBe('instigateur');
  expect(organises(seen!, tom.id)).toBe(false);
  expect(seen!.codes?.complice_code).toBe(code);
  expect(await myRole()).toMatchObject({ role: 'instigateur' });
  // Ticks the bookings; chooses neither the reveal nor who comes, deletes nothing.
  await saveBookedSteps(row.page_name, ['test:quiz']);
  await expect(saveRevealMode(row.id, 'veille')).rejects.toThrow("Cette soirée n'est pas gardée sur votre compte.");
  await expect(removeGuest(row.id, guest.id)).rejects.toThrow("Cet invité n'a pas pu être retiré.");
  await expect(resetPassager(row.id)).rejects.toThrow('Soirée introuvable.');
  await expect(deleteEvening(row.id)).rejects.toThrow("Cette soirée n'a pas pu être supprimée.");

  // A passager of the band books nothing.
  await as(guest);
  await expect(saveBookedSteps(row.page_name, [])).rejects.toThrow("Cette soirée n'est pas gardée sur votre compte.");

  await as(lea);
  const kept = await keptEvening(row.page_name);
  expect(kept!.booked).toEqual(['test:quiz']);
  expect(guests(kept!).map((g) => g.role).sort()).toEqual(['complice', 'passager']);
});

test('the instigateur lets one of the band go, whose place another takes; a guest may leave', async () => {
  const lea = await newAccount('cerveau');
  const row = await keepBand(3);
  const sam = await newAccount('sam');
  await joinEvening(row.invite_code);
  const zoe = await newAccount('zoe');
  await joinEvening(row.invite_code);

  await as(lea);
  await removeGuest(row.id, sam.id);
  expect(guests((await keptEvening(row.page_name))!).map((g) => g.user_id)).toEqual([zoe.id]);
  await as(sam);
  expect(await keptEvening(row.page_name)).toBeNull();
  // The link still works for the band: the place freed is taken again.
  await newAccount('remplacant');
  await joinEvening(row.invite_code);
  expect(await keptEvening(row.page_name)).not.toBeNull();

  await as(zoe);
  await removeGuest(row.id, zoe.id);
  expect(await keptEvening(row.page_name)).toBeNull();
});

test('the whole band seals its book, each page shown once one’s own is sealed', async () => {
  const lea = await newAccount('cerveau');
  const row = await keepBand(3, PAST);
  const sam = await newAccount('sam');
  await joinEvening(row.invite_code);
  await newAccount('zoe');
  await joinEvening(row.invite_code);
  await sealPage(row.id, 'Le karaoké, jamais plus', null);

  await as(sam);
  expect((await book(row.page_name))!.pages.map((p) => p.note)).toEqual([]);
  await sealPage(row.id, 'Le quiz, on a gagné', null);
  expect((await book(row.page_name))!.pages.map((p) => p.note).sort()).toEqual(['Le karaoké, jamais plus', 'Le quiz, on a gagné']);

  await as(lea);
  await sealPage(row.id, 'Merci la bande', null);
  const all = (await book(row.page_name))!;
  expect(all.pages).toHaveLength(3);
  expect(guests(all.evening)).toHaveLength(2);
});

test('a band counts 2 to 10, a couple two', async () => {
  await newAccount('compte');
  for (const personnes of [1, 11]) {
    await expect(keepBand(personnes)).rejects.toThrow();
  }
  // Two friends: a band all the same, one place for the friend.
  const friends = await keepBand(2);
  expect(friends).toMatchObject({ formule: 'squad', personnes: 2 });
  expect(friends.codes?.complice_code).toMatch(/^[0-9a-f]{12}$/);
  expect(placesLeft(friends)).toBe(1);
  await newAccount('pote');
  expect(await joinEvening(friends.invite_code)).toBe('passager');
  await newAccount('de-trop');
  await expect(joinEvening(friends.invite_code)).rejects.toThrow("La bande est au complet : demandez une place de plus à l'organisateur.");
  await signOut();
});
