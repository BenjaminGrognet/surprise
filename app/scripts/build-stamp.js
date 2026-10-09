// A web build's fingerprint (its sources and the EXPO_PUBLIC_ variables it is made with), kept beside it: an export
// takes from ten seconds to over a minute, so it is made again only when the fingerprint changed.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const APP = path.resolve(__dirname, '..');
// What the build is made of: the app's code and pictures, its settings and dependencies.
const SOURCES = ['src', 'assets', 'public', 'index.js', 'app.json', 'app.config.js', 'babel.config.js', 'metro.config.js', 'tsconfig.json', 'package-lock.json'];

function files(entry) {
  if (!fs.existsSync(entry)) return [];
  if (!fs.statSync(entry).isDirectory()) return [entry];
  return fs.readdirSync(entry).sort().flatMap((name) => files(path.join(entry, name)));
}

function stamp(env, extra = []) {
  const hash = crypto.createHash('sha256');
  for (const file of [...SOURCES, ...extra].flatMap((source) => files(path.join(APP, source)))) {
    hash.update(path.relative(APP, file).replaceAll('\\', '/'));
    hash.update(fs.readFileSync(file));
  }
  hash.update(JSON.stringify(Object.entries(env).filter(([key]) => key.startsWith('EXPO_PUBLIC_')).sort()));
  return hash.digest('hex');
}

const stampFile = (out) => path.join(APP, 'node_modules/.cache', `${out}.stamp`);

// Whether the build in `out` was made from this fingerprint.
function upToDate(out, wanted) {
  const file = stampFile(out);
  return fs.existsSync(path.join(APP, out, 'index.html')) && fs.existsSync(file) && fs.readFileSync(file, 'utf8') === wanted;
}

// Exports the build into `out` and keeps its fingerprint. No --clear: Metro's cache is one per set of variables
// (metro.config.js), so it never brings another build's into this one.
function exportWeb(out, env, wanted) {
  const { execSync } = require('node:child_process');
  fs.rmSync(stampFile(out), { force: true });
  execSync(`npx expo export -p web --output-dir ${out}`, { cwd: APP, env, stdio: 'inherit' });
  fs.mkdirSync(path.dirname(stampFile(out)), { recursive: true });
  fs.writeFileSync(stampFile(out), wanted);
}

module.exports = { APP, stamp, upToDate, exportWeb };
