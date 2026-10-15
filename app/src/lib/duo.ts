// Le duo (supabase/migrations/…_duo_question_du_jour.sql, docs/complicite.md): two accounts linked, one duo per
// account, formed by itself when a passager joins an evening for two, or by a code from « Mon couple ». The day's
// question, the quizzes, the défis and the gauge are the duo's. Leaving it dissolves it: its answers go with it.
import { currentUser } from '@/lib/account';
import type { Profile } from '@/lib/api';
import { supabase } from '@/lib/supabase';

export type DuoMember = { user_id: string; email: string | null; joined_at: string };
// The account's duo: its code (to send while it waits for its second), its two, and the other one once there.
export type Duo = { id: string; code: string; members: DuoMember[]; partner: DuoMember | null; complete: boolean };

export async function myDuo(): Promise<Duo | null> {
  const user = await currentUser();
  if (!user) return null;
  const { data: mine, error } = await supabase.from('duo_members').select('duo_id').eq('user_id', user.id).maybeSingle();
  if (error) throw new Error(error.message);
  if (!mine) return null;
  const [duo, members] = await Promise.all([
    supabase.from('duos').select('id, code').eq('id', mine.duo_id).single(),
    supabase.from('duo_members').select('user_id, email, joined_at').eq('duo_id', mine.duo_id).order('joined_at'),
  ]);
  if (duo.error) throw new Error(duo.error.message);
  if (members.error) throw new Error(members.error.message);
  const two = members.data as DuoMember[];
  return { ...duo.data, members: two, partner: two.find((m) => m.user_id !== user.id) ?? null, complete: two.length === 2 };
}

// The account's duo opened, waiting for its second: its code to send.
export async function openDuo(): Promise<string> {
  const { data, error } = await supabase.rpc('open_duo');
  if (error) throw new Error(error.message);
  return data as string;
}

export async function joinDuo(code: string) {
  const { error } = await supabase.rpc('join_duo', { given: code });
  if (error) throw new Error(error.message);
}

export async function leaveDuo() {
  const { error } = await supabase.rpc('leave_duo');
  if (error) throw new Error(error.message);
}

// What one calls the other: the start of their email, until they choose a name.
export const partnerName = (member: Pick<DuoMember, 'email'> | null) => {
  const local = member?.email?.split('@')[0]?.split(/[._+-]/)[0] ?? '';
  return local ? local.charAt(0).toUpperCase() + local.slice(1) : 'Votre moitié';
};

export type Question = { id: number; texte: string; theme: string; profondeur: 1 | 2 | 3 | 4 }; // the palier of the journey (couple.tsx PALIERS)
// The day's question for the duo: the account's answer, and the other's once its own is given (before, only whether
// it was given: `sienne_donnee`). The questions begin the day after the duo's first evening lived (`commence`; before,
// no question, and `premiere`: that evening, lived or the next one chosen); they follow its profile when it has one
// (`adaptee`).
export type FirstEvening = { vecue: string | null; prevue: string | null };
export type Jour = {
  day: string; commence: boolean; premiere: FirstEvening | null; adaptee: boolean;
  question: Question | null; mienne: string | null; sienne_donnee: boolean; sienne: string | null;
};

export async function todaysQuestion(): Promise<Jour> {
  const { data, error } = await supabase.rpc('mon_jour');
  if (error) throw new Error(error.message);
  return data as Jour;
}

// The duo's profile (surprise.quiz): the account's own, else its partner's; null when neither made it.
export async function duoProfile(): Promise<{ answers: Record<string, unknown>; profile: Profile } | null> {
  const { data, error } = await supabase.rpc('profil_du_duo');
  if (error) throw new Error(error.message);
  return (data as { answers: Record<string, unknown>; profile: Profile } | null) ?? null;
}

// Sealed: final, the other's answer then read.
export async function answerToday(texte: string) {
  const { error } = await supabase.rpc('repondre_du_jour', { texte });
  if (error) throw new Error(error.message);
}

// The days before today both answered, the latest first: the question, then each one's answer.
export type Paired = { day: string; question: string; mienne: string; sienne: string };

