// The passager's week and the instigateur's reminders, as the phone's notifications tell them (lib/story.ts): when
// each comes, what it says, and what the plan keeps of several evenings.
import { describe, expect, test } from '@jest/globals';

import { cluesFor, stepWords } from '@/lib/clues';
import { formatTime } from '@/lib/dates';
import {
  clueChapter, countdown, instigateurWeek, MAX_SCHEDULED, notificationPlan, passagerWeek, type PlannedEvening,
} from '@/lib/story';

import { evening, local, SECRET } from './fixtures';

const HOUR = 3_600_000;
const PAGE = 'soiree-test-semaine';

const route = evening();
const start = Date.parse(route.start);
const end = Date.parse(route.end);
const titles = (beats: { title: string }[]) => beats.map((b) => b.title);
const clue = (kind: string) => cluesFor(route).find((c) => c.kind === kind)!;

describe('the passager’s week', () => {
  const week = passagerWeek({ route, mode: 'etapes', secretTitle: SECRET, pageName: PAGE });

  test('opens a week before on a sealed letter, the day and the hour alone, and runs in chapters to their turn', () => {
    expect(week[0].title).toBe('J-7 · Le pli scellé');
    expect(week[0].body).toBe(`« ${SECRET} » commence vendredi 16 octobre à ${formatTime(route.start)}. Gardez votre soirée : tout le reste est un secret.`);
    expect(titles(week)).toEqual(expect.arrayContaining([
      'J-5 · Le premier pli', 'J-4 · La bourse', 'J-3 · La garde-robe', 'J-3 · Un mot mystère', "J-2 · L'appétit", 'J-2 · Un murmure',
      'J-1 · Le sablier', 'J-1 · Un mot mystère', 'J-1 · La veille', "Jour J · C'est ce soir", 'Jour J · La carte',
      'H-2 · Le compte à rebours', 'H-1 · Le départ', 'Le lendemain · Le Livre des Secrets', 'J+4 · À votre tour',
    ]));
    expect(week.find((b) => b.title === 'J-3 · La garde-robe')!.body).toBe(clue('tenue').text);
    expect(week.map((b) => b.at)).toEqual([...week.map((b) => b.at)].sort((a, b) => a - b));
    // Each opens the evening's page; the morning after, its book; their turn, a new evening.
    expect(week[0].url).toBe(`/revelation?soiree=${PAGE}`);
    expect(week.find((b) => b.title.endsWith('Le Livre des Secrets'))!.url).toBe(`/livre?soiree=${PAGE}`);
    expect(week.find((b) => b.title.endsWith('À votre tour'))!.url).toBe('/soiree');
  });

  test('each veil lifts at its hour, its mystery word turned into a name', () => {
    const words = stepWords(route, 'etapes');
    const veils = week.filter((b) => b.title.endsWith('Le voile se lève'));
    expect(veils.map((b) => b.body)).toEqual(route.steps.map((s, i) => `« ${words[i].word} » prend un nom : ${s.title}, à ${formatTime(s.start)}.`));
    expect(titles(veils)).toEqual(['H-1 · Le voile se lève', 'Ce soir · Le voile se lève', 'Ce soir · Le voile se lève']);
    expect(veils[0].at).toBe(start - HOUR / 4);
  });

  test('nothing in the night but the evening itself; beats of one moment told in one notification', () => {
    for (const beat of week) {
      const hour = new Date(beat.at).getHours();
      if (beat.at < start - 3 * HOUR || beat.at > end) expect(hour >= 9 && hour < 22).toBe(true);
    }
    // The second murmur, due at 7:30 on the day, waits for 9:00 and comes with the day's own words.
    const day = week.find((b) => b.title === "Jour J · C'est ce soir")!;
    expect(day.at).toBe(local(route.day, 9));
    expect(day.body).toBe(`Rendez-vous à ${formatTime(route.start)}. Les derniers indices tombent au fil de la journée.\nPréparez vos zygomatiques.`);
    week.slice(1).forEach((beat, i) => expect(beat.at - week[i].at).toBeGreaterThan(20 * 60_000));
    expect(new Set(week.map((b) => b.id)).size).toBe(week.length);
  });

  test('told the day before, the programme comes at once and nothing after but the day and the curtain', () => {
    const eve = passagerWeek({ route, mode: 'veille', secretTitle: SECRET, pageName: PAGE });
    const programme = eve.find((b) => b.title === 'J-1 · Le programme')!;
    expect(programme.at).toBe(start - 24 * HOUR);
    expect(programme.body).toBe('Tout le programme de demain se dévoile : 3 étapes. À vous de lire… ou de garder la surprise.');
    expect(eve.some((b) => /Le voile se lève|La veille|Un murmure|La carte|Le compte à rebours/.test(b.title) && b.at > start - 24 * HOUR)).toBe(false);
    expect(eve.find((b) => b.title === "Jour J · C'est ce soir")!.body).toBe(`Le programme est entre vos mains : rendez-vous à ${formatTime(route.start)}.`);
  });

  test('its clues are shown under their chapters, the meeting time from the start', () => {
    expect(clueChapter(route, clue('rendezvous'))).toBe('Le rendez-vous');
    expect(clueChapter(route, clue('tenue'))).toBe('J-3 · La garde-robe');
    expect(clueChapter(route, clue('compte'))).toBe('H-2 · Le compte à rebours');
  });
});

