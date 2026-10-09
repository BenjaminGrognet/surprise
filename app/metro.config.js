// Metro's cache, one per set of EXPO_PUBLIC_ variables: they are written into the bundle, so a build made with other
// ones (the browser tests' local Supabase, the phone's API address) never reuses this one's code. Each build then
// starts from its own warm cache instead of clearing it (a cold export takes over a minute).
const crypto = require('node:crypto');
const path = require('node:path');
const { getDefaultConfig } = require('expo/metro-config');
const { FileStore } = require('metro-cache');

const config = getDefaultConfig(__dirname);

const publicEnv = Object.entries(process.env)
  .filter(([key]) => key.startsWith('EXPO_PUBLIC_'))
  .sort(([a], [b]) => a.localeCompare(b));
const key = crypto.createHash('sha256').update(JSON.stringify(publicEnv)).digest('hex').slice(0, 12);
config.cacheStores = [new FileStore({ root: path.join(__dirname, 'node_modules/.cache/metro', key) })];

module.exports = config;
