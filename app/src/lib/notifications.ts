// The phone's notifications, scheduled on the device (no server): for each evening of the last month and those to
// come, the passager's week or the instigateur's reminders (lib/story.ts). All of them scheduled again whenever the
// app comes back to the front or an evening changes (kept, a booking ticked, a plan B, its reveal mode, its passager
// joined); none on the web, where everything below does nothing.
import { Platform } from 'react-native';

import { currentUser, upcomingEvenings } from '@/lib/account';
import { getSoireeState } from '@/lib/api';
import { revealMode } from '@/lib/clues';
import { eveningRole } from '@/lib/couple';
import { isoDay } from '@/lib/dates';
import { notificationPlan, type PlannedEvening, type StoryRole } from '@/lib/story';

const supported = () => Platform.OS !== 'web';
// Android files them apart: the passager's story, the instigateur's backstage.
const CHANNELS: Record<StoryRole, { id: string; name: string }> = {
  passager: { id: 'recit', name: 'Le récit de vos soirées' },
  instigateur: { id: 'coulisses', name: 'Les coulisses' },
};
// The evening after still has its morning-after and its call for the next one: three weeks.
const KEPT_DAYS = 30;

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
  if (status === 'granted') syncNotifications(0);
  return status === 'granted' ? 'granted' : 'denied';
}

// A burst of changes (an evening kept, then opened) makes one sync.
let timer: ReturnType<typeof setTimeout> | null = null;
export function syncNotifications(delay = 1_000) {
  if (!supported()) return;
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    scheduleNotifications().catch(() => {});
  }, delay);
}

// Signed out: another account may use this phone next.
export async function clearNotifications() {
  if (!supported()) return;
  await (await lib()).cancelAllScheduledNotificationsAsync();
}

// Everything scheduled again, now. Offline, nothing changes: what was scheduled stays rather than going for an evening
// that could not be read.
export async function scheduleNotifications() {
  if ((await notifyState()) !== 'granted') return;
  const user = await currentUser();
  if (!user) return clearNotifications();
  const rows = await upcomingEvenings(isoDay(new Date(Date.now() - KEPT_DAYS * 86_400_000)), 50);
  const evenings = await Promise.all(rows.map(async (row): Promise<PlannedEvening | null> => {
    const state = await getSoireeState(row.page_name).catch((e: Error) => {
      if (e.message.endsWith(': 404')) return null; // gone from the server: nothing more to tell of it
      throw e;
    });
    const route = state?.chosen ? state.routes[0] : null;
    if (!route) return null;
    return {
      pageName: row.page_name,
      route,
      role: eveningRole(row, user.id),
      mode: revealMode(row.reveal_mode),
      secretTitle: row.secret_title ?? route.secret_title,
      booked: row.booked ?? [],
      passager: !!row.passager,
    };
  }));
  const beats = notificationPlan(evenings.filter((e): e is PlannedEvening => !!e), Date.now());
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
