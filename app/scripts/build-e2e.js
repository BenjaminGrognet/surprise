// The web build the browser tests drive (npm run build:e2e → dist-e2e, served by tests/e2e_server.py): never app/.env's
// Supabase. With the local one running (npm run db:start), accounts on it; else no accounts at all. An export takes a
// minute or more: it is made again only when the app, its settings or its variables changed since the last one
// (E2E_REBUILD=1 to make it anyway).
const { execSync } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const { localSupabase } = require('./supabase-local');

const APP = path.resolve(__dirname, '..');
const OUT = path.join(APP, 'dist-e2e');
const STAMP = path.join(APP, 'node_modules/.cache/dist-e2e.stamp');
// What the build is made of: the app's code and pictures, its settings and dependencies.
const SOURCES = ['src', 'assets', 'public', 'index.js', 'app.json', 'app.config.js', 'babel.config.js', 'tsconfig.json', 'package-lock.json'];

function files(entry) {
  if (!fs.existsSync(entry)) return [];
  if (!fs.statSync(entry).isDirectory()) return [entry];
  return fs.readdirSync(entry).sort().flatMap((name) => files(path.join(entry, name)));
}

// The build's fingerprint: its sources and the variables it is made with.
function stamp(env) {
  const hash = crypto.createHash('sha256');
  for (const file of SOURCES.flatMap((source) => files(path.join(APP, source)))) {
    hash.update(path.relative(APP, file).replaceAll('\\', '/'));
    hash.update(fs.readFileSync(file));
  }
  hash.update(JSON.stringify(Object.entries(env).filter(([key]) => key.startsWith('EXPO_PUBLIC_')).sort()));
  return hash.digest('hex');
}

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
  const built = fs.existsSync(path.join(OUT, 'index.html')) && fs.existsSync(STAMP) && fs.readFileSync(STAMP, 'utf8');
  if (built === wanted && !process.env.E2E_REBUILD) {
    console.log('dist-e2e à jour : le build est repris tel quel (E2E_REBUILD=1 pour le refaire)');
    return;
  }
  fs.rmSync(STAMP, { force: true });
  // --clear: Metro's cache would keep the variables of the last build.
  execSync('npx expo export -p web --output-dir dist-e2e --clear', { cwd: APP, env, stdio: 'inherit' });
  fs.mkdirSync(path.dirname(STAMP), { recursive: true });
  fs.writeFileSync(STAMP, wanted);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
