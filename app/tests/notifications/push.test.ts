// The server's pushes (lib/push.ts), on the local Supabase: once allowed, the device's FCM token is kept for the
// account signed in, taken from another account signed in before, never read by anyone else, forgotten at sign-out;
// the browser's through Firebase's web SDK and its service worker, the Android phone's through expo-notifications.
// The browser, Firebase and the phone are stand-ins, the accounts and their tokens real.
import { afterAll, beforeAll, beforeEach, describe, expect, jest, test } from '@jest/globals';
import { Platform } from 'react-native';

import { signIn, signOut } from '@/lib/account';
import { askPush, pushPlatform, pushState, registerPush } from '@/lib/push';
import { supabase } from '@/lib/supabase';

import { admin, newAccount } from '../comptes/helpers';

const unique = () => Math.random().toString(36).slice(2, 10);

// Firebase's web SDK: the token FCM gives this browser, and what it was asked with.
const mockWeb = { token: '', calls: [] as { vapidKey?: string; serviceWorkerRegistration?: unknown }[] };
jest.mock('firebase/app', () => ({ getApps: () => [], initializeApp: (config: object) => ({ config }) }));
jest.mock('firebase/messaging', () => ({
  getMessaging: (app: object) => ({ app }),
  getToken: async (_messaging: unknown, options: { vapidKey?: string; serviceWorkerRegistration?: unknown }) => {
    mockWeb.calls.push(options);
    return mockWeb.token;
  },
}));
// The Android phone: its FCM token, notifications allowed.
const mockAndroid = { token: '' };
jest.mock('expo-notifications', () => ({
  setNotificationHandler: () => {},
  getPermissionsAsync: async () => ({ status: 'granted', canAskAgain: true }),
  getDevicePushTokenAsync: async () => ({ type: 'android', data: mockAndroid.token }),
}));

// The browser: its permission, the answer it gives, its service worker.
const browser = { permission: 'default' as NotificationPermission, answer: 'granted' as NotificationPermission, scripts: [] as string[] };
const worker = { scope: 'http://127.0.0.1/' };
const FIREBASE = {
  EXPO_PUBLIC_FIREBASE_API_KEY: 'AIza-test',
  EXPO_PUBLIC_FIREBASE_PROJECT_ID: 'secret-date-test',
  EXPO_PUBLIC_FIREBASE_SENDER_ID: '1234',
  EXPO_PUBLIC_FIREBASE_APP_ID: '1:1234:web:abcd',
  EXPO_PUBLIC_FIREBASE_VAPID_KEY: 'BTestVapidKey',
};
const platform = (os: string) => Object.defineProperty(Platform, 'OS', { value: os, configurable: true, writable: true });

beforeAll(() => {
  Object.assign(globalThis, {
    PushManager: function PushManager() {},
    Notification: {
      get permission() {
        return browser.permission;
      },
      requestPermission: async () => (browser.permission = browser.answer),
    },
  });
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: { serviceWorker: { register: async (script: string) => browser.scripts.push(script), ready: Promise.resolve(worker) } },
  });
});
afterAll(async () => {
  await signOut();
  platform('web');
});
beforeEach(() => {
  Object.assign(process.env, FIREBASE);
  Object.assign(browser, { permission: 'default', answer: 'granted', scripts: [] });
  mockWeb.token = `fcm-web-${unique()}`;
  mockWeb.calls = [];
  platform('web');
});

// Who the server reaches with this token: the account's id and the device, or nothing.
async function kept(token: string) {
  const { data, error } = await admin.from('push_tokens').select('user_id,platform').eq('token', token);
  if (error) throw new Error(error.message);
  return data;
}

describe('the browser', () => {
  test('asked at a touch: its token kept for the account, through its service worker', async () => {
    const lea = await newAccount('push');
    expect(pushPlatform()).toBe('web');
    expect(await pushState()).toBe('ask');
    expect(await kept(mockWeb.token)).toEqual([]);

    expect(await askPush()).toBe('granted');
    expect(await pushState()).toBe('granted');
    expect(browser.scripts).toEqual(['/firebase-messaging-sw.js']);
    expect(mockWeb.calls).toEqual([{ vapidKey: 'BTestVapidKey', serviceWorkerRegistration: worker }]);
    expect(await kept(mockWeb.token)).toEqual([{ user_id: lea.id, platform: 'web' }]);
    // The account reads its own; at each start, the same token kept again (FCM renews it now and then).
    const { data } = await supabase.from('push_tokens').select('token');
    expect(data).toEqual([{ token: mockWeb.token }]);
    expect(await registerPush()).toBe(mockWeb.token);
    expect(await kept(mockWeb.token)).toHaveLength(1);
  });

  test('refused, or not yet: no token', async () => {
    await newAccount('push-non');
    browser.answer = 'denied';
    expect(await askPush()).toBe('denied');
    expect(await pushState()).toBe('denied');
    expect(await registerPush()).toBeNull();
    expect(mockWeb.calls).toEqual([]);
  });

  test('signed in to another account, the device goes with it; signed out, it is forgotten', async () => {
    const lea = await newAccount('push-lea');
    const tom = await newAccount('push-tom');
    await signIn(lea.email, lea.password);
    browser.permission = 'granted';
    await registerPush();
    // Another account on the same browser, Léa's sign-out never reached the server.
    await signIn(tom.email, tom.password);
    await registerPush();
    expect(await kept(mockWeb.token)).toEqual([{ user_id: tom.id, platform: 'web' }]);
    await signIn(lea.email, lea.password);
    expect((await supabase.from('push_tokens').select('token')).data).toEqual([]);
    // Léa can't take it back by deleting it, nor anyone signed out keep one.
    await supabase.from('push_tokens').delete().eq('token', mockWeb.token);
    expect(await kept(mockWeb.token)).toHaveLength(1);

    await signIn(tom.email, tom.password);
    await signOut();
    expect(await kept(mockWeb.token)).toEqual([]);
    await expect(registerPush()).rejects.toThrow();
    expect(await kept(mockWeb.token)).toEqual([]);
  });

  test('without a Web Push key of the project’s own, Firebase’s', async () => {
    await newAccount('push-cle');
    delete process.env.EXPO_PUBLIC_FIREBASE_VAPID_KEY;
    expect(await askPush()).toBe('granted');
    expect(mockWeb.calls).toEqual([{ serviceWorkerRegistration: worker }]);
    expect(await kept(mockWeb.token)).toHaveLength(1);
  });

  test('without Firebase configured, nothing is asked', async () => {
    delete process.env.EXPO_PUBLIC_FIREBASE_APP_ID;
    expect(pushPlatform()).toBeNull();
    expect(await pushState()).toBe('unsupported');
    expect(await askPush()).toBe('unsupported');
    expect(mockWeb.calls).toEqual([]);
  });
});

describe('the phone', () => {
  test('Android: its FCM token kept for the account, forgotten at sign-out', async () => {
    const sam = await newAccount('push-android');
    platform('android');
    mockAndroid.token = `fcm-android-${unique()}`;
    expect(pushPlatform()).toBe('android');
    expect(await registerPush()).toBe(mockAndroid.token);
    expect(await kept(mockAndroid.token)).toEqual([{ user_id: sam.id, platform: 'android' }]);
    await signOut();
    expect(await kept(mockAndroid.token)).toEqual([]);
  });

  test('iOS: FCM does not reach it, its own notifications stay', async () => {
    platform('ios');
    expect(pushPlatform()).toBeNull();
    expect(await pushState()).toBe('unsupported');
    expect(await registerPush()).toBeNull();
  });
});
