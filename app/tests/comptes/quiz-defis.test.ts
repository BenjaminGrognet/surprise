// The week's quiz, the week's défi and the cards of the evening (supabase/migrations/…_quiz_defis_cartes.sql): each
// answers for themselves and guesses the other, read once both answered; a défi done once both ticked it; the cards the
// same for everyone on an evening. All of it climbing the gauge.
import { expect, test } from '@jest/globals';
import { allCards, cardFor } from '@/lib/cartes';
import { myComplicity } from '@/lib/complicity';
import { answerQuiz, badgesFor, defiDone, joinDuo, weeksQuiz, openDuo, weeksDefi } from '@/lib/duo';
import { supabase } from '@/lib/supabase';

import { as, newAccount } from './helpers';

async function pair(label: string) {
  const one = await newAccount(`${label}-un`);
  const code = await openDuo();
  const other = await newAccount(`${label}-deux`);
  await joinDuo(code);
  return { one, other };
}

test("the week's quiz: one's answer and guess, the other's read once both answered, the right guesses counted", async () => {
  const { one } = await pair('quiz');
  const quiz = await weeksQuiz();
  expect(quiz.questions).toHaveLength(8);
  expect(quiz.questions.map((q) => q.rang)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
  expect(quiz.questions.every((q) => q.choix.length === 4 && q.moi === null)).toBe(true);
  const [first, second] = quiz.questions;

  // The second account (signed in) answers the first question: 2 for itself, guesses 1 for the other.
  await answerQuiz(first.id, 2, 1);
  await expect(answerQuiz(first.id, 0, 0)).rejects.toThrow('Votre réponse à cette question est déjà donnée.');
  await expect(answerQuiz(99999, 0, 0)).rejects.toThrow("Cette question n'est pas celle de la semaine.");
  expect((await weeksQuiz()).questions[0]).toMatchObject({ moi: 2, devine: 1, sienne_donnee: false, sien_moi: null });

  await as(one);
  const before = (await weeksQuiz()).questions[0];
  expect(before).toMatchObject({ moi: null, sienne_donnee: true, sien_moi: null, sien_devine: null });
  // Not even from the table: only one's own answers are read there.
  expect((await supabase.from('quiz_reponses').select('moi')).data).toEqual([]);
  // The first account answers 1 for itself (guessed right by the other) and guesses 3 (wrong: the other said 2).
  await answerQuiz(first.id, 1, 3);
  const after = await weeksQuiz();
  expect(after.questions[0]).toMatchObject({ moi: 1, devine: 3, sien_moi: 2, sien_devine: 1 });
  expect(after.score).toEqual({ moi: 0, sien: 1 });
  expect(after.questions[1]).toMatchObject({ id: second.id, moi: null });
  // One right guess: a point; the series not finished yet.
  expect(await myComplicity()).toMatchObject({ points: 1 });
});

test('a quiz finished by both counts its series and every right guess', async () => {
  const { one } = await pair('serie');
  const { questions } = await weeksQuiz();
  for (const q of questions) await answerQuiz(q.id, 0, 0);
  await as(one);
  for (const q of questions) await answerQuiz(q.id, 0, 1);
  // One series (3) and the second account's eight right guesses (8); the first one's guesses were all wrong.
  expect((await myComplicity()).points).toBe(11);
  expect((await weeksQuiz()).score).toEqual({ moi: 0, sien: 8 });
});

test("the week's défi: ticked by one, done once both ticked it; its points and badges", async () => {
  const { one } = await pair('defi');
  const week = await weeksDefi();
  expect(week.defi.titre.length).toBeGreaterThan(3);
  expect(week).toMatchObject({ fait_par_moi: false, fait_par_l_autre: false, valides: 0 });
  await defiDone();
  await defiDone(); // twice: still once
  expect(await weeksDefi()).toMatchObject({ fait_par_moi: true, fait_par_l_autre: false, valides: 0 });
  expect((await myComplicity()).points).toBe(0);

  await as(one);
  expect(await weeksDefi()).toMatchObject({ fait_par_moi: false, fait_par_l_autre: true });
  await defiDone();
  expect(await weeksDefi()).toMatchObject({ fait_par_moi: true, fait_par_l_autre: true, valides: 1 });
  expect((await myComplicity()).points).toBe(4);
  expect(badgesFor(1)).toEqual(['Premier pas']);
  expect(badgesFor(12)).toEqual(['Premier pas', 'Un mois de complicité', 'Saison complice']);

  // Without a duo, no défi to tick.
  await newAccount('seul');
  await expect(defiDone()).rejects.toThrow("Formez d'abord votre duo : les défis se relèvent à deux.");
});

test('the cards of the evening: read by any account, the same for a step, of its kind, another at each turn', async () => {
  await newAccount('cartes');
  const cards = await allCards();
  expect(cards.filter((c) => c.formule === 'duo').length).toBeGreaterThanOrEqual(20);
  expect(cards.filter((c) => c.formule === 'squad').every((c) => c.genre === 'gage')).toBe(true);

  const dinner = cardFor(cards, 'duo', 'repas', 'soiree-abc', 0)!;
  expect(dinner).toBe(cardFor(cards, 'duo', 'repas', 'soiree-abc', 0)); // the passager's phone draws the same
  expect(dinner.formule).toBe('duo');
  expect([null, 'repas']).toContain(dinner.role);
  const turns = new Set([0, 1, 2, 3].map((t) => cardFor(cards, 'duo', 'repas', 'soiree-abc', 0, t)!.id));
  expect(turns.size).toBe(4);
  const gage = cardFor(cards, 'squad', 'verre', 'soiree-abc', 1)!;
  expect(gage.genre).toBe('gage');
  expect([null, 'verre']).toContain(gage.role);
});
