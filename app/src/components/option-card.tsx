import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg from 'react-native-svg';

import { QUIZ_ICONS } from '@/components/quiz-icons';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// A square velvet card: gold line icon, title, a word of description; a gold border, a soft
// glow and a gold dot once chosen. `compact`: wider than tall, for a long list of answers.
export function OptionCard({
  label, desc, icon, emoji, selected, disabled, compact, onPress,
}: {
  label: string;
  desc?: string;
  icon?: string;
  emoji?: string;
  selected: boolean;
  disabled?: boolean;
  compact?: boolean;
  onPress: () => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      accessibilityRole="checkbox"
      accessibilityState={{ checked: selected, disabled }}
      style={({ pressed }) => [
        styles.card,
        compact && styles.compact,
        { backgroundColor: theme.velvet, borderColor: selected ? theme.accent : theme.accentHair },
        selected && styles.glow,
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}>
      <View style={[styles.icon, compact && styles.compactIcon]}>
        {icon && icon in QUIZ_ICONS ? (
          <Svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke={theme.accent} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            {QUIZ_ICONS[icon]}
          </Svg>
        ) : (
          <ThemedText style={styles.emoji}>{emoji}</ThemedText>
        )}
      </View>
      <ThemedText style={[styles.title, { color: theme.cream }]}>{label}</ThemedText>
      {desc ? <ThemedText style={[styles.desc, { color: theme.cream }]}>{desc}</ThemedText> : null}
      {selected ? <View style={[styles.dot, { backgroundColor: theme.accent }]} /> : null}
    </Pressable>
  );
}

export function OptionGrid({ children }: { children: ReactNode }) {
  return <View style={styles.grid}>{children}</View>;
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: Spacing.three },
  card: {
    width: '47%',
    aspectRatio: 1,
    maxHeight: 220,
    borderRadius: 16,
    borderWidth: 1,
    padding: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  compact: { aspectRatio: 1.45, padding: Spacing.two },
  glow: { boxShadow: '0 4px 10px rgba(212, 175, 55, 0.3)' },
  pressed: { opacity: 0.8 },
  disabled: { opacity: 0.35 },
  icon: { marginBottom: 12 },
  compactIcon: { marginBottom: 6 },
  emoji: { fontSize: 26, lineHeight: 32 },
  title: { fontFamily: Fonts.sansSemiBold, fontSize: 14, lineHeight: 19, textAlign: 'center' },
  desc: { fontSize: 11, lineHeight: 15, textAlign: 'center', marginTop: 4, opacity: 0.4 },
  dot: { position: 'absolute', top: 10, right: 10, width: 6, height: 6, borderRadius: 3 },
});
