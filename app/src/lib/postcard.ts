// The postcard of an evening, to share in a story: its secret name, its day and hour, its mystery words as the
// passager knows them (one still veiled stays "?"), and once the evening is over, the steps it went through. Never
// more than the passager may know at that moment: shared before the evening, it spoils nothing.
import type { SoireeRoute } from '@/lib/api';
import { stepWords, type RevealMode } from '@/lib/clues';
import { eveningWhen } from '@/lib/dates';

export type Postcard = {
  title: string;
  when: string; // "Vendredi 16 octobre · 19:30"
  words: string[]; // one per step, "?" until it shows
  steps: string[]; // the steps' names, once the evening is over
  line: string;
};

// The image's name when shared: the secret name, as a file name.
export const postcardFile = (title: string) =>
  `secret-date-${title.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`;

export function postcard(route: SoireeRoute, mode: RevealMode, secretTitle: string, now: number): Postcard {
  const over = now >= Date.parse(route.end);
  const band = route.formule === 'squad';
  return {
    title: secretTitle,
    when: eveningWhen(route),
    words: stepWords(route, mode).map((w) => (w.at <= now || over ? w.word : '?')),
    steps: over ? [...route.steps, ...(route.night ? [route.night] : [])].map((s) => s.title) : [],
    line: over
      ? band ? 'Une soirée vécue en bande, en secret.' : 'Une soirée vécue à deux, en secret.'
      : now >= Date.parse(route.start)
        ? band ? 'Ce soir, une intrigue se joue pour toute la bande.' : 'Ce soir, une intrigue se joue pour nous deux.'
        : band ? 'Une virée secrète attend la bande : le reste est un mystère.' : 'Une soirée secrète nous attend : le reste est un mystère.',
  };
}
