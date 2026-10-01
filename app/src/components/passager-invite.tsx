import { useState } from 'react';
import { Platform, Pressable, Share, StyleSheet, View } from 'react-native';

import { GhostButton, PrimaryButton, TextButton } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTheme } from '@/hooks/use-theme';
import { invitation, invitationLink, renewInvitation } from '@/lib/couple';

// The instigateur's side of the couple: invite the passager by a link, see that they joined, or start over.
export function PassagerInvite() {
  const theme = useTheme();
  const { couple, refresh } = useCouple();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [confirm, setConfirm] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function share(link: string) {
    const message = `Je te prépare une soirée secrète. Rejoins-moi sur SecretDate, tu n'auras que des indices : ${link}`;
    if (Platform.OS === 'web') {
      await navigator.clipboard?.writeText(link);
      setCopied(true);
    } else {
      await Share.share({ message });
    }
  }

  const link = couple ? invitationLink(couple.invite_code) : null;
  return (
    <View style={[styles.card, { borderColor: theme.accentSoft, backgroundColor: theme.backgroundElement }]}>
      <ThemedText type="eyebrow">Votre passager</ThemedText>
      {couple?.passager ? (
        <>
          <ThemedText type="subtitle">Complices connectés</ThemedText>
          <ThemedText themeColor="textSecondary">
            {couple.passager_email ?? 'Votre passager'} reçoit les indices de vos intrigues, rien de plus.
          </ThemedText>
          {confirm ? (
            <View style={styles.row}>
              <TextButton onPress={() => setConfirm(false)}>Annuler</TextButton>
              <GhostButton onPress={() => run(renewInvitation).then(() => setConfirm(false))}>Oui, nouveau lien</GhostButton>
            </View>
          ) : (
            <TextButton onPress={() => setConfirm(true)}>Changer de passager…</TextButton>
          )}
          {confirm ? (
            <ThemedText type="small" themeColor="textSecondary">
              {couple.passager_email ?? 'Votre passager'} n&apos;aura plus accès à vos intrigues ; un nouveau lien d&apos;invitation est créé.
            </ThemedText>
          ) : null}
        </>
      ) : link ? (
        <>
          <ThemedText themeColor="textSecondary">
            Envoyez ce lien à votre passager : il crée son propre compte et ne recevra que les indices.
          </ThemedText>
          <Pressable onPress={() => share(link)} style={[styles.link, { borderColor: theme.accentFaint, backgroundColor: theme.glass }]}>
            <ThemedText type="small" numberOfLines={1}>{link}</ThemedText>
          </Pressable>
          <PrimaryButton wide disabled={busy} onPress={() => share(link)}>
            {Platform.OS === 'web' ? (copied ? '✓ Lien copié' : 'Copier le lien') : 'Envoyer le lien'}
          </PrimaryButton>
          <ThemedText type="small" themeColor="textSecondary">En attente de votre passager…</ThemedText>
        </>
      ) : (
        <>
          <ThemedText themeColor="textSecondary">
            Vous tramez, il ou elle se laisse surprendre : invitez votre passager, il aura son propre compte et ne verra que les indices.
          </ThemedText>
          <PrimaryButton wide disabled={busy} onPress={() => run(invitation)}>Inviter mon passager</PrimaryButton>
        </>
      )}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { padding: Spacing.four, borderRadius: 22, borderWidth: 1, gap: Spacing.three },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three },
  link: { borderWidth: 1, borderRadius: 14, padding: 14 },
});