export async function pairedAnswers(today: string, days = 7): Promise<Paired[]> {
  const user = await currentUser();
  if (!user) return [];
  const since = new Date(`${today}T12:00:00`);
  since.setDate(since.getDate() - days);
  const { data, error } = await supabase
    .from('reponses_du_jour').select('day, author, texte, questions_du_jour(texte)')
    .gte('day', since.toISOString().slice(0, 10)).lt('day', today).order('day', { ascending: false });
  if (error) throw new Error(error.message);
  type Row = { day: string; author: string; texte: string; questions_du_jour: { texte: string } | null };
  const byDay = new Map<string, Row[]>();
  for (const row of data as unknown as Row[]) byDay.set(row.day, [...(byDay.get(row.day) ?? []), row]);
  return [...byDay.values()].flatMap((rows) => {
    const mine = rows.find((r) => r.author === user.id);
    const theirs = rows.find((r) => r.author !== user.id);
    return mine && theirs ? [{ day: mine.day, question: mine.questions_du_jour?.texte ?? '', mienne: mine.texte, sienne: theirs.texte }] : [];
  });
}

// The week's quiz (docs/complicite.md, A2): eight questions; for each, one's own answer and the guess of the other's
// (0 to 3, among its four choices), the other's read once both answered it. The score: each one's right guesses.
export type QuizQuestion = {
  id: number; rang: number; question: string; choix: string[];
  moi: number | null; devine: number | null; sienne_donnee: boolean; sien_moi: number | null; sien_devine: number | null;
};
export type Quiz = {
  semaine: string; serie: { id: number; titre: string; accroche: string }; questions: QuizQuestion[]; score: { moi: number; sien: number };
};

export async function weeksQuiz(): Promise<Quiz> {
  const { data, error } = await supabase.rpc('mon_quiz');
  if (error) throw new Error(error.message);
  return data as Quiz;
}

export async function answerQuiz(questionId: number, pourMoi: number, pourLAutre: number) {
  const { error } = await supabase.rpc('repondre_quiz', { question_id: questionId, pour_moi: pourMoi, pour_l_autre: pourLAutre });
  if (error) throw new Error(error.message);
}

// The week's défi (A3): done for the duo once both ticked it. `valides`: the défis both ticked, all weeks.
export type Defi = { id: number; genre: 'geste' | 'rituel' | 'sortie' | 'jeu'; titre: string; texte: string; envie: string | null };
export type Semaine = { semaine: string; defi: Defi; fait_par_moi: boolean; fait_par_l_autre: boolean; valides: number };

export async function weeksDefi(): Promise<Semaine> {
  const { data, error } = await supabase.rpc('mon_defi');
  if (error) throw new Error(error.message);
  return data as Semaine;
}

export async function defiDone() {
  const { error } = await supabase.rpc('defi_fait');
  if (error) throw new Error(error.message);
}

// The badges, from the défis both ticked.
export const BADGES = [
  { from: 1, name: 'Premier pas' },
  { from: 4, name: 'Un mois de complicité' },
  { from: 12, name: 'Saison complice' },
  { from: 52, name: 'Année complice' },
];
export const badgesFor = (valides: number) => BADGES.filter((b) => valides >= b.from).map((b) => b.name);

// The programme « 4 semaines pour se retrouver » (C11): started by the duo, a week opening every seven days; each week's
// défi ticked by each, done once both did. `semaine`: the week the duo is in, 0 before it began, 5 once it is over.
export type ProgrammeWeek = {
  semaine: number; titre: string; texte: string; envies: string[]; question: string; defi: string;
  ouverte: boolean; fait_par_moi: boolean; fait_par_l_autre: boolean;
};
export type Programme = { started_on: string | null; semaine: number; semaines: ProgrammeWeek[] };

export async function myProgramme(): Promise<Programme> {
  const { data, error } = await supabase.rpc('mon_programme');
  if (error) throw new Error(error.message);
  return data as Programme;
}

export async function startProgramme() {
  const { error } = await supabase.rpc('commencer_programme');
  if (error) throw new Error(error.message);
}

export async function programmeDone(semaine: number) {
  const { error } = await supabase.rpc('programme_fait', { semaine_faite: semaine });
  if (error) throw new Error(error.message);
}

// The week's quiz finished by both, its verdict: their right guesses together, out of sixteen.
export function verdict(right: number): string {
  if (right >= 14) return 'Télépathes : vous finissez les phrases de l’autre.';
  if (right >= 10) return 'Âmes complices : il vous reste juste assez de mystère.';
  if (right >= 6) return 'Complices en rodage : de belles découvertes en vue.';
  return 'Deux mystères ambulants : tout reste à découvrir, et c’est la meilleure part.';
}
