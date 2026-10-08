import { type ReactNode, useEffect, useState } from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';

import { AuthForm } from '@/components/auth-form';
import { GhostButton, PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { PageCard } from '@/components/intrigue-card';
import { PersonaCard } from '@/components/persona-card';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Icon } from '@/components/ui-icons';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTheme } from '@/hooks/use-theme';
import {
  accountProfile, currentUser, signOut, deleteMyAccount, myTastes, saveTaste, type AccountProfile, type TasteRow,
} from '@/lib/account';
import { getQuiz, type QuizData } from '@/lib/api';
import { emailsOn, setEmails, stopEmails } from '@/lib/emails';
import type { NotifyState } from '@/lib/notifications';
import { askPush, pushState } from '@/lib/push';
import { supabaseConfigured } from '@/lib/supabase';

export default function CompteScreen() {
  const [user, setUser] = useState<{ email?: string } | null | 'loading'>(supabaseConfigured ? 'loading' : null);
  // The link at the foot of an email: no more of them, signed in or not.
  const { stop, t } = useLocalSearchParams<{ stop?: string; t?: string }>();

  const refresh = () => currentUser().then(setUser);
  useEffect(() => {
    if (supabaseConfigured) refresh();
  }, []);

  if (stop && t) {
    return (
      <Screen>
        <StopEmails address={stop} token={t} />
      </Screen>
    );
  }

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

// Signing in: the same emerald card as every page's head, then the couple's photo above the form.
function LoggedOut({ onSignedIn }: { onSignedIn: () => void }) {
  const theme = useTheme();
  return (
    <>
      <PageCard
        badge="Accès privé"
        title="Laissez la routine derrière vous."
        text={
          'Secret Date imagine des soirées surprises à Paris pour celles et ceux qui aiment ne pas savoir ce qui les attend.\n\n' +
          'D’un côté, l’Instigateur : celui qui choisit, orchestre et garde le secret.\n' +
          'De l’autre, son invité·e : une aventure à découvrir, indice après indice, jusqu’au jour J.\n\n' +
          'Deux espaces, une même aventure — chacun découvre l’expérience de son côté.'
        }
      />
      <View style={[styles.photo, { borderColor: theme.line }]}>
        <Image source={require('@/assets/images/bannieres/romantiques.jpg')} style={StyleSheet.absoluteFill} contentFit="cover" />
        <View style={[StyleSheet.absoluteFill, styles.veil]} />
        <ThemedText style={[styles.motto, { color: theme.gold }]}>Le mystère commence.</ThemedText>
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
          ? `${who}\nVous recevez les indices des soirées auxquelles on vous invite, le reste vous sera révélé le jour J. À votre tour, vous pouvez en tramer une : votre profil s'y appliquera.`
          : who}
      />
      <CoupleProfile />
      <CoupleTastes />
      <PushNotifications />
      <EmailChoice />
      <TextLink href="/historique">Mes soirées →</TextLink>
      <ThemedText type="small" themeColor="textSecondary">
        Certains liens « Réserver » mènent aux sites partenaires de Secret Date : une réservation peut nous rapporter une
        commission, sans rien changer à votre prix.
      </ThemedText>
      <TextButton onPress={onSignOut}>Se déconnecter</TextButton>
      <DeleteAccount onDeleted={onSignOut} />
    </>
  );
}

// The couple's profile, made by whoever composes the evenings (the quiz), in full: it lives in the account.
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

const TASTES_SHOWN = 8;

