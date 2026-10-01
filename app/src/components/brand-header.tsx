import { Link } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { currentUser } from '@/lib/account';
import { supabaseConfigured } from '@/lib/supabase';

// Every screen's top line: the SecretDate wordmark (back home) and, once signed in,
// the "Complices connectés" pill that leads to the account.
export function BrandHeader() {
  const theme = useTheme();
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    if (supabaseConfigured) currentUser().then((u) => setSignedIn(!!u)).catch(() => {});
  }, []);

  return (
    <View style={styles.row}>
      <Link href="/" asChild>
        <Pressable>
          <ThemedText style={[styles.wordmark, { color: theme.accent }]}>SecretDate</ThemedText>
        </Pressable>
      </Link>
      {signedIn ? (
        <Link href="/compte" asChild>
          <Pressable style={[styles.pill, { backgroundColor: theme.backgroundSelected }]}>
            <View style={[styles.dot, { backgroundColor: theme.cream }]} />
            <ThemedText type="small">Complices connectés</ThemedText>
          </Pressable>
        </Link>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.two, paddingVertical: Spacing.two },
  wordmark: { fontFamily: Fonts.headingBold, fontSize: 26, lineHeight: 34 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, borderRadius: 999, paddingVertical: 6, paddingHorizontal: 14 },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
