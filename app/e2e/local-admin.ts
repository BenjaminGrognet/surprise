// Past the row-level security of the local Supabase (npm run db:start), never the project's: what a test sets up that
// the app itself would take days to make (evenings lived, a season coming, intrigues composed by the server).
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { localSupabase } = require('../scripts/supabase-local');

let client: SupabaseClient | null = null;

export async function admin(): Promise<SupabaseClient> {
  if (client) return client;
  const local = await localSupabase();
  if (!local || !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(local.url)) throw new Error('Supabase local attendu');
  client = createClient(local.url, local.serviceKey, { auth: { persistSession: false } });
  return client;
}

export async function userId(email: string): Promise<string> {
  const { data } = await (await admin()).auth.admin.listUsers({ perPage: 1000 });
  const user = data.users.find((u) => u.email === email);
  if (!user) throw new Error(`${email} : pas de compte`);
  return user.id;
}
