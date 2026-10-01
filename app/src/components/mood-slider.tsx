import { useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const KNOB = 26;

// A horizontal slider snapping to a few stops: drag the knob or tap anywhere on the line.
// Children ignore touches so the line itself always answers, and the line keeps the gesture
// once it starts, so a vertical ScrollView around it cannot steal it.
export function MoodSlider({
  stops, value, onChange, left, right,
}: {
  stops: { label: string; emoji?: string }[];
  value: number;
  onChange: (index: number) => void;
  left: string;
  right: string;
}) {
  const theme = useTheme();
  const [width, setWidth] = useState(0);
  const origin = useRef(0); // the line's pageX, taken when a gesture starts
  const last = stops.length - 1;

  const pick = (x: number) => {
    if (!width) return;
    const index = Math.round((Math.min(Math.max(x, 0), width) / width) * last);
    if (index !== value) onChange(index);
  };

  const at = last > 0 ? (value / last) * width : 0;
  const stop = stops[value];

  return (
    <View style={styles.wrap}>
      <ThemedText type="subtitle" style={styles.current}>
        {stop.emoji ? `${stop.emoji}  ` : ''}{stop.label}
      </ThemedText>
      <View
        onStartShouldSetResponder={() => true}
        onMoveShouldSetResponder={() => true}
        onResponderTerminationRequest={() => false}
        onResponderGrant={(e) => {
          origin.current = e.nativeEvent.pageX - e.nativeEvent.locationX;
          pick(e.nativeEvent.locationX);
        }}
        onResponderMove={(e) => pick(e.nativeEvent.pageX - origin.current)}
        accessible
        accessibilityRole="adjustable"
        accessibilityLabel="Votre humeur"
        accessibilityValue={{ text: stop.label }}
        accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
        onAccessibilityAction={(e) => onChange(Math.min(last, Math.max(0, value + (e.nativeEvent.actionName === 'increment' ? 1 : -1))))}
        onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
        style={styles.hit}>
        <View pointerEvents="none" style={[styles.track, { backgroundColor: theme.line }]} />
        <View pointerEvents="none" style={[styles.fill, { width: at, backgroundColor: theme.accent }]} />
        {stops.map((s, i) => (
          <View
            key={s.label}
            pointerEvents="none"
            style={[styles.tick, { left: last > 0 ? (i / last) * width - 3 : 0, backgroundColor: i <= value ? theme.accent : theme.line }]}
          />
        ))}
        <View
          pointerEvents="none"
          style={[styles.knob, { left: at - KNOB / 2, backgroundColor: theme.cream, borderColor: theme.accent }]}
        />
      </View>
      <View style={styles.ends}>
        <ThemedText type="small" themeColor={value === 0 ? 'accentInk' : 'textSecondary'}>{left}</ThemedText>
        <ThemedText type="small" themeColor={value === last ? 'accentInk' : 'textSecondary'} style={styles.right}>{right}</ThemedText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: Spacing.two, userSelect: 'none' }, // a drag on web would otherwise select the labels
  current: { textAlign: 'center' },
  hit: { height: 44, justifyContent: 'center', marginHorizontal: KNOB / 2, cursor: 'pointer' },
  track: { position: 'absolute', left: 0, right: 0, height: 2, borderRadius: 1 },
  fill: { position: 'absolute', left: 0, height: 2, borderRadius: 1 },
  tick: { position: 'absolute', width: 6, height: 6, borderRadius: 3 },
  knob: {
    position: 'absolute', width: KNOB, height: KNOB, borderRadius: KNOB / 2, borderWidth: 2,
    shadowColor: '#D4AF37', shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.5, shadowRadius: 10, elevation: 4,
  },
  ends: { flexDirection: 'row', justifyContent: 'space-between', gap: Spacing.three },
  right: { textAlign: 'right' },
});
