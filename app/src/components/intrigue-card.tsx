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

// "48 : 12" with HEURES / MINUTES under, or days and hours when it's far off.
export function Countdown({ to, now }: { to: number; now: number }) {
  const theme = useTheme();
  const minutes = Math.max(0, Math.floor((to - now) / 60_000));
  const hours = Math.floor(minutes / 60);
  const [a, b, la, lb] = hours >= 100
    ? [Math.floor(hours / 24), hours % 24, 'jours', 'heures']
    : [hours, minutes % 60, 'heures', 'minutes'];
  return (
    <View style={styles.countdown} accessibilityLabel={`${a} ${la} et ${b} ${lb}`}>
      <Unit value={a} label={la} />
      <ThemedText style={[styles.colon, { color: theme.accent }]}>:</ThemedText>
      <Unit value={b} label={lb} />
    </View>
  );
}

function Unit({ value, label }: { value: number; label: string }) {
  return (
    <View style={styles.unit}>
      <ThemedText style={styles.number}>{String(value).padStart(2, '0')}</ThemedText>
      <ThemedText type="eyebrow" themeColor="textSecondary" style={styles.unitLabel}>{label}</ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  outer: { borderWidth: 1, borderRadius: 28, padding: 6 },
  inner: { borderWidth: 1, borderRadius: 22, paddingVertical: Spacing.five, paddingHorizontal: Spacing.four, gap: Spacing.four, alignItems: 'center' },
  countdown: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.three },
  unit: { alignItems: 'center', minWidth: 76, gap: Spacing.one },
  number: { fontFamily: Fonts.sansLight, fontSize: 46, lineHeight: 54 },
  colon: { fontFamily: Fonts.sansLight, fontSize: 40, lineHeight: 50 },
  unitLabel: { fontSize: 10, letterSpacing: 2 },
});
