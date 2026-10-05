// The notifications scheduled on the phone from the account's evenings (lib/notifications.ts), on the local Supabase:
// the instigateur's reminders, the passager's week once they joined, told again as bookings are ticked or the reveal
// mode changes; kept while the server can't be reached, cleared once signed out. The phone and the server's routes are
// stand-ins, the accounts and evenings real.
import { afterAll, beforeAll, beforeEach, expect, jest, test } from '@jest/globals';
import { Platform } from 'react-native';

import { saveBookedSteps, saveRevealMode, signOut } from '@/lib/account';
import { getSoireeState, type ComposedSoiree, type SoireeRoute } from '@/lib/api';
import { joinEvening } from '@/lib/couple';
import { isoDay } from '@/lib/dates';
import { clearNotifications, scheduleNotifications } from '@/lib/notifications';

import { as, keep, newAccount } from '../comptes/helpers';
import { evening, local } from './fixtures';

type Scheduled = {
  identifier: string;
  content: { title: string; body: string; data: { url: string } };
  trigger: { date: Date; channelId: string };
};

// The phone: what is scheduled on it, by id.
const mockPhone = new Map<string, Scheduled>();
jest.mock('expo-notifications', () => ({
  setNotificationHandler: () => {},
  getPermissionsAsync: async () => ({ status: 'granted', canAskAgain: true }),
  setNotificationChannelAsync: async () => null,
  cancelAllScheduledNotificationsAsync: async () => mockPhone.clear(),
  scheduleNotificationAsync: async (request: Scheduled) => {
    mockPhone.set(request.identifier, request);
    return request.identifier;
  },
  SchedulableTriggerInputTypes: { DATE: 'date' },
  AndroidImportance: { DEFAULT: 3 },
}));

// The server: each kept evening's route, or none (404), or no answer at all.
const server = new Map<string, SoireeRoute | 'offline'>();
jest.mock('@/lib/api', () => ({ ...jest.requireActual<object>('@/lib/api'), getSoireeState: jest.fn() }));
const getState = getSoireeState as jest.MockedFunction<typeof getSoireeState>;

// On a phone: the Supabase client, made at import, keeps its web storage.
const platform = (os: string) => {
  Object.defineProperty(Platform, 'OS', { value: os, configurable: true, writable: true });
};
beforeAll(() => platform('ios'));
afterAll(() => platform('web'));

beforeEach(() => {
  mockPhone.clear();
  getState.mockImplementation(async (name: string) => {
    const route = server.get(name);
    if (route === 'offline') throw new TypeError('Failed to fetch');
    if (!route) throw new Error(`/api/parcours/${name}: 404`);
    return { chosen: true, routes: [route] } as unknown as ComposedSoiree;
  });
});

// Ten days from now: a week ahead and more.
const day = isoDay(new Date(Date.now() + 10 * 86_400_000));
const ids = () => [...mockPhone.keys()];

test('the instigateur is told what is left to book and to send; the passager, once joined, lives their week', async () => {
  const lea = await newAccount('instigatrice');
  const row = await keep(day);
  const page = row.page_name;
  server.set(page, evening(day));

  await scheduleNotifications();
  const booking = mockPhone.get(`${page}:resa:6`)!;
  expect(booking.content.title).toBe('J-6 · Les coulisses');
  expect(booking.content.body).toBe('2 réservations à faire pour ' + new Date(`${day}T12:00`).toLocaleDateString('fr-FR', { weekday: 'long' }) + ' : Le Comptoir, Le Comedy Club.');
  expect(booking.content.data.url).toBe(`/revelation?soiree=${page}`);
  expect(booking.trigger).toEqual({ type: 'date', date: new Date(local(day, 18, 0, -6)), channelId: 'coulisses' });
  expect(ids()).toContain(`${page}:invitation:5`);
  expect(ids().some((id) => id.startsWith(`${page}:ombre:`))).toBe(false);

  // Both booked: the reminders go, the rest stays.
  await saveBookedSteps(page, ['test:comptoir', 'test:comedy']);
  await scheduleNotifications();
  expect(ids().some((id) => id.includes(':resa:'))).toBe(false);
  expect(ids()).toContain(`${page}:depart`);

  // The passager joins: their phone tells their week, under the name the evening was kept with.
  await newAccount('passager');
  await joinEvening(row.invite_code);
  await scheduleNotifications();
  const prologue = mockPhone.get(`${page}:prologue`)!;
  expect(prologue.content.title).toBe('J-7 · Le pli scellé');
  expect(prologue.content.body).toContain('« Le Pacte du Marais » commence');
  expect(prologue.trigger.channelId).toBe('recit');
  expect(ids()).toContain(`${page}:voile:0`);
  expect(ids().filter((id) => /:(resa|invitation|ombre|etape):/.test(id))).toEqual([]);

  // The instigateur's phone: no more invitation to send, each morning's clue as the passager gets it.
  await as(lea);
  await scheduleNotifications();
  expect(ids().some((id) => id.includes(':invitation:'))).toBe(false);
  expect(ids().some((id) => id.startsWith(`${page}:ombre:`))).toBe(true);
});

test('the passager’s phone follows the reveal mode the instigateur picks', async () => {
  const lea = await newAccount('instigatrice');
  const row = await keep(day);
  const page = row.page_name;
  server.set(page, evening(day));
  const sam = await newAccount('passager');
  await joinEvening(row.invite_code);

  await scheduleNotifications();
  expect(ids()).toContain(`${page}:voile:0`);
  expect(ids()).not.toContain(`${page}:programme`);

  await as(lea);
  await saveRevealMode(row.id, 'veille');
  await as(sam);
  await scheduleNotifications();
  expect(ids()).toContain(`${page}:programme`);
  expect(ids().some((id) => id.includes(':voile:'))).toBe(false);
});

test('offline, what was scheduled stays; an evening gone from the server goes; signed out, nothing is left', async () => {
  await newAccount('instigateur');
  const row = await keep(day);
  const page = row.page_name;
  server.set(page, evening(day));
  await scheduleNotifications();
  const before = ids();
  expect(before.length).toBeGreaterThan(5);

  server.set(page, 'offline');
  await expect(scheduleNotifications()).rejects.toThrow('Failed to fetch');
  expect(ids()).toEqual(before);

  server.delete(page);
  await scheduleNotifications();
  expect(ids()).toEqual([]);

  server.set(page, evening(day));
  await scheduleNotifications();
  expect(ids().length).toBe(before.length);
  await signOut();
  await scheduleNotifications();
  expect(ids()).toEqual([]);

  mockPhone.set('x', {} as Scheduled);
  await clearNotifications();
  expect(ids()).toEqual([]);
});
