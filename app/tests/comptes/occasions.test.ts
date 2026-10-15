// Les dates et les occasions (supabase/migrations/…_dates_saisons.sql): the duo's dates noted by either and read by
// both only; the intrigues the server composed for a date, ready for the account alone; the seasons coming; an
// evening lived a year ago, come back.
import { expect, test } from '@jest/globals';
import { eveningsHistory } from '@/lib/account';
import { joinDuo, myDuo, openDuo } from '@/lib/duo';
import { addKeyDate, dayOfYear, keyDates, parseDayMonth, readyIntrigues, removeKeyDate, seasonsAhead, yearAgo } from '@/lib/occasions';
import { sealPage } from '@/lib/souvenirs';
import { supabase } from '@/lib/supabase';

import { admin, as, keep, newAccount, PHOTO } from './helpers';

async function pair(label: string) {
  const one = await newAccount(`${label}-un`);
  const code = await openDuo();
  const other = await newAccount(`${label}-deux`);
  await joinDuo(code);
  return { one, other, duo: (await myDuo())! };
}

test('the dates that count: noted by either, read by both, a birthday for one of the two, never seen outside', async () => {
  const { one, other, duo } = await pair('dates');
  await addKeyDate(duo.id, { label: ' Notre rencontre ', genre: 'rencontre', jour: 20, mois: 11 });
  await addKeyDate(duo.id, { label: 'Anniversaire de Léa', genre: 'anniversaire', jour: 3, mois: 2, pour: one.id });
  await expect(addKeyDate(duo.id, { label: 'Jamais', genre: 'autre', jour: 31, mois: 2 })).rejects.toThrow("Cette date n'existe pas");
  await expect(addKeyDate(duo.id, { label: '  ', genre: 'autre', jour: 1, mois: 2 })).rejects.toThrow('Donnez un nom à cette date.');

  await as(one);
  const dates = await keyDates();
  expect(dates.map((d) => [d.label, d.mois, d.jour, d.pour])).toEqual([['Anniversaire de Léa', 2, 3, one.id], ['Notre rencontre', 11, 20, null]]);
  expect(dayOfYear(dates[1])).toBe('20 novembre');

  // Someone else: reads nothing, writes nothing into the duo, nor a birthday for a stranger.
  const intrus = await newAccount('intrus');
  expect(await keyDates()).toEqual([]);
  const forged = await supabase.from('dates_cles').insert({ duo_id: duo.id, label: 'X', genre: 'autre', mois: 1, jour: 1 });
  expect(forged.error).not.toBeNull();
  await as(other);
  const stranger = await supabase.from('dates_cles').insert({ duo_id: duo.id, label: 'X', genre: 'anniversaire', mois: 1, jour: 1, pour: intrus.id });
  expect(stranger.error).not.toBeNull();
  await removeKeyDate(dates[0].id);
  expect((await keyDates()).map((d) => d.label)).toEqual(['Notre rencontre']);
});

test('a day of the year as typed: 14/02, 1.6, 3-12', () => {
  expect(parseDayMonth('14/02')).toEqual({ jour: 14, mois: 2 });
  expect(parseDayMonth(' 1.6 ')).toEqual({ jour: 1, mois: 6 });
  expect(parseDayMonth('3-12')).toEqual({ jour: 3, mois: 12 });
  expect(parseDayMonth('demain')).toBeNull();
});

test('the intrigues ready for a date are the account’s alone, gone once an evening is kept that day', async () => {
  const lea = await newAccount('pretes');
  const rows = [
    { user_id: lea.id, cle: 'date:x:2099-11-20', page_name: 'soiree-prete', day: '2099-11-20', label: '« Notre rencontre »' },
    { user_id: lea.id, cle: 'date:y:2020-02-14', page_name: 'soiree-passee', day: '2020-02-14', label: 'La saint-valentin' },
  ];
  expect((await admin.from('intrigues_pretes').insert(rows)).error).toBeNull();
  const today = new Date().toISOString().slice(0, 10);
  expect((await readyIntrigues(today, [])).map((r) => r.page_name)).toEqual(['soiree-prete']);
  expect(await readyIntrigues(today, [{ day: '2099-11-20' }])).toEqual([]);
  await newAccount('voisin');
  expect(await readyIntrigues(today, [])).toEqual([]);
});

test('the seasons coming within three weeks, with their wishes and days', async () => {
  await newAccount('saisons');
  expect((await seasonsAhead('2026-10-15')).map((s) => [s.id, s.debut, s.fin])).toEqual([['halloween', '2026-10-31', '2026-10-31']]);
  expect((await seasonsAhead('2026-12-10')).map((s) => [s.id, s.debut, s.fin])).toEqual([['noel', '2026-12-01', '2026-12-24']]);
  expect(await seasonsAhead('2026-08-01')).toEqual([]);
  const [summer] = await seasonsAhead('2027-06-05');
  expect(summer).toMatchObject({ id: 'fete-de-la-musique', debut: '2027-06-21', envies: ['musique', 'fete'] });
});

test('an evening lived a year ago comes back, with the photo of its Livre', async () => {
  await newAccount('un-an');
  const row = await keep('2025-10-17');
  await sealPage(row.id, 'Inoubliable', PHOTO);
  const history = await eveningsHistory();
  const back = await yearAgo(history, '2026-10-15');
  expect(back?.evening.id).toBe(row.id);
  expect(back?.photoUrl).toMatch(/^http/);
  expect(await yearAgo(history, '2026-11-15')).toBeNull();
});
