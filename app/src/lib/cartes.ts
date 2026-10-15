// Les cartes du soir (docs/complicite.md, A5): on each step of the evening revealed, a card — a question or a little
// défi for two, a gage for a band (Secret Squad) — of the step's kind (repas, verre, sortie) or for any step. Drawn
// from the evening and the step's place, so that everyone on the evening sees the same; « Une autre carte » the next.
import type { Formule } from '@/lib/api';
import { eveningDay, isoDay } from '@/lib/dates';
import { supabase } from '@/lib/supabase';

export type Carte = {
  id: number; formule: Formule; genre: 'conversation' | 'defi' | 'gage'; role: 'repas' | 'verre' | 'sortie' | null; profondeur: 1 | 2 | 3; texte: string;
};

let cards: Promise<Carte[]> | null = null;

// All of them, once per session: a few dozen short lines.
export function allCards(): Promise<Carte[]> {
  cards ??= (async () => {
    const { data, error } = await supabase.from('cartes_du_soir').select('id, formule, genre, role, profondeur, texte').order('id');
    if (error) throw new Error(error.message);
    return data as Carte[];
  })().catch((err) => {
    cards = null;
    throw err;
  });
  return cards;
}

// A string's hash, steady from one device to another.
const hash = (text: string) => [...text].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) | 0, 7) >>> 0;

// How deep a duo's cards go: light on its first evenings, deeper once it lived some (2 from the second, 3 from the
// fourth); a band's gages are all of the first.
export const cardDepth = (lived: number) => Math.min(3, 1 + Math.floor(lived / 2));

// The card of a step: among those of its formula, its kind (or of any step) and its depth, the `turn`-th after the one
// the evening and the step's place draw.
export function cardFor(all: Carte[], formule: Formule, role: string, evening: string, position: number, turn = 0, depth = 1): Carte | null {
  const fitting = all.filter((c) => c.formule === formule && (c.role === null || c.role === role) && c.profondeur <= depth);
  if (!fitting.length) return null;
  return fitting[(hash(`${evening}:${position}`) + turn) % fitting.length];
}

// Whether it is the evening's day: its date, or the night after it until 6 in the morning (eveningDay).
export const onTheDay = (day: string, now: number) => day === isoDay(new Date(now)) || day === eveningDay(new Date(now));
