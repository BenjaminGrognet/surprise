// The passager's week before their evening, and the instigateur's side of it: what each notification says and when,
// read off the kept evening with plain rules (no Claude call). A story in chapters on a countdown — the sealed letter a
// week before, a clue each morning, the mystery words, the day itself, each veil lifting, the morning after, then their
// turn to surprise — and, for the instigateur, the bookings still to make, the invitation still to send, what the
// passager just received, when to set off. Pure: lib/notifications.ts schedules it on the phone; the instigateur's
// Coulisses show the passager's week as it will come.
import { place, type SoireeRoute, type SoireeStep } from '@/lib/api';
import { cluesFor, revealAt, stepWords, type Clue, type ClueKind, type RevealMode } from '@/lib/clues';
import { formatTime, isoDay, longDay } from '@/lib/dates';

export type StoryRole = 'passager' | 'instigateur';

// One notification: its id within the evening, when, its countdown and chapter, what it says, where a touch leads.
export type Beat = { id: string; at: number; title: string; body: string; url: string; role: StoryRole };

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
// On foot up to this hop, as the evening was composed (surprise.parcours WALK_KM) and as the roadmap's hops say.
export const WALK_KM = 1.3;
// Nothing between these hours but on the evening itself: a beat of the night waits for the morning.
const QUIET_FROM = 22;
const QUIET_TO = 9;
// Two beats this close make one notification.
const TOGETHER = 20 * MINUTE;
// iOS keeps only the 64 nearest notifications an app scheduled.
export const MAX_SCHEDULED = 60;

// Each clue opens a chapter of its own.
export const CHAPTERS: Record<ClueKind, string> = {
  rendezvous: 'Le rendez-vous',
  ouverture: 'Le premier pli',
  budget: 'La bourse',
  tenue: 'La garde-robe',
  table: "L'appétit",
  duree: 'Le sablier',
  bagage: 'Le bagage',
  sens: 'Un murmure',
  carte: 'La carte',
  compte: 'Le compte à rebours',
};
// The clues of the mornings before, the instigateur hears of as the passager gets them.
const MORNINGS = new Set<ClueKind>(['ouverture', 'budget', 'tenue', 'table', 'duree', 'bagage']);

// A local hour, `offset` days from the evening's day.
function localAt(day: string, offset: number, hour: number, minute = 0) {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(y, m - 1, d + offset, hour, minute).getTime();
}

const allSteps = (route: SoireeRoute) => [...route.steps, ...(route.night ? [route.night] : [])];
// A step and where it is, its venue named once: "Le Comedy Club (Paris 2ᵉ)".
function named(step: SoireeStep) {
  const venue = step.venue && step.title.toLowerCase().includes(step.venue.toLowerCase()) ? '' : step.venue;
  const where = place({ ...step, venue });
  return where ? `${step.title} (${where})` : step.title;
}

const revelation = (pageName: string) => `/revelation?soiree=${encodeURIComponent(pageName)}`;
const book = (pageName: string) => `/livre?soiree=${encodeURIComponent(pageName)}`;

// "J-5", "Jour J", "H-2" in its last three hours, "Ce soir" once begun, "Le lendemain", then "J+4".
export function countdown(route: SoireeRoute, at: number) {
  const start = Date.parse(route.start);
  const days = Math.round((localAt(route.day, 0, 12) - localAt(isoDay(new Date(at)), 0, 12)) / DAY);
  if (days > 0) return `J-${days}`;
  if (at < start) return at >= start - 3 * HOUR ? `H-${Math.ceil((start - at) / HOUR)}` : 'Jour J';
  if (at < Date.parse(route.end) || days === 0) return 'Ce soir';
  return days === -1 ? 'Le lendemain' : `J+${-days}`;
}

// A clue's place in the passager's week, as their page shows it; the meeting time is theirs from the start.
export function clueChapter(route: SoireeRoute, clue: Clue) {
  return clue.at === 0 ? CHAPTERS.rendezvous : `${countdown(route, clue.at)} · ${CHAPTERS[clue.kind]}`;
}

// What the story says, before it is timed and gathered: `lead`, the lower the likelier to title a notification it
// shares with others (the story's own beats, then the veils, the clues, the words).
type Line = { id: string; at: number; chapter: string; body: string; url?: string; lead?: number };

// A beat out of the night, to the next morning; the evening itself keeps its hours. One that would then come too
// late, past the curtain, is left to the app.
function awake(route: SoireeRoute, at: number): number | null {
  const start = Date.parse(route.start);
  if (at >= start - 3 * HOUR && at <= Date.parse(route.end)) return at;
  const date = new Date(at);
  const hour = date.getHours();
  if (hour >= QUIET_TO && hour < QUIET_FROM) return at;
  const moved = new Date(date.getFullYear(), date.getMonth(), date.getDate() + (hour >= QUIET_FROM ? 1 : 0), QUIET_TO).getTime();
  return at < start && moved > start - 30 * MINUTE ? null : moved;
}

