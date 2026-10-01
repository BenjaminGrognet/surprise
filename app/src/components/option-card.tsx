import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg from 'react-native-svg';

import { QUIZ_ICONS } from '@/components/quiz-icons';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// A small velvet card: gold line icon on the left, title and a word of description beside it;
// a gold border, a soft glow and a gold dot once chosen. Two side by side, so a question fits on a screen.
export function OptionCard({
  label, desc, icon, emoji, selected, disabled, onPress,
}: {
  label: string;
  desc?: string;
  icon?: string;
  emoji?: string;
  selected: boolean;
  disabled?: boolean;
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
        { backgroundColor: theme.velvet, borderColor: selected ? theme.accent : theme.accentHair },
        selected && styles.glow,
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}>
      <View style={styles.icon}>
        {icon && icon in QUIZ_ICONS ? (
          <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={theme.accent} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            {QUIZ_ICONS[icon]}
          </Svg>
        ) : (
          <ThemedText style={styles.emoji}>{emoji}</ThemedText>
        )}
      </View>
      <View style={styles.text}>
        <ThemedText style={[styles.title, { color: theme.cream }]}>{label}</ThemedText>
        {desc ? <ThemedText style={[styles.desc, { color: theme.cream }]} numberOfLines={1}>{desc}</ThemedText> : null}
      </View>
      {selected ? <View style={[styles.dot, { backgroundColor: theme.accent }]} /> : null}
    </Pressable>
  );
}

export function OptionGrid({ children }: { children: ReactNode }) {
  return <View style={styles.grid}>{children}</View>;
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: Spacing.two },
  card: {
    width: '49%',
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: Spacing.two,
    paddingLeft: Spacing.two + 2,
    paddingRight: Spacing.three,
  },
  glow: { boxShadow: '0 2px 8px rgba(217, 183, 113, 0.3)' },
  pressed: { opacity: 0.8 },
  disabled: { opacity: 0.35 },
  icon: { width: 22, alignItems: 'center' },
  emoji: { fontSize: 18, lineHeight: 22 },
  text: { flex: 1 },
  title: { fontFamily: Fonts.sansSemiBold, fontSize: 13, lineHeight: 17 },
  desc: { fontSize: 11, lineHeight: 14, marginTop: 1, opacity: 0.45 },
  dot: { position: 'absolute', top: 7, right: 7, width: 5, height: 5, borderRadius: 3 },
});
