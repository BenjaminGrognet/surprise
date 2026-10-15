// The duo's journey, light first and deeper with time (supabase/migrations/…_duo_question_du_jour.sql and
// …_quiz_defis_cartes.sql): the day's question the next once one of them answered, the week's quiz the next series
// once a week played, the week's défi the next each week since the duo was formed, the evening's cards deeper with the
// evenings lived; the quiz's verdict.
import { expect, test } from '@jest/globals';
import { allCards, cardDepth, cardFor } from '@/lib/cartes';
import { answerToday, joinDuo, weeksQuiz, myDuo, openDuo, todaysQuestion, verdict, weeksDefi } from '@/lib/duo';

import { admin, as, firstEvening, newAccount } from './helpers';

const parisDay = (offset: number) => new Date(Date.now() + offset * 86_400_000).toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' });

async function pair(label: string) {
  const one = await newAccount(`${label}-un`);
  const code = await openDuo();
  const other = await newAccount(`${label}-deux`);
  await joinDuo(code);
  await firstEvening(one.id);
  return { one, other, duo: (await myDuo())! };
}

test("the day's question: the journey's first for a new duo, the next once one of them answered a day, the same for both", async () => {
  const { one, other, duo } = await pair('parcours-question');
  const first = (await todaysQuestion()).question;
  expect(first).toMatchObject({ id: 1, profondeur: 1 });
  await as(one);
  expect((await todaysQuestion()).question!.id).toBe(1);

  // Days without an answer: the question waits. Yesterday answered by one only: today's is the second.
  expect((await admin.from('reponses_du_jour').insert({ duo_id: duo.id, day: parisDay(-1), author: other.id, question_id: 1, texte: 'Le pilote.' })).error).toBeNull();
  expect((await todaysQuestion()).question).toMatchObject({ id: 2, profondeur: 1 });
  await answerToday('Le fromage, sans hésiter.');
  await as(other);
  expect((await todaysQuestion()).question!.id).toBe(2);

  // Far along the journey: deeper.
  const days = Array.from({ length: 95 }, (_, i) => ({ duo_id: duo.id, day: parisDay(-100 + i), author: other.id, question_id: 1, texte: '…' }));
  expect((await admin.from('reponses_du_jour').insert(days)).error).toBeNull();
  // 95 + yesterday's before today (today's answer not counted): the 97th.
  expect((await todaysQuestion()).question).toMatchObject({ id: 97, profondeur: 4 });
});

test('the paliers climb from the lightest to the most intimate, a light one now and then on the way', async () => {
  await newAccount('parcours-paliers');
  const { data } = await admin.from('questions_du_jour').select('id, profondeur').order('id');
  const paliers = (data as { id: number; profondeur: number }[]).map((q) => q.profondeur);
  expect(paliers.length).toBeGreaterThanOrEqual(100);
  expect(paliers.slice(0, 30).every((p) => p === 1)).toBe(true);
  expect(Math.max(...paliers.slice(0, 55))).toBeLessThanOrEqual(2);
  expect(paliers.indexOf(4)).toBeGreaterThan(80);
  // A light one keeps coming back.
  expect(paliers.slice(60).filter((p) => p === 1).length).toBeGreaterThanOrEqual(3);
});

test("the week's quiz: a new duo's first series, the next once a week played; the verdict of its guesses", async () => {
  const { other, duo } = await pair('parcours-quiz');
  const quiz = await weeksQuiz();
  expect(quiz.serie).toMatchObject({ id: 1, titre: 'Petites manies' });
  // Last week played (by one, one question): this week, the second series.
  const monday = new Date(`${quiz.semaine}T12:00:00`);
  monday.setDate(monday.getDate() - 7);
  const last = monday.toLocaleDateString('sv-SE');
  expect((await admin.from('quiz_reponses').insert({ duo_id: duo.id, semaine: last, question_id: quiz.questions[0].id, author: other.id, moi: 0, devine: 0 })).error).toBeNull();
  const next = await weeksQuiz();
  expect(next.serie).toMatchObject({ id: 2, titre: 'Et si…' });
  expect(next.questions).toHaveLength(8);

  // Eight weeks played: the second season's first; sixteen: the journey again from the start.
  const weeks = (from: number, to: number) => Array.from({ length: to - from }, (_, i) => {
    const day = new Date(`${quiz.semaine}T12:00:00`);
    day.setDate(day.getDate() - 7 * (from + i + 2));
    return { duo_id: duo.id, semaine: day.toLocaleDateString('sv-SE'), question_id: 1, author: other.id, moi: 0, devine: 0 };
  });
  expect((await admin.from('quiz_reponses').insert(weeks(0, 7))).error).toBeNull();
  expect((await weeksQuiz()).serie).toMatchObject({ id: 9, titre: 'Mode survie' });
  expect((await admin.from('quiz_reponses').insert(weeks(7, 15))).error).toBeNull();
  expect((await weeksQuiz()).serie).toMatchObject({ id: 1, titre: 'Petites manies' });

  expect(verdict(16)).toMatch(/^Télépathes/);
  expect(verdict(11)).toMatch(/^Âmes complices/);
  expect(verdict(7)).toMatch(/^Complices en rodage/);
  expect(verdict(0)).toMatch(/^Deux mystères ambulants/);
});

test("the week's défi: a new duo's first, the next each week since it was formed", async () => {
  const { duo } = await pair('parcours-defi');
  const first = await weeksDefi();
  expect(first.defi).toMatchObject({ id: 1, titre: 'Le mot caché' });
  // Formed three weeks ago: the fourth.
  await admin.from('duos').update({ created_at: new Date(Date.now() - 21 * 86_400_000).toISOString() }).eq('id', duo.id);
  expect((await weeksDefi()).defi.id).toBe(4);
});

test("the evening's cards: a duo's deeper with the evenings it lived, a band's gages all at hand", async () => {
  await newAccount('parcours-cartes');
  const cards = await allCards();
  expect([0, 1, 2, 3, 4, 9].map(cardDepth)).toEqual([1, 1, 2, 2, 3, 3]);
  const drawn = (depth: number) => new Set(Array.from({ length: 40 }, (_, t) => cardFor(cards, 'duo', 'verre', 'soiree-xyz', 0, t, depth)!.profondeur));
  expect([...drawn(1)]).toEqual([1]);
  expect(drawn(3)).toEqual(new Set([1, 2, 3]));
  expect(cardFor(cards, 'squad', 'verre', 'soiree-xyz', 0)!.genre).toBe('gage');
});
