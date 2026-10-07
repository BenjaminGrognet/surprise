// The site's push notifications (Firebase Cloud Messaging, app/src/lib/push.ts): what the server sends (surprise.push)
// shown even with the page closed, and its page opened at a touch. The message is the one Android's expo-notifications
// reads: its data's title and message, and its body, a JSON of the page to open ({"url": "/historique"}).
/* global self, clients */

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

function notificationOf(payload) {
  const data = (payload && payload.data) || {};
  const notification = (payload && payload.notification) || {};
  let body = {};
  try {
    body = JSON.parse(data.body || '{}');
  } catch {
    body = {};
  }
  return {
    title: notification.title || data.title || 'Secret Date',
    options: {
      body: notification.body || data.message || '',
      icon: '/favicon.ico',
      tag: data.tag || undefined,
      data: { url: typeof body.url === 'string' && body.url.startsWith('/') ? body.url : '/' },
    },
  };
}

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = {};
  }
  const { title, options } = notificationOf(payload);
  event.waitUntil(self.registration.showNotification(title, options));
});

// The site's tab, if one is open, goes to the page; else a new one opens on it.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || '/', self.location.origin).href;
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((tabs) => {
      const tab = tabs.find((t) => t.url.startsWith(self.location.origin));
      return tab ? tab.focus().then((t) => t.navigate(url)) : clients.openWindow(url);
    }),
  );
});
