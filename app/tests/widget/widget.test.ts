// The home-screen widget (lib/widget.ts): what it shows of the next evening at each moment, the timeline the phone
// plays on its own, and the Android widget drawn from it without the app.
import { afterAll, beforeAll, describe, expect, jest, test } from '@jest/globals';
import { Platform } from 'react-native';

import { formatTime } from '@/lib/dates';
import type { PlannedEvening } from '@/lib/story';
import { cardAt, NO_EVENING, showOnWidgets, widgetCard, widgetTimeline, type WidgetCard } from '@/lib/widget';
import { widgetTaskHandler } from '@/widgets/next-evening-android';

import { evening, local, SECRET } from '../notifications/fixtures';

// The phone's storage, and the Android widgets on its home screen.
const mockStorage = new Map<string, string>();
jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: {
    getItem: async (key: string) => mockStorage.get(key) ?? null,
    setItem: async (key: string, value: string) => void mockStorage.set(key, value),
  },
}));
const mockDrawn: WidgetCard[] = [];
jest.mock('react-native-android-widget', () => ({
  FlexWidget: () => null,
  TextWidget: () => null,
  requestWidgetUpdate: async ({ renderWidget }: { renderWidget: () => { props: { card: WidgetCard } } }) => {
    mockDrawn.push(renderWidget().props.card);
  },
}));

const DAY = '2026-10-16';
const route = evening(DAY);
const [dinner, comedy, bar] = route.steps;
const kept = (role: PlannedEvening['role'], fields: Partial<PlannedEvening> = {}): PlannedEvening => ({
  pageName: 'soiree-widget', route, role, mode: 'etapes', secretTitle: SECRET, booked: [], passager: true, ...fields,
});

describe('the card of the moment', () => {
  test('the countdown: days, then the day before and the day itself at the hour, then the evening under way', () => {
    const at = (offset: number, hour: number) => widgetCard([kept('passager')], local(DAY, hour, 0, offset)).countdown;
    expect(at(-5, 12)).toBe('J-5');
    expect(at(-1, 12)).toBe(`Demain · ${formatTime(route.start)}`);
    expect(at(0, 9)).toBe(`Ce soir · ${formatTime(route.start)}`);
    expect(at(0, 22)).toBe('En ce moment');
    expect(widgetCard([kept('passager')], Date.parse(route.end) + 1)).toEqual(NO_EVENING);
  });

  test('the passager holds the latest clue; once begun, nothing more to guess', () => {
    const card = widgetCard([kept('passager')], local(DAY, 12, 0, -3));
    expect(card).toMatchObject({ kicker: 'Passager · ven. 16 oct.', title: SECRET, url: 'secretdate://revelation?soiree=soiree-widget' });
    expect(card.line).toBe("Portez une touche de doré : ce soir, on s'habille un peu.");
    expect(widgetCard([kept('passager')], local(DAY, 22)).line).toBe('Le rideau est levé : belle soirée.');
  });

  test('the instigateur: the bookings left, the invitation, the latest clue sent, then on the day the next step', () => {
    const before = local(DAY, 12, 0, -3);
    expect(widgetCard([kept('instigateur')], before).line).toBe('2 réservations encore à faire.');
    const booked = { booked: [dinner.id, comedy.id] };
    expect(widgetCard([kept('instigateur', { ...booked, passager: false })], before).line).toBe('Votre passager attend son invitation.');
    expect(widgetCard([kept('instigateur', booked)], before).line).toMatch(/^Dernier indice : Portez une touche de doré/);
    expect(widgetCard([kept('instigateur', booked)], local(DAY, 9)).line).toBe(`${formatTime(dinner.start)} · ${dinner.title}`);
    expect(widgetCard([kept('instigateur', booked)], local(DAY, 21, 30)).line).toBe(`${formatTime(bar.start)} · ${bar.title}`);
    expect(widgetCard([kept('instigateur', booked)], local(DAY, 23, 30)).line).toBe('Dernière étape : rien ne presse.');
  });

  test('the nearest evening not over yet comes first', () => {
    const later = { ...kept('instigateur'), pageName: 'soiree-suivante', route: evening('2026-10-30'), secretTitle: 'Un autre secret' };
    expect(widgetCard([later, kept('passager')], local(DAY, 12, 0, -1)).title).toBe(SECRET);
    expect(widgetCard([later, kept('passager')], local(DAY, 12, 0, 1)).title).toBe('Un autre secret');
  });
});

describe('the timeline the phone plays', () => {
  const now = local(DAY, 12, 0, -3);
  const timeline = widgetTimeline([kept('passager')], now);

  test('from now, one entry per change: each morning, each clue, the curtain, and the empty card after', () => {
    expect(timeline[0]).toEqual({ at: now, card: widgetCard([kept('passager')], now) });
    timeline.slice(1).forEach((entry, i) => {
      expect(entry.at).toBeGreaterThan(timeline[i].at);
      expect(entry.card).not.toEqual(timeline[i].card);
    });
    expect(timeline.find((e) => e.card.countdown === `Demain · ${formatTime(route.start)}`)!.at).toBe(local(DAY, 0, 0, -1));
    expect(timeline.find((e) => e.card.countdown === 'En ce moment')!.at).toBe(Date.parse(route.start));
    expect(timeline[timeline.length - 1]).toEqual({ at: Date.parse(route.end), card: NO_EVENING });
  });

  test('the card due at a moment is the latest entry begun', () => {
    expect(cardAt(timeline, now + 1)).toEqual(timeline[0].card);
    expect(cardAt(timeline, local(DAY, 20))).toEqual(widgetCard([kept('passager')], local(DAY, 20)));
    expect(cardAt([], now)).toEqual(NO_EVENING);
  });
});

describe('the Android widget', () => {
  const platform = (os: string) => {
    Object.defineProperty(Platform, 'OS', { value: os, configurable: true, writable: true });
  };
  beforeAll(() => platform('android'));
  afterAll(() => platform('web'));

  test('given its timeline, it is drawn at once, then again from what the phone kept, without the app', async () => {
    await showOnWidgets([kept('passager', { route: evening('2099-06-12') })]);
    expect(mockDrawn.pop()).toMatchObject({ title: SECRET, kicker: expect.stringMatching(/^Passager · /) });

    const drawn: { props: { card: WidgetCard } }[] = [];
    const renderWidget = (element: unknown) => void drawn.push(element as { props: { card: WidgetCard } });
    const widgetInfo = { widgetName: 'ProchaineSoiree', widgetId: 1, height: 110, width: 180, screenInfo: { screenHeightDp: 800, screenWidthDp: 400, density: 3, densityDpi: 480 } };
    await widgetTaskHandler({ widgetInfo, widgetAction: 'WIDGET_UPDATE', renderWidget });
    expect(drawn[0].props.card.title).toBe(SECRET);
    await widgetTaskHandler({ widgetInfo, widgetAction: 'WIDGET_DELETED', renderWidget });
    expect(drawn).toHaveLength(1);

    await showOnWidgets(null); // signed out
    expect(mockDrawn.pop()).toEqual(NO_EVENING);
  });
});
