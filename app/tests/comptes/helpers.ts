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

export type Account = { email: string; password: string; id: string };

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

// A new account, created through the app's form, and signed in.
export async function newAccount(label: string): Promise<Account> {
  const email = `${label}-${unique()}@example.com`;
  const password = `secret-${unique()}`;
  await signOut();
  await signUp(email, password);
  const { data } = await supabase.auth.getUser();
  if (!data.user) throw new Error(`${email} : pas connecté après la création du compte`);
  return { email, password, id: data.user.id };
}

// Signed in as this account, and only this one.
export async function as(account: Account) {
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