// The lines timed, those close together told in one notification, titled by its countdown and its leading chapter.
function tell(route: SoireeRoute, lines: Line[], role: StoryRole, url: string): Beat[] {
  const placed = lines
    .flatMap((line) => {
      const at = awake(route, line.at);
      return at === null ? [] : [{ ...line, at }];
    })
    .sort((a, b) => a.at - b.at);
  const groups: Line[][] = [];
  for (const line of placed) {
    const group = groups[groups.length - 1];
    if (group && line.at - group[0].at <= TOGETHER) group.push(line);
    else groups.push([line]);
  }
  return groups.map((group) => {
    const told = [...group].sort((a, b) => (a.lead ?? 2) - (b.lead ?? 2));
    const at = group[0].at;
    return { id: told[0].id, at, title: `${countdown(route, at)} · ${told[0].chapter}`, body: told.map((l) => l.body).join('\n'), url: told[0].url ?? url, role };
  });
}

export type StoryInput = {
  route: SoireeRoute;
  mode: RevealMode;
  secretTitle: string;
  pageName: string;
  later?: boolean; // another evening of the couple's comes after this one: no call to plan the next
};

// The passager's week: a sealed letter a week before (the day and hour, nothing else), a clue each morning and the
// mystery words in the afternoons, the eve, the day's crescendo, each step's veil lifting with its word turned into a
// name, the morning after with the Livre des Secrets, and a few days later, their turn.
export function passagerWeek({ route, mode, secretTitle, pageName, later = false }: StoryInput): Beat[] {
  const start = Date.parse(route.start);
  const time = formatTime(route.start);
  const words = stepWords(route, mode);
  const steps = allSteps(route);
  const lines: Line[] = [
    {
      id: 'prologue', at: localAt(route.day, -7, 10), chapter: 'Le pli scellé', lead: 0,
      body: `« ${secretTitle} » commence ${longDay(route.day)} à ${time}. Gardez votre soirée : tout le reste est un secret.`,
    },
    ...cluesFor(route, mode)
      .filter((c) => c.kind !== 'rendezvous')
      .map((c, i): Line => ({ id: `indice:${i}`, at: c.at, chapter: CHAPTERS[c.kind], body: c.text })),
    ...words.flatMap((w, i): Line[] => (w.at > 0
      ? [{ id: `mot:${i}`, at: w.at, chapter: 'Un mot mystère', lead: 3, body: `« ${w.word} » : l'une de vos étapes se cache derrière ce mot.` }]
      : [])),
    {
      id: 'jour-j', at: localAt(route.day, 0, 9), chapter: "C'est ce soir", lead: 0,
      body: mode === 'veille'
        ? `Le programme est entre vos mains : rendez-vous à ${time}.`
        : `Rendez-vous à ${time}. Les derniers indices tombent au fil de la journée.`,
    },
    { id: 'depart', at: start - HOUR, chapter: 'Le départ', lead: 0, body: 'Dans une heure, le rideau se lève. Un dernier regard au miroir, et en route.' },
    {
      id: 'lendemain', at: Math.max(localAt(route.day, 1, 11), Date.parse(route.end) + 3 * HOUR), chapter: 'Le Livre des Secrets', lead: 0,
      url: book(pageName),
      body: 'Une page vous attend : une photo, un mot sur hier soir. Celle de votre complice se découvre quand vous scellez la vôtre.',
    },
  ];
  if (mode === 'veille') {
    const count = route.steps.length;
    lines.push({
      id: 'programme', at: start - DAY, chapter: 'Le programme', lead: 1,
      body: `Tout le programme de demain se dévoile : ${count} étape${count > 1 ? 's' : ''}${route.night ? ' et une nuit' : ''}. À vous de lire… ou de garder la surprise.`,
    });
  } else {
    lines.push({ id: 'veille', at: localAt(route.day, -1, 21), chapter: 'La veille', lead: 0, body: `Demain, ${time}. Rien de plus ce soir : la suite s'écrit demain matin.` });
    steps.forEach((step, i) => lines.push({
      id: `voile:${i}`, at: revealAt(route, step, mode), chapter: step.role === 'nuit' ? 'La nuit se dévoile' : 'Le voile se lève', lead: 1,
      body: `« ${words[i].word} » prend un nom : ${step.title}, à ${formatTime(step.start)}.`,
    }));
  }
  if (!later) {
    lines.push({
      id: 'tour', at: localAt(route.day, 4, 19), chapter: 'À votre tour', lead: 0, url: '/soiree',
      body: "Et si, la prochaine fois, c'était vous qui gardiez le secret ? Composez une soirée : votre complice n'en verra que les indices.",
    });
  }
  return tell(route, lines, 'passager', revelation(pageName));
}

