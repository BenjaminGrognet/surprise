import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Icon } from '@/components/ui-icons';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { Vote } from '@/lib/account';

const LABELS: Record<Vote, string> = { 1: 'On aime ce genre', [-1]: 'Pas pour nous' };
// What the vote does, said once it is cast (`said`): the couple knows it counts for the evenings to come.
const SAID: Record<Vote, string> = { 1: 'Noté : plus de soirées dans ce genre.', [-1]: 'Noté : on évitera ce genre.' };

// The instigateur's vote on a step, for the evenings to come: a thumb up lit in emerald, a thumb down in the
// danger's red; the same again withdraws it.
export function TasteVote({ vote, onVote, said }: { vote?: Vote; onVote: (vote: Vote) => void; said?: boolean }) {
  const theme = useTheme();
  const thumb = (value: Vote) => {
    const on = vote === value;
    const ink = value === 1 ? theme.accent : theme.danger;
    return (
      <Pressable
        onPress={() => onVote(value)}
        role="checkbox"
        aria-label={LABELS[value]}
        aria-checked={on}
        hitSlop={4}
        style={({ pressed }) => [
          styles.thumb,
          { borderColor: on ? ink : theme.line },
          on && { backgroundColor: value === 1 ? theme.accent : theme.dangerFaint },
          pressed && styles.pressed,
        ]}>
        <Icon name={value === 1 ? 'pouce_haut' : 'pouce_bas'} size={15} strokeWidth={1.8} color={on && value === 1 ? theme.onAccent : ink} />
      </Pressable>
    );
  };
  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        {thumb(1)}
        {thumb(-1)}
      </View>
      {said && vote ? <ThemedText type="small" themeColor="textSecondary">{SAID[vote]}</ThemedText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: Spacing.one },
  row: { flexDirection: 'row', gap: Spacing.two, alignItems: 'center' },
  thumb: { width: 30, height: 30, borderRadius: 15, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  pressed: { opacity: 0.75 },
});
