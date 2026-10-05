// The local Supabase the account tests run against (npm run db:start, Docker running): its URL and keys, set for
// the app's lib/supabase.ts before any test loads it. Never the project's own Supabase (app/.env).
const { execSync } = require('node:child_process');
const path = require('node:path');

module.exports = async () => {
  let status;
  try {
    const out = execSync('npx supabase status -o json', {
      cwd: path.resolve(__dirname, '../..'),
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
    status = JSON.parse(out.slice(out.indexOf('{')));
  } catch {
    throw new Error('Supabase local pas lancé : `npm run db:start` dans app/, Docker Desktop ouvert.');
  }
  const url = status.API_URL;
  if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(url ?? '')) throw new Error(`Supabase local attendu, pas ${url}`);
  process.env.EXPO_PUBLIC_SUPABASE_URL = url;
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY = status.ANON_KEY ?? status.PUBLISHABLE_KEY;
  process.env.SUPABASE_TEST_SERVICE_KEY = status.SERVICE_ROLE_KEY ?? status.SECRET_KEY;
};