test('the countdown: days, the day, its last hours, the evening, the morning after', () => {
  expect(countdown(route, local(route.day, 10, 0, -7))).toBe('J-7');
  expect(countdown(route, local(route.day, 9))).toBe('Jour J');
  expect(countdown(route, start - 3 * HOUR)).toBe('H-3');
  expect(countdown(route, start - HOUR / 4)).toBe('H-1');
  expect(countdown(route, start + HOUR)).toBe('Ce soir');
  expect(countdown(route, local(route.day, 0, 15, 1))).toBe('Ce soir'); // past midnight, still on
  expect(countdown(route, local(route.day, 11, 0, 1))).toBe('Le lendemain');
  expect(countdown(route, local(route.day, 19, 0, 4))).toBe('J+4');
});

describe('the instigateur’s week', () => {
  const base = { route, mode: 'etapes' as const, secretTitle: SECRET, pageName: PAGE };
  const busy = instigateurWeek({ ...base, booked: [], passager: true });

  test('reminded of the bookings still to make, until they are ticked', () => {
    expect(busy.find((b) => b.title === 'J-6 · Les coulisses')!.body).toBe('2 réservations à faire pour vendredi : Le Comptoir, Le Comedy Club.');
    expect(busy.find((b) => b.title === 'J-1 · Dernier appel')!.body).toBe('Il reste 2 réservations pour demain : Le Comptoir, Le Comedy Club.');
    const one = instigateurWeek({ ...base, booked: ['test:comptoir'], passager: true });
    expect(one.find((b) => b.title === 'J-3 · Les coulisses')!.body).toBe('Encore 1 réservation à faire : Le Comedy Club. Les places partent vite.');
    const done = instigateurWeek({ ...base, booked: ['test:comptoir', 'test:comedy'], passager: true });
    expect(done.some((b) => /Les coulisses|Dernier appel/.test(b.title))).toBe(false);
  });

  test('without a passager, the invitation to send; with one, each morning’s clue as they receive it', () => {
    const alone = instigateurWeek({ ...base, booked: [], passager: false });
    expect(titles(alone.filter((b) => b.title.endsWith('Votre passager')))).toEqual(['J-5 · Votre passager', 'J-2 · Votre passager']);
    expect(alone.some((b) => b.title.includes("Dans l'ombre"))).toBe(false);

    const shadow = busy.filter((b) => b.title.includes("Dans l'ombre"));
    expect(titles(shadow)).toEqual(['J-5', 'J-4', 'J-3', 'J-2', 'J-1'].map((d) => `${d} · Dans l'ombre`));
    expect(shadow[0].body).toBe(`Votre passager vient de recevoir : « ${clue('ouverture').text} »`);
    expect(shadow[0].at).toBe(clue('ouverture').at + 5 * 60_000);
    expect(busy.some((b) => b.title.endsWith('Votre passager'))).toBe(false);
  });

  test('on the day, when to set off, then when to leave for each next step', () => {
    expect(busy.find((b) => b.title === 'H-1 · Le départ')!.body).toBe(`Premier rendez-vous à ${formatTime(route.start)} : Le Comptoir (Paris 11ᵉ). La boussole vous guide.`);
    const next = busy.filter((b) => b.title === 'Ce soir · Étape suivante');
    const [, comedy, bar] = route.steps;
    expect(next.map((b) => b.body)).toEqual([
      `${formatTime(comedy.start)} · Le Comedy Club (Paris 2ᵉ) : en métro, 15 min. Partez dans dix minutes.`,
      `${formatTime(bar.start)} · Un bar caché (Le Bar Caché · Paris 2ᵉ) : à pied, 8 min. Partez dans dix minutes.`,
    ]);
    expect(next[0].at).toBe(Date.parse(comedy.start) - 25 * 60_000);
  });

  test('the morning after, the book and the thumbs; three weeks on, the next evening, unless one is already kept', () => {
    const after = busy.find((b) => b.title === 'Le lendemain · Le Livre des Secrets')!;
    expect(after.url).toBe(`/livre?soiree=${PAGE}`);
    expect(busy.find((b) => b.title === 'J+21 · La prochaine intrigue')!.url).toBe('/soiree');
    expect(instigateurWeek({ ...base, booked: [], passager: true, later: true }).some((b) => b.title.endsWith('La prochaine intrigue'))).toBe(false);
  });
});

