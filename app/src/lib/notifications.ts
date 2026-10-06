// The phone's notifications, scheduled on the device (no server): for each evening of the last month and those to
// come, the passager's week or the instigateur's reminders (lib/story.ts), scheduled again with the widget whenever
// the account's evenings are read (lib/phone.ts). None on the web, where everything below does nothing.
import { Platform } from 'react-native';

import { syncPhone } from '@/lib/phone';
import { notificationPlan, type PlannedEvening, type StoryRole } from '@/lib/story';

const supported = () => Platform.OS !== 'web';
// Android files them apart: the passager's story, the instigateur's backstage.
const CHANNELS: Record<StoryRole, { id: string; name: string }> = {
  passager: { id: 'recit', name: 'Le récit de vos soirées' },
  instigateur: { id: 'coulisses', name: 'Les coulisses' },
};

async function lib() {
  const Notifications = await import('expo-notifications');
  Notifications.setNotificationHandler({
    handleNotification: async () => ({ shouldPlaySound: false, shouldSetBadge: false, shouldShowBanner: true, shouldShowList: true }),
  });
  return Notifications;
}

export type NotifyState = 'granted' | 'denied' | 'ask' | 'unsupported';

export async function notifyState(): Promise<NotifyState> {
  if (!supported()) return 'unsupported';
  const { getPermissionsAsync } = await lib();
  const { status, canAskAgain } = await getPermissionsAsync();
  return status === 'granted' ? 'granted' : canAskAgain ? 'ask' : 'denied';
}

// Android asks for a channel before the first notification of its kind: made again at each sync, it changes nothing.
async function channels(N: Awaited<ReturnType<typeof lib>>) {
  if (Platform.OS !== 'android') return;
  for (const channel of Object.values(CHANNELS)) {
    await N.setNotificationChannelAsync(channel.id, { name: channel.name, importance: N.AndroidImportance.DEFAULT });
  }
}

export async function askNotify(): Promise<NotifyState> {
  if (!supported()) return 'unsupported';
  const N = await lib();
  await channels(N);
  const { status } = await N.requestPermissionsAsync();
  if (status === 'granted') syncPhone(0);
  return status === 'granted' ? 'granted' : 'denied';
}

// Signed out: another account may use this phone next.
export async function clearNotifications() {
  if (!supported()) return;
  await (await lib()).cancelAllScheduledNotificationsAsync();
}

// Everything scheduled again from the account's evenings (null: signed out, nothing left), once allowed.
export async function scheduleNotifications(evenings: PlannedEvening[] | null) {
  if ((await notifyState()) !== 'granted') return;
  if (!evenings) return clearNotifications();
  const beats = notificationPlan(evenings, Date.now());
  const N = await lib();
  await channels(N);
  await N.cancelAllScheduledNotificationsAsync();
  for (const beat of beats) {
    await N.scheduleNotificationAsync({
      identifier: beat.id,
      content: { title: beat.title, body: beat.body, data: { url: beat.url } },
      trigger: { type: N.SchedulableTriggerInputTypes.DATE, date: new Date(beat.at), channelId: CHANNELS[beat.role].id },
    });
  }
}

// A touch on a notification opens its page (Beat.url), the one that opened the app included.
export function onNotificationOpen(open: (url: string) => void) {
  if (!supported()) return () => {};
  let live = true;
  let listener: { remove: () => void } | null = null;
  lib().then((N) => {
    const follow = (response: { notification: { request: { content: { data?: Record<string, unknown> | null } } } } | null) => {
      const url = response?.notification.request.content.data?.url;
      if (live && typeof url === 'string') open(url);
    };
    const last = N.getLastNotificationResponse();
    if (last) {
      N.clearLastNotificationResponse();
      follow(last);
    }
    if (live) listener = N.addNotificationResponseReceivedListener(follow);
  }).catch(() => {});
  return () => {
    live = false;
    listener?.remove();
  };
}
