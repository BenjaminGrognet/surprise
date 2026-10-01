import { Link, type Href } from 'expo-router';
import { Pressable, StyleSheet } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// The gold call to action. `wide` spans the whole column, for a screen's one main action.
export function PrimaryLink({ href, wide, children }: { href: Href; wide?: boolean; children: string }) {
  const theme = useTheme();
  return (
    <Link href={href} asChild>
      <Pressable style={StyleSheet.flatten([styles.primary, wide && styles.wide, { backgroundColor: theme.accent }])}>
        <ThemedText style={[styles.primaryLabel, { color: theme.onAccent }]}>{children}</ThemedText>
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
export function PrimaryButton({
  onPress, disabled, wide, children,
}: { onPress: () => void; disabled?: boolean; wide?: boolean; children: string }) {
  const theme = useTheme();
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[styles.primary, wide && styles.wide, { backgroundColor: theme.accent }, disabled && styles.disabled]}>
      <ThemedText style={[styles.primaryLabel, { color: theme.onAccent }]}>{children}</ThemedText>
    </Pressable>
  );
}

// A gold outline: the secondary action next to a PrimaryButton.
export function GhostButton({ onPress, children }: { onPress: () => void; children: string }) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} style={[styles.ghost, { borderColor: theme.accentSoft }]}>
      <ThemedText type="smallBold" themeColor="accentInk">{children}</ThemedText>
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
    borderRadius: 16,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.four,
    alignSelf: 'flex-start',
    alignItems: 'center',
    shadowColor: '#D4AF37',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.22,
    shadowRadius: 22,
    elevation: 6,
  },
  wide: { alignSelf: 'stretch' },
  primaryLabel: { fontFamily: Fonts.sansSemiBold, fontSize: 16, lineHeight: 22 },
  ghost: { borderWidth: 1, borderRadius: 999, paddingVertical: Spacing.two, paddingHorizontal: Spacing.three, alignSelf: 'flex-start' },
  disabled: { opacity: 0.4 },
});
