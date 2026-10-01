import { Inter_300Light, Inter_400Regular, Inter_500Medium, Inter_600SemiBold, useFonts } from '@expo-google-fonts/inter';
import {
  PlayfairDisplay_400Regular, PlayfairDisplay_400Regular_Italic, PlayfairDisplay_600SemiBold,
} from '@expo-google-fonts/playfair-display';
import { DarkTheme, Stack, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';

import { Colors } from '@/constants/theme';
import { supabase, supabaseConfigured } from '@/lib/supabase';

// The navigator's own surfaces (between screens, behind a transition) in the brand's night.
const navTheme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: Colors.dark.background, card: Colors.dark.background, primary: Colors.dark.accent },
};

export default function RootLayout() {
  const [loaded] = useFonts({
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

  useEffect(() => {
    if (!supabaseConfigured) return;
    supabase.auth.getSession().then(({ data }) => setSignedIn(!!data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, session) => setSignedIn(!!session));
    return () => data.subscription.unsubscribe();
  }, []);

  if (!loaded || signedIn === null) return null;

  return (
    <ThemeProvider value={navTheme}>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerShown: false, title: 'SecretDate', contentStyle: { backgroundColor: Colors.dark.background } }}>
        {/* The couple signs in or creates an account before anything else. */}
        <Stack.Protected guard={signedIn}>
          <Stack.Screen name="index" />
          <Stack.Screen name="profil" />
          <Stack.Screen name="soiree" />
          <Stack.Screen name="revelation" />
          <Stack.Screen name="historique" />
        </Stack.Protected>
        <Stack.Screen name="compte" />
      </Stack>
    </ThemeProvider>
  );
}
