// The web build the browser tests drive (npm run build:e2e → dist-e2e, served by tests/e2e_server.py): never app/.env's
// Supabase. With the local one running (npm run db:start), accounts on it; else no accounts at all. An export takes a
// minute cold, seconds from a warm cache: it is made again only when the app, its settings or its variables changed
// since the last one (E2E_REBUILD=1 to make it anyway).
const { localSupabase } = require('./supabase-local');
const { stamp, upToDate, exportWeb } = require('./build-stamp');

async function main() {
  const env = { ...process.env, EXPO_NO_DOTENV: '1' };
  delete env.EXPO_PUBLIC_SUPABASE_URL;
  delete env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
  const local = await localSupabase();
  if (local) {
    env.EXPO_PUBLIC_SUPABASE_URL = local.url;
    env.EXPO_PUBLIC_SUPABASE_ANON_KEY = local.anonKey;
    console.log(`Comptes : Supabase local ${local.url}`);
  } else {
    console.log('Comptes : aucun (Supabase local pas lancé)');
  }
  // A Firebase project of the tests' own, never app/.env's: the browser tests stand in for Google (e2e/push.spec.ts).
  Object.assign(env, {
    EXPO_PUBLIC_FIREBASE_API_KEY: 'e2e-api-key',
    EXPO_PUBLIC_FIREBASE_PROJECT_ID: 'secret-date-e2e',
    EXPO_PUBLIC_FIREBASE_SENDER_ID: '424242',
    EXPO_PUBLIC_FIREBASE_APP_ID: '1:424242:web:e2e',
    EXPO_PUBLIC_FIREBASE_VAPID_KEY: 'BAcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwc',
  });
  const wanted = stamp(env);
  if (upToDate('dist-e2e', wanted) && !process.env.E2E_REBUILD) {
    console.log('dist-e2e à jour : le build est repris tel quel (E2E_REBUILD=1 pour le refaire)');
    return;
  }
  exportWeb('dist-e2e', env, wanted);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
