import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';

import { AuthForm } from '@/components/auth-form';
import { PrimaryButton } from '@/components/buttons';
import { PageCard } from '@/components/intrigue-card';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { currentUser } from '@/lib/account';
import { joinEvening } from '@/lib/couple';

// Where the instigateur's link leads (/invitation?code=…): the passager creates their own account, or signs in,
// and joins the evening — a couple's, or a band's (Secret Squad). From then on they only get its clues; by a band's
// complices' link, they are in on the secret and see the whole evening.
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
      <PageCard
        badge="Invitation"
        title="Quelqu'un trame une soirée pour vous…"
        text="À deux ou en bande, vous serez du voyage : pas de programme, seulement des indices dévoilés peu à peu jusqu'au jour J. Sauf si l'on vous a mis dans la confidence : alors vous verrez tout."
      />

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
