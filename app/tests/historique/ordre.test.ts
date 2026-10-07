// "Mes soirées" in time: the evenings to come first, the next one on top, then those gone, the latest first.
import { expect, test } from '@jest/globals';

import { chronological } from '@/lib/couple';

test('the next evening first, the furthest to come after it, then the latest gone', () => {
  const days = [null, '2026-09-12', '2026-11-20', '2026-10-07', '2026-10-30', '2026-10-02'];
  const order = chronological(days.map((day) => ({ day })), '2026-10-07').map((e) => e.day);
  expect(order).toEqual(['2026-10-07', '2026-10-30', '2026-11-20', '2026-10-02', '2026-09-12', null]);
});
