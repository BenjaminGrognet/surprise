import { useState } from 'react';
import { Platform, Pressable, Share, StyleSheet, View } from 'react-native';

import { GhostButton, PrimaryButton, TextButton } from '@/components/buttons';
import { InvitationCarton } from '@/components/invitation-carton';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { EveningHistoryRow } from '@/lib/account';
import { invitationLink, resetPassager } from '@/lib/couple';

// The instigateur's side of one evening: invite its passager (one at most) by a link, or a printed card with its QR code
// (`card`: the evening's secret name and day), see that they joined, or start over.
export function PassagerInvite({
  evening, onChange, card,
}: { evening: EveningHistoryRow; onChange: () => void; card: { secretTitle: string; when: string } }) {
  const theme = useTheme();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [confirm, setConfirm] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    try {
      await action();
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function share(link: string) {
    const message = `Je te prépare une soirée secrète. Rejoins-moi sur Secret Date, tu n'auras que des indices : ${link}`;
    if (Platform.OS === 'web') {
      await navigator.clipboard?.writeText(link);
      setCopied(true);
    } else {
      await Share.share({ message });
    }
  }

  const link = invitationLink(evening.invite_code);
  return (
    <View style={[styles.card, { borderColor: theme.accentSoft, backgroundColor: theme.backgroundElement }]}>
      <ThemedText type="eyebrow">Votre passager pour cette soirée</ThemedText>
      {evening.passager ? (
        <>
          <ThemedText type="subtitle">Complices connectés</ThemedText>
          <ThemedText themeColor="textSecondary">
            {evening.passager_email ?? 'Votre passager'} reçoit les indices de cette soirée, rien de plus.
          </ThemedText>
          {confirm ? (
            <View style={styles.row}>
              <TextButton onPress={() => setConfirm(false)}>Annuler</TextButton>
              <GhostButton onPress={() => run(() => resetPassager(evening.id)).then(() => setConfirm(false))}>Oui, nouveau lien</GhostButton>
            </View>
          ) : (
            <TextButton onPress={() => setConfirm(true)}>Changer de passager…</TextButton>
          )}
          {confirm ? (
            <ThemedText type="small" themeColor="textSecondary">
              {evening.passager_email ?? 'Votre passager'} n&apos;aura plus accès à cette soirée ; un nouveau lien d&apos;invitation est créé.
            </ThemedText>
          ) : null}
        </>
      ) : (
        <>
          <ThemedText themeColor="textSecondary">
            Envoyez ce lien à votre passager : il crée son propre compte et ne recevra que les indices.
          </ThemedText>
          <Pressable onPress={() => share(link)} style={[styles.link, { borderColor: theme.line, backgroundColor: theme.background }]}>
            <ThemedText type="small" numberOfLines={1}>{link}</ThemedText>
          </Pressable>
          <PrimaryButton wide disabled={busy} onPress={() => share(link)}>
            {Platform.OS === 'web' ? (copied ? '✓ Lien copié' : 'Copier le lien') : 'Envoyer le lien'}
          </PrimaryButton>
          <InvitationCarton {...card} link={link} />
          <ThemedText type="small" themeColor="textSecondary">En attente de votre passager…</ThemedText>
        </>
      )}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { padding: Spacing.four, borderRadius: Radius.card, borderWidth: 1, gap: Spacing.three },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three },
  link: { borderWidth: 1, borderRadius: Radius.field, padding: 14 },
});
