// A couple's order (supabase/migrations/…_premier_soir_profil.sql): their profile first, one for two; the questions du
// jour from the day after their first evening for two lived, never before; and each duo's journey moved a little by
// its profile's answers.
import { expect, test } from '@jest/globals';
import { answerToday, duoProfile, joinDuo, myDuo, openDuo, todaysQuestion } from '@/lib/duo';

import { admin, as, firstEvening, FUTURE, keep, newAccount, PAST } from './helpers';

const parisDay = (offset: number) => new Date(Date.now() + offset * 86_400_000).toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' });

async function pair(label: string) {
  const one = await newAccount(`${label}-un`);
  const code = await openDuo();
  const other = await newAccount(`${label}-deux`);
  await joinDuo(code);
  return { one, other, duo: (await myDuo())! };
}

// A profile made by an account (surprise.quiz's answers), past the row-level security.
async function profile(userId: string, answers: Record<string, unknown>) {
  const { error } = await admin.from('couple_profiles').insert({ id: userId, user_id: userId, answers, profile: { vibes: {} } });
  expect(error).toBeNull();
}

// `count` days answered by the account before today, the oldest first: the journey that far along.
async function answered(duoId: string, author: string, count: number) {
  const days = Array.from({ length: count }, (_, i) => ({ duo_id: duoId, day: parisDay(-count - 1 + i), author, question_id: 1, texte: '…' }));
  expect((await admin.from('reponses_du_jour').insert(days)).error).toBeNull();
}

test('no question du jour before the day after their first evening for two: when it begins, and no answer before', async () => {
  const { one, other } = await pair('premier-soir');
  expect(await todaysQuestion()).toMatchObject({ commence: false, question: null, premiere: { vecue: null, prevue: null } });
  await expect(answerToday('Déjà ?')).rejects.toThrow('Vos questions du jour commencent au lendemain de votre première soirée à deux.');

  // The first evening chosen by the other, ahead: told when they begin.
  await as(one);
  await keep(FUTURE);
  await as(other);
  expect((await todaysQuestion()).premiere).toEqual({ vecue: null, prevue: FUTURE });
  // Lived today: tomorrow, not yet.
  await firstEvening(one.id, parisDay(0));
  expect(await todaysQuestion()).toMatchObject({ commence: false, premiere: { vecue: null, prevue: parisDay(0) } });
  // Lived before: the journey begins, from its first question.
  await firstEvening(one.id, PAST);
  const jour = await todaysQuestion();
  expect(jour).toMatchObject({ commence: true, premiere: null, adaptee: false, question: { id: 1, profondeur: 1 } });
  await answerToday('Le pilote.');
});

test("the duo's profile: the account's own, else its partner's; the questions then follow it", async () => {
  const { one, other } = await pair('profil-duo');
  await firstEvening(one.id);
  expect(await duoProfile()).toBeNull();
  await profile(one.id, { couple: 'complices' });
  // Made by the other: it counts for both, and only its answers and profile are read.
  expect(await duoProfile()).toEqual({ answers: { couple: 'complices' }, profile: { vibes: {} } });
  expect((await todaysQuestion()).adaptee).toBe(true);
  await profile(other.id, { couple: 'longue' });
  expect((await duoProfile())!.answers).toEqual({ couple: 'longue' });
  await as(one);
  expect((await duoProfile())!.answers).toEqual({ couple: 'complices' });
  // Someone outside the duo reads none.
  await newAccount('profil-curieux');
  expect(await duoProfile()).toBeNull();
});

test('a couple discovering each other meets the most intimate later; one wanting nothing « coquin », never the désir', async () => {
  const { data } = await (await newAccount('profil-parcours'), admin.from('questions_du_jour').select('id, profondeur, theme').order('id'));
  const questions = data as { id: number; profondeur: number; theme: string }[];
  const firstIntimate = questions.findIndex((q) => q.profondeur === 4);
  const desirs = questions.filter((q) => q.theme === 'désir').length;
  expect(desirs).toBeGreaterThan(0);

  // Without a profile, as far along as the first « À cœur ouvert »: it comes (parcours.test.ts); just met, not yet.
  const debut = await pair('profil-debut');
  await firstEvening(debut.one.id);
  await profile(debut.one.id, { couple: 'debut' });
  await answered(debut.duo.id, debut.one.id, firstIntimate);
  expect((await todaysQuestion()).question!.profondeur).toBeLessThan(4);

  // « Le coquin » never wanted: the désir out of the journey, which starts again sooner.
  const sage = await pair('profil-sage');
  await firstEvening(sage.one.id);
  await profile(sage.one.id, { eviter: ['coquin', 'peur'] });
  await answered(sage.duo.id, sage.one.id, questions.length - desirs);
  expect((await todaysQuestion()).question).toMatchObject({ id: 1 });
});
