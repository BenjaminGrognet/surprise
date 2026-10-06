// The Android widget (react-native-android-widget): the next evening on the home screen, drawn from the timeline
// lib/widget.ts gives it, kept on the phone so the widget redraws itself every half hour without the app (the task
// handler, registered in index.js).
import AsyncStorage from '@react-native-async-storage/async-storage';
import { FlexWidget, requestWidgetUpdate, TextWidget, type WidgetTaskHandler } from 'react-native-android-widget';

import { cardAt, type WidgetCard, type WidgetEntry } from '@/lib/widget';

export const WIDGET = 'ProchaineSoiree';
const KEY = 'widget-prochaine-soiree';
// The fonts given to the widget by the config plugin (app.json), named after their files.
const HEADING = 'CormorantGaramond_500Medium_Italic';
const SANS = 'Manrope_400Regular';

export function NextEveningWidget({ card }: { card: WidgetCard }) {
  return (
    <FlexWidget
      clickAction="OPEN_URI"
      clickActionData={{ uri: card.url }}
      style={{
        height: 'match_parent', width: 'match_parent', flexDirection: 'column', justifyContent: 'space-between',
        padding: 14, borderRadius: 22, backgroundColor: '#040F0A', borderWidth: 1, borderColor: '#3A3527',
      }}>
      <FlexWidget style={{ flexDirection: 'column' }}>
        <TextWidget text={card.kicker.toUpperCase()} maxLines={1} style={{ fontSize: 10, fontFamily: SANS, color: '#8F9E91', letterSpacing: 0.12 }} />
        <TextWidget text={card.title} maxLines={2} truncate="END" style={{ fontSize: 20, fontFamily: HEADING, color: '#E9E5D8', marginTop: 4 }} />
      </FlexWidget>
      <FlexWidget style={{ flexDirection: 'column' }}>
        {card.countdown ? (
          <TextWidget text={card.countdown} maxLines={1} style={{ fontSize: 20, fontFamily: SANS, fontWeight: '700', color: '#DBC18C' }} />
        ) : null}
        <TextWidget text={card.line} maxLines={2} truncate="END" style={{ fontSize: 13, fontFamily: HEADING, color: '#E9E5D8', marginTop: 2 }} />
      </FlexWidget>
    </FlexWidget>
  );
}

async function storedEntries(): Promise<WidgetEntry[]> {
  const raw = await AsyncStorage.getItem(KEY);
  return raw ? (JSON.parse(raw) as WidgetEntry[]) : [];
}

// The new timeline kept, and the widgets on the home screen redrawn at once.
export async function showOnAndroid(entries: WidgetEntry[]) {
  await AsyncStorage.setItem(KEY, JSON.stringify(entries));
  await requestWidgetUpdate({ widgetName: WIDGET, renderWidget: () => <NextEveningWidget card={cardAt(entries, Date.now())} /> });
}

// Added, resized or due again (every half hour): the card of the moment from the timeline kept.
export const widgetTaskHandler: WidgetTaskHandler = async ({ widgetAction, renderWidget }) => {
  if (widgetAction === 'WIDGET_DELETED' || widgetAction === 'WIDGET_CLICK') return;
  renderWidget(<NextEveningWidget card={cardAt(await storedEntries(), Date.now())} />);
};
