// What the phone shows of the account's evenings outside the app: the notifications (lib/notifications.ts) and the
// home-screen widget (lib/widget.ts). Both told again from the evenings of the last month and those to come, whenever
// the app comes back to the front or an evening changes (kept, a booking ticked, a plan B, its reveal mode, its
// passager joined). Nothing on the web.
import { Platform } from 'react-native';

import { currentUser, upcomingEvenings } from '@/lib/account';
import { getSoireeState } from '@/lib/api';
import { revealMode } from '@/lib/clues';
import { eveningRole, guests, isSquad } from '@/lib/couple';
import { isoDay } from '@/lib/dates';
import { clearNotifications, scheduleNotifications } from '@/lib/notifications';
import type { PlannedEvening } from '@/lib/story';
import { showOnWidgets } from '@/lib/widget';

// The evening after still has its morning-after and its call for the next one: three weeks.
const KEPT_DAYS = 30;

// The account's evenings as the phone tells them; null when signed out. Offline, it throws: what the phone shows stays
// rather than going for an evening that could not be read.
export async function phoneEvenings(): Promise<PlannedEvening[] | null> {
  const user = await currentUser();
  if (!user) return null;
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
      passager: guests(row, 'passager').length > 0,
      squad: isSquad(row),
    };
  }));
  return evenings.filter((e): e is PlannedEvening => !!e);
}

// The notifications and the widget told again, now.
export async function tellPhone() {
  const evenings = await phoneEvenings();
  await scheduleNotifications(evenings);
  await showOnWidgets(evenings);
}

// A burst of changes (an evening kept, then opened) makes one sync.
let timer: ReturnType<typeof setTimeout> | null = null;
export function syncPhone(delay = 1_000) {
  if (Platform.OS === 'web') return;
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    tellPhone().catch(() => {});
  }, delay);
}

// Signed out: another account may use this phone next.
export async function clearPhone() {
  await clearNotifications();
  await showOnWidgets(null);
}