// The votes cast on steps, the latest first: the kinds of outing the evenings to come favour or leave out. One
// withdrawn at a touch, as a « pas pour nous » left out a whole kind.
function CoupleTastes() {
  const theme = useTheme();
  const [rows, setRows] = useState<TasteRow[] | null>(null);
  const [all, setAll] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    myTastes().then(setRows).catch(() => setRows([]));
  }, []);

  if (rows === null) return null;
  const withdraw = (row: TasteRow) => {
    setError('');
    saveTaste({ id: row.activity_id, title: row.title }, null)
      .then(() => setRows((rows) => (rows ?? []).filter((r) => r.activity_id !== row.activity_id)))
      .catch((e: Error) => setError(e.message));
  };
  const shown = all ? rows : rows.slice(0, TASTES_SHOWN);
  return (
    <View style={styles.section}>
      <ThemedText type="eyebrow">Nos goûts</ThemedText>
      {rows.length === 0 ? (
        <Notice>Aucun vote pour l&apos;instant : sur chaque étape d&apos;une soirée, un pouce levé ou baissé nous dit si son genre vous plaît.</Notice>
      ) : (
        <View testID="nos-gouts" style={[styles.tastes, { backgroundColor: theme.backgroundElement, borderColor: theme.line }]}>
          {shown.map((row) => (
            <View key={row.activity_id} style={styles.taste}>
              <Icon
                name={row.vote === 1 ? 'pouce_haut' : 'pouce_bas'}
                size={16}
                strokeWidth={1.8}
                color={row.vote === 1 ? theme.accent : theme.danger}
              />
              <ThemedText type="small" style={styles.tasteTitle} numberOfLines={1}>{row.title || 'Une étape'}</ThemedText>
              <TextButton onPress={() => withdraw(row)}>Retirer</TextButton>
            </View>
          ))}
          {rows.length > TASTES_SHOWN ? (
            <TextButton onPress={() => setAll(!all)}>{all ? 'Moins' : `Tout voir (${rows.length})`}</TextButton>
          ) : null}
        </View>
      )}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

// The server's notifications on this device (lib/push.ts), allowed here for each device of the account; nothing where
// they can't reach it (iOS, a browser without push, Firebase not configured).
function PushNotifications() {
  const [state, setState] = useState<NotifyState>('unsupported');
  const [error, setError] = useState('');
  useEffect(() => {
    pushState().then(setState).catch(() => {});
  }, []);
  if (state === 'unsupported') return null;
  const closed = Platform.OS === 'web' ? 'même la page fermée' : 'même l’app fermée';
  const ask = () => {
    setError('');
    askPush().then(setState).catch(() => setError('Les notifications n’ont pas pu être activées sur cet appareil : réessayez.'));
  };
  return (
    <View style={styles.section}>
      <ThemedText type="eyebrow">Notifications</ThemedText>
      {state === 'granted' ? (
        <Notice>{`Activées sur cet appareil : Secret Date vous y prévient, ${closed}.`}</Notice>
      ) : state === 'denied' ? (
        <Notice>Refusées sur cet appareil : autorisez-les dans les réglages du navigateur ou du téléphone.</Notice>
      ) : (
        <>
          <Notice>{`Recevez les notifications de Secret Date sur cet appareil, ${closed}.`}</Notice>
          <GhostButton onPress={ask}>Activer les notifications</GhostButton>
        </>
      )}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

// The evenings' key moments by email too, beside the notifications (lib/emails.ts): turned off and on at a touch.
function EmailChoice() {
  const [on, setOn] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    emailsOn().then(setOn).catch(() => {});
  }, []);
  if (on === null) return null;
  const toggle = () => {
    setError('');
    setEmails(!on).then(() => setOn(!on)).catch((e: Error) => setError(e.message));
  };
  return (
    <View style={styles.section}>
      <ThemedText type="eyebrow">Emails</ThemedText>
      <Notice>
        {on
          ? 'Les moments clés de vos soirées vous arrivent aussi par email : la soirée gardée et ses réservations, le pli scellé, le Livre des Secrets.'
          : 'Vous ne recevez plus nos emails, seulement les notifications.'}
      </Notice>
      <GhostButton onPress={toggle}>{on ? 'Ne plus recevoir les emails' : 'Recevoir les emails'}</GhostButton>
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

// From an email's link (/compte?stop=…&t=…): no more emails to that address, said at once.
function StopEmails({ address, token }: { address: string; token: string }) {
  const [state, setState] = useState<'stopping' | 'stopped' | { error: string }>('stopping');
  useEffect(() => {
    stopEmails(address, token).then(() => setState('stopped'), (e: Error) => setState({ error: e.message }));
  }, [address, token]);
  return (
    <>
      <PageCard
        badge="Emails"
        title={state === 'stopped' ? 'C’est noté.' : state === 'stopping' ? 'Un instant…' : 'Lien invalide'}
        text={state === 'stopped'
          ? `${address} ne recevra plus nos emails. Les notifications de l’app, elles, se règlent sur l’appareil.`
          : state === 'stopping' ? 'On arrête nos emails.' : state.error}
      />
      <TextLink href="/">Retour à l’accueil →</TextLink>
    </>
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
  photo: { height: 104, borderRadius: Radius.card, borderWidth: 1, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  veil: { backgroundColor: 'rgba(4, 15, 10, 0.45)' },
  motto: { fontFamily: Fonts.headingItalic, fontSize: 26, lineHeight: 32 },
  confirmRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, marginTop: Spacing.two },
  notice: { padding: Spacing.three, borderRadius: Radius.tile, borderWidth: 1 },
  section: { gap: Spacing.three, marginVertical: Spacing.two },
  tastes: { paddingVertical: Spacing.two, paddingHorizontal: Spacing.three, borderRadius: Radius.tile, borderWidth: 1 },
  taste: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, minHeight: 36 },
  tasteTitle: { flex: 1 },
});
