// The couple's two accounts (supabase/migrations/…_couples.sql): the instigateur makes the profile and orders
// the evenings, the passager is invited by a link and only gets the clues. Without a couple, or as the account
// that created it, one is an instigateur; having joined one, its passager.
import * as Linking from 'expo-linking';

import { currentUser } from '@/lib/account';
import { supabase } from '@/lib/supabase';

export type AccountRole = 'instigateur' | 'passager';

export type Couple = {
  id: string;
  instigateur: string;
  instigateur_email: string | null;
  passager: string | null;
  passager_email: string | null;
  invite_code: string;
  joined_at: string | null;
};

export type CoupleState = { role: AccountRole; couple: Couple | null };

export async function myCouple(): Promise<CoupleState> {
  const user = await currentUser();
  if (!user) return { role: 'instigateur', couple: null };
  const { data, error } = await supabase.from('couples').select('*').limit(1);
  if (error) throw new Error(error.message);
  const couple = (data?.[0] as Couple | undefined) ?? null;
  return { role: couple?.passager === user.id ? 'passager' : 'instigateur', couple };
}

// The instigateur's invitation: their couple, created on first ask.
export async function invitation(): Promise<Couple> {
  const user = await currentUser();
  if (!user) throw new Error('Connectez-vous pour inviter votre passager.');
  const { couple } = await myCouple();
  if (couple) return couple;
  const { data, error } = await supabase.from('couples').insert({ instigateur: user.id, instigateur_email: user.email ?? null }).select('*').single();
  if (error) throw new Error(error.message);
  return data as Couple;
}

// A fresh link, and the passager (if any) let go: the couple is drawn again.
export async function renewInvitation(): Promise<Couple> {
  const { couple } = await myCouple();
  if (couple) {
    const { error } = await supabase.from('couples').delete().eq('id', couple.id);
    if (error) throw new Error(error.message);
  }
  return invitation();
}

export async function joinCouple(code: string) {
  const { error } = await supabase.rpc('join_couple', { code });
  if (error) throw new Error(error.message);
}

export const invitationLink = (code: string) => Linking.createURL('/invitation', { queryParams: { code } });
