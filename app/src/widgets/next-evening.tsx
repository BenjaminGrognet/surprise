// The iOS widget (expo-widgets): the next evening on the home screen and the lock screen, in the app's night, gold
// and ivory. Its layout runs in the widget's own runtime (the 'widget' directive): only SwiftUI components and
// modifiers from @expo/ui, and what lib/widget.ts gives it (WidgetCard), entry after entry of its timeline.
import { Spacer, Text, VStack } from '@expo/ui/swift-ui';
import { containerBackground, font, foregroundStyle, italic, kerning, lineLimit, widgetURL } from '@expo/ui/swift-ui/modifiers';
import { createWidget, type WidgetEnvironment } from 'expo-widgets';

import type { WidgetCard } from '@/lib/widget';

const NextEvening = (props: WidgetCard, environment: WidgetEnvironment) => {
  'widget';
  const family = environment.widgetFamily;
  if (family === 'accessoryInline') {
    return <Text modifiers={[widgetURL(props.url)]}>{props.countdown ? `${props.countdown} · ${props.title}` : props.title}</Text>;
  }
  if (family === 'accessoryRectangular') {
    return (
      <VStack alignment="leading" spacing={1} modifiers={[containerBackground('#00000000', 'widget'), widgetURL(props.url)]}>
        <Text modifiers={[font({ size: 13, weight: 'semibold' }), lineLimit(1)]}>{props.title}</Text>
        <Text modifiers={[font({ size: 12 }), lineLimit(1)]}>{props.countdown || props.line}</Text>
        <Text modifiers={[font({ size: 11 }), lineLimit(1)]}>{props.countdown ? props.line : ''}</Text>
      </VStack>
    );
  }
  const small = family === 'systemSmall';
  return (
    <VStack alignment="leading" spacing={4} modifiers={[containerBackground('#040F0A', 'widget'), widgetURL(props.url)]}>
      <Text modifiers={[font({ size: 10, weight: 'semibold' }), kerning(1.2), foregroundStyle('#8F9E91'), lineLimit(1)]}>
        {props.kicker.toUpperCase()}
      </Text>
      <Text modifiers={[font({ size: small ? 18 : 21, design: 'serif' }), italic(), foregroundStyle('#E9E5D8'), lineLimit(2)]}>
        {props.title}
      </Text>
      <Spacer />
      <Text modifiers={[font({ size: small ? 19 : 23, weight: 'bold' }), foregroundStyle('#DBC18C'), lineLimit(1)]}>{props.countdown}</Text>
      <Text modifiers={[font({ size: 12, design: 'serif' }), italic(), foregroundStyle('#E9E5D8'), lineLimit(small ? 2 : 3)]}>
        {props.line}
      </Text>
    </VStack>
  );
};

export default createWidget('ProchaineSoiree', NextEvening);
