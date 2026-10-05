// The browser tests (e2e/): the web build for the local Supabase (npm run build:e2e → dist-e2e) and the API on the
// test catalogue, both served by tests/e2e_server.py. `npm run e2e` builds, then runs them; Supabase local first
// (npm run db:start).
import { defineConfig, devices } from '@playwright/test';

const PORT = 8011;

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    ...devices['Desktop Chrome'],
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `uv run python tests/e2e_server.py --port ${PORT}`,
    cwd: '..',
    url: `http://127.0.0.1:${PORT}/api/soiree`,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
