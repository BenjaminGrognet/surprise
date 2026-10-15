// The programme « 4 semaines pour se retrouver » and the morning after's review
// (supabase/migrations/…_programme_bilans.sql): a week opening every seven days, its défi done once both ticked it and
// counted in the gauge; each one's favourite moment of an evening read by the other once their own is given, never
// before the evening's day, its « à refaire » and « à éviter » kept as the couple's votes.
import { expect, test } from '@jest/globals';
import { myTastes } from '@/lib/account';
import { giveReview, reviews } from '@/lib/bilan';
import { myComplicity } from '@/lib/complicity';
import { joinEvening } from '@/lib/couple';
import { joinDuo, myDuo, myProgramme, openDuo, programmeDone, startProgramme } from '@/lib/duo';
import { supabase } from '@/lib/supabase';

import { admin, as, FUTURE, keep, newAccount, PAST } from './helpers';

const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' });

test('the programme: started by a complete duo, a week every seven days, its défi done by both counted', async () => {
  const one = await newAccount('programme-un');
  const code = await openDuo();
  await expect(startProgramme()).rejects.toThrow("Formez d'abord votre duo : le programme se vit à deux.");
  expect(await myProgramme()).toEqual({ started_on: null, semaine: 0, semaines: [] });
  await expect(programmeDone(1)).rejects.toThrow("Commencez d'abord le programme.");

  await newAccount('programme-deux');
  await joinDuo(code);
  await startProgramme();
  const started = await myProgramme();
  expect(started.semaine).toBe(1);
  expect(started.semaines.map((w) => [w.semaine, w.titre, w.ouverte])).toEqual([
    [1, 'Se retrouver', true], [2, 'Se redécouvrir', false], [3, 'Se surprendre', false], [4, 'Se promettre', false],
  ]);
  expect(started.semaines[0].envies).toEqual(['nous', 'cocooning']);
  await expect(programmeDone(2)).rejects.toThrow("Cette semaine n'est pas encore ouverte.");

  const before = (await myComplicity()).points;
  await programmeDone(1);
  await programmeDone(1); // twice: once only
  expect((await myProgramme()).semaines[0]).toMatchObject({ fait_par_moi: true, fait_par_l_autre: false });
  expect((await myComplicity()).points).toBe(before);
  await as(one);
  expect((await myProgramme()).semaines[0]).toMatchObject({ fait_par_moi: false, fait_par_l_autre: true });
  await programmeDone(1);
  expect((await myComplicity()).points).toBe(before + 4);

  await expect(startProgramme()).rejects.toThrow('Votre programme est en cours : il se recommence une fois ses quatre semaines passées.');

  // Fifteen days later (the start and its ticks moved back): the third week; past the fourth, the programme is over
  // (5), begun again at will.
  const duo = (await myDuo())!;
  const startedOn = async (day: string) => {
    await admin.from('programme_faits').update({ started_on: day }).eq('duo_id', duo.id);
    await admin.from('programmes_duo').update({ started_on: day }).eq('duo_id', duo.id);
  };
  await startedOn(daysAgo(15));
  const third = await myProgramme();
  expect(third.semaine).toBe(3);
  expect(third.semaines.filter((w) => w.ouverte).map((w) => w.semaine)).toEqual([1, 2, 3]);
  expect(third.semaines[0]).toMatchObject({ fait_par_moi: true, fait_par_l_autre: true });
  await startedOn(daysAgo(40));
  expect((await myProgramme()).semaine).toBe(5);
  await programmeDone(4);
  await startProgramme();
  const again = await myProgramme();
  expect(again.semaine).toBe(1);
  expect(again.semaines.every((w) => !w.fait_par_moi && !w.fait_par_l_autre)).toBe(true);
  // Its défis done before stay counted.
  expect((await myComplicity()).points).toBe(before + 4);

  // Nobody else reads it.
  await newAccount('programme-autre');
  expect((await supabase.from('programmes_duo').select('*')).data).toEqual([]);
  expect((await supabase.from('programme_faits').select('*')).data).toEqual([]);
});

test("the morning after: each one's favourite read once one's own is given, the votes kept, never before the day", async () => {
  const lea = await newAccount('bilan-un');
  const row = await keep(PAST);
  const later = await keep(FUTURE);
  const sam = await newAccount('bilan-deux');
  await joinEvening(row.invite_code);
  const steps = [
    { id: 'test:musee', title: 'Le Musée des Rêves' },
    { id: 'test:bar', title: 'Le Bar Secret' },
    { id: 'test:club', title: 'Le Club Bruyant' },
  ];

  await giveReview(row.id, steps[0], [steps[1]], [steps[2]]);
  await expect(giveReview(row.id, steps[1], [], [])).rejects.toThrow('Votre bilan est déjà donné.');
  expect(await reviews(row.id)).toEqual([{ author: sam.id, prefere: 'test:musee', prefere_titre: 'Le Musée des Rêves', mine: true }]);
  const votes = Object.fromEntries((await myTastes()).map((t) => [t.activity_id, t.vote]));
  expect(votes).toMatchObject({ 'test:bar': 1, 'test:club': -1 });
  expect(votes['test:musee']).toBeUndefined();

  // Léa reads nothing of Sam's before giving hers; then both, hers first.
  await as(lea);
  expect(await reviews(row.id)).toEqual([]);
  await giveReview(row.id, steps[1], [], []);
  expect((await reviews(row.id)).map((b) => [b.prefere_titre, b.mine])).toEqual([['Le Bar Secret', true], ['Le Musée des Rêves', false]]);
  // An evening still to come: no review yet.
  await expect(giveReview(later.id, steps[0], [], [])).rejects.toThrow(/row-level security/);

  // A stranger reads none.
  await newAccount('bilan-autre');
  expect((await supabase.from('bilans').select('*').eq('soiree_id', row.id)).data).toEqual([]);
});
