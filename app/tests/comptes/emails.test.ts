// The emails beside the notifications (lib/emails.ts, supabase/migrations/…_courriers.sql), on the local Supabase: each
// account's choice, its own only; the invitations sent by email, by an evening's organisers alone, to a valid address,
// for an evening to come, and few of them; seen by its organisers, never by its passagers.
import { expect, test } from '@jest/globals';

import { chooseEvening, keptEvening } from '@/lib/account';
import { joinEvening } from '@/lib/couple';
import { emailInvitations, emailsOn, inviteByEmail, setEmails } from '@/lib/emails';

import { admin, as, keep, newAccount, PAST, pageName } from './helpers';

test('each account chooses its emails, yes until it says no, and no one else’s choice is read', async () => {
  const lea = await newAccount('emails');
  expect(await emailsOn()).toBe(true);
  await setEmails(false);
  expect(await emailsOn()).toBe(false);
  await setEmails(true);
  await setEmails(false); // again: one row, changed
  const { data } = await admin.from('email_prefs').select('user_id,emails').eq('user_id', lea.id);
  expect(data).toEqual([{ user_id: lea.id, emails: false }]);

  await newAccount('emails-autre');
  expect(await emailsOn()).toBe(true);
  const { data: seen } = await (await import('@/lib/supabase')).supabase.from('email_prefs').select('user_id');
  expect(seen?.map((r) => r.user_id)).not.toContain(lea.id);
});

test('an invitation by email: its organiser’s, to a valid address, for an evening to come; seen by them only', async () => {
  await newAccount('invite-mail');
  const row = await keep();
  await inviteByEmail(row.id, '  Tom@Example.com ');
  await expect(inviteByEmail(row.id, 'pas-un-email')).rejects.toThrow("Cet email n'est pas valide.");
  await expect(inviteByEmail(row.id, '')).rejects.toThrow('Indiquez son email.');
  await expect(inviteByEmail(row.id, 'ana@example.com', 'complice')).rejects.toThrow('Invitation inconnue.'); // a couple's: no complices
  const sent = await emailInvitations(row.id);
  expect(sent).toMatchObject([{ email: 'tom@example.com', role: 'passager', sent_at: null }]);

  // Someone else's evening, a past one: refused.
  const past = await keep(PAST);
  await expect(inviteByEmail(past.id, 'tom@example.com')).rejects.toThrow('Cette soirée est passée.');
  await newAccount('invite-mail-autre');
  await expect(inviteByEmail(row.id, 'x@example.com')).rejects.toThrow("Cette soirée n'est pas gardée sur votre compte.");
  // Its passager, once joined, sees none of them.
  await joinEvening(row.invite_code);
  expect(await emailInvitations(row.id)).toEqual([]);
});

test('a band’s complice sends its guests’ link by email, its instigateur the complices’ too', async () => {
  await newAccount('bande-mail');
  const page = pageName();
  await chooseEvening({ pageName: page, title: 'Karaoké', secretTitle: 'La Virée', pitch: 'En bande.', vibes: ['fete'], day: '2099-06-12', formule: 'squad', personnes: 6 });
  const band = (await keptEvening(page))!;
  await inviteByEmail(band.id, 'temoin@example.com', 'complice');
  await newAccount('bande-mail-temoin');
  await joinEvening(band.codes!.complice_code);
  await inviteByEmail(band.id, 'invite@example.com');
  await expect(inviteByEmail(band.id, 'autre-temoin@example.com', 'complice')).rejects.toThrow("Cette soirée n'est pas gardée sur votre compte.");
  expect((await emailInvitations(band.id)).map((i) => i.email)).toEqual(['invite@example.com']); // the complice sees the ones it sent
});

test('so few that nobody mails strangers through Secret Date', async () => {
  const lea = await newAccount('invite-limite');
  const evenings = [await keep(), await keep(), await keep(), await keep()];
  // An evening for two: six invitations at most (its places and a few retries).
  for (let i = 0; i < 6; i++) await inviteByEmail(evenings[0].id, `ami${i}@example.com`);
  await expect(inviteByEmail(evenings[0].id, 'ami6@example.com')).rejects.toThrow("Assez d'invitations pour cette soirée");
  // Twenty a day for an account, whatever the evenings.
  for (let i = 0; i < 14; i++) await inviteByEmail(evenings[1 + (i % 3)].id, `autre${i}@example.com`);
  await expect(inviteByEmail(evenings[3].id, 'encore@example.com')).rejects.toThrow("Trop d'invitations envoyées aujourd'hui");
  await as(lea);
  const { count } = await admin.from('email_invitations').select('id', { count: 'exact', head: true }).eq('invited_by', lea.id);
  expect(count).toBe(20);
});
