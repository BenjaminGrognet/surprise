import { type ReactNode, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { router } from 'expo-router';

import { AuthForm } from '@/components/auth-form';
import { GhostButton, PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { PageCard } from '@/components/intrigue-card';
import { LogoSecretDate } from '@/components/logo-secretdate';
import { PersonaCard } from '@/components/persona-card';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, currentUser, signOut, deleteMyAccount, type AccountProfile } from '@/lib/account';
import { getQuiz, type QuizData } from '@/lib/api';
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
        <PageCard title="Mon compte" text="Les comptes ne sont pas encore configurés sur ce serveur." />
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

  return <Screen gap={user ? undefined : Spacing.two}>{user ? <LoggedIn email={user.email} onSignOut={() => signOut().then(refresh)} /> : <LoggedOut onSignedIn={refresh} />}</Screen>;
}

function LoggedOut({ onSignedIn }: { onSignedIn: () => void }) {
  const theme = useTheme();
  return (
    <>
      <View style={[styles.logoContainer, { borderColor: theme.accentSoft }]}>
        <Image source={require('@/assets/images/bannieres/romantiques.jpg')} style={StyleSheet.absoluteFill} contentFit="cover" />
        <View style={[StyleSheet.absoluteFill, styles.veil]} />
        <LogoSecretDate size={64} />
        <ThemedText style={[styles.appName, { color: theme.gold }]}>Secret Date</ThemedText>
      </View>
      <ThemedText type="subtitle">Ce soir, laissez-vous surprendre.</ThemedText>
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
  const { role } = useCouple();
  const who = email ? `Connecté·e en tant que ${email}.` : 'Connecté·e.';
  return (
    <>
      <PageCard
        badge={role === 'passager' ? 'Passager' : 'Instigateur'}
        title="Mon compte"
        text={role === 'passager'
          ? `${who}\nVous recevez les indices des soirées auxquelles on vous invite, le reste vous sera révélé le jour J.`
          : who}
      />
      {role === 'passager' ? null : <CoupleProfile />}
      <TextLink href="/historique">Mes soirées →</TextLink>
      <TextButton onPress={onSignOut}>Se déconnecter</TextButton>
      <DeleteAccount onDeleted={onSignOut} />
    </>
  );
}

// The couple's profile, which only the instigateur makes (the quiz), in full: it lives in the account.
function CoupleProfile() {
  const [profile, setProfile] = useState<AccountProfile | null | 'loading' | 'error'>('loading');
  const [quiz, setQuiz] = useState<QuizData | null>(null);

  useEffect(() => {
    accountProfile().then(setProfile).catch(() => setProfile('error'));
    // The quiz names the vibes and the "never"; out of reach, the card goes without.
    getQuiz().then(setQuiz).catch(() => {});
  }, []);

  return (
    <View style={styles.section}>
      <ThemedText type="eyebrow">Notre profil</ThemedText>
      {profile === 'loading' ? (
        <ThemedText themeColor="textSecondary">On retrouve votre profil…</ThemedText>
      ) : profile === 'error' ? (
        <ThemedText themeColor="danger">Le profil n&apos;a pas pu être chargé.</ThemedText>
      ) : profile ? (
        <PersonaCard profile={profile.profile} answers={profile.answers} quiz={quiz}>
          <PrimaryLink href={{ pathname: '/profil', params: { modifier: '1' } }}>Modifier notre profil</PrimaryLink>
        </PersonaCard>
      ) : (
        <>
          <Notice>Vous n&apos;avez pas encore de profil : faites le quiz, il sera gardé sur votre compte.</Notice>
          <PrimaryLink href="/profil">Faire notre profil</PrimaryLink>
        </>
      )}
    </View>
  );
}

// Deleting the account: the profile, the evenings and their books go for good; asked twice.
function DeleteAccount({ onDeleted }: { onDeleted: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const run = async () => {
    setBusy(true);
    setError('');
    try {
      await deleteMyAccount();
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };
  if (!confirm) return <TextButton onPress={() => setConfirm(true)}>Supprimer mon compte…</TextButton>;
  return (
    <>
      <Notice>Votre compte, votre profil, vos soirées et leurs souvenirs seront effacés définitivement, et vos passagers perdront leurs indices. Cette action est irréversible.</Notice>
      <View style={styles.confirmRow}>
        <TextButton onPress={() => setConfirm(false)}>Annuler</TextButton>
        <GhostButton onPress={run}>{busy ? 'Suppression…' : 'Oui, tout supprimer'}</GhostButton>
      </View>
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
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
  logoContainer: { alignItems: 'center', justifyContent: 'center', gap: 2, height: 132, borderRadius: Radius.card, borderWidth: 1, overflow: 'hidden' },
  veil: { backgroundColor: 'rgba(4, 15, 10, 0.62)' },
  justify: { textAlign: 'justify' },
  appName: { fontFamily: Fonts.headingBold, fontSize: 31, lineHeight: 36, letterSpacing: 0.4, textAlign: 'center' },
  points: { gap: 4 },
  confirmRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, marginTop: Spacing.two },
  notice: { padding: Spacing.three, borderRadius: Radius.tile, borderWidth: 1 },
  section: { gap: Spacing.three, marginVertical: Spacing.two },
});
