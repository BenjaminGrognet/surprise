import { router } from 'expo-router';
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { DiscoFacets, NeonDiscoBall } from '@/components/disco-ball';
import { EmeraldFacets } from '@/components/emerald-facets';
import { LogoSecretDate } from '@/components/logo-secretdate';
import { OverWall, ThemedText } from '@/components/themed-text';
import { Icon } from '@/components/ui-icons';
import { Brands, Fonts, Radius, Spacing } from '@/constants/theme';
import { usePalette, useTheme } from '@/hooks/use-theme';

// The sealed invitation, cut like a membership card: a faceted emerald under a gold hairline, with its halo (a band's
// evening, Secret Squad: a disco ball's mirror tiles behind a neon tube, glowing inside and out).
// Centred by default; `align="start"` lays it out like the card itself, from the left.
export function IntrigueCard({
  children, onPress, align = 'center', label,
}: { children: ReactNode; onPress?: () => void; align?: 'center' | 'start'; label?: string }) {
  const theme = useTheme();
  const squad = usePalette() === 'squad';
  return (
    <Pressable
      disabled={!onPress}
      onPress={onPress}
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityLabel={label}
      style={({ pressed }) => [
        styles.card,
        {
          borderColor: theme.accentSoft, backgroundColor: theme.backgroundElement,
          boxShadow: squad ? `0 0 26px -4px ${theme.glow}, inset 0 0 22px -10px ${theme.glow}` : `0 24px 48px -24px ${theme.glow}`,
        },
        squad && styles.tube,
        pressed && styles.pressed,
      ]}>
      {squad ? <DiscoFacets /> : <EmeraldFacets />}
      <View style={[styles.body, align === 'start' ? styles.start : styles.centred]}>
        <OverWall.Provider value={squad}>{children}</OverWall.Provider>
      </View>
    </Pressable>
  );
}

// Back to the page before, or home when the page was opened straight from a link.
const goBack = () => (router.canGoBack() ? router.back() : router.replace('/'));

// A card's head, opening every page since there is no bar above: the emblem and the app's name like a card issuer's,
// a gold badge on the right, then its name in italics. `back` puts a way back before the emblem, on the pages one
// reaches from another.
export function CardHead({ badge, title, back }: { badge?: string; title: string; back?: boolean }) {
  const theme = useTheme();
  return (
    <View style={styles.head}>
      <View style={styles.top}>
        <View style={styles.issuer}>
          {back ? (
            <Pressable onPress={goBack} hitSlop={10} accessibilityRole="button" accessibilityLabel="Retour" style={styles.back}>
              <Icon name="retour" size={22} color={theme.text} strokeWidth={1.8} />
            </Pressable>
          ) : null}
          <CardEmblem />
          <ThemedText style={[styles.brand, { color: theme.gold }]}>{Brands[usePalette()]}</ThemedText>
        </View>
        {badge ? <Badge>{badge}</Badge> : null}
      </View>
      <ThemedText style={styles.title}>{title}</ThemedText>
    </View>
  );
}

// The top of every page, cut like the home's card: its head, a few lines in cream justified to the card's width,
// then what the page adds (a link, a countdown, a progress bar). Short lines, like verse, stay flush left (`justify={false}`).
export function PageCard({
  badge, title, text, children, onPress, label, back, justify = true,
}: {
  badge?: string; title: string; text?: string; children?: ReactNode; onPress?: () => void; label?: string; back?: boolean; justify?: boolean;
}) {
  const theme = useTheme();
  return (
    <IntrigueCard onPress={onPress} align="start" label={label}>
      <CardHead badge={badge} title={title} back={back} />
      {text ? <ThemedText style={[justify && styles.text, { color: theme.creamSoft }]}>{text}</ThemedText> : null}
      {children}
    </IntrigueCard>
  );
}

