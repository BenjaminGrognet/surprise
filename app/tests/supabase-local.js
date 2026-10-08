// The local Supabase the account tests run against (npm run db:start, Docker running): its URL and keys, set for
// the app's lib/supabase.ts before any test loads it. Never the project's own Supabase (app/.env).
const { localSupabase } = require('../scripts/supabase-local');

module.exports = async () => {
  const local = await localSupabase();
  if (!local) throw new Error('Supabase local pas lancé : `npm run db:start` dans app/, Docker Desktop ouvert.');
  process.env.EXPO_PUBLIC_SUPABASE_URL = local.url;
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY = local.anonKey;
  process.env.SUPABASE_TEST_SERVICE_KEY = local.serviceKey;
};