describe('the plan scheduled on the phone', () => {
  const kept = (pageName: string, day: string, role: PlannedEvening['role']): PlannedEvening => ({
    pageName, route: evening(day), role, mode: 'etapes', secretTitle: SECRET, booked: [], passager: true,
  });

  test('every evening’s beats still to come, the nearest first, ids by page; a later evening silences the call for the next', () => {
    const now = local('2026-10-16', 12, 0, -4);
    const plan = notificationPlan([kept('soiree-a', '2026-10-16', 'passager'), kept('soiree-b', '2026-11-06', 'instigateur')], now);
    expect(plan.every((b) => b.at > now)).toBe(true);
    expect(plan.map((b) => b.at)).toEqual([...plan.map((b) => b.at)].sort((a, b) => a - b));
    expect(plan[0].id).toBe('soiree-a:indice:2'); // J-4 at 9:00 is past: the outfit, J-3
    const a = plan.filter((b) => b.id.startsWith('soiree-a:'));
    const b = plan.filter((b) => b.id.startsWith('soiree-b:'));
    expect(a.every((x) => x.role === 'passager') && b.every((x) => x.role === 'instigateur')).toBe(true);
    expect(a.some((x) => x.title.endsWith('À votre tour'))).toBe(false);
    expect(b.some((x) => x.title.endsWith('La prochaine intrigue'))).toBe(true);
    expect(a.some((x) => x.title === 'J-5 · Le premier pli')).toBe(false);
  });

  test('no more than the phone keeps: the nearest', () => {
    const days = ['2026-10-16', '2026-10-23', '2026-10-30', '2026-11-06'];
    const evenings = days.map((day, i) => kept(`soiree-${i}`, day, 'passager'));
    const now = local('2026-10-01', 12);
    const plan = notificationPlan(evenings, now);
    expect(plan).toHaveLength(MAX_SCHEDULED);
    expect(plan[plan.length - 1].at).toBeLessThan(local('2026-11-06', 9));
    expect(plan[0].title).toBe('J-7 · Le pli scellé');
  });
});
