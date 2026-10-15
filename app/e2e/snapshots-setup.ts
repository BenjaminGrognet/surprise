// Before the browser tests: last run's pictures of the pages taken away (e2e/fixtures.ts).
import fs from 'node:fs';

import { SNAPSHOTS } from './fixtures';

export default function setup() {
  fs.rmSync(SNAPSHOTS, { recursive: true, force: true });
  fs.mkdirSync(SNAPSHOTS, { recursive: true });
}
