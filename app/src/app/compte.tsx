import { type ReactNode, useEffect, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';
import { router } from 'expo-router';

import { PrimaryButton, PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, currentUser, signIn, signOut, signUp, type AccountProfile } from '@/lib/account';
import { supabaseConfigured } from '@/lib/supabase';

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
        <Notice>Les comptes ne sont pas encore configurés sur ce serveur.</Notice>
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

  const input = [styles.input, { backgroundColor: theme.backgroundElement, color: theme.text, borderColor: theme.line }];
  return (
    <>
      <ThemedText type="eyebrow">Bienvenue, complices</ThemedText>
      <ThemedText type="title">Les soirées qu&apos;on ne voit pas venir.</ThemedText>
      <ThemedText themeColor="textSecondary">
        SecretDate trame des soirées à deux dans Paris : l&apos;un organise, l&apos;autre ne reçoit que des indices jusqu&apos;au
        jour J. Un compte garde votre profil et vos intrigues, sur tous vos téléphones.
      </ThemedText>
      <View style={[styles.tabs, { backgroundColor: theme.backgroundElement, borderColor: theme.line }]}>
        <Tab label="Se connecter" active={tab === 'in'} onPress={() => setTab('in')} />
        <Tab label="Créer un compte" active={tab === 'up'} onPress={() => setTab('up')} />
      </View>
      <View style={styles.form}>
        <Field label="Email">
          <TextInput value={email} onChangeText={setEmail} autoComplete="email" keyboardType="email-address" autoCapitalize="none" style={input} />
        </Field>
        <Field label="Mot de passe">
          <TextInput
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete={tab === 'in' ? 'current-password' : 'new-password'}
            style={input}
          />
        </Field>
        {error ? <ThemedText themeColor="danger">{error}</ThemedText> : null}
        <PrimaryButton wide onPress={submit}>{tab === 'in' ? 'Se connecter' : 'Créer notre compte'}</PrimaryButton>
      </View>
    </>
  );
}

function LoggedIn({ email, onSignOut }: { email?: string; onSignOut: () => void }) {
  const theme = useTheme();
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
        <ThemedText themeColor="danger">Le profil n&apos;a pas pu être chargé.</ThemedText>
      </>
    );
  }
  const p = profile?.profile;
  return (
    <>
      <ThemedText type="title">Mon compte</ThemedText>
      <ThemedText themeColor="textSecondary">Connecté·e en tant que {email}.</ThemedText>
      {p ? (
        <View style={[styles.persona, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }]}>
          <ThemedText type="eyebrow">{p.names ? `${p.names}, vous êtes…` : 'Vous êtes…'}</ThemedText>
          <ThemedText type="subtitle">{p.persona.name}</ThemedText>
          <ThemedText themeColor="textSecondary">{p.persona.text}</ThemedText>
        </View>
      ) : (
        <Notice>Vous n&apos;avez pas encore de profil : faites le quiz, il sera gardé sur votre compte.</Notice>
      )}
      <View style={styles.actions}>
        <PrimaryLink href="/profil">{p ? 'Modifier notre profil' : 'Faire notre profil'}</PrimaryLink>
        <TextLink href="/historique">Nos intrigues passées →</TextLink>
      </View>
      <TextButton onPress={onSignOut}>Se déconnecter</TextButton>
    </>
  );
}

function Notice({ children }: { children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={[styles.notice, { backgroundColor: theme.backgroundElement, borderColor: theme.line }]}>
      <ThemedText themeColor="textSecondary">{children}</ThemedText>
    </View>
  );
}

function Tab({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} style={[styles.tab, active && { backgroundColor: theme.accent }]}>
      <ThemedText type="smallBold" themeColor={active ? 'onAccent' : 'textSecondary'}>{label}</ThemedText>
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

const styles = StyleSheet.create({
  tabs: { flexDirection: 'row', gap: 4, borderRadius: 999, borderWidth: 1, padding: 4, alignSelf: 'flex-start' },
  tab: { paddingVertical: Spacing.two, paddingHorizontal: Spacing.three, borderRadius: 999 },
  form: { gap: Spacing.three, maxWidth: 420 },
  field: { gap: Spacing.two },
  input: { fontFamily: Fonts.sans, fontSize: 16, padding: 14, borderRadius: 14, borderWidth: 1 },
  notice: { padding: Spacing.three, borderRadius: 16, borderWidth: 1 },
  persona: { padding: Spacing.four, borderRadius: 22, borderWidth: 1, gap: Spacing.two },
  actions: { gap: Spacing.two, alignItems: 'flex-start' },
});
