// The phone's own side of its notifications (lib/notifications.ts): allowing them, Android's two channels, and a touch
// on one opening its page, the one that opened the app included; none of it on the web. The phone is a stand-in.
import { afterAll, beforeEach, expect, jest, test } from '@jest/globals';
import { Platform } from 'react-native';

import { askNotify, notifyState, onNotificationOpen } from '@/lib/notifications';

type Response = { notification: { request: { content: { data?: Record<string, unknown> | null } } } };

const mockPhone = {
  answer: 'granted' as 'granted' | 'denied',
  status: 'undetermined',
  channels: [] as string[],
  last: null as Response | null,
  listeners: new Set<(response: Response) => void>(),
};
jest.mock('expo-notifications', () => ({
  setNotificationHandler: () => {},
  getPermissionsAsync: async () => ({ status: mockPhone.status, canAskAgain: mockPhone.status !== 'denied' }),
  requestPermissionsAsync: async () => ({ status: (mockPhone.status = mockPhone.answer) }),
  setNotificationChannelAsync: async (id: string) => mockPhone.channels.push(id),
  AndroidImportance: { DEFAULT: 3 },
  getLastNotificationResponse: () => mockPhone.last,
  clearLastNotificationResponse: () => {
    mockPhone.last = null;
  },
  addNotificationResponseReceivedListener: (listener: (response: Response) => void) => {
    mockPhone.listeners.add(listener);
    return { remove: () => mockPhone.listeners.delete(listener) };
  },
}));
// Allowed, the phone tells its evenings again and keeps the server's pushes: stand-ins, counted.
const mockSync = jest.fn();
jest.mock('@/lib/phone', () => ({ syncPhone: (...args: unknown[]) => mockSync(...args) }));
const mockRegister = jest.fn(async () => null);
jest.mock('@/lib/push', () => ({ registerPush: () => mockRegister() }));

const platform = (os: string) => Object.defineProperty(Platform, 'OS', { value: os, configurable: true, writable: true });
const touched = (url: unknown): Response => ({ notification: { request: { content: { data: { url } } } } });
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

beforeEach(() => {
  Object.assign(mockPhone, { answer: 'granted', status: 'undetermined', channels: [], last: null });
  mockPhone.listeners.clear();
  mockSync.mockClear();
  mockRegister.mockClear();
  platform('android');
});
afterAll(() => {
  platform('web');
});

test('allowed: its two channels on Android, the evenings told to the phone, the server’s pushes kept', async () => {
  expect(await notifyState()).toBe('ask');
  expect(await askNotify()).toBe('granted');
  expect(mockPhone.channels).toEqual(['recit', 'coulisses']);
  expect(await notifyState()).toBe('granted');
  expect(mockSync).toHaveBeenCalledWith(0);
  await settle();
  expect(mockRegister).toHaveBeenCalled();
});

test('refused: nothing told, and once refused for good, not asked again', async () => {
  mockPhone.answer = 'denied';
  expect(await askNotify()).toBe('denied');
  expect(await notifyState()).toBe('denied');
  await settle();
  expect(mockSync).not.toHaveBeenCalled();
  expect(mockRegister).not.toHaveBeenCalled();
});

test('a touch opens the page of its notification, the one that opened the app first, until the screen goes', async () => {
  mockPhone.last = touched('/revelation?soiree=soiree-ab');
  const opened: string[] = [];
  const stop = onNotificationOpen((url) => opened.push(url));
  await settle();
  // The notification that opened the app: its page, once.
  expect(opened).toEqual(['/revelation?soiree=soiree-ab']);
  expect(mockPhone.last).toBeNull();
  // One touched while the app is open; one without a page leads nowhere.
  for (const listener of mockPhone.listeners) {
    listener(touched('/livre?soiree=soiree-ab'));
    listener(touched(undefined));
  }
  expect(opened).toEqual(['/revelation?soiree=soiree-ab', '/livre?soiree=soiree-ab']);
  stop();
  expect(mockPhone.listeners.size).toBe(0);
});

test('on the web, nothing is asked nor listened to', async () => {
  platform('web');
  expect(await notifyState()).toBe('unsupported');
  expect(await askNotify()).toBe('unsupported');
  const opened: string[] = [];
  onNotificationOpen((url) => opened.push(url))();
  await settle();
  expect(mockPhone.listeners.size).toBe(0);
  expect(opened).toEqual([]);
});
