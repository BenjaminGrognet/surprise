import { Link } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { LogoSecretDate } from '@/components/logo-secretdate';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTheme } from '@/hooks/use-theme';
import { currentUser } from '@/lib/account';
import { supabaseConfigured } from '@/lib/supabase';

// Every screen's top line: the SecretDate logo (back home) and, once signed in, a pill to the account —
// "Complices connectés" once the passager joined, else an invitation to send.
export function BrandHeader() {
  const theme = useTheme();
  const { couple } = useCouple();
  const together = !!couple?.passager;
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    if (supabaseConfigured) currentUser().then((u) => setSignedIn(!!u)).catch(() => {});
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
        <Link href="/compte" asChild>
          <Pressable style={StyleSheet.flatten([styles.pill, { backgroundColor: theme.backgroundSelected }])}>
            <View style={[styles.dot, { backgroundColor: together ? theme.cream : theme.accent }]} />
            <ThemedText type="small">{together ? 'Complices connectés' : 'Inviter mon passager'}</ThemedText>
          </Pressable>
        </Link>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.two, paddingVertical: Spacing.two },
  brand: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  wordmark: { fontFamily: Fonts.headingBold, fontSize: 26, lineHeight: 34 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, borderRadius: 999, paddingVertical: 6, paddingHorizontal: 14 },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
