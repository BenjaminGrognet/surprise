// The site's push notifications (Firebase Cloud Messaging, src/lib/push.ts): allowed on the account page, the
// browser's FCM token kept for the account, a push shown by the service worker even on another page, the token
// forgotten at sign-out. Google stands in: Firebase's servers answer from here, and the push subscription, which
// Chromium asks of Google's push service, is the tests' own (the e2e build's Firebase project, scripts/build-e2e.js).
// The browser's question too: not asked yet, then answered as the test grants it.
import { expect, type Page, test } from '@playwright/test';

const PASSWORD = `e2e-${Math.random().toString(36).slice(2)}`;
const email = (label: string) => `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@e2e.test`;
const FCM_TOKEN = `e2e-fcm-${Math.random().toString(36).slice(2)}`;

async function createAccount(page: Page, label: string) {
  await page.getByText('Créer un compte', { exact: true }).click();
  await page.getByLabel('Email').fill(email(label));
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByText('Créer notre compte', { exact: true }).click();
}

// Firebase's installations and FCM's registrations, answered here; what FCM was asked to register.
async function fakeGoogle(page: Page) {
  const registered: unknown[] = [];
  await page.addInitScript(() => {
    // Headless Chromium's Notification.permission stays "denied": the answer is the permission the test granted.
    const answered = () => sessionStorage.getItem('e2e-notifications') as NotificationPermission | null;
    Object.defineProperty(Notification, 'permission', { configurable: true, get: () => answered() ?? 'default' });
    Notification.requestPermission = async () => {
      const { state } = await navigator.permissions.query({ name: 'notifications' });
      sessionStorage.setItem('e2e-notifications', state === 'granted' ? 'granted' : 'denied');
      return Notification.permission;
    };
    const key = (name: string) => new Uint8Array(name === 'auth' ? 16 : 65).fill(7).buffer;
    const subscription = { endpoint: 'https://fcm.googleapis.com/fcm/send/e2e', expirationTime: null, getKey: key, unsubscribe: async () => true };
    let subscribed: typeof subscription | null = null;
    PushManager.prototype.subscribe = async () => (subscribed = subscription) as unknown as PushSubscription;
    PushManager.prototype.getSubscription = async () => subscribed as unknown as PushSubscription | null;
  });
  await page.route(/^https:\/\/[\w-]+\.googleapis\.com\//, async (route) => {
    const request = route.request();
    const cors = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors });
    const host = new URL(request.url()).host;
    if (host === 'firebaseinstallations.googleapis.com') {
      return route.fulfill({ headers: cors, json: {
        name: 'projects/424242/installations/e2e', fid: 'e2e-installation', refreshToken: 'e2e-refresh',
        authToken: { token: 'e2e-auth', expiresIn: '604800s' },
      } });
    }
    if (host === 'fcmregistrations.googleapis.com' && request.method() === 'POST') {
      registered.push(request.postDataJSON());
      return route.fulfill({ headers: cors, json: { token: FCM_TOKEN } });
    }
    return route.fulfill({ status: 404, headers: cors, json: {} });
  });
  return registered;
}

const rpc = (page: Page, name: string) =>
  page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === `/rest/v1/rpc/${name}`);

