// Les dates et les occasions (docs/complicite.md, phase 3): the dates that count for the duo — the server composes
// three intrigues three weeks before each (surprise.rappels), ready here —, the seasons of Paris coming, and an evening
// lived a year ago, come back with its photo.
import type { EveningHistoryRow } from '@/lib/account';
import { isoDay } from '@/lib/dates';
import { photoUrls } from '@/lib/souvenirs';
import { supabase } from '@/lib/supabase';

export type Genre = 'rencontre' | 'anniversaire' | 'autre';
export type KeyDate = { id: string; label: string; genre: Genre; mois: number; jour: number; pour: string | null; author: string };

export async function keyDates(): Promise<KeyDate[]> {
  const { data, error } = await supabase.from('dates_cles').select('id, label, genre, mois, jour, pour, author').order('mois').order('jour');
  if (error) throw new Error(error.message);
  return data as KeyDate[];
}

// A date noted for the duo: `pour`, whose birthday it is (only the other is reminded).
export async function addKeyDate(duoId: string, date: { label: string; genre: Genre; mois: number; jour: number; pour?: string | null }) {
  const label = date.label.trim();
  if (!label) throw new Error('Donnez un nom à cette date.');
  const probe = new Date(2024, date.mois - 1, date.jour);
  if (!(date.mois >= 1 && date.mois <= 12) || probe.getMonth() !== date.mois - 1 || probe.getDate() !== date.jour) {
    throw new Error("Cette date n'existe pas : jour et mois, par exemple 14/02.");
  }
  const { error } = await supabase.from('dates_cles').insert({ duo_id: duoId, ...date, label, pour: date.pour ?? null });
  if (error) throw new Error(error.message);
}

export async function removeKeyDate(id: string) {
  const { error } = await supabase.from('dates_cles').delete().eq('id', id);
  if (error) throw new Error(error.message);
}

// "14/02", "1/6": a day of the year typed by the couple; null if it is none.
export function parseDayMonth(text: string): { jour: number; mois: number } | null {
  const found = /^\s*(\d{1,2})\s*[/.\-\s]\s*(\d{1,2})\s*$/.exec(text);
  return found ? { jour: Number(found[1]), mois: Number(found[2]) } : null;
}

export const dayOfYear = (date: Pick<KeyDate, 'jour' | 'mois'>) =>
  new Date(2024, date.mois - 1, date.jour).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });

// The intrigues the server composed for a date that counts, still ahead and not kept (no evening that day).
export type Ready = { cle: string; page_name: string; day: string; label: string };

export async function readyIntrigues(today: string, kept: Pick<EveningHistoryRow, 'day'>[]): Promise<Ready[]> {
  const { data, error } = await supabase.from('intrigues_pretes').select('cle, page_name, day, label').gte('day', today).order('day');
  if (error) throw new Error(error.message);
  const busy = new Set(kept.map((e) => e.day));
  return (data as Ready[]).filter((r) => !busy.has(r.day));
}

// The seasons of Paris coming within three weeks, or under way.
export type Season = { id: string; nom: string; texte: string; deroule: string; envies: string[]; debut: string; fin: string };
export const SEASON_AHEAD_DAYS = 21;

export async function seasonsAhead(today: string): Promise<Season[]> {
  const { data, error } = await supabase.rpc('saisons_a_venir', { d: today });
  if (error) throw new Error(error.message);
  const horizon = new Date(`${today}T12:00:00`);
  horizon.setDate(horizon.getDate() + SEASON_AHEAD_DAYS);
  return (data as Season[]).filter((s) => s.debut <= isoDay(horizon));
}

// An evening for two lived a year ago (three days either side), its photo from the Livre if one was sealed.
export type YearAgo = { evening: EveningHistoryRow; photoUrl: string | null };

export async function yearAgo(history: EveningHistoryRow[], today: string): Promise<YearAgo | null> {
  const around = (offset: number) => {
    const d = new Date(`${today}T12:00:00`);
    d.setFullYear(d.getFullYear() - 1);
    d.setDate(d.getDate() + offset);
    return isoDay(d);
  };
  const evening = history.find((e) => e.formule !== 'squad' && !!e.day && e.day >= around(-3) && e.day <= around(3));
  if (!evening) return null;
  const photo = evening.souvenirs?.find((s) => s.photo)?.photo ?? null;
  const urls = photo ? await photoUrls([photo]) : {};
  return { evening, photoUrl: photo ? urls[photo] ?? null : null };
}
