// The emails beside the notifications (supabase/migrations/…_courriers.sql; the server sends them, surprise.courriers):
// whether the account gets them, the invitations to an evening sent by email to an address, and stopping them from the
// link of one of them (the server's API checks its signature).
import type { GuestRole } from '@/lib/account';
import { API_URL } from '@/lib/api';
import { currentUser, supabase } from '@/lib/supabase';

// Whether the account gets its evenings' emails: yes until it says otherwise.
export async function emailsOn(): Promise<boolean> {
  const user = await currentUser();
  if (!user) return false;
  const { data, error } = await supabase.from('email_prefs').select('emails').eq('user_id', user.id).maybeSingle();
  if (error) throw new Error(error.message);
  return data?.emails ?? true;
}

export async function setEmails(on: boolean) {
  const user = await currentUser();
  if (!user) throw new Error('Connectez-vous d’abord.');
  const { error } = await supabase
    .from('email_prefs')
    .upsert({ user_id: user.id, emails: on, updated_at: new Date().toISOString() }, { onConflict: 'user_id' });
  if (error) throw new Error(error.message);
}

// An invitation sent by email: to whom, which link, whether the server sent it yet.
export type EmailInvitation = { id: string; email: string; role: GuestRole; created_at: string; sent_at: string | null };

// The evening's link sent to this address by the server (a band's complices' too): its instigateur's, a few a day.
export async function inviteByEmail(soireeId: string, email: string, role: GuestRole = 'passager') {
  if (!email.trim()) throw new Error('Indiquez son email.');
  const { error } = await supabase.rpc('invite_by_email', { sid: soireeId, address: email.trim(), as_role: role });
  if (error) throw new Error(error.message);
}

export async function emailInvitations(soireeId: string): Promise<EmailInvitation[]> {
  const { data, error } = await supabase
    .from('email_invitations').select('id,email,role,created_at,sent_at').eq('soiree_id', soireeId).order('created_at');
  if (error) throw new Error(error.message);
  return (data ?? []) as EmailInvitation[];
}

// The link at the foot of an email (/compte?stop=…&t=…): no more emails to its address, signed in or not.
export async function stopEmails(address: string, token: string) {
  const response = await fetch(`${API_URL}/api/courriels/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stop: address, t: token }),
  }).catch(() => null);
  if (!response?.ok) {
    throw new Error(response?.status === 403 ? 'Ce lien n’est pas valide : arrêtez les emails depuis votre compte.' : 'Les emails n’ont pas pu être arrêtés : réessayez dans un instant.');
  }
}
