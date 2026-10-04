import {
  CormorantGaramond_500Medium, CormorantGaramond_500Medium_Italic, CormorantGaramond_600SemiBold,
} from '@expo-google-fonts/cormorant-garamond';
import {
  Manrope_200ExtraLight, Manrope_300Light, Manrope_400Regular, Manrope_500Medium, Manrope_600SemiBold, Manrope_700Bold, useFonts,
} from '@expo-google-fonts/manrope';
import { DarkTheme, Stack, ThemeProvider, usePathname } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { TabBar, TabBarContext } from '@/components/tab-bar';
import { Colors } from '@/constants/theme';
import { CoupleContext } from '@/hooks/use-couple';
import { myRole, type CoupleState } from '@/lib/couple';
import { claimDevice } from '@/lib/local-store';
import { supabase, supabaseConfigured } from '@/lib/supabase';

// The navigator's own surfaces (between screens, behind a transition) in the brand's night.
const navTheme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: Colors.dark.background, card: Colors.dark.background, primary: Colors.dark.accent },
};

// Unreadable (offline…): an instigateur, the account's default.
const readCouple = () => myRole().catch((): CoupleState => ({ role: 'instigateur', userId: null }));

export default function RootLayout() {
  const [loaded] = useFonts({
    Manrope_200ExtraLight,
    Manrope_300Light,
    Manrope_400Regular,
    Manrope_500Medium,
    Manrope_600SemiBold,
    Manrope_700Bold,
    CormorantGaramond_500Medium,
    CormorantGaramond_500Medium_Italic,
    CormorantGaramond_600SemiBold,
  });
  const path = usePathname();
  // null while the stored session is read. Without accounts configured, everything stays locked.
  const [signedIn, setSignedIn] = useState<boolean | null>(supabaseConfigured ? null : false);

  // Instigateur or passager: read once signed in (null meanwhile), again after joining a couple. The first
  // read holds the app back (`booted`); later ones don't, so the navigator isn't torn down on a new sign-in.
  const [couple, setCouple] = useState<CoupleState | null>(null);
  const [booted, setBooted] = useState(false);

  useEffect(() => {
    if (!supabaseConfigured) return;
    supabase.auth.getSession().then(async ({ data }) => {
      await claimDevice(data.session?.user.id ?? null);
      setSignedIn(!!data.session);
      if (!data.session) setBooted(true); // nothing to read: the app opens on /compte
    });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      void claimDevice(session?.user.id ?? null);
      setSignedIn(!!session);
      if (!session) setCouple(null);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const refresh = useCallback(
    () => readCouple().then((state) => {
      setCouple(state);
      setBooted(true);
    }),
    [],
  );

  useEffect(() => {
    if (!signedIn) return;
    readCouple().then((state) => {
      setCouple(state);
      setBooted(true);
    });
  }, [signedIn]);

  const value = useMemo(
    () => ({ role: couple?.role ?? 'instigateur', userId: couple?.userId ?? null, refresh }),
    [couple, refresh],
  );

  if (!loaded || signedIn === null || (signedIn && !booted)) return null;
  // The floating bar, for a signed-in account; not on the invitation, where a passager is only on their way in.
  const tabBar = signedIn && path !== '/invitation';

  return (
    <CoupleContext.Provider value={value}>
      <TabBarContext.Provider value={tabBar}>
        <ThemeProvider value={navTheme}>
          <StatusBar style="light" />
          <View style={styles.root}>
            <Stack screenOptions={{ headerShown: false, title: 'Secret Date', contentStyle: { backgroundColor: Colors.dark.background } }}>
              {/* The couple signs in or creates an account before anything else. */}
              <Stack.Protected guard={signedIn}>
                <Stack.Screen name="index" />
                <Stack.Screen name="revelation" />
                <Stack.Screen name="historique" />
                <Stack.Screen name="livre" />
                {/* The profile and the evenings: the instigateur's, and the passager's once it is their turn to surprise. */}
                <Stack.Screen name="profil" />
                <Stack.Screen name="soiree" />
              </Stack.Protected>
              <Stack.Screen name="compte" />
              <Stack.Screen name="invitation" />
            </Stack>
            {tabBar ? <TabBar /> : null}
          </View>
        </ThemeProvider>
      </TabBarContext.Provider>
    </CoupleContext.Provider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.dark.background },
});
