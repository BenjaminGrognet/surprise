// The guests belong to an evening (supabase/migrations/…_secret_squad.sql, table soiree_invites): an instigateur keeps
// several evenings, each with its guests invited by a link from that evening. A couple's evening (Secret Date) has one
// passager at most; a band's (Secret Squad) as many guests as it has places, passagers — who only get the clues — and
// complices, in on the secret with the instigateur, who join by a link of their own. An account that is the passager
// of some evening is a passager; any other is an instigateur. A passager may in turn compose evenings of their own: on
// those, they are the instigateur (eveningRole).
import * as Linking from 'expo-linking';

import { currentUser, type EveningHistoryRow, type GuestRole, type Invite } from '@/lib/account';
import { supabase } from '@/lib/supabase';

export type AccountRole = 'instigateur' | 'passager';

export type CoupleState = { role: AccountRole; userId: string | null };

export async function myRole(): Promise<CoupleState> {
  const user = await currentUser();
  if (!user) return { role: 'instigateur', userId: null };
  const { count, error } = await supabase
    .from('soiree_invites').select('soiree_id', { count: 'exact', head: true }).eq('user_id', user.id).eq('role', 'passager');
  if (error) throw new Error(error.message);
  return { role: count ? 'passager' : 'instigateur', userId: user.id };
}

type Guests = Pick<EveningHistoryRow, 'invites'>;

// The account's place among the evening's guests, if it is one.
export const guestOf = (evening: Guests, userId: string | null): Invite | null =>
  (userId && evening.invites?.find((i) => i.user_id === userId)) || null;

// The account's side of one evening: one of its passagers, or else on the secret's side — its instigateur, or a
// complice of a band's evening, who sees it as the instigateur does.
export const eveningRole = (evening: Guests, userId: string | null): AccountRole =>
  guestOf(evening, userId)?.role === 'passager' ? 'passager' : 'instigateur';

// The evening's own instigateur: who keeps it, invites, lets a guest go, chooses how it is revealed, deletes it.
export const organises = (evening: Pick<EveningHistoryRow, 'user_id'>, userId: string | null) => !!userId && evening.user_id === userId;

export const guests = (evening: Guests, role?: GuestRole) => (evening.invites ?? []).filter((i) => !role || i.role === role);

// A band's evening: Secret Squad's look and words.
export const isSquad = (evening: Pick<EveningHistoryRow, 'formule'> | null | undefined) => evening?.formule === 'squad';

// Its places left for guests (the instigateur counted among its personnes).
export const placesLeft = (evening: Pick<EveningHistoryRow, 'personnes'> & Guests) => Math.max(0, (evening.personnes ?? 2) - 1 - guests(evening).length);

// A fresh link for the evening, and its passagers (if any) let go; its complices stay.
export async function resetPassager(soireeId: string) {
  const { error } = await supabase.rpc('reset_passager', { sid: soireeId });
  if (error) throw new Error(error.message);
}

// A guest let go by the instigateur, or leaving the band.
export async function removeGuest(soireeId: string, userId: string) {
  const { data, error } = await supabase.from('soiree_invites').delete().eq('soiree_id', soireeId).eq('user_id', userId).select('user_id');
  if (error) throw new Error(error.message);
  if (!data?.length) throw new Error("Cet invité n'a pas pu être retiré.");
}

// Joins the evening of the link: as its passager, or as a complice by a band's complices' link; the role it gives.
export async function joinEvening(code: string): Promise<GuestRole> {
  const { data, error } = await supabase.rpc('join_evening', { code });
  if (error) throw new Error(error.message);
  return data as GuestRole;
}

export const invitationLink = (code: string) => Linking.createURL('/invitation', { queryParams: { code } });
