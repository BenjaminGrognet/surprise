// What the server always answers the same (the quiz, the evening form's options): asked once per launch, given at once
// after, asked again when it failed — the form opens without a "Chargement…" in between.
import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';

import { forgetKnown, getQuiz, getSoiree, knownSoiree, prefetchSoiree } from '@/lib/api';

const QUIZ = { questions: [], vibes: { rire: 'Rire', fete: 'Faire la fête' } };
const DUO = { formule: 'duo', envies: [{ value: 'nous', label: 'Fidèles à nous-mêmes' }], max: 3 };
const SQUAD = { formule: 'squad', envies: [], max: 4, vibes: { rire: 'Fous rires' } };

const answer = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
let fetched: string[] = [];
let failing = false;

beforeEach(() => {
  forgetKnown();
  fetched = [];
  failing = false;
  jest.spyOn(global, 'fetch').mockImplementation((input) => {
    const path = new URL(String(input), 'http://serveur').pathname + new URL(String(input), 'http://serveur').search;
    fetched.push(path);
    if (failing) return Promise.reject(new TypeError('Failed to fetch'));
    return answer(path === '/api/quiz' ? QUIZ : path.endsWith('formule=squad') ? SQUAD : DUO);
  });
});
afterEach(() => {
  jest.restoreAllMocks();
});

describe('the evening form’s options', () => {
  test('are asked of the server once, however many screens want them', async () => {
    const [a, b] = await Promise.all([getSoiree('duo'), getSoiree('duo')]);
    await getSoiree('duo');
    expect(a).toEqual(DUO);
    expect(b).toBe(a);
    expect(fetched).toEqual(['/api/soiree']);
  });

  test('asked ahead, are there at once for either formula, a band saying its vibes its own way', async () => {
    expect(knownSoiree('duo')).toBeNull();
    prefetchSoiree();
    await Promise.all([getQuiz(), getSoiree('duo'), getSoiree('squad')]);
    expect(fetched.sort()).toEqual(['/api/quiz', '/api/soiree', '/api/soiree?formule=squad']);
    expect(knownSoiree('duo')).toEqual({ data: DUO, vibes: QUIZ.vibes });
    expect(knownSoiree('squad')?.vibes).toEqual({ rire: 'Fous rires', fete: 'Faire la fête' });
  });

  test('not had (server out of reach), are asked again the next time', async () => {
    failing = true;
    await expect(getQuiz()).rejects.toThrow();
    prefetchSoiree(); // quiet, whatever happens
    await new Promise((settled) => setTimeout(settled, 0));
    failing = false;
    await expect(getQuiz()).resolves.toEqual(QUIZ);
    expect(fetched.filter((p) => p === '/api/quiz').length).toBeGreaterThanOrEqual(2);
  });
});
