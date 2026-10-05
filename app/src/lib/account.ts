// Accounts (Supabase Auth) and the couple's own data: profile sync and evening history.
// Row-level security scopes couple_profiles/soirees_choisies to the signed-in user.
import { currentUser, supabase } from '@/lib/supabase';
import type { Profile } from '@/lib/api';
import type { RevealMode } from '@/lib/clues';
import { removePhotos } from '@/lib/souvenirs';

export { currentUser };

// Supabase Auth's refusals (by their code), as the couple reads them; any other one in a general sentence.
const AUTH_ERRORS: Record<string, string> = {
  invalid_credentials: 'Email ou mot de passe incorrect.',
  user_already_exists: 'Un compte existe déjà avec cet email : connectez-vous.',
  email_exists: 'Un compte existe déjà avec cet email : connectez-vous.',
  weak_password: 'Mot de passe trop court : 6 caractères au moins.',
  email_address_invalid: "Cet email n'est pas valide.",
  validation_failed: "Cet email n'est pas valide.",
  email_not_confirmed: "Votre email n'est pas encore confirmé : ouvrez le lien reçu.",
  signup_disabled: 'Les nouveaux comptes sont fermés pour le moment.',
  over_request_rate_limit: 'Trop de tentatives : réessayez dans quelques minutes.',
  over_email_send_rate_limit: 'Trop de tentatives : réessayez dans quelques minutes.',
};

function authError(error: { code?: string; name?: string }) {
  if (error.code && AUTH_ERRORS[error.code]) return new Error(AUTH_ERRORS[error.code]);
  if (error.name === 'AuthRetryableFetchError') return new Error('Connexion impossible : vérifiez votre réseau, puis réessayez.');
  return new Error("La connexion n'a pas abouti. Réessayez dans un instant.");
}

export async function signIn(email: string, password: string) {
  if (!email.trim() || !password) throw new Error('Indiquez votre email et votre mot de passe.');
  const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
  if (error) throw authError(error);
}

export async function signUp(email: string, password: string) {
  if (!email.trim() || !password) throw new Error('Indiquez votre email et votre mot de passe.');
  const { error } = await supabase.auth.signUp({ email: email.trim(), password });
  if (error) throw authError(error);
}

export const signOut = () => supabase.auth.signOut();

export type AccountProfile = { id: string; answers: Record<string, unknown>; profile: Profile };

export async function accountProfile(): Promise<AccountProfile | null> {
  const user = await currentUser();
  if (!user) return null;
  const { data, error } = await supabase
    .from('couple_profiles')
    .select('id,answers,profile')
    .eq('user_id', user.id)
    .maybeSingle();
  if (error) throw new Error(error.message);
  return data as AccountProfile | null;
}

export async function saveAccountProfile(answers: Record<string, unknown>, profile: Profile) {
  const user = await currentUser();
  if (!user) return;
  const existing = await accountProfile();
  if (existing) {
    const { error } = await supabase.from('couple_profiles').update({ answers, profile }).eq('id', existing.id);
    if (error) throw new Error(error.message);
  } else {
    const { error } = await supabase.from('couple_profiles').insert({ id: user.id, user_id: user.id, answers, profile }); // `id` has no default: one profile per account
    if (error) throw new Error(error.message);
  }
}

export type EveningHistoryRow = {
  id: string;
  user_id: string;
  passager: string | null; // the one passager invited to this evening, once joined
  passager_email: string | null;
  invite_code: string; // the link's code, renewed when the passager is let go
  reveal_mode?: string; // how its programme is lifted for the passager (lib/clues.ts RevealMode); absent before the migration
  page_name: string; // the evening's page on the server: once kept, its only route
  title: string;
  secret_title: string | null; // "Le Pacte de l'Île Saint-Louis", fixed when kept; null for older evenings
  pitch: string;
  vibes: string[] | null;
  day: string | null;
  // Its Livre des Secrets: empty until the account sealed its own page, then both pages (RLS).
  souvenirs?: { author: string; note: string; photo: string | null }[];
};

export async function eveningsHistory(): Promise<EveningHistoryRow[]> {
  const { data, error } = await supabase
    .from('soirees_choisies').select('*, souvenirs(author,note,photo)').order('chosen_at', { ascending: false });
  if (error) throw new Error(error.message);
  return data as EveningHistoryRow[];
}

// The next evening the couple chose, until its day is over.
export async function upcomingEvening(today: string): Promise<EveningHistoryRow | null> {
  return (await upcomingEvenings(today, 1))[0] ?? null;
}

// The evenings still to come, the nearest first: the compass leafs through them.
export async function upcomingEvenings(today: string, limit = 20): Promise<EveningHistoryRow[]> {
  const { data, error } = await supabase
    .from('soirees_choisies').select('*, souvenirs(author,note,photo)').gte('day', today).order('day').order('chosen_at', { ascending: false }).limit(limit);
  if (error) throw new Error(error.message);
  return (data ?? []) as EveningHistoryRow[];
}