// The card's emblem, top left like an issuer's: the SecretDate monogram in a gold ring (Secret Squad's disco ball in
// neon, on the night so it lights up over the mirror wall).
export function CardEmblem() {
  const theme = useTheme();
  const squad = usePalette() === 'squad';
  return (
    <View style={[styles.emblem, { borderColor: theme.goldSoft }, squad && { backgroundColor: theme.background }]}>
      {squad ? <NeonDiscoBall size={30} /> : <LogoSecretDate size={30} round />}
    </View>
  );
}

// A gold outlined pill in spaced capitals, like a membership tier: "INSTIGATEUR", "≈ 180 € À DEUX". Secret Squad's is
// filled with its gold, in the night's ink.
export function Badge({ children }: { children: string }) {
  const theme = useTheme();
  const squad = usePalette() === 'squad';
  return (
    <View style={[styles.badge, { borderColor: theme.goldSoft }, squad && { backgroundColor: theme.gold, borderColor: theme.gold }]}>
      <ThemedText style={[styles.badgeLabel, { color: squad ? theme.background : theme.gold }]}>{children}</ThemedText>
    </View>
  );
}

// "15 J · 05 H", "05 H · 32 MIN": the card's countdown, in gold figures.
export function countdownLabel(to: number, now: number) {
  const minutes = Math.max(0, Math.floor((to - now) / 60_000));
  const hours = Math.floor(minutes / 60);
  const two = (n: number) => String(n).padStart(2, '0');
  return hours >= 100 ? `${Math.floor(hours / 24)} J · ${two(hours % 24)} H` : `${two(hours)} H · ${two(minutes % 60)} MIN`;
}

// "15 jours 05 heures": watchmaking-fine figures with their unit beside them, hours and minutes once
// it's under a hundred hours.
export function Countdown({ to, now }: { to: number; now: number }) {
  const minutes = Math.max(0, Math.floor((to - now) / 60_000));
  const hours = Math.floor(minutes / 60);
  const [a, b, la, lb] = hours >= 100
    ? [Math.floor(hours / 24), hours % 24, 'jours', 'heures']
    : [hours, minutes % 60, 'heures', 'minutes'];
  return (
    <View style={styles.countdown} accessibilityLabel={`${a} ${la} et ${b} ${lb}`}>
      <Unit value={a} label={la} />
      <Unit value={b} label={lb} />
    </View>
  );
}

function Unit({ value, label }: { value: number; label: string }) {
  const theme = useTheme();
  return (
    <View style={styles.unit}>
      <ThemedText style={styles.number}>{String(value).padStart(2, '0')}</ThemedText>
      <ThemedText style={[styles.unitLabel, { color: theme.gold }]}>{label}</ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 1, borderRadius: Radius.card, overflow: 'hidden' },
  tube: { borderWidth: 1.5 },
  pressed: { opacity: 0.9 },
  body: { padding: Spacing.four - 2, gap: Spacing.two },
  centred: { alignItems: 'center' },
  start: { alignItems: 'stretch' },
  head: { gap: Spacing.three },
  top: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: Spacing.two },
  issuer: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  back: { marginLeft: -Spacing.one, marginRight: -Spacing.one },
  text: { textAlign: 'justify' },
  brand: { fontFamily: Fonts.headingBold, fontSize: 20, lineHeight: 24, letterSpacing: 0.4 },
  title: { fontFamily: Fonts.headingItalic, fontSize: 32, lineHeight: 37 },
  emblem: { borderWidth: 1, borderRadius: 18, padding: 2 },
  badge: { borderWidth: 1, borderRadius: Radius.pill, paddingVertical: 5, paddingHorizontal: 13 },
  badgeLabel: { fontFamily: Fonts.sansBold, fontSize: 10, lineHeight: 13, letterSpacing: 2, textTransform: 'uppercase' },
  countdown: { flexDirection: 'row', alignItems: 'baseline', gap: Spacing.four },
  unit: { flexDirection: 'row', alignItems: 'baseline', gap: Spacing.two },
  number: { fontFamily: Fonts.sansThin, fontSize: 50, lineHeight: 58, letterSpacing: 1 },
  unitLabel: { fontFamily: Fonts.sansSemiBold, fontSize: 11, lineHeight: 14, letterSpacing: 2, textTransform: 'uppercase' },
});
