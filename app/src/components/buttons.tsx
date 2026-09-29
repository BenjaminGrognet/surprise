import { Link, type Href } from 'expo-router';
import { Pressable, StyleSheet } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// Mirrors a.primary / a.link in src/surprise/client.css.
export function PrimaryLink({ href, children }: { href: Href; children: string }) {
  const theme = useTheme();
  return (
    <Link href={href} asChild>
      <Pressable style={StyleSheet.flatten([styles.primary, { backgroundColor: theme.accent }])}>
        <ThemedText type="smallBold" style={{ color: theme.text }}>{children}</ThemedText>
      </Pressable>
    </Link>
  );
}

export function TextLink({ href, children }: { href: Href; children: string }) {
  return (
    <Link href={href} asChild>
      <Pressable>
        <ThemedText type="link" themeColor="textSecondary">{children}</ThemedText>
      </Pressable>
    </Link>
  );
}

// Same look as PrimaryLink/TextLink, but for in-page actions (advance a quiz step, submit a
// form) rather than navigation — a Link would remount the screen and lose local state.
export function PrimaryButton({ onPress, disabled, children }: { onPress: () => void; disabled?: boolean; children: string }) {
  const theme = useTheme();
  return (
    <Pressable disabled={disabled} onPress={onPress} style={[styles.primary, { backgroundColor: theme.accent }, disabled && styles.disabled]}>
      <ThemedText type="smallBold" style={{ color: theme.text }}>{children}</ThemedText>
    </Pressable>
  );
}

export function TextButton({ onPress, children }: { onPress: () => void; children: string }) {
  return (
    <Pressable onPress={onPress}>
      <ThemedText type="link" themeColor="textSecondary">{children}</ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  primary: {
    borderRadius: 999,
    paddingVertical: Spacing.two + 2,
    paddingHorizontal: Spacing.four,
    alignSelf: 'flex-start',
  },
  disabled: { opacity: 0.45 },
});
