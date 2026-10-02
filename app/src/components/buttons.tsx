import { Link, type Href } from 'expo-router';
import { Pressable, StyleSheet } from 'react-native';

import { Spinner } from '@/components/spinner';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// The emerald call to action, a jewel of a pill with its halo. `wide` spans the whole column, for a screen's one main action.
export function PrimaryLink({ href, wide, children }: { href: Href; wide?: boolean; children: string }) {
  const theme = useTheme();
  return (
    <Link href={href} asChild>
      <Pressable style={StyleSheet.flatten([styles.primary, wide && styles.wide, { backgroundColor: theme.satin, boxShadow: `0 8px 22px ${theme.glow}` }])}>
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
  onPress, disabled, wide, compact, children,
}: { onPress: () => void; disabled?: boolean; wide?: boolean; compact?: boolean; children: string }) {
  const theme = useTheme();
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[
        styles.primary, wide && styles.wide, compact && styles.primaryCompact,
        { backgroundColor: theme.satin, boxShadow: disabled ? 'none' : `0 8px 22px ${theme.glow}` }, disabled && styles.disabled,
      ]}>
      <ThemedText style={[styles.primaryLabel, { color: theme.onAccent }]}>{children}</ThemedText>
    </Pressable>
  );
}

// An emerald outline: the secondary action next to a PrimaryButton.
export function GhostButton({ onPress, children }: { onPress: () => void; children: string }) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} style={[styles.ghost, { borderColor: theme.accentFaint, backgroundColor: theme.backgroundElement }]}>
      <ThemedText type="smallBold" themeColor="accentInk">{children}</ThemedText>
    </Pressable>
  );
}

export function TextButton({ onPress, children, busy }: { onPress: () => void; children: string; busy?: boolean }) {
  return (
    <Pressable onPress={busy ? undefined : onPress} style={busy ? { flexDirection: 'row', alignItems: 'center', gap: 8 } : undefined}>
      {busy ? <Spinner size={12} /> : null}
      <ThemedText type="link" themeColor="textSecondary">{children}</ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  primary: {
    borderRadius: Radius.pill,
    paddingVertical: 15,
    paddingHorizontal: Spacing.four + 4,
    alignSelf: 'flex-start',
    alignItems: 'center',
  },
  wide: { alignSelf: 'stretch' },
  primaryLabel: { fontFamily: Fonts.sansBold, fontSize: 15, lineHeight: 20, letterSpacing: 0.3 },
  primaryCompact: { paddingVertical: 12 },
  ghost: { borderWidth: 1, borderRadius: Radius.pill, paddingVertical: Spacing.two + 2, paddingHorizontal: Spacing.three + 2, alignSelf: 'flex-start' },
  disabled: { opacity: 0.4 },
});
