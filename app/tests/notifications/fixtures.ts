// A kept evening as the server gives it, for the notifications' tests: real enough for its clues, words and bookings.
import type { SoireeRoute, SoireeStep } from '@/lib/api';

export const SECRET = 'Le Pacte du Canal';

// A local hour, `offset` days from `day`, as the phone reads it.
export function local(day: string, hour: number, minute = 0, offset = 0) {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(y, m - 1, d + offset, hour, minute).getTime();
}
export const iso = (at: number) => new Date(at).toISOString();

function step(fields: Partial<SoireeStep> & Pick<SoireeStep, 'id' | 'title' | 'role' | 'start' | 'end'>): SoireeStep {
  return {
    travel_minutes: 0, distance_km: 0, venue: '', arrondissement: null, town: 'Paris', lat: 48.86, lon: 2.35,
    kind: 'verifie', price: 30, price_estimated: false, booking_url: null, booking_action: 'voir_lieu', image_url: null,
    text: null, vibes: [], keywords: [], originality: 0, basis: '', source_id: 'test', source_name: 'Test', redo: null,
    ...fields,
  };
}

// A Friday evening: dinner at 19:30 (to book), a comedy club across Paris (to book), a bar next door until 00:30.
export function evening(day = '2026-10-16'): SoireeRoute {
  return {
    index: 0, title: 'Rire puis trinquer', secret_title: SECRET, pitch: '', day,
    start: iso(local(day, 19, 30)), end: iso(local(day, 0, 30, 1)), price: 90, price_estimated: false, night: null, redo: '',
    steps: [
      step({
        id: 'test:comptoir', title: 'Le Comptoir', venue: 'Le Comptoir', role: 'repas', arrondissement: 11, vibes: ['savourer'],
        start: iso(local(day, 19, 30)), end: iso(local(day, 21, 0)), booking_action: 'reserver', booking_url: 'https://example.com/comptoir',
      }),
      step({
        id: 'test:comedy', title: 'Le Comedy Club', venue: 'Comedy Club', role: 'sortie', arrondissement: 2, vibes: ['rire'],
        start: iso(local(day, 21, 20)), end: iso(local(day, 23, 0)), travel_minutes: 15, distance_km: 2.4,
        booking_action: 'reserver', booking_url: 'https://example.com/comedy',
      }),
      step({
        id: 'test:bar', title: 'Un bar caché', venue: 'Le Bar Caché', role: 'verre', arrondissement: 2, vibes: ['fete'],
        start: iso(local(day, 23, 10)), end: iso(local(day, 0, 30, 1)), travel_minutes: 8, distance_km: 0.6,
      }),
    ],
  };
}
