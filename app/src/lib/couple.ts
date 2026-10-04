// The passager belongs to an evening (supabase/migrations/…_passager_per_evening.sql): an instigateur keeps
// several evenings, each with at most one passager invited by a link from that evening. The passager only gets
// the clues. An account that is the passager of some evening is a passager; any other is an instigateur. A passager
// may in turn compose evenings of their own: on those, they are the instigateur (eveningRole).
import * as Linking from 'expo-linking';

import { currentUser, type EveningHistoryRow } from '@/lib/account';
import { supabase } from '@/lib/supabase';

export type AccountRole = 'instigateur' | 'passager';

export type CoupleState = { role: AccountRole; userId: string | null };

export async function myRole(): Promise<CoupleState> {
  const user = await currentUser();
  if (!user) return { role: 'instigateur', userId: null };
  const { count, error } = await supabase
    .from('soirees_choisies').select('id', { count: 'exact', head: true }).eq('passager', user.id);
  if (error) throw new Error(error.message);
  return { role: count ? 'passager' : 'instigateur', userId: user.id };
}

// The account's side of one evening: its passager, or else its instigateur (the account only sees those two kinds).
export const eveningRole = (evening: Pick<EveningHistoryRow, 'passager'>, userId: string | null): AccountRole =>
  userId && evening.passager === userId ? 'passager' : 'instigateur';

// A fresh link for the evening, and its passager (if any) let go.
export async function resetPassager(soireeId: string) {
  const { error } = await supabase.rpc('reset_passager', { sid: soireeId });
  if (error) throw new Error(error.message);
}

export async function joinEvening(code: string) {
  const { error } = await supabase.rpc('join_evening', { code });
  if (error) throw new Error(error.message);
}

export const invitationLink = (code: string) => Linking.createURL('/invitation', { queryParams: { code } });
