import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg from 'react-native-svg';

import { QUIZ_ICONS } from '@/components/quiz-icons';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing, type ThemeColor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// A small tile of the night: emerald line icon on the left, title and a word of description beside it;
// an emerald border, a soft halo and an emerald dot once chosen. Two side by side, so a question fits on a screen.
// `tint`: another colour of the palette in place of the accent, outlining it at rest too (Secret Squad's secret options).
export function OptionCard({
  label, desc, icon, emoji, selected, disabled, onPress, tint,
}: {
  label: string;
  desc?: string;
  icon?: string;
  emoji?: string;
  selected: boolean;
  disabled?: boolean;
  onPress: () => void;
  tint?: ThemeColor;
}) {
  const theme = useTheme();
  const accent = theme[tint ?? 'accent'];
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      accessibilityRole="checkbox"
      // aria-*, not accessibilityState: react-native-web leaves the latter out of the page.
      aria-checked={selected}
      aria-disabled={disabled}
      style={({ pressed }) => [
        styles.card,
        !desc && styles.compact,
        { backgroundColor: theme.velvet, borderColor: selected ? accent : tint ? `${accent}B3` : theme.accentHair },
        selected && { boxShadow: tint ? `0 0 18px ${accent}A6` : `0 4px 14px ${theme.glow}` },
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}>
      <View style={styles.icon}>
        {icon && icon in QUIZ_ICONS ? (
          <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={accent} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
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
      {selected ? <View style={[styles.dot, { backgroundColor: accent }]} /> : null}
    </Pressable>
  );
}

export function OptionGrid({ children }: { children: ReactNode }) {
  return <View style={styles.grid}>{children}</View>;
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: 6 },
  card: {
    width: '49%',
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    borderRadius: 16,
    borderWidth: 1,
    paddingVertical: 6,
    paddingLeft: Spacing.two + 2,
    paddingRight: Spacing.three,
  },
  compact: { minHeight: 36, paddingVertical: 4 },
  pressed: { opacity: 0.8 },
  disabled: { opacity: 0.35 },
  icon: { width: 22, alignItems: 'center' },
  emoji: { fontSize: 18, lineHeight: 22 },
  text: { flex: 1 },
  title: { fontFamily: Fonts.sansSemiBold, fontSize: 13, lineHeight: 17 },
  desc: { fontSize: 11, lineHeight: 14, marginTop: 1, opacity: 0.45 },
  dot: { position: 'absolute', top: 7, right: 7, width: 5, height: 5, borderRadius: 3 },
});
