import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// The sealed invitation: a card with a double gold frame, like a tarot card.
export function IntrigueCard({ children, onPress }: { children: ReactNode; onPress?: () => void }) {
  const theme = useTheme();
  return (
    <Pressable disabled={!onPress} onPress={onPress} style={[styles.outer, { borderColor: theme.accentSoft, backgroundColor: theme.backgroundElement }]}>
      <View style={[styles.inner, { borderColor: theme.line }]}>{children}</View>
    </Pressable>
  );
}

// "15 jours 05 heures": watchmaking-fine figures with their unit beside them, hours and minutes once
// it's under a hundred hours.
export function Countdown({ to, now }: { to: number; now: number }) {
  const minutes = Math.max(0, Math.floor((to - now) / 60_000));
  const hours = Math.floor(minutes / 60);
  const [a, b, la, lb] = hours >= 100
    ? [Math.floor(hours / 24), hours % 24, 'jours', 'heures']
    : [hours, minutes % 60, 'heures', 'minutes'];
  return (
    <View style={styles.countdown} accessibilityLabel={`${a} ${la} et ${b} ${lb}`}>
      <Unit value={a} label={la} />
      <Unit value={b} label={lb} />
    </View>
  );
}

function Unit({ value, label }: { value: number; label: string }) {
  return (
    <View style={styles.unit}>
      <ThemedText style={styles.number}>{String(value).padStart(2, '0')}</ThemedText>
      <ThemedText type="small" themeColor="accentInk" style={styles.unitLabel}>{label}</ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  outer: { borderWidth: 1, borderRadius: 28, padding: 6 },
  inner: { borderWidth: 1, borderRadius: 22, paddingVertical: Spacing.three, paddingHorizontal: Spacing.three, gap: Spacing.two, alignItems: 'center' },
  countdown: { flexDirection: 'row', alignItems: 'baseline', gap: Spacing.four },
  unit: { flexDirection: 'row', alignItems: 'baseline', gap: Spacing.two },
  number: { fontFamily: Fonts.sansThin, fontSize: 52, lineHeight: 60, letterSpacing: 1 },
  unitLabel: { fontFamily: Fonts.sansLight, letterSpacing: 1 },
});
