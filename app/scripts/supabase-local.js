// The local Supabase (npm run db:start, Docker running): its URL and keys, never the project's own. `supabase status`
// takes seconds (it asks Docker), so its answer is kept in node_modules/.cache while those keys still open the local
// API; asked again when Supabase was restarted with others, or stopped.
const { execSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const CACHE = path.resolve(__dirname, '../node_modules/.cache/supabase-local.json');
const LOCAL = /^http:\/\/(127\.0\.0\.1|localhost):\d+$/;

// Both keys open the API: PostgREST answers 401 to a key it does not know.
async function opens(local) {
  try {
    const answers = await Promise.all([local.anonKey, local.serviceKey].map((key) => fetch(`${local.url}/rest/v1/`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
      signal: AbortSignal.timeout(2000),
    })));
    return answers.every((answer) => answer.ok);
  } catch {
    return false;
  }
}

function status() {
  const out = execSync('npx supabase status -o json', {
    cwd: path.resolve(__dirname, '../..'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
  });
  const found = JSON.parse(out.slice(out.indexOf('{')));
  return {
    url: found.API_URL,
    anonKey: found.ANON_KEY ?? found.PUBLISHABLE_KEY,
    serviceKey: found.SERVICE_ROLE_KEY ?? found.SECRET_KEY,
  };
}

// { url, anonKey, serviceKey }, or null when the local Supabase is not running.
async function localSupabase() {
  try {
    const kept = JSON.parse(fs.readFileSync(CACHE, 'utf8'));
    if (LOCAL.test(kept.url ?? '') && (await opens(kept))) return kept;
  } catch {
    // Nothing kept yet, or unreadable: asked below.
  }
  let found;
  try {
    found = status();
  } catch {
    return null;
  }
  if (!LOCAL.test(found.url ?? '')) throw new Error(`Supabase local attendu, pas ${found.url}`);
  fs.mkdirSync(path.dirname(CACHE), { recursive: true });
  fs.writeFileSync(CACHE, JSON.stringify(found));
  return found;
}

module.exports = { localSupabase };
