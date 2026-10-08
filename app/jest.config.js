// The app's tests (npm test): its own lib/, run as on the web, in Node. tests/comptes runs it against a local
// Supabase (npm run db:start), whose URL and keys tests/supabase-local.js finds: never the project's own.
module.exports = {
  preset: 'jest-expo/node',
  roots: ['<rootDir>/tests'],
  globalSetup: '<rootDir>/tests/supabase-local.js',
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  // As tsconfig.json: the app's images are outside src/.
  moduleNameMapper: { '^@/assets/(.*)$': '<rootDir>/assets/$1' },
  testTimeout: 30000,
  // The account tests share the local Supabase: half the cores leave it room (all of them is slower).
  maxWorkers: '50%',
};