test('push notifications: allowed on the account page, shown by the service worker, forgotten at sign-out', async ({ page, context, baseURL }) => {
  const registered = await fakeGoogle(page);
  await page.goto('/');
  await createAccount(page, 'push');
  await expect(page.getByText('Bonjour, cher instigateur.')).toBeVisible();
  await page.getByRole('tab', { name: 'Mon compte', exact: true }).click();
  await expect(page.getByText('Notifications', { exact: true })).toBeVisible();
  await expect(page.getByText('Recevez les notifications de Secret Date sur cet appareil, même la page fermée.')).toBeVisible();

  // Allowed at a touch: the token FCM gives this browser, kept for the account.
  await context.grantPermissions(['notifications']);
  const keeping = rpc(page, 'register_push_token');
  await page.getByText('Activer les notifications', { exact: true }).click();
  const kept = await keeping;
  expect(kept.ok()).toBe(true);
  expect(kept.request().postDataJSON()).toEqual({ token: FCM_TOKEN, platform: 'web' });
  expect(registered).toEqual([expect.objectContaining({ web: expect.objectContaining({ endpoint: 'https://fcm.googleapis.com/fcm/send/e2e' }) })]);
  await expect(page.getByText('Activées sur cet appareil : Secret Date vous y prévient, même la page fermée.')).toBeVisible();
  const script = await page.evaluate(async () => (await navigator.serviceWorker.ready).active?.scriptURL);
  expect(script).toBe(`${baseURL}/firebase-messaging-sw.js`);

  // At the next start, the token kept again (FCM renews it now and then).
  const again = rpc(page, 'register_push_token');
  await page.goto('/historique');
  expect((await again).request().postDataJSON()).toEqual({ token: FCM_TOKEN, platform: 'web' });

  // A push as surprise.push sends it, delivered to the service worker: what it shows, and the page it opens. The
  // system's notification centre stands in (headless Chromium shows none).
  const cdp = await context.newCDPSession(page);
  const workers: { registrationId: string; scopeURL: string }[] = [];
  cdp.on('ServiceWorker.workerRegistrationUpdated', ({ registrations }) => workers.push(...registrations));
  await cdp.send('ServiceWorker.enable');
  await expect.poll(() => workers.find((w) => w.scopeURL === `${baseURL}/`)).toBeTruthy();
  const worker = context.serviceWorkers().find((w) => w.url() === `${baseURL}/firebase-messaging-sw.js`)!;
  await worker.evaluate(() => {
    const scope = self as unknown as { registration: ServiceWorkerRegistration; e2eShown: unknown[] };
    scope.e2eShown = [];
    scope.registration.showNotification = async (title, options) => void scope.e2eShown.push({ title, ...options });
  });
  await cdp.send('ServiceWorker.deliverPushMessage', {
    origin: baseURL!,
    registrationId: workers.find((w) => w.scopeURL === `${baseURL}/`)!.registrationId,
    data: JSON.stringify({
      from: '424242', priority: 'high', fcmMessageId: 'e2e-1',
      data: { title: 'Secret Date', message: 'Ceci est une notification test.', body: JSON.stringify({ url: '/historique' }) },
    }),
  });
  await expect.poll(() => worker.evaluate(() => (self as unknown as { e2eShown: unknown[] }).e2eShown)).toEqual([
    { title: 'Secret Date', body: 'Ceci est une notification test.', icon: '/favicon.ico', data: { url: '/historique' } },
  ]);

  // Signed out: the server reaches this browser no more for the account.
  await page.getByRole('tab', { name: 'Mon compte', exact: true }).click();
  const forgetting = page.waitForResponse((r) => r.request().method() === 'DELETE' && new URL(r.url()).pathname === '/rest/v1/push_tokens');
  await page.getByText('Se déconnecter', { exact: true }).click();
  const forgotten = await forgetting;
  expect(forgotten.ok()).toBe(true);
  expect(new URL(forgotten.url()).searchParams.get('token')).toBe(`eq.${FCM_TOKEN}`);
});

test('notifications refused: nothing asked of Firebase, the way to allow them said', async ({ page }) => {
  const registered = await fakeGoogle(page);
  const asked: string[] = [];
  page.on('request', (r) => {
    if (/googleapis\.com|register_push_token/.test(r.url())) asked.push(r.url());
  });
  await page.goto('/');
  await createAccount(page, 'sans-push');
  await expect(page.getByText('Bonjour, cher instigateur.')).toBeVisible();
  await page.getByRole('tab', { name: 'Mon compte', exact: true }).click();
  await page.getByText('Activer les notifications', { exact: true }).click();
  await expect(page.getByText('Refusées sur cet appareil : autorisez-les dans les réglages du navigateur ou du téléphone.')).toBeVisible();
  await expect(page.getByText('Activer les notifications', { exact: true })).toHaveCount(0);
  expect(asked).toEqual([]);
  expect(registered).toEqual([]);
});
