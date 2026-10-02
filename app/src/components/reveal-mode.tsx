import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { saveRevealMode, type EveningHistoryRow } from '@/lib/account';
import { REVEAL_MODES, revealMode, type RevealMode } from '@/lib/clues';

// The instigateur's choice of how the passager's programme lifts: step by step, the day before, or on the spot.
export function RevealModePicker({ evening, onChange }: { evening: EveningHistoryRow; onChange: () => void }) {
  const theme = useTheme();
  const [mode, setMode] = useState<RevealMode>(revealMode(evening.reveal_mode));
  const [error, setError] = useState('');

  function pick(next: RevealMode) {
    const before = mode;
    setMode(next);
    setError('');
    saveRevealMode(evening.id, next)
      .then(onChange)
      .catch((e: Error) => {
        setMode(before);
        setError(e.message);
      });
  }

  return (
    <View style={[styles.card, { borderColor: theme.accentSoft, backgroundColor: theme.backgroundElement }]}>
      <ThemedText type="eyebrow">Ce que découvre votre passager</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        Vous gardez toute la feuille de route. Les jours d’avant, votre passager reçoit des indices : l’heure, la
        tenue, le budget, l’ambiance… Puis le programme lui est dévoilé, au rythme que vous choisissez :
      </ThemedText>
      {REVEAL_MODES.map((m) => {
        const active = m.key === mode;
        return (
          <Pressable
            key={m.key}
            onPress={() => pick(m.key)}
            style={[styles.option, { borderColor: active ? theme.accent : theme.line, backgroundColor: active ? theme.backgroundSelected : 'transparent' }]}>
            <ThemedText type="smallBold" themeColor={active ? 'accentInk' : 'text'}>{m.label}</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">{m.hint}</ThemedText>
          </Pressable>
        );
      })}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { padding: Spacing.four, borderRadius: Radius.card, borderWidth: 1, gap: Spacing.three },
  option: { borderWidth: 1, borderRadius: Radius.field, padding: 14, gap: 2 },
});
