import { type ReactNode, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { router } from 'expo-router';

import { AuthForm } from '@/components/auth-form';
import { PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { PassagerInvite } from '@/components/passager-invite';
import { LogoSecretDate } from '@/components/logo-secretdate';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, currentUser, signOut, type AccountProfile } from '@/lib/account';
import { supabaseConfigured } from '@/lib/supabase';

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

  return <Screen bare={!user} gap={user ? undefined : Spacing.two}>{user ? <LoggedIn email={user.email} onSignOut={() => signOut().then(refresh)} /> : <LoggedOut onSignedIn={refresh} />}</Screen>;
}

function LoggedOut({ onSignedIn }: { onSignedIn: () => void }) {
  const theme = useTheme();
  return (
    <>
      <View style={styles.logoContainer}>
        <Image source={require('@/assets/images/bannieres/romantiques.jpg')} style={StyleSheet.absoluteFill} contentFit="cover" />
        <View style={[StyleSheet.absoluteFill, styles.veil]} />
        <LogoSecretDate size={64} />
        <ThemedText style={[styles.appName, { color: theme.accent }]}>Secret Date</ThemedText>
      </View>
      <ThemedText type="subtitle">Les soirées qu&apos;on ne voit pas venir.</ThemedText>
      <ThemedText type="small" themeColor="textSecondary" style={styles.justify}>
        Secret Date organise des soirées surprises pour les couples à Paris. Une personne planifie l&apos;événement tandis que
        son partenaire reçoit uniquement des indices jusqu&apos;au jour J.
      </ThemedText>
      <View style={styles.points}>
        <ThemedText type="small" themeColor="textSecondary" style={styles.justify}>
          <ThemedText type="smallBold" themeColor="textSecondary">Création de compte : </ThemedText>
          chaque partenaire possède son propre profil.
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary" style={styles.justify}>
          <ThemedText type="smallBold" themeColor="textSecondary">Invitation : </ThemedText>
          l&apos;organisateur envoie un lien secret pour intégrer son partenaire à l&apos;aventure.
        </ThemedText>
      </View>
      <AuthForm
        compact
        onSignedIn={() => {
          onSignedIn();
          router.replace('/');
        }}
      />
    </>
  );
}

function LoggedIn({ email, onSignOut }: { email?: string; onSignOut: () => void }) {
  const { role, couple } = useCouple();
  return (
    <>
      <ThemedText type="eyebrow">{role === 'passager' ? 'Passager' : 'Instigateur'}</ThemedText>
      <ThemedText type="title">Mon compte</ThemedText>
      <ThemedText themeColor="textSecondary">Connecté·e en tant que {email}.</ThemedText>
      {role === 'passager' ? (
        <Notice>
          Vous êtes le passager de {couple?.instigateur_email ?? 'votre instigateur'} : vous recevez les indices de ses intrigues,
          le reste vous sera révélé le jour J.
        </Notice>
      ) : (
        <>
          <PassagerInvite />
          <CoupleProfile />
        </>
      )}
      <TextLink href="/historique">Les Archives →</TextLink>
      <TextButton onPress={onSignOut}>Se déconnecter</TextButton>
    </>
  );
}

// The couple's profile, which only the instigateur makes (the quiz).
function CoupleProfile() {
  const theme = useTheme();
  const [profile, setProfile] = useState<AccountProfile | null | 'loading' | 'error'>('loading');

  useEffect(() => {
    accountProfile().then(setProfile).catch(() => setProfile('error'));
  }, []);

  if (profile === 'loading') return <ThemedText themeColor="textSecondary">On retrouve votre profil…</ThemedText>;
  if (profile === 'error') return <ThemedText themeColor="danger">Le profil n&apos;a pas pu être chargé.</ThemedText>;
  const p = profile?.profile;
  return (
    <>
      {p ? (
        <View style={[styles.persona, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }]}>
          <ThemedText type="eyebrow">{p.names ? `${p.names}, vous êtes…` : 'Vous êtes…'}</ThemedText>
          <ThemedText type="subtitle">{p.persona.name}</ThemedText>
          <ThemedText themeColor="textSecondary">{p.persona.text}</ThemedText>
        </View>
      ) : (
        <Notice>Vous n&apos;avez pas encore de profil : faites le quiz, il sera gardé sur votre compte.</Notice>
      )}
      <PrimaryLink href="/profil">{p ? 'Modifier notre profil' : 'Faire notre profil'}</PrimaryLink>
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

const styles = StyleSheet.create({
  logoContainer: { alignItems: 'center', justifyContent: 'center', gap: 2, height: 120, borderRadius: 16, overflow: 'hidden' },
  veil: { backgroundColor: 'rgba(8, 42, 30, 0.62)' },
  justify: { textAlign: 'justify' },
  appName: { fontFamily: Fonts.headingBold, fontSize: 26, lineHeight: 32, textAlign: 'center' },
  points: { gap: 4 },
  notice: { padding: Spacing.three, borderRadius: 16, borderWidth: 1 },
  persona: { padding: Spacing.four, borderRadius: 22, borderWidth: 1, gap: Spacing.two },
});
