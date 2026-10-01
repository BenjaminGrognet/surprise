import { Platform, StyleSheet, Text, type TextProps } from 'react-native';

import { Fonts, ThemeColor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export type ThemedTextProps = TextProps & {
  type?: 'default' | 'title' | 'small' | 'smallBold' | 'subtitle' | 'eyebrow' | 'clue' | 'link' | 'linkPrimary' | 'code';
  themeColor?: ThemeColor;
};

export function ThemedText({ style, type = 'default', themeColor, ...rest }: ThemedTextProps) {
  const theme = useTheme();

  return (
    <Text
      style={[
        { color: theme[themeColor ?? (type === 'eyebrow' ? 'accentInk' : 'text')] },
        type === 'default' && styles.default,
        type === 'title' && styles.title,
        type === 'small' && styles.small,
        type === 'smallBold' && styles.smallBold,
        type === 'subtitle' && styles.subtitle,
        type === 'eyebrow' && styles.eyebrow,
        type === 'clue' && styles.clue,
        type === 'link' && styles.link,
        type === 'linkPrimary' && styles.linkPrimary,
        type === 'code' && styles.code,
        style,
      ]}
      {...rest}
    />
  );
}

// Custom fonts bake their weight in — setting fontWeight alongside fontFamily makes RN
// silently fall back to the system font, so weight is chosen via which font file to use.
const styles = StyleSheet.create({
  small: {
    fontFamily: Fonts.sans,
    fontSize: 14,
    lineHeight: 20,
  },
  smallBold: {
    fontFamily: Fonts.sansMedium,
    fontSize: 14,
    lineHeight: 20,
  },
  default: {
    fontFamily: Fonts.sans,
    fontSize: 16,
    lineHeight: 24,
  },
  title: {
    fontFamily: Fonts.heading,
    fontSize: 32,
    lineHeight: 40,
  },
  subtitle: {
    fontFamily: Fonts.heading,
    fontSize: 22,
    lineHeight: 30,
  },
  // Small spaced capitals in gold, above a title: "VOTRE PROCHAINE INTRIGUE".
  eyebrow: {
    fontFamily: Fonts.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 2.5,
    textTransform: 'uppercase',
  },
  // A hint for the partner to surprise: an italic serif, like a handwritten note.
  clue: {
    fontFamily: Fonts.headingItalic,
    fontSize: 17,
    lineHeight: 25,
  },
  link: {
    fontFamily: Fonts.sans,
    lineHeight: 30,
    fontSize: 14,
  },
  linkPrimary: {
    fontFamily: Fonts.sansMedium,
    lineHeight: 30,
    fontSize: 14,
  },
  code: {
    fontFamily: Fonts.mono,
    fontWeight: Platform.select({ android: 700 }) ?? 500,
    fontSize: 12,
  },
});
