// The web build the browser tests drive (npm run build:e2e → dist-e2e, served by tests/e2e_server.py): never app/.env's
// Supabase. With the local one running (npm run db:start), accounts on it; else no accounts at all.
const { execSync } = require('node:child_process');
const path = require('node:path');

const env = { ...process.env, EXPO_NO_DOTENV: '1' };
delete env.EXPO_PUBLIC_SUPABASE_URL;
delete env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
try {
  const out = execSync('npx supabase status -o json', { cwd: path.resolve(__dirname, '../..'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
  const status = JSON.parse(out.slice(out.indexOf('{')));
  env.EXPO_PUBLIC_SUPABASE_URL = status.API_URL;
  env.EXPO_PUBLIC_SUPABASE_ANON_KEY = status.ANON_KEY ?? status.PUBLISHABLE_KEY;
  console.log(`Comptes : Supabase local ${status.API_URL}`);
} catch {
  console.log('Comptes : aucun (Supabase local pas lancé)');
}
// --clear: Metro's cache would keep the variables of the last build.
execSync('npx expo export -p web --output-dir dist-e2e --clear', { cwd: path.resolve(__dirname, '..'), env, stdio: 'inherit' });
