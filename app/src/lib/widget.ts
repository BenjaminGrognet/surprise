// The home-screen widget: the next evening at a glance. Its secret name, the countdown, and a line that moves with
// the week (the passager's latest clue; for the instigateur, the bookings left, then on the day the next step). Pure
// here: what it shows and when, as a timeline the phone plays on its own (src/widgets/ draws it: iOS with expo-widgets,
// Android with react-native-android-widget).
import { Platform } from 'react-native';

import { cluesFor, shownClues } from '@/lib/clues';
import { formatTime, shortDay } from '@/lib/dates';
import { daysBefore, type PlannedEvening } from '@/lib/story';

export type WidgetCard = {
  kicker: string; // "Passager · mer. 7 oct."
  title: string; // the evening's secret name
  countdown: string; // "J-3", "Demain · 19:30", "Ce soir · 19:30", "En ce moment"; empty without an evening
  line: string;
  url: string; // where a touch leads, in the app
};
export type WidgetEntry = { at: number; card: WidgetCard };

const LINK = 'secretdate://';
const HOUR = 3_600_000;
const DAY = 24 * HOUR;
// How far ahead the phone is given what to show: it asks again when the app comes back.
const HORIZON = 10 * DAY;

export const NO_EVENING: WidgetCard = {
  kicker: 'Secret Date', title: 'Aucune soirée prévue', countdown: '', line: 'Et si vous en trammiez une ?', url: `${LINK}soiree`,
};

const steps = (e: PlannedEvening) => [...e.route.steps, ...(e.route.night ? [e.route.night] : [])];

function countdownAt(e: PlannedEvening, at: number) {
  if (at >= Date.parse(e.route.start)) return 'En ce moment';
  const days = daysBefore(e.route.day, at);
  const time = formatTime(e.route.start);
  return days <= 0 ? `Ce soir · ${time}` : days === 1 ? `Demain · ${time}` : `J-${days}`;
}

// The passager: the latest clue they hold; the evening begun, nothing more to guess.
function passagerLine(e: PlannedEvening, at: number) {
  if (at >= Date.parse(e.route.start)) return 'Le rideau est levé : belle soirée.';
  const shown = shownClues(cluesFor(e.route, e.mode), at);
  return shown[shown.length - 1].text;
}

// The instigateur: the bookings left; on the day, the next step to come; before, the latest clue sent.
function instigateurLine(e: PlannedEvening, at: number) {
  const start = Date.parse(e.route.start);
  const left = steps(e).filter((s) => s.booking_action === 'reserver' && s.booking_url && !e.booked.includes(s.id)).length;
  if (left && at < start) return `${left} réservation${left > 1 ? 's' : ''} encore à faire.`;
  if (daysBefore(e.route.day, at) <= 0) {
    const next = steps(e).find((s) => Date.parse(s.start) > at);
    return next ? `${formatTime(next.start)} · ${next.title}` : 'Dernière étape : rien ne presse.';
  }
  if (!e.passager) return e.squad ? 'Votre bande attend son invitation.' : 'Votre passager attend son invitation.';
  const shown = shownClues(cluesFor(e.route, e.mode), at);
  return `Dernier indice : ${shown[shown.length - 1].text}`;
}

// What the widget shows at `at`: the next evening not over yet, or an invitation to plan one.
export function widgetCard(evenings: PlannedEvening[], at: number): WidgetCard {
  const next = evenings
    .filter((e) => Date.parse(e.route.end) > at)
    .sort((a, b) => Date.parse(a.route.start) - Date.parse(b.route.start))[0];
  if (!next) return NO_EVENING;
  return {
    kicker: `${next.squad ? 'Squad · ' : ''}${next.role === 'passager' ? (next.squad ? 'Invité' : 'Passager') : 'Instigateur'} · ${shortDay(next.route.day)}`,
    title: next.secretTitle,
    countdown: countdownAt(next, at),
    line: next.role === 'passager' ? passagerLine(next, at) : instigateurLine(next, at),
    url: `${LINK}revelation?soiree=${encodeURIComponent(next.pageName)}`,
  };
}

// Each moment the widget changes over the days ahead: every midnight (the countdown), each clue, each step, each
// curtain; one entry per change, from now.
export function widgetTimeline(evenings: PlannedEvening[], now: number): WidgetEntry[] {
  const moments = new Set<number>();
  const midnight = new Date(now);
  midnight.setHours(24, 0, 0, 0);
  for (let at = midnight.getTime(); at <= now + HORIZON; at = new Date(at + DAY + HOUR).setHours(0, 0, 0, 0)) moments.add(at);
  for (const e of evenings) {
    for (const clue of cluesFor(e.route, e.mode)) moments.add(clue.at);
    for (const step of steps(e)) moments.add(Date.parse(step.start));
    moments.add(Date.parse(e.route.start));
    moments.add(Date.parse(e.route.end));
  }
  const entries: WidgetEntry[] = [];
  for (const at of [now, ...[...moments].filter((m) => m > now && m <= now + HORIZON).sort((a, b) => a - b)]) {
    const card = widgetCard(evenings, at);
    const last = entries[entries.length - 1];
    if (!last || JSON.stringify(last.card) !== JSON.stringify(card)) entries.push({ at, card });
  }
  return entries;
}

// The card of a timeline due at `now`: its latest entry begun.
export function cardAt(entries: WidgetEntry[], now: number): WidgetCard {
  return [...entries].reverse().find((e) => e.at <= now)?.card ?? entries[0]?.card ?? NO_EVENING;
}

// The timeline handed to the phone's widget (null: signed out, the empty card). Nothing on the web.
export async function showOnWidgets(evenings: PlannedEvening[] | null) {
  const entries = widgetTimeline(evenings ?? [], Date.now());
  if (Platform.OS === 'ios') {
    const { default: widget } = await import('@/widgets/next-evening');
    widget.updateTimeline(entries.map((e) => ({ date: new Date(e.at), props: e.card })));
  } else if (Platform.OS === 'android') {
    const { showOnAndroid } = await import('@/widgets/next-evening-android');
    await showOnAndroid(entries);
  }
}