// The instigateur's week: the bookings still to make (until ticked), the invitation still to send, then what the
// passager receives each morning; the eve, when to set off, when to leave for each next step, the morning after.
export function instigateurWeek({
  route, mode, secretTitle, pageName, later = false, booked, passager,
}: StoryInput & { booked: string[]; passager: boolean }): Beat[] {
  const start = Date.parse(route.start);
  const steps = allSteps(route);
  const first = steps[0];
  const weekday = longDay(route.day).split(' ')[0];
  const toBook = steps.filter((s) => s.booking_action === 'reserver' && s.booking_url && !booked.includes(s.id));
  const lines: Line[] = [];
  if (toBook.length) {
    const what = `${toBook.length} réservation${toBook.length > 1 ? 's' : ''}`;
    const which = toBook.map((s) => s.title).join(', ');
    lines.push(
      { id: 'resa:6', at: localAt(route.day, -6, 18), chapter: 'Les coulisses', body: `${what} à faire pour ${weekday} : ${which}.` },
      { id: 'resa:3', at: localAt(route.day, -3, 18), chapter: 'Les coulisses', body: `Encore ${what} à faire : ${which}. Les places partent vite.` },
      { id: 'resa:1', at: localAt(route.day, -1, 10), chapter: 'Dernier appel', lead: 0, body: `Il reste ${what} pour demain : ${which}.` },
    );
  }
  if (!passager) {
    for (const days of [5, 2]) {
      lines.push({
        id: `invitation:${days}`, at: localAt(route.day, -days, 18, 30), chapter: 'Votre passager',
        body: "Votre passager n'a pas encore son invitation : sans elle, pas d'indices. Envoyez-lui le lien depuis la soirée.",
      });
    }
  } else {
    cluesFor(route, mode).forEach((clue, i) => {
      if (MORNINGS.has(clue.kind)) {
        lines.push({ id: `ombre:${i}`, at: clue.at + 5 * MINUTE, chapter: "Dans l'ombre", lead: 3, body: `Votre passager vient de recevoir : « ${clue.text} »` });
      }
    });
    if (mode === 'veille') {
      lines.push({ id: 'ombre:programme', at: start - DAY + 5 * MINUTE, chapter: "Dans l'ombre", body: 'Votre passager découvre tout le programme de demain.' });
    }
  }
  lines.push(
    {
      id: 'veille', at: localAt(route.day, -1, 19), chapter: 'La veille', lead: 0,
      body: `Demain, premier rendez-vous à ${formatTime(first.start)} : ${first.title}. Un dernier coup d'œil à la feuille de route ?`,
    },
    {
      id: 'depart', at: start - HOUR, chapter: 'Le départ', lead: 0,
      body: `Premier rendez-vous à ${formatTime(first.start)} : ${named(first)}. La boussole vous guide.`,
    },
    {
      id: 'lendemain', at: Math.max(localAt(route.day, 1, 10, 30), Date.parse(route.end) + 3 * HOUR), chapter: 'Le Livre des Secrets', lead: 0,
      url: book(pageName),
      body: "Scellez votre page d'hier soir. Et d'un pouce sur chaque étape, dites ce qui vous a plu : la prochaine soirée en tiendra compte.",
    },
  );
  steps.slice(1).forEach((step, i) => {
    const leave = Date.parse(step.start) - step.travel_minutes * MINUTE;
    const way = step.travel_minutes <= 2
      ? "c'est à deux pas"
      : `${step.distance_km <= WALK_KM ? 'à pied' : 'en métro'}, ${step.travel_minutes} min`;
    lines.push({
      id: `etape:${i + 1}`, at: leave - 10 * MINUTE, chapter: step.role === 'nuit' ? 'La nuit' : 'Étape suivante', lead: 1,
      body: `${formatTime(step.start)} · ${named(step)} : ${way}. Partez dans dix minutes.`,
    });
  });
  if (!later) {
    lines.push({
      id: 'prochaine', at: localAt(route.day, 21, 19), chapter: 'La prochaine intrigue', lead: 0, url: '/soiree',
      body: `Trois semaines depuis « ${secretTitle} ». Une nouvelle soirée ? Vos pouces guident la suivante.`,
    });
  }
  return tell(route, lines, 'instigateur', revelation(pageName));
}

// A kept evening as the phone tells it: its side for this account, and what the instigateur knows of its state.
export type PlannedEvening = {
  pageName: string;
  route: SoireeRoute;
  role: StoryRole;
  mode: RevealMode;
  secretTitle: string;
  booked: string[];
  passager: boolean;
};

// Every evening's beats still to come, the nearest first, as many as the phone keeps; ids prefixed with the page. An
// evening followed by another of the couple's doesn't call for the next one.
export function notificationPlan(evenings: PlannedEvening[], now: number): Beat[] {
  return evenings
    .flatMap((evening) => {
      const input = { ...evening, later: evenings.some((other) => other.route.day > evening.route.day) };
      const week = evening.role === 'passager' ? passagerWeek(input) : instigateurWeek(input);
      return week.map((beat) => ({ ...beat, id: `${evening.pageName}:${beat.id}` }));
    })
    .filter((beat) => beat.at > now + 5_000)
    .sort((a, b) => a.at - b.at)
    .slice(0, MAX_SCHEDULED);
}
