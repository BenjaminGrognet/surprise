// Push notifications, sent by the server through Firebase Cloud Messaging (surprise.push), beside those the phone
// schedules itself (lib/notifications.ts): once they are allowed, this device's FCM token is kept for the account
// signed in (public.push_tokens), again at each start (FCM renews it), and forgotten at sign-out. The browser's comes
// from Firebase's web SDK and its service worker (public/firebase-messaging-sw.js), the Android phone's from
// expo-notifications (google-services.json in the build). Not on iOS, where FCM needs Firebase's native SDK.
import { Platform } from 'react-native';

import { askNotify, notifyState, type NotifyState } from '@/lib/notifications';
import { supabase } from '@/lib/supabase';

export type PushPlatform = 'web' | 'android';

// The Firebase project's web app (console › Project settings › Your apps) and its Web Push key (Cloud Messaging):
// public values, as Supabase's anon key.
function firebaseWeb() {
  return {
    config: {
      apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY ?? '',
      projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID ?? '',
      messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_SENDER_ID ?? '',
      appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID ?? '',
    },
    vapidKey: process.env.EXPO_PUBLIC_FIREBASE_VAPID_KEY ?? '',
  };
}

// Where FCM reaches this device; null where it can't (iOS, a browser without push, Firebase not configured).
export function pushPlatform(): PushPlatform | null {
  if (Platform.OS === 'android') return 'android';
  if (Platform.OS !== 'web') return null;
  const { config, vapidKey } = firebaseWeb();
  if (!config.apiKey || !config.projectId || !vapidKey) return null;
  // Not while the static pages are rendered (Node, no service worker), nor in a browser without push.
  const browser = typeof navigator !== 'undefined' && 'serviceWorker' in navigator;
  return browser && 'PushManager' in globalThis && 'Notification' in globalThis ? 'web' : null;
}

export async function pushState(): Promise<NotifyState> {
  const platform = pushPlatform();
  if (!platform) return 'unsupported';
  if (platform === 'android') return notifyState();
  return Notification.permission === 'granted' ? 'granted' : Notification.permission === 'denied' ? 'denied' : 'ask';
}

// The service worker shows what FCM brings, the page closed (public/firebase-messaging-sw.js).
async function webToken() {
  const [{ getApps, initializeApp }, { getMessaging, getToken }] = await Promise.all([import('firebase/app'), import('firebase/messaging')]);
  const { config, vapidKey } = firebaseWeb();
  const app = getApps()[0] ?? initializeApp(config);
  await navigator.serviceWorker.register('/firebase-messaging-sw.js');
  const serviceWorkerRegistration = await navigator.serviceWorker.ready;
  return getToken(getMessaging(app), { vapidKey, serviceWorkerRegistration });
}

// The FCM token itself, on Android: a build without google-services.json has none, and throws.
async function androidToken() {
  const { getDevicePushTokenAsync } = await import('expo-notifications');
  const { data } = await getDevicePushTokenAsync();
  return typeof data === 'string' ? data : null;
}

// This device's FCM token, once notifications are allowed; null otherwise.
export async function deviceToken(): Promise<string | null> {
  const platform = pushPlatform();
  if (!platform || (await pushState()) !== 'granted') return null;
  return platform === 'web' ? webToken() : androidToken();
}

// The token kept for the account signed in, taken from any other account this device was signed in to.
export async function registerPush(): Promise<string | null> {
  const platform = pushPlatform();
  const token = await deviceToken();
  if (!platform || !token) return null;
  const { error } = await supabase.rpc('register_push_token', { token, platform });
  if (error) throw new Error(error.message);
  return token;
}

// Allowed at a touch, then registered: the browser's own question, or the phone's (lib/notifications.ts, which
// registers it once allowed).
export async function askPush(): Promise<NotifyState> {
  const platform = pushPlatform();
  if (!platform) return 'unsupported';
  if (platform === 'android') return askNotify();
  const answer = await Notification.requestPermission();
  if (answer !== 'granted') return answer === 'denied' ? 'denied' : 'ask';
  await registerPush();
  return 'granted';
}

// Before signing out: the server reaches this device no more for the account (another may sign in on it next).
export async function forgetPush() {
  const token = await deviceToken().catch(() => null);
  if (!token) return;
  const { error } = await supabase.from('push_tokens').delete().eq('token', token);
  if (error) throw new Error(error.message);
}

// Android renews its token now and then: kept again for the account.
export function onPushTokenChange() {
  if (pushPlatform() !== 'android') return () => {};
  let live = true;
  let listener: { remove: () => void } | null = null;
  import('expo-notifications').then((N) => {
    if (live) listener = N.addPushTokenListener(() => void registerPush().catch(() => {}));
  }).catch(() => {});
  return () => {
    live = false;
    listener?.remove();
  };
}
