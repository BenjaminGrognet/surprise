import { Inter_200ExtraLight, Inter_300Light, Inter_400Regular, Inter_500Medium, Inter_600SemiBold, useFonts } from '@expo-google-fonts/inter';
import {
  PlayfairDisplay_400Regular, PlayfairDisplay_400Regular_Italic, PlayfairDisplay_600SemiBold,
} from '@expo-google-fonts/playfair-display';
import { DarkTheme, Stack, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Colors } from '@/constants/theme';
import { CoupleContext } from '@/hooks/use-couple';
import { myRole, type CoupleState } from '@/lib/couple';
import { supabase, supabaseConfigured } from '@/lib/supabase';

// The navigator's own surfaces (between screens, behind a transition) in the brand's night.
const navTheme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: Colors.dark.background, card: Colors.dark.background, primary: Colors.dark.accent },
};

// Unreadable (offline…): an instigateur, the account's default.
const readCouple = () => myRole().catch((): CoupleState => ({ role: 'instigateur' }));

export default function RootLayout() {
  const [loaded] = useFonts({
    Inter_200ExtraLight,
    Inter_300Light,
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    PlayfairDisplay_400Regular,
    PlayfairDisplay_400Regular_Italic,
    PlayfairDisplay_600SemiBold,
  });
  // null while the stored session is read. Without accounts configured, everything stays locked.
  const [signedIn, setSignedIn] = useState<boolean | null>(supabaseConfigured ? null : false);

  // Instigateur or passager: read once signed in (null meanwhile), again after joining a couple. The first
  // read holds the app back (`booted`); later ones don't, so the navigator isn't torn down on a new sign-in.
  const [couple, setCouple] = useState<CoupleState | null>(null);
  const [booted, setBooted] = useState(false);

  useEffect(() => {
    if (!supabaseConfigured) return;
    supabase.auth.getSession().then(({ data }) => {
      setSignedIn(!!data.session);
      if (!data.session) setBooted(true); // nothing to read: the app opens on /compte
    });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
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

  const value = useMemo(() => ({ role: couple?.role ?? 'instigateur', refresh }), [couple, refresh]);

  if (!loaded || signedIn === null || (signedIn && !booted)) return null;
  const instigateur = signedIn && couple?.role === 'instigateur';

  return (
    <CoupleContext.Provider value={value}>
      <ThemeProvider value={navTheme}>
        <StatusBar style="light" />
        <Stack screenOptions={{ headerShown: false, title: 'Secret Date', contentStyle: { backgroundColor: Colors.dark.background } }}>
          {/* The couple signs in or creates an account before anything else. */}
          <Stack.Protected guard={signedIn}>
            <Stack.Screen name="index" />
            <Stack.Screen name="revelation" />
            <Stack.Screen name="historique" />
            <Stack.Screen name="livre" />
            {/* The instigateur makes the profile and orders the evenings; the passager only gets the clues. */}
            <Stack.Protected guard={instigateur}>
              <Stack.Screen name="profil" />
              <Stack.Screen name="soiree" />
            </Stack.Protected>
          </Stack.Protected>
          <Stack.Screen name="compte" />
          <Stack.Screen name="invitation" />
        </Stack>
      </ThemeProvider>
    </CoupleContext.Provider>
  );
}
