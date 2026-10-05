import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { TextButton } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { SoireeRoute } from '@/lib/api';
import type { RevealMode } from '@/lib/clues';
import { formatTime, isoDay, shortDay } from '@/lib/dates';
import { passagerWeek } from '@/lib/story';

const SHOWN = 6;

// The passager's week as their phone tells it (lib/story.ts), in the instigateur's Coulisses: each notification, when
// it comes and what it says, those past marked in gold. It opens on the last one past and those to come.
export function PassagerWeek({
  route, mode, secretTitle, pageName, now,
}: { route: SoireeRoute; mode: RevealMode; secretTitle: string; pageName: string; now: number }) {
  const theme = useTheme();
  const [all, setAll] = useState(false);
  const beats = passagerWeek({ route, mode, secretTitle, pageName });
  const next = beats.findIndex((b) => b.at > now);
  const from = Math.max(0, (next === -1 ? beats.length : next) - 1);
  const shown = all ? beats : beats.slice(from, from + SHOWN);
  return (
    <View testID="semaine-passager" style={[styles.card, { borderColor: theme.line, backgroundColor: theme.backgroundElement }]}>
      <ThemedText type="eyebrow">La semaine de votre passager</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        Les notifications de son téléphone, chapitre après chapitre, et quand elles tombent.
      </ThemedText>
      {shown.map((beat) => {
        const past = beat.at <= now;
        return (
          <View key={beat.id} style={styles.row}>
            <View style={[styles.dot, { borderColor: past ? theme.gold : theme.textSecondary, backgroundColor: past ? theme.gold : 'transparent' }]} />
            <View style={styles.body}>
              <ThemedText type="small" themeColor={past ? 'textSecondary' : 'gold'}>
                {shortDay(isoDay(new Date(beat.at)))} · {formatTime(new Date(beat.at).toISOString())}
              </ThemedText>
              <ThemedText type="smallBold">{beat.title}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">{beat.body}</ThemedText>
            </View>
          </View>
        );
      })}
      {all || shown.length < beats.length ? (
        <TextButton onPress={() => setAll(!all)}>{all ? 'Réduire' : `Toute la semaine (${beats.length})`}</TextButton>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { gap: Spacing.three, padding: Spacing.four, borderRadius: Radius.card, borderWidth: 1 },
  row: { flexDirection: 'row', gap: Spacing.three, alignItems: 'flex-start' },
  dot: { width: 9, height: 9, borderRadius: 5, borderWidth: 1, marginTop: 5 },
  body: { flex: 1, gap: 2 },
});
