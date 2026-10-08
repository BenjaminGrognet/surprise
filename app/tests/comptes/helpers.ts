// The tests' accounts, on the local Supabase only (tests/supabase-local.js): made and signed in as the app does.
import { createClient } from '@supabase/supabase-js';

import { chooseEvening, keptEvening, signIn, signOut, signUp } from '@/lib/account';
import { supabase } from '@/lib/supabase';

const url = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(url)) throw new Error(`Supabase local attendu, pas ${url}`);

// Past the row-level security, to see what an account cannot.
export const admin = createClient(url, process.env.SUPABASE_TEST_SERVICE_KEY ?? '', {
  auth: { persistSession: false, autoRefreshToken: false },
});

export type Account = { email: string; password: string; id: string; session: { access_token: string; refresh_token: string } };

const unique = () => Math.random().toString(36).slice(2, 10);

// A page of the server's for each evening kept: unique in the history, as on the server.
export const pageName = () => `soiree-test-${unique()}`;

// A one-pixel PNG, as the photo picker would give it.
export const PHOTO = {
  uri: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  mimeType: 'image/png',
};

export const PAST = '2020-06-12';
export const FUTURE = '2099-06-12';

// A new account, created through the app's form, and signed in. The one signed in before keeps its session on the
// server, as on another phone: `as` takes it back without its password (a sign-in hashes it: a quarter of a second).
export async function newAccount(label: string): Promise<Account> {
  const email = `${label}-${unique()}@example.com`;
  const password = `secret-${unique()}`;
  await signUp(email, password);
  const { data } = await supabase.auth.getSession();
  if (!data.session) throw new Error(`${email} : pas connecté après la création du compte`);
  const { access_token, refresh_token } = data.session;
  return { email, password, id: data.session.user.id, session: { access_token, refresh_token } };
}

// Signed in as this account, and only this one: its session taken back, or its password once it signed out.
export async function as(account: Account) {
  if (!(await supabase.auth.setSession(account.session)).error) return;
  await signOut();
  await signIn(account.email, account.password);
}

// An evening kept by the account signed in, as the app keeps it; its row.
export async function keep(day: string | null = FUTURE, page = pageName()) {
  await chooseEvening({
    pageName: page, title: 'Rires au Marais', secretTitle: 'Le Pacte du Marais', pitch: 'Un soir à deux.',
    vibes: ['rire'], day,
  });
  const row = await keptEvening(page);
  if (!row) throw new Error(`${page} : pas gardée`);
  return row;
}
