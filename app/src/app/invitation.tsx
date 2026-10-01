import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet } from 'react-native';

import { AuthForm } from '@/components/auth-form';
import { PrimaryButton } from '@/components/buttons';
import { IntrigueCard } from '@/components/intrigue-card';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { currentUser } from '@/lib/account';
import { joinEvening } from '@/lib/couple';

// Where the instigateur's link leads (/invitation?code=…): the passager creates their own account, or signs in,
// and joins the couple. From then on they only get the clues of the evenings.
export default function InvitationScreen() {
  const { code } = useLocalSearchParams<{ code?: string }>();
  const { refresh } = useCouple();
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    currentUser().then((u) => setSignedIn(!!u));
  }, []);

  async function join() {
    if (!code) return;
    setBusy(true);
    setError('');
    try {
      await joinEvening(code);
      await refresh();
      router.replace('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <Screen gap={Spacing.four}>
      <IntrigueCard>
        <ThemedText type="eyebrow" style={styles.center}>Une invitation</ThemedText>
        <ThemedText type="title" style={styles.center}>Quelqu&apos;un trame une soirée pour vous…</ThemedText>
        <ThemedText themeColor="textSecondary" style={styles.center}>
          Vous serez le passager : pas de programme, seulement des indices, dévoilés peu à peu jusqu&apos;au jour J.
        </ThemedText>
      </IntrigueCard>

      {!code ? (
        <ThemedText themeColor="danger">Ce lien d&apos;invitation est incomplet : demandez-le à nouveau.</ThemedText>
      ) : signedIn === null ? null : signedIn ? (
        <PrimaryButton wide disabled={busy} onPress={join}>{busy ? 'On vous fait monter…' : "Rejoindre l'intrigue"}</PrimaryButton>
      ) : (
        <>
          <ThemedText themeColor="textSecondary">Créez votre compte de passager, ou connectez-vous si vous en avez un.</ThemedText>
          <AuthForm startWith="up" signUpLabel="Créer mon compte passager" onSignedIn={join} />
        </>
      )}
      {error ? <ThemedText themeColor="danger">{error}</ThemedText> : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  center: { textAlign: 'center' },
});
