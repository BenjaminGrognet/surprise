import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

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
        pill ? styles.pill : styles.tile,
        {
          backgroundColor: selected ? theme.backgroundSelected : theme.backgroundElement,
          borderColor: selected ? theme.accent : theme.line,
        },
        disabled && styles.disabled,
      ]}>
      {emoji ? <ThemedText style={pill ? styles.emoji : styles.tileEmoji}>{emoji}</ThemedText> : null}
      <ThemedText
        type="smallBold"
        numberOfLines={pill ? 1 : undefined}
        style={[!pill && styles.tileLabel, selected ? { color: theme.accentInk } : undefined]}>
        {label}
      </ThemedText>
      {selected && !pill ? (
        <View style={[styles.check, { backgroundColor: theme.accent }]}>
          <ThemedText style={[styles.checkMark, { color: theme.onAccent }]}>✓</ThemedText>
        </View>
      ) : null}
    </Pressable>
  );
}

// A discreet line with a square gold check: the "secret options" of an evening.
export function CheckLine({
  label, emoji, checked, disabled, onPress,
}: { label: string; emoji?: string; checked: boolean; disabled?: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable disabled={disabled} onPress={onPress} style={[styles.checkLine, { borderColor: theme.line }, disabled && styles.disabled]}>
      <View style={[styles.box, { borderColor: checked ? theme.accent : theme.textSecondary, backgroundColor: checked ? theme.accent : 'transparent' }]}>
        {checked ? <ThemedText style={[styles.boxMark, { color: theme.onAccent }]}>✓</ThemedText> : null}
      </View>
      <ThemedText style={checked ? { color: theme.accentInk } : undefined}>{label}</ThemedText>
      {emoji ? <ThemedText style={styles.lineEmoji}>{emoji}</ThemedText> : null}
    </Pressable>
  );
}

export function OptionRow({ children }: { children: ReactNode }) {
  return <View style={styles.row}>{children}</View>;
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two + 4 },
  tile: {
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.one,
    borderRadius: 18,
    borderWidth: 1,
    padding: Spacing.two,
    width: 116,
    minHeight: 116,
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 999,
    borderWidth: 1,
    paddingVertical: Spacing.two + 1,
    paddingHorizontal: Spacing.three,
    gap: Spacing.two,
  },
  disabled: { opacity: 0.35 },
  emoji: { fontSize: 20 },
  tileEmoji: { fontSize: 30, lineHeight: 38 },
  tileLabel: { textAlign: 'center', fontSize: 13, lineHeight: 17 },
  check: { position: 'absolute', top: 10, right: 10, width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  checkMark: { fontSize: 11, lineHeight: 14 },
  checkLine: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, paddingVertical: Spacing.three, borderBottomWidth: 1 },
  box: { width: 20, height: 20, borderRadius: 4, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  boxMark: { fontSize: 12, lineHeight: 14 },
  lineEmoji: { marginLeft: 'auto', fontSize: 18, opacity: 0.8 },
});
