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
        { borderColor: selected ? theme.accent : theme.line, backgroundColor: selected ? theme.backgroundSelected : theme.backgroundElement },
        disabled && styles.disabled,
      ]}>
      {emoji ? <ThemedText style={styles.emoji}>{emoji}</ThemedText> : null}
      <ThemedText type="smallBold">{label}</ThemedText>
    </Pressable>
  );
}

export function OptionRow({ children }: { children: ReactNode }) {
  return <View style={styles.row}>{children}</View>;
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    borderWidth: 1.5,
    borderRadius: 14,
    padding: Spacing.three,
    minWidth: 150,
  },
  pill: { borderRadius: 999, paddingVertical: Spacing.two, paddingHorizontal: Spacing.three, minWidth: 0 },
  disabled: { opacity: 0.4 },
  emoji: { fontSize: 22 },
});
