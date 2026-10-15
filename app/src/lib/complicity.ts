// The couple's complicity, a living gauge (docs/complicite.md, A4): points for each evening for two lived (a band's,
// Secret Squad, is not the couple's), each page of their Livre sealed, each day both answered the day's question, each
// month's quiz both finished and each right guess in it, each week's défi both ticked — counted by the base
// (public.complicite()) —, climbing through named levels. Each level from the second unlocks
// something: a secret option more in the evening form, the special intrigue, the « Minuit » theme. A thin gold line on
// the home screen and on « Mon couple » shows the way to the next.
import { supabase } from '@/lib/supabase';

// What the base counts for the account and its duo.
export type Counts = {
  duo: boolean; complet: boolean; soirees: number; pages: number; reponses: number; quiz: number; devinettes: number; defis: number;
};

export const POINTS = { soirees: 10, pages: 3, reponses: 1, quiz: 3, devinettes: 1, defis: 4 } as const;

export type Unlock = 'option-secrete' | 'intrigue-speciale' | 'theme-minuit';

export const LEVELS: { from: number; name: string; unlock?: { key: Unlock; label: string } }[] = [
  { from: 0, name: 'Premiers regards' },
  { from: 15, name: 'Étincelles', unlock: { key: 'option-secrete', label: 'une option secrète de plus pour vos soirées' } },
  { from: 40, name: 'Étoiles filantes', unlock: { key: 'intrigue-speciale', label: 'l’intrigue spéciale, tout en audace' } },
  { from: 80, name: 'Constellation', unlock: { key: 'theme-minuit', label: 'le thème « Minuit »' } },
  { from: 150, name: 'Âmes complices' },
];

export type Complicity = {
  points: number;
  lived: number;
  name: string;
  progress: number;
  next: { name: string; left: number; unlock: string | null } | null;
  unlocked: Unlock[];
};

export function complicity(counts: Counts): Complicity {
  const points = (Object.keys(POINTS) as (keyof typeof POINTS)[]).reduce((sum, key) => sum + (counts[key] ?? 0) * POINTS[key], 0);
  const at = LEVELS.findLastIndex((l) => points >= l.from);
  const level = LEVELS[at];
  const next = LEVELS[at + 1];
  return {
    points,
    lived: counts.soirees,
    name: level.name,
    progress: next ? (points - level.from) / (next.from - level.from) : 1,
    next: next ? { name: next.name, left: next.from - points, unlock: next.unlock?.label ?? null } : null,
    unlocked: LEVELS.slice(0, at + 1).flatMap((l) => (l.unlock ? [l.unlock.key] : [])),
  };
}

export async function myComplicity(): Promise<Complicity> {
  const { data, error } = await supabase.rpc('complicite');
  if (error) throw new Error(error.message);
  return complicity(data as Counts);
}

// How the points are earned, said under the gauge.
export const EARNED = [
  `Une soirée à deux vécue : ${POINTS.soirees} points`,
  `Une page du Livre scellée : ${POINTS.pages} points`,
  `La question du jour, à deux : ${POINTS.reponses} point`,
  `Le quiz de la semaine fini à deux : ${POINTS.quiz} points, et ${POINTS.devinettes} par bonne devinette`,
  `Le défi de la semaine relevé à deux : ${POINTS.defis} points`,
];
