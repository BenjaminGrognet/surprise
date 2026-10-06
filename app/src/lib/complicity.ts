// The couple's complicity: one point per evening lived together (a chosen evening of two whose day has passed: a
// band's, Secret Squad, is not the couple's), climbing through named levels. A thin gold line on the home screen shows
// the way to the next.
import type { EveningHistoryRow } from '@/lib/account';

const LEVELS = [
  { from: 0, name: 'Premiers regards' },
  { from: 1, name: 'Étincelles' },
  { from: 3, name: 'Étoiles filantes' },
  { from: 6, name: 'Constellation' },
  { from: 10, name: 'Âmes complices' },
];

export type Complicity = { lived: number; name: string; progress: number; next: { name: string; left: number } | null };

export function complicity(history: EveningHistoryRow[], today: string): Complicity {
  const lived = history.filter((h) => h.day && h.day < today && h.formule !== 'squad').length;
  const at = LEVELS.findLastIndex((l) => lived >= l.from);
  const level = LEVELS[at];
  const next = LEVELS[at + 1];
  return {
    lived,
    name: level.name,
    progress: next ? (lived - level.from) / (next.from - level.from) : 1,
    next: next ? { name: next.name, left: next.from - lived } : null,
  };
}
