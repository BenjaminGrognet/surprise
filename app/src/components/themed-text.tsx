import { Platform, StyleSheet, Text, type TextProps } from 'react-native';

import { Fonts, ThemeColor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export type ThemedTextProps = TextProps & {
  type?: 'default' | 'title' | 'small' | 'smallBold' | 'subtitle' | 'eyebrow' | 'clue' | 'link' | 'linkPrimary' | 'code';
  themeColor?: ThemeColor;
};

// French typography: a no-break space before ? ! : ; » and after «, so a sign never wraps alone onto a line.
const keepTogether = (text: string) => text.replace(/ ([?!:;»])/g, '\u00a0$1').replace(/« /g, '«\u00a0');

export function ThemedText({ style, type = 'default', themeColor, children, ...rest }: ThemedTextProps) {
  const theme = useTheme();

  return (
    <Text
      style={[
        { color: theme[themeColor ?? (type === 'eyebrow' ? 'textSecondary' : 'text')] },
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
      {...rest}>
      {typeof children === 'string' ? keepTogether(children) : children}
    </Text>
  );
}

// Custom fonts bake their weight in — setting fontWeight alongside fontFamily makes RN
// silently fall back to the system font, so weight is chosen via which font file to use.
const styles = StyleSheet.create({
  small: {
    fontFamily: Fonts.sans,
    fontSize: 13,
    lineHeight: 19,
  },
  smallBold: {
    fontFamily: Fonts.sansSemiBold,
    fontSize: 13,
    lineHeight: 19,
  },
  default: {
    fontFamily: Fonts.sans,
    fontSize: 15,
    lineHeight: 23,
  },
  title: {
    fontFamily: Fonts.heading,
    fontSize: 34,
    lineHeight: 40,
  },
  subtitle: {
    fontFamily: Fonts.heading,
    fontSize: 25,
    lineHeight: 31,
  },
  // Small spaced capitals in sage, above a title or a row: "VOTRE PROCHAINE INTRIGUE".
  eyebrow: {
    fontFamily: Fonts.sansSemiBold,
    fontSize: 11,
    lineHeight: 15,
    letterSpacing: 2.4,
    textTransform: 'uppercase',
  },
  // A hint for the partner to surprise: an italic serif, like a handwritten note.
  clue: {
    fontFamily: Fonts.headingItalic,
    fontSize: 19,
    lineHeight: 26,
  },
  link: {
    fontFamily: Fonts.sansMedium,
    lineHeight: 30,
    fontSize: 13,
  },
  linkPrimary: {
    fontFamily: Fonts.sansSemiBold,
    lineHeight: 30,
    fontSize: 13,
  },
  code: {
    fontFamily: Fonts.mono,
    fontWeight: Platform.select({ android: 700 }) ?? 500,
    fontSize: 12,
  },
});
