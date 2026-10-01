// Accounts (Supabase Auth) and the couple's own data: profile sync and evening history.
// Row-level security scopes couple_profiles/soirees_choisies to the signed-in user.
import { supabase } from '@/lib/supabase';
import type { Profile } from '@/lib/api';

export async function currentUser() {
  const { data } = await supabase.auth.getSession();
  return data.session?.user ?? null;
}

export async function signIn(email: string, password: string) {
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);
}

export async function signUp(email: string, password: string) {
  const { error } = await supabase.auth.signUp({ email, password });
  if (error) throw new Error(error.message);
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
    const { error } = await supabase.from('couple_profiles').insert({ user_id: user.id, answers, profile });
    if (error) throw new Error(error.message);
  }
}

export type EveningHistoryRow = {
  id: string;
  page_name: string;
  route_index: number;
  title: string;
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
  const { data, error } = await supabase
    .from('soirees_choisies').select('*, souvenirs(author,note,photo)').gte('day', today).order('day').order('chosen_at', { ascending: false }).limit(1);
  if (error) throw new Error(error.message);
  return (data?.[0] as EveningHistoryRow) ?? null;
}

// One evening kept in the couple's history: the route they actually picked, among the ones proposed.
export async function chooseEvening(input: {
  pageName: string;
  routeIndex: number;
  title: string;
  pitch: string;
  vibes: string[];
  day: string | null;
}) {
  const user = await currentUser();
  if (!user) throw new Error('Connectez-vous pour la garder dans votre historique.');
  const { error } = await supabase.from('soirees_choisies').insert({
    user_id: user.id, page_name: input.pageName, route_index: input.routeIndex,
    title: input.title, pitch: input.pitch, vibes: input.vibes, day: input.day,
  });
  if (error) throw new Error(error.message);
}

// What the organiser has booked for a kept evening: the id (source_id:external_id) of each step marked "réservé".
export async function bookedSteps(pageName: string, routeIndex: number): Promise<string[]> {
  const { data, error } = await supabase
    .from('soirees_choisies').select('booked').eq('page_name', pageName).eq('route_index', routeIndex)
    .order('chosen_at', { ascending: false }).limit(1);
  if (error) throw new Error(error.message);
  return (data?.[0]?.booked as string[] | undefined) ?? [];
}

export async function saveBookedSteps(pageName: string, routeIndex: number, booked: string[]) {
  const { data, error } = await supabase
    .from('soirees_choisies').update({ booked }).eq('page_name', pageName).eq('route_index', routeIndex).select('id');
  if (error) throw new Error(error.message);
  if (!data?.length) throw new Error("Cette soirée n'est pas gardée sur votre compte.");
}
