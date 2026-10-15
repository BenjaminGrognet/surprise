import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { Complicity } from '@/lib/complicity';

// The complicity gauge (lib/complicity.ts): its level in gold italics, its points, a thin line to the next level and
// what that one unlocks. On the home, a touch opens « Mon couple » (`onPress`).
export function Gauge({ gauge, onPress }: { gauge: Complicity; onPress?: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityLabel={onPress ? `Niveau de complicité : ${gauge.name}. Ouvrir Mon couple` : undefined}
      testID="jauge"
      style={({ pressed }) => [styles.gauge, { backgroundColor: theme.backgroundElement, borderColor: theme.line }, pressed && styles.pressed]}>
      <View style={styles.head}>
        <ThemedText type="eyebrow">Niveau de complicité</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{gauge.points} point{gauge.points > 1 ? 's' : ''}</ThemedText>
      </View>
      <ThemedText style={[styles.level, { color: theme.gold }]}>{gauge.name}</ThemedText>
      <View style={[styles.track, { backgroundColor: theme.line }]}>
        <View style={[styles.fill, { width: `${Math.max(gauge.progress, 0.03) * 100}%`, backgroundColor: theme.accent }]} />
      </View>
      <ThemedText type="small" themeColor="textSecondary">
        {gauge.next
          ? `Encore ${gauge.next.left} point${gauge.next.left > 1 ? 's' : ''} pour « ${gauge.next.name} »${gauge.next.unlock ? ` : ${gauge.next.unlock}` : ''}`
          : 'Vous avez atteint le sommet de la complicité.'}
      </ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  gauge: { gap: Spacing.two, padding: Spacing.three + 2, borderRadius: Radius.tile, borderWidth: 1 },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: Spacing.two },
  level: { fontFamily: Fonts.headingItalic, fontSize: 24, lineHeight: 30 },
  track: { height: 3, borderRadius: 2, overflow: 'hidden', marginVertical: Spacing.one },
  fill: { height: '100%', borderRadius: 2 },
  pressed: { opacity: 0.8 },
});
