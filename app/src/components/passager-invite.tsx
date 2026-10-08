import { useEffect, useState } from 'react';
import { Platform, Pressable, Share, StyleSheet, View } from 'react-native';

import { GhostButton, PrimaryButton, TextButton } from '@/components/buttons';
import { InvitationCarton } from '@/components/invitation-carton';
import { TextField } from '@/components/text-field';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { EveningHistoryRow, GuestRole, Invite } from '@/lib/account';
import { guests, invitationLink, isSquad, placesLeft, removeGuest, resetPassager } from '@/lib/couple';
import { emailInvitations, inviteByEmail, type EmailInvitation } from '@/lib/emails';

type Card = { secretTitle: string; when: string };

// The instigateur's side of one evening's guests. A couple's: its passager (one at most) invited by a link, or a printed
// card with its QR code (`card`: the evening's secret name and day), seen once joined, or let go for a fresh link. A
// band's (Secret Squad): two links — the passagers', who only get the clues, and the complices', in on the secret —,
// the band as it joins, and its places left. `owner`: the evening's own instigateur, who lets a guest go; a complice
// sees the links and the band.
export function PassagerInvite({
  evening, onChange, card, owner = true,
}: { evening: EveningHistoryRow; onChange: () => void; card: Card; owner?: boolean }) {
  return isSquad(evening)
    ? <BandInvite evening={evening} onChange={onChange} card={card} owner={owner} />
    : <CoupleInvite evening={evening} onChange={onChange} card={card} />;
}

// What a guest's link does on this device: copied on the web, shared from a phone.
function useShare() {
  const [copied, setCopied] = useState<string | null>(null);
  async function share(link: string, message: string) {
    if (Platform.OS === 'web') {
      await navigator.clipboard?.writeText(link);
      setCopied(link);
    } else {
      await Share.share({ message: `${message} ${link}` });
    }
  }
  return { copied, share };
}

function useAction(onChange: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
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
  return { busy, error, run };
}

function CoupleInvite({ evening, onChange, card }: { evening: EveningHistoryRow; onChange: () => void; card: Card }) {
  const theme = useTheme();
  const { busy, error, run } = useAction(onChange);
  const { copied, share } = useShare();
  const [confirm, setConfirm] = useState(false);
  const passager = guests(evening, 'passager')[0] ?? null;
  const link = invitationLink(evening.invite_code);
  const send = () => share(link, "Je te prépare une soirée secrète. Rejoins-moi sur Secret Date, tu n'auras que des indices :");
  return (
    <View style={[styles.card, { borderColor: theme.accentSoft, backgroundColor: theme.backgroundElement }]}>
      <ThemedText type="eyebrow">Votre passager pour cette soirée</ThemedText>
      {passager ? (
        <>
          <ThemedText type="subtitle">Complices connectés</ThemedText>
          <ThemedText themeColor="textSecondary">
            {passager.email ?? 'Votre passager'} reçoit les indices de cette soirée, rien de plus.
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
              {passager.email ?? 'Votre passager'} n&apos;aura plus accès à cette soirée ; un nouveau lien d&apos;invitation est créé.
            </ThemedText>
          ) : null}
        </>
      ) : (
        <>
          <ThemedText themeColor="textSecondary">
            Envoyez ce lien à votre passager : il crée son propre compte et ne recevra que les indices.
          </ThemedText>
          <LinkBox link={link} onPress={send} />
          <PrimaryButton wide disabled={busy} onPress={send}>
            {Platform.OS === 'web' ? (copied === link ? '✓ Lien copié' : 'Copier le lien') : 'Envoyer le lien'}
          </PrimaryButton>
          <EmailInvite evening={evening} hint="Ou par email : nous lui envoyons l'invitation, à votre nom." />
          <InvitationCarton {...card} link={link} />
          <ThemedText type="small" themeColor="textSecondary">En attente de votre passager…</ThemedText>
        </>
      )}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

