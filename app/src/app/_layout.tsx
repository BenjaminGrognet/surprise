import { Fredoka_600SemiBold, Fredoka_700Bold } from '@expo-google-fonts/fredoka';
import { SpaceGrotesk_400Regular, SpaceGrotesk_500Medium, useFonts } from '@expo-google-fonts/space-grotesk';
import { DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { useEffect, useState } from 'react';

import { supabase, supabaseConfigured } from '@/lib/supabase';

export default function RootLayout() {
  const [loaded] = useFonts({
    SpaceGrotesk_400Regular,
    SpaceGrotesk_500Medium,
    Fredoka_600SemiBold,
    Fredoka_700Bold,
  });
  // null while the stored session is read. Without accounts configured, nothing is locked.
  const [signedIn, setSignedIn] = useState<boolean | null>(supabaseConfigured ? null : true);

  useEffect(() => {
    if (!supabaseConfigured) return;
    supabase.auth.getSession().then(({ data }) => setSignedIn(!!data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, session) => setSignedIn(!!session));
    return () => data.subscription.unsubscribe();
  }, []);

  if (!loaded || signedIn === null) return null;

  return (
    <ThemeProvider value={DefaultTheme}>
      <Stack screenOptions={{ headerShown: false }}>
        {/* The couple signs in or creates an account before anything else. */}
        <Stack.Protected guard={signedIn}>
          <Stack.Screen name="index" />
          <Stack.Screen name="profil" />
          <Stack.Screen name="soiree" />
          <Stack.Screen name="historique" />
        </Stack.Protected>
        <Stack.Screen name="compte" />
      </Stack>
    </ThemeProvider>
  );
}
