import { type ReactNode, useEffect, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';

import { PrimaryButton, PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, currentUser, signIn, signOut, signUp, type AccountProfile } from '@/lib/account';
import { supabaseConfigured } from '@/lib/supabase';

const BANNER = 'https://images.unsplash.com/photo-1671691302268-e316f81c7b3e?auto=format&fit=crop&w=1600&q=60';

type TabKey = 'in' | 'up';

export default function CompteScreen() {
  const [user, setUser] = useState<{ email?: string } | null | 'loading'>(supabaseConfigured ? 'loading' : null);

  const refresh = () => currentUser().then(setUser);
  useEffect(() => {
    if (supabaseConfigured) refresh();
  }, []);

  if (!supabaseConfigured) {
    return (
      <Screen>
        <ThemedText type="title">Mon compte</ThemedText>
        <ThemedView type="backgroundElement" style={styles.notice}>
          <ThemedText themeColor="textSecondary">Les comptes ne sont pas encore configurés sur ce serveur.</ThemedText>
        </ThemedView>
      </Screen>
    );
  }

  if (user === 'loading') {
    return (
      <Screen>
        <ThemedText themeColor="textSecondary">Chargement…</ThemedText>
      </Screen>
    );
  }

  return <Screen>{user ? <LoggedIn email={user.email} onSignOut={() => signOut().then(refresh)} /> : <LoggedOut onSignedIn={refresh} />}</Screen>;
}

function LoggedOut({ onSignedIn }: { onSignedIn: () => void }) {
  const theme = useTheme();
  const [tab, setTab] = useState<TabKey>('in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function submit() {
    setError('');
    try {
      if (tab === 'in') await signIn(email, password);
      else await signUp(email, password);
      onSignedIn();
      router.replace('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <ThemedText type="title">Mon compte</ThemedText>
      <ThemedText themeColor="textSecondary">
        Un compte garde votre profil et l&apos;historique de vos soirées, retrouvables sur n&apos;importe quel appareil.
      </ThemedText>
      <View style={[styles.tabs, { backgroundColor: theme.backgroundElement }]}>
        <Tab label="Se connecter" active={tab === 'in'} onPress={() => setTab('in')} />
        <Tab label="Créer un compte" active={tab === 'up'} onPress={() => setTab('up')} />
      </View>
      <View style={styles.form}>
        <Field label="Email">
          <TextInput
            value={email}
            onChangeText={setEmail}
            autoComplete="email"
            keyboardType="email-address"
            autoCapitalize="none"
            style={[styles.input, { backgroundColor: theme.backgroundElement, color: theme.text }]}
          />
        </Field>
        <Field label="Mot de passe">
          <TextInput
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete={tab === 'in' ? 'current-password' : 'new-password'}
            style={[styles.input, { backgroundColor: theme.backgroundElement, color: theme.text }]}
          />
        </Field>
        {error ? <ThemedText style={styles.error}>{error}</ThemedText> : null}
        <PrimaryButton onPress={submit}>{tab === 'in' ? 'Se connecter' : 'Créer notre compte'}</PrimaryButton>
      </View>
    </>
  );
}

function LoggedIn({ email, onSignOut }: { email?: string; onSignOut: () => void }) {
  const [profile, setProfile] = useState<AccountProfile | null | 'loading' | 'error'>('loading');

  useEffect(() => {
    accountProfile().then(setProfile).catch(() => setProfile('error'));
  }, []);

  if (profile === 'loading') {
    return (
      <>
        <ThemedText type="title">Mon compte</ThemedText>
        <ThemedText themeColor="textSecondary">On retrouve votre profil…</ThemedText>
      </>
    );
  }
  if (profile === 'error') {
    return (
      <>
        <ThemedText type="title">Mon compte</ThemedText>
        <ThemedText style={styles.error}>Le profil n&apos;a pas pu être chargé.</ThemedText>
      </>
    );
  }
  const p = profile?.profile;
  return (
    <>
      <ThemedText type="title">Mon compte</ThemedText>
      <ThemedText themeColor="textSecondary">Connecté·e en tant que {email}.</ThemedText>
      {p ? (
        <ThemedView type="backgroundElement" style={styles.persona}>
          <ThemedText type="small" style={styles.eyebrow}>{p.names ? `${p.names}, vous êtes…` : 'Vous êtes…'}</ThemedText>
          <ThemedText type="subtitle">{p.persona.name}</ThemedText>
          <ThemedText>{p.persona.text}</ThemedText>
        </ThemedView>
      ) : (
        <ThemedView type="backgroundElement" style={styles.notice}>
          <ThemedText themeColor="textSecondary">Vous n&apos;avez pas encore de profil : faites le quiz, il sera gardé sur votre compte.</ThemedText>
        </ThemedView>
      )}
      <View style={styles.actions}>
        <PrimaryLink href="/profil">{p ? 'Modifier notre profil' : 'Faire notre profil'}</PrimaryLink>
        <TextLink href="/historique">Voir notre historique →</TextLink>
      </View>
      <TextButton onPress={onSignOut}>Se déconnecter</TextButton>
    </>
  );
}

function Tab({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} style={[styles.tab, active && { backgroundColor: theme.background }]}>
      <ThemedText type="smallBold" style={active ? { color: theme.text } : { color: theme.textSecondary }}>{label}</ThemedText>
    </Pressable>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      {children}
    </View>
  );
}

function Screen({ children }: { children: ReactNode }) {
  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <SafeAreaView style={styles.safeArea}>
          <Image source={{ uri: BANNER }} style={styles.banner} />
          <View style={styles.badge}>
            <ThemedText type="smallBold" style={styles.badgeText}>Soirée à deux</ThemedText>
          </View>
          {children}
        </SafeAreaView>
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flexGrow: 1, alignItems: 'center' },
  safeArea: { width: '100%', maxWidth: MaxContentWidth, paddingHorizontal: Spacing.four, paddingVertical: Spacing.three, gap: Spacing.three },
  banner: { width: '100%', height: 160, borderRadius: Spacing.three },
  badge: { alignSelf: 'flex-start', paddingVertical: 6, paddingHorizontal: 14, borderRadius: 999, backgroundColor: '#caa15a' },
  badgeText: { color: '#ffffff', letterSpacing: 0.5 },
  tabs: { flexDirection: 'row', gap: 4, borderRadius: 999, padding: 4, alignSelf: 'flex-start' },
  tab: { paddingVertical: Spacing.two, paddingHorizontal: Spacing.three, borderRadius: 999 },
  form: { gap: Spacing.two + 2, maxWidth: 380 },
  field: { gap: Spacing.one },
  input: { fontSize: 16, padding: 14, borderRadius: 14 },
  error: { color: '#ff5c72' },
  notice: { padding: Spacing.three, borderRadius: 14 },
  persona: { padding: Spacing.four, borderRadius: 18, gap: Spacing.one },
  eyebrow: { textTransform: 'uppercase', letterSpacing: 1, color: '#a67c1e' },
  actions: { gap: Spacing.two, alignItems: 'flex-start' },
});
