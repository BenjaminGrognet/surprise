import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// Mirrors .option / .chips .option in src/surprise/client.css.
export function OptionButton({
  label,
  emoji,
  selected,
  disabled,
  onPress,
  pill,
}: {
  label: string;
  emoji?: string;
  selected: boolean;
  disabled?: boolean;
  onPress: () => void;
  pill?: boolean;
}) {
  const theme = useTheme();
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[
        styles.option,
        pill && styles.pill,
        { backgroundColor: selected ? theme.backgroundSelected : theme.backgroundElement },
        selected && !pill && styles.optionSelected,
        disabled && styles.disabled,
      ]}>
      {emoji ? <ThemedText style={styles.emoji}>{emoji}</ThemedText> : null}
      <ThemedText type="smallBold" style={selected ? { color: theme.accentInk } : undefined}>{label}</ThemedText>
      {selected && !pill ? (
        <View style={[styles.check, { backgroundColor: theme.accent }]}>
          <ThemedText style={styles.checkMark}>✓</ThemedText>
        </View>
      ) : null}
    </Pressable>
  );
}

export function OptionRow({ children }: { children: ReactNode }) {
  return <View style={styles.row}>{children}</View>;
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two + 4 },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    borderRadius: 20,
    padding: Spacing.three,
    minWidth: 150,
  },
  optionSelected: {
    shadowColor: '#caa15a',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.28,
    shadowRadius: 12,
    elevation: 4,
  },
  pill: { borderRadius: 999, paddingVertical: Spacing.two + 1, paddingHorizontal: Spacing.three, minWidth: 0 },
  disabled: { opacity: 0.4 },
  emoji: { fontSize: 22 },
  check: { position: 'absolute', top: 10, right: 10, width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  checkMark: { fontSize: 11, color: '#ffffff' },
});
