// Local notifications for the passager: one at each clue still to come, at each mystery word and at each step still
// to lift its veil, scheduled on the device (no server). Not available on the web, where everything below does nothing.
import { Platform } from 'react-native';

import type { SoireeRoute } from '@/lib/api';
import { cluesFor, revealAt, stepWords, type RevealMode } from '@/lib/clues';

const supported = Platform.OS !== 'web';
const CHANNEL = 'indices';

async function lib() {
  const Notifications = await import('expo-notifications');
  Notifications.setNotificationHandler({
    handleNotification: async () => ({ shouldPlaySound: false, shouldSetBadge: false, shouldShowBanner: true, shouldShowList: true }),
  });
  return Notifications;
}

export type NotifyState = 'granted' | 'denied' | 'ask' | 'unsupported';

export async function notifyState(): Promise<NotifyState> {
  if (!supported) return 'unsupported';
  const { getPermissionsAsync } = await lib();
  const { status, canAskAgain } = await getPermissionsAsync();
  return status === 'granted' ? 'granted' : canAskAgain ? 'ask' : 'denied';
}

export async function askNotify(): Promise<NotifyState> {
  if (!supported) return 'unsupported';
  const N = await lib();
  if (Platform.OS === 'android') {
    await N.setNotificationChannelAsync(CHANNEL, { name: 'Indices', importance: N.AndroidImportance.DEFAULT });
  }
  const { status } = await N.requestPermissionsAsync();
  return status === 'granted' ? 'granted' : 'denied';
}

// Replaces what was scheduled for this evening: the clues and steps still to come, and nothing already past.
export async function scheduleReveals(evening: string, route: SoireeRoute, mode: RevealMode, secretTitle: string) {
  if (!supported || (await notifyState()) !== 'granted') return;
  const N = await lib();
  const now = Date.now();
  const all = await N.getAllScheduledNotificationsAsync();
  await Promise.all(all.filter((n) => n.identifier.startsWith(`${evening}:`)).map((n) => N.cancelScheduledNotificationAsync(n.identifier)));

  const items: { id: string; at: number; title: string; body: string }[] = [];
  cluesFor(route, mode).forEach((c, i) => items.push({ id: `${evening}:clue:${i}`, at: c.at, title: `Nouvel indice · ${secretTitle}`, body: c.text }));
  stepWords(route, mode).forEach((w, i) => items.push({ id: `${evening}:word:${i}`, at: w.at, title: `Un mot mystère · ${secretTitle}`, body: `« ${w.word} » : une étape se laisse deviner.` }));
  [...route.steps, ...(route.night ? [route.night] : [])].forEach((step, i) => {
    if (mode === 'arrivee') return; // lifted on arrival, or at the hour: the hour is the one to announce
    items.push({ id: `${evening}:step:${i}`, at: revealAt(route, step, mode), title: `Un voile se lève · ${secretTitle}`, body: i === 0 || mode === 'veille' ? 'Une étape de votre soirée vient de se dévoiler.' : 'La prochaine étape se dévoile.' });
  });
  const seenSteps = new Set<number>(); // "la veille": one announcement for the whole programme
  for (const item of items.filter((i) => i.at > now + 5_000).sort((a, b) => a.at - b.at)) {
    if (item.id.includes(":step:")) {
      if (seenSteps.has(item.at)) continue;
      seenSteps.add(item.at);
    }
    await N.scheduleNotificationAsync({
      identifier: item.id,
      content: { title: item.title, body: item.body },
      trigger: { type: N.SchedulableTriggerInputTypes.DATE, date: new Date(item.at), channelId: CHANNEL },
    });
  }
}