// One evening kept in the couple's history: the route they actually picked, the page's only one once chosen (chooseRoute).
export async function chooseEvening(input: {
  pageName: string;
  title: string;
  secretTitle: string;
  pitch: string;
  vibes: string[];
  day: string | null;
}) {
  const user = await currentUser();
  if (!user) throw new Error('Connectez-vous pour la garder dans votre historique.');
  const { error } = await supabase.from('soirees_choisies').insert({
    user_id: user.id, page_name: input.pageName,
    title: input.title, secret_title: input.secretTitle, pitch: input.pitch, vibes: input.vibes, day: input.day,
  });
  // Already kept (a second tap, one page per evening): nothing more to do.
  if (error && error.code !== '23505') throw new Error(error.message);
}

// A kept evening's secret name, as it was fixed when kept (readable by the passager too).
export async function keptSecretTitle(pageName: string): Promise<string | null> {
  const { data, error } = await supabase.from('soirees_choisies').select('secret_title').eq('page_name', pageName).maybeSingle();
  if (error) throw new Error(error.message);
  return (data?.secret_title as string | null | undefined) ?? null;
}

// What the organiser has booked for a kept evening: the id (source_id:external_id) of each step marked "réservé".
export async function bookedSteps(pageName: string): Promise<string[]> {
  const { data, error } = await supabase.from('soirees_choisies').select('booked').eq('page_name', pageName).maybeSingle();
  if (error) throw new Error(error.message);
  return (data?.booked as string[] | undefined) ?? [];
}

export async function saveBookedSteps(pageName: string, booked: string[]) {
  const { data, error } = await supabase.from('soirees_choisies').update({ booked }).eq('page_name', pageName).select('id');
  if (error) throw new Error(error.message);
  if (!data?.length) throw new Error("Cette soirée n'est pas gardée sur votre compte.");
}

// The couple's tastes (table gouts): on a step, « on aime ce genre » (1) or « pas pour nous » (-1), one vote per
// activity. Sent with each new evening (Night.votes): the server favours the kinds liked and leaves out the others.
export type Vote = 1 | -1;
export type TasteRow = { activity_id: string; vote: Vote; title: string; voted_at: string };

export async function myTastes(): Promise<TasteRow[]> {
  const { data, error } = await supabase.from('gouts').select('activity_id,vote,title,voted_at').order('voted_at', { ascending: false });
  if (error) throw new Error(error.message);
  return (data ?? []) as TasteRow[];
}

// A vote on a step (its id: source_id:external_id), or withdrawn (null).
export async function saveTaste(step: { id: string; title: string }, vote: Vote | null) {
  const user = await currentUser();
  if (!user) throw new Error('Connectez-vous pour garder vos goûts.');
  const { error } = vote === null
    ? await supabase.from('gouts').delete().eq('activity_id', step.id)
    : await supabase.from('gouts').upsert(
      { user_id: user.id, activity_id: step.id, vote, title: step.title, voted_at: new Date().toISOString() },
      { onConflict: 'user_id,activity_id' },
    );
  if (error) throw new Error(error.message);
}

// The votes as the server reads them with a new evening.
export const votesOf = (rows: TasteRow[]): Record<string, Vote> => Object.fromEntries(rows.map((r) => [r.activity_id, r.vote]));

// A past evening removed from the archives, its book and photos with it (instigateur only, RLS: day is over).
export async function deleteEvening(id: string) {
  await removePhotos([id]);
  const { data, error } = await supabase.from('soirees_choisies').delete().eq('id', id).select('id');
  if (error) throw new Error(error.message);
  if (!data?.length) throw new Error("Cette soirée n'a pas pu être supprimée.");
}

// The account and everything of it: the photos first (storage isn't cascaded), then the auth row (cascade).
export async function deleteMyAccount() {
  const user = await currentUser();
  if (!user) return;
  const rows = await eveningsHistory();
  await removePhotos(rows.filter((r) => r.user_id === user.id).map((r) => r.id));
  await removePhotos(rows.filter((r) => r.user_id !== user.id).map((r) => r.id), user.id);
  const { error } = await supabase.rpc('delete_my_account');
  if (error) throw new Error(error.message);
  await supabase.auth.signOut();
}

// The kept evening of a page, as the revelation finds it.
export async function keptEvening(pageName: string): Promise<EveningHistoryRow | null> {
  const { data, error } = await supabase.from('soirees_choisies').select('*').eq('page_name', pageName).maybeSingle();
  if (error) throw new Error(error.message);
  return (data as EveningHistoryRow | null) ?? null;
}

// How the passager's programme is lifted (instigateur only, RLS: their own row).
export async function saveRevealMode(id: string, mode: RevealMode) {
  const { data, error } = await supabase.from('soirees_choisies').update({ reveal_mode: mode }).eq('id', id).select('id');
  if (error) throw new Error(error.message);
  if (!data?.length) throw new Error("Cette soirée n'est pas gardée sur votre compte.");
}
