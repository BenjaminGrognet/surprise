import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Icon } from '@/components/ui-icons';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { upcomingEvenings, type EveningHistoryRow } from '@/lib/account';
import { eveningDay, shortDay } from '@/lib/dates';

// Above an evening still to come, when several are: the one before, "2 / 3" and its day, the one after.
export function EveningsNav({ soiree, route }: { soiree: string; route: number }) {
  const theme = useTheme();
  const [evenings, setEvenings] = useState<EveningHistoryRow[]>([]);

  useEffect(() => {
    upcomingEvenings(eveningDay(new Date())).then(setEvenings).catch(() => {});
  }, []);

  const at = evenings.findIndex((e) => e.page_name === soiree && e.route_index === route);
  if (evenings.length < 2 || at < 0) return null;

  const go = (e: EveningHistoryRow | undefined) =>
    e && router.setParams({ soiree: e.page_name, route: String(e.route_index) });
  const day = evenings[at].day;

  return (
    <View style={[styles.row, { borderColor: theme.line, backgroundColor: theme.backgroundElement }]}>
      <Arrow icon="retour" label="Soirée précédente" onPress={() => go(evenings[at - 1])} off={at === 0} />
      <View style={styles.middle}>
        <ThemedText type="eyebrow">Soirée {at + 1} / {evenings.length}</ThemedText>
        {day ? <ThemedText type="small" themeColor="gold">{shortDay(day)}</ThemedText> : null}
      </View>
      <Arrow icon="suite" label="Soirée suivante" onPress={() => go(evenings[at + 1])} off={at === evenings.length - 1} />
    </View>
  );
}

function Arrow({ icon, label, onPress, off }: { icon: string; label: string; onPress: () => void; off: boolean }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: off }}
      style={({ pressed }) => [styles.arrow, off && styles.off, pressed && styles.pressed]}>
      <Icon name={icon} size={22} strokeWidth={1.6} color={theme.accent} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Spacing.two, paddingVertical: Spacing.one,
  },
  middle: { alignItems: 'center', gap: 2 },
  arrow: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  off: { opacity: 0.25 },
  pressed: { opacity: 0.7 },
});
