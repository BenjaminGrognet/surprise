import { Link } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { LogoSecretDate } from '@/components/logo-secretdate';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTheme } from '@/hooks/use-theme';
import { currentUser, upcomingEvening, type EveningHistoryRow } from '@/lib/account';
import { isoDay } from '@/lib/dates';
import { supabaseConfigured } from '@/lib/supabase';

// Every screen's top line: the SecretDate logo (back home) and, once signed in, a pill to the next evening's invitation and a link to the account —
// "Complices connectés" once the next evening's passager joined, else an invitation to send for it.
export function BrandHeader() {
  const theme = useTheme();
  const { role } = useCouple();
  const [signedIn, setSignedIn] = useState(false);
  const [evening, setEvening] = useState<EveningHistoryRow | null>(null);
  const together = !!evening?.passager;

  useEffect(() => {
    if (!supabaseConfigured) return;
    currentUser().then((u) => setSignedIn(!!u)).catch(() => {});
    upcomingEvening(isoDay(new Date())).then((r) => setEvening(r)).catch(() => {});
  }, []);

  return (
    <View style={styles.row}>
      <Link href="/" asChild>
        <Pressable style={styles.brand}>
          <LogoSecretDate size={34} />
          <ThemedText style={[styles.wordmark, { color: theme.accent }]}>Secret Date</ThemedText>
        </Pressable>
      </Link>
      {signedIn ? (
        <View style={styles.right}>
      {role === 'instigateur' && evening ? (
        <Link href={{ pathname: '/revelation', params: { soiree: evening.page_name, route: String(evening.route_index) } }} asChild>
          <Pressable style={StyleSheet.flatten([styles.pill, { backgroundColor: theme.backgroundSelected }])}>
            <View style={[styles.dot, { backgroundColor: together ? theme.cream : theme.accent }]} />
            <ThemedText type="small">{together ? 'Complices' : 'Inviter'}</ThemedText>
          </Pressable>
        </Link>
      ) : null}
        <Link href="/compte" asChild>
          <Pressable accessibilityLabel="Mon compte">
            <ThemedText type="small" themeColor="textSecondary">Compte</ThemedText>
          </Pressable>
        </Link>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.two, paddingVertical: Spacing.two },
  right: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three },
  brand: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  wordmark: { fontFamily: Fonts.headingBold, fontSize: 26, lineHeight: 34 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, borderRadius: 999, paddingVertical: 6, paddingHorizontal: 14 },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
