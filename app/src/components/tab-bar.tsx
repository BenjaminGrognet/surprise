import { router, useFocusEffect, useGlobalSearchParams, usePathname, type Href } from 'expo-router';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

import { DiscoBall } from '@/components/disco-ball';
import { Icon } from '@/components/ui-icons';
import { Spacing, type PaletteName } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { usePalette, useTheme } from '@/hooks/use-theme';
import { upcomingEvenings, type EveningHistoryRow } from '@/lib/account';
import { eveningRole } from '@/lib/couple';
import { eveningDay } from '@/lib/dates';

const BAR_HEIGHT = 68;
const BAR_GAP = 12;
// What a screen keeps free at its foot so its last lines scroll clear of the bar.
export const TAB_BAR_SPACE = BAR_HEIGHT + BAR_GAP + Spacing.four;

// Whether the floating bar is shown: every screen of a signed-in account but the invitation, decided by the root layout.
export const TabBarContext = createContext(false);
export const useTabBar = () => useContext(TabBarContext);

type Item = { icon: string; label: string; href: Href | null; active: boolean; center?: boolean };

// The floating bar at the foot of every screen: home, the evenings' grimoire, the jewel in the middle — a new
// intrigue for the instigateur, the next evening's clues for the passager —, the instigateur's compass to the next
// evening (its guide on the day) or the passager's own new intrigue, and the account, where the couple's profile now
// lives. Every icon is drawn in emerald, as the home's calls; only the tab one is on is lit, as the jewel: an emerald
// disc, its icon in the night's ink, a halo under it.
export function TabBar() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const path = usePathname();
  const params = useGlobalSearchParams<{ soiree?: string }>();
  const { role, userId } = useCouple();
  const [upcoming, setUpcoming] = useState<EveningHistoryRow[]>([]);
  // The passager's key opens the next evening they are surprised by, else the next one they compose.
  const next = (role === 'passager' ? upcoming.find((e) => eveningRole(e, userId) === 'passager') : null) ?? upcoming[0] ?? null;

  // The next evening, behind the compass and the passager's jewel: looked up again on each move, one may just have
  // been kept. Past midnight, the evening under way is still the one.
  useEffect(() => {
    upcomingEvenings(eveningDay(new Date())).then(setUpcoming).catch(() => {});
  }, [role, path]);

  const evening: Href | null = next ? { pathname: '/revelation', params: { soiree: next.page_name } } : null;
  // Lit on any evening still to come: the compass leafs through them (EveningsNav).
  const onEvening = path === '/revelation' && upcoming.some((e) => params.soiree === e.page_name);
  const items: Item[] = role === 'passager'
    ? [
      { icon: 'maison', label: 'Accueil', href: '/', active: path === '/' },
      { icon: 'grimoire', label: 'Mes soirées', href: '/historique', active: path === '/historique' || path === '/livre' },
      { icon: 'cle', label: next ? 'Vos indices' : 'Pas encore de soirée', center: true, active: onEvening, href: evening },
      { icon: 'diamant', label: 'À votre tour : une nouvelle intrigue', href: '/soiree', active: path === '/soiree' },
      { icon: 'profil', label: 'Mon compte', href: '/compte', active: path === '/compte' || path === '/profil' },
    ]
    : [
      { icon: 'maison', label: 'Accueil', href: '/', active: path === '/' },
      { icon: 'grimoire', label: 'Mes soirées', href: '/historique', active: path === '/historique' || path === '/livre' },
      { icon: 'diamant', label: 'Nouvelle intrigue', href: '/soiree', center: true, active: path === '/soiree' },
      { icon: 'boussole', label: next ? 'La boussole : votre prochaine soirée' : 'Pas encore de soirée', href: evening, active: onEvening },
      { icon: 'profil', label: 'Mon compte', href: '/compte', active: path === '/compte' || path === '/profil' },
    ];

  // Home unwinds the stack back to it; any other tab comes back to its page if it is already open, else opens it.
  const go = (item: Item) => {
    if (!item.href || item.active) return;
    if (item.href === '/') router.dismissTo('/');
    else router.navigate(item.href);
  };

  return (
    <>
      {/* The page fades into the night under the bar, rather than being cut by it. */}
      <View pointerEvents="none" style={[styles.fade, { height: insets.bottom + BAR_GAP + BAR_HEIGHT + Spacing.five }]}>
        <Svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 1 1">
          <Defs>
            <LinearGradient id="tab-fade" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={theme.background} stopOpacity={0} />
              <Stop offset="0.55" stopColor={theme.background} stopOpacity={0.88} />
              <Stop offset="1" stopColor={theme.background} stopOpacity={1} />
            </LinearGradient>
          </Defs>
          <Rect width="1" height="1" fill="url(#tab-fade)" />
        </Svg>
      </View>
      <View pointerEvents="box-none" style={[styles.dock, { bottom: insets.bottom + BAR_GAP }]}>
        <View style={[styles.bar, { borderColor: theme.line, backgroundColor: theme.background }]} accessibilityRole="tablist">
          {items.map((item) => (
            <Pressable
              key={item.label}
              onPress={() => go(item)}
              disabled={!item.href}
              accessibilityRole="tab"
              accessibilityLabel={item.label}
              // aria-*, not accessibilityState: react-native-web leaves the latter out of the page.
              aria-selected={item.active}
              aria-disabled={!item.href}
              style={({ pressed }) => [
                item.center ? [styles.jewel, { borderColor: item.active ? theme.accent : theme.line }] : styles.item,
                item.active && { backgroundColor: theme.accent, boxShadow: `0 6px 18px ${theme.glow}` },
                !item.href && styles.off,
                pressed && styles.pressed,
              ]}>
              <Icon
                name={item.icon}
                size={item.center ? 24 : 22}
                strokeWidth={item.center ? 1.8 : 1.6}
                color={item.active ? theme.onAccent : theme.accent}
              />
            </Pressable>
          ))}
        </View>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  fade: { position: 'absolute', left: 0, right: 0, bottom: 0 },
  dock: { position: 'absolute', left: 0, right: 0, alignItems: 'center', paddingHorizontal: Spacing.three },
  bar: {
    width: '100%', maxWidth: 420, height: BAR_HEIGHT, borderRadius: BAR_HEIGHT / 2, borderWidth: 1,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingHorizontal: Spacing.two,
    boxShadow: '0 14px 34px rgba(0, 0, 0, 0.55)',
  },
  item: { width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center' },
  jewel: { width: 50, height: 50, borderRadius: 25, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  off: { opacity: 0.4 },
  pressed: { opacity: 0.75 },
});
