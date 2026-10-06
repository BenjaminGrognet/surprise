import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { SvgXml } from 'react-native-svg';

import { PrimaryButton, TextButton } from '@/components/buttons';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { invitationHtml, qrSvg, type Invitation } from '@/lib/invitation-card';
import { canShareCardPdf, printCard, shareCardPdf } from '@/lib/print-card';

// The invitation on paper (lib/invitation-card.ts), for the instigateur whose passager has not joined yet: a preview of
// the card, its QR code to the link, and the card printed (or sent as a PDF from a phone).
export function InvitationCarton(invitation: Invitation) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');

  async function run(action: (html: string) => Promise<void>) {
    setError('');
    try {
      await action(invitationHtml(invitation));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (!open) return <TextButton onPress={() => setOpen(true)}>Ou un carton d&apos;invitation à imprimer…</TextButton>;
  return (
    <View testID="carton-invitation" style={styles.block}>
      <ThemedText type="small" themeColor="textSecondary">
        À glisser sous son oreiller ou dans son livre : le nom de la soirée, le jour, et un code à scanner pour ses indices.
      </ThemedText>
      <View style={styles.paper}>
        <View style={styles.text}>
          <ThemedText style={styles.brand}>SECRET DATE</ThemedText>
          <ThemedText style={styles.kicker}>VOUS ÊTES INVITÉ(E)</ThemedText>
          <ThemedText style={styles.title}>{invitation.secretTitle}</ThemedText>
          <ThemedText style={styles.when}>{invitation.when}</ThemedText>
        </View>
        <SvgXml xml={qrSvg(invitation.link, 104)} width={104} height={104} />
      </View>
      <PrimaryButton wide onPress={() => run(printCard)}>Imprimer le carton</PrimaryButton>
      {canShareCardPdf ? <TextButton onPress={() => run(shareCardPdf)}>L&apos;envoyer en PDF</TextButton> : null}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

// The paper's own colours: ivory, ink green, gold, as printed.
const styles = StyleSheet.create({
  block: { gap: Spacing.three },
  paper: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.three, padding: Spacing.three, borderRadius: Radius.tile,
    backgroundColor: '#FBF8F0', borderWidth: 1, borderColor: '#B8975A',
  },
  text: { flex: 1, gap: Spacing.one },
  brand: { fontFamily: Fonts.headingBold, fontSize: 11, letterSpacing: 3, color: '#9A7B3F' },
  kicker: { fontFamily: Fonts.sans, fontSize: 9, letterSpacing: 2, color: '#5E6E62' },
  title: { fontFamily: Fonts.headingItalic, fontSize: 21, lineHeight: 24, color: '#06281B' },
  when: { fontFamily: Fonts.sansSemiBold, fontSize: 11, color: '#9A7B3F' },
});