function BandInvite({ evening, onChange, card, owner }: { evening: EveningHistoryRow; onChange: () => void; card: Card; owner: boolean }) {
  const theme = useTheme();
  const { error, run } = useAction(onChange);
  const { copied, share } = useShare();
  const band = guests(evening);
  const left = placesLeft(evening);
  const passagers = invitationLink(evening.invite_code);
  const complices = evening.codes?.complice_code ? invitationLink(evening.codes.complice_code) : null;
  const copy = (link: string, label: string) => (Platform.OS === 'web' ? (copied === link ? '✓ Lien copié' : `Copier ${label}`) : `Envoyer ${label}`);
  return (
    <View style={[styles.card, { borderColor: theme.accentSoft, backgroundColor: theme.backgroundElement }]}>
      <View style={styles.head}>
        <ThemedText type="eyebrow">Votre bande pour cette soirée</ThemedText>
        <ThemedText type="small" themeColor={left ? 'textSecondary' : 'ok'}>
          {band.length + 1} sur {evening.personnes ?? 2}
        </ThemedText>
      </View>
      <ThemedText type="subtitle">{left ? `Encore ${left} place${left > 1 ? 's' : ''} dans la bande` : 'La bande est au complet'}</ThemedText>

      {band.length ? (
        <View style={styles.members}>
          {band.map((guest) => (
            <Member key={guest.user_id} guest={guest} onRemove={owner ? () => run(() => removeGuest(evening.id, guest.user_id)) : null} />
          ))}
        </View>
      ) : null}

      {left ? (
        <>
          <View style={styles.block}>
            <ThemedText type="smallBold">Le lien des invités</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              Pour la bande à surprendre : chacun crée son compte et ne reçoit que les indices. Un seul lien pour tout le groupe.
            </ThemedText>
            <LinkBox link={passagers} onPress={() => share(passagers, 'On te prépare une soirée secrète entre potes. Rejoins la bande sur Secret Squad, tu n\'auras que des indices :')} />
            <PrimaryButton wide onPress={() => share(passagers, 'On te prépare une soirée secrète entre potes. Rejoins la bande sur Secret Squad, tu n\'auras que des indices :')}>
              {copy(passagers, 'le lien des invités')}
            </PrimaryButton>
            <EmailInvite evening={evening} hint="Ou par email, à chacun : nous lui envoyons le lien des invités." />
            <InvitationCarton {...card} link={passagers} brand="Secret Squad" />
          </View>
          {complices ? (
            <View style={styles.block}>
              <ThemedText type="smallBold">Le lien des complices</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                Pour ceux qui organisent avec vous (les témoins d&apos;un EVJF) : ils voient tout le programme et cochent les réservations. À ne pas envoyer à ceux que vous voulez surprendre.
              </ThemedText>
              <LinkBox link={complices} onPress={() => share(complices, 'Je prépare une soirée secrète pour la bande, et tu es dans la confidence :')} />
              <TextButton onPress={() => share(complices, 'Je prépare une soirée secrète pour la bande, et tu es dans la confidence :')}>
                {copy(complices, 'le lien des complices')}
              </TextButton>
              {owner ? <EmailInvite evening={evening} role="complice" hint="Ou par email : nous lui envoyons le lien des complices." /> : null}
            </View>
          ) : null}
        </>
      ) : null}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

// The evening's link sent by email (lib/emails.ts): the server writes to the address typed here, in the evening's
// name; those sent already, and those on their way.
function EmailInvite({ evening, role = 'passager', hint }: { evening: EveningHistoryRow; role?: GuestRole; hint: string }) {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState<EmailInvitation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const load = () => emailInvitations(evening.id).then((rows) => setSent(rows.filter((r) => r.role === role))).catch(() => {});
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evening.id, role]);
  async function send() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await inviteByEmail(evening.id, email, role);
      setEmail('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <View style={styles.block}>
      <ThemedText type="small" themeColor="textSecondary">{hint}</ThemedText>
      <View style={styles.emailRow}>
        <TextField
          value={email} onChangeText={setEmail} onSubmitEditing={send} placeholder="son@email.fr" accessibilityLabel={role === 'complice' ? 'Email du complice' : "Email de l'invité"}
          keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" style={styles.emailField} />
        <GhostButton onPress={send}>{busy ? 'Envoi…' : 'Envoyer'}</GhostButton>
      </View>
      {sent.map((invitation) => (
        <ThemedText key={invitation.id} type="small" themeColor={invitation.sent_at ? 'ok' : 'textSecondary'}>
          {invitation.sent_at ? `✓ Invitation envoyée à ${invitation.email}` : `Invitation en route vers ${invitation.email}…`}
        </ThemedText>
      ))}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

// One of the band: who, whether in on the secret, and — for the instigateur — a way to let them go.
function Member({ guest, onRemove }: { guest: Invite; onRemove: (() => void) | null }) {
  const theme = useTheme();
  const [confirm, setConfirm] = useState(false);
  return (
    <View style={[styles.member, { borderBottomColor: theme.line }]}>
      <View style={styles.memberText}>
        <ThemedText type="smallBold" numberOfLines={1}>{guest.email ?? 'Un invité'}</ThemedText>
        <ThemedText type="small" themeColor={guest.role === 'complice' ? 'gold' : 'textSecondary'}>
          {guest.role === 'complice' ? 'Complice : voit tout' : 'Invité : les indices seulement'}
        </ThemedText>
      </View>
      {onRemove ? (
        confirm ? (
          <View style={styles.row}>
            <TextButton onPress={() => setConfirm(false)}>Garder</TextButton>
            <GhostButton onPress={onRemove}>Retirer</GhostButton>
          </View>
        ) : (
          <TextButton onPress={() => setConfirm(true)}>Retirer…</TextButton>
        )
      ) : null}
    </View>
  );
}

function LinkBox({ link, onPress }: { link: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} style={[styles.link, { borderColor: theme.line, backgroundColor: theme.background }]}>
      <ThemedText type="small" numberOfLines={1}>{link}</ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { padding: Spacing.four, borderRadius: Radius.card, borderWidth: 1, gap: Spacing.three },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: Spacing.two },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three },
  block: { gap: Spacing.two },
  members: { gap: Spacing.two },
  member: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, paddingBottom: Spacing.two, borderBottomWidth: 1 },
  memberText: { flex: 1, gap: 2 },
  link: { borderWidth: 1, borderRadius: Radius.field, padding: 14 },
  emailRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  emailField: { flex: 1 },
});
