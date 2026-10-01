import * as ImagePicker from 'expo-image-picker';
import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Image, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';

import { PrimaryLink, TextLink } from '@/components/buttons';
import { Screen } from '@/components/screen';
import { TextField } from '@/components/text-field';
import { ThemedText } from '@/components/themed-text';
import { Veil } from '@/components/veil';
import { Fonts, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTheme } from '@/hooks/use-theme';
import { isoDay, longDay } from '@/lib/dates';
import { book, bookOpen, sealPage, type Book, type Fragment, type Page } from '@/lib/souvenirs';

// "Le Livre des Secrets", at the end of the evening or the day after: each of the couple seals one page — a
// photo, a note. Once sealed, the route fades from the history and only the memory stays; the other's page
// shows once one's own is sealed.
export default function LivreScreen() {
  const { soiree, route } = useLocalSearchParams<{ soiree?: string; route?: string }>();
  const [state, setState] = useState<Book | null | 'loading' | 'error'>('loading');

  const load = useCallback(
    () => (soiree && route !== undefined ? book(soiree, Number(route)) : Promise.resolve(null)).then(setState, () => setState('error')),
    [soiree, route],
  );
  useEffect(() => {
    load();
  }, [load]);

  if (state === 'loading') {
    return (
      <Screen>
        <ThemedText themeColor="textSecondary">On ouvre le grimoire…</ThemedText>
      </Screen>
    );
  }
  if (state === 'error' || state === null) {
    return (
      <Screen>
        <ThemedText type="title">Livre introuvable</ThemedText>
        <ThemedText themeColor="textSecondary">
          {state === 'error' ? "Le livre n'a pas pu être ouvert." : "Cette soirée n'est pas gardée sur votre compte."}
        </ThemedText>
        <PrimaryLink href="/">Retour au tableau</PrimaryLink>
      </Screen>
    );
  }
  return <Grimoire book={state} onSealed={load} />;
}

function Grimoire({ book: { evening, pages }, onSealed }: { book: Book; onSealed: () => void }) {
  const { role, couple } = useCouple();
  const mine = pages.find((p) => p.mine);
  const theirs = pages.find((p) => !p.mine);
  const open = bookOpen(evening, isoDay(new Date()));
  const params = { soiree: evening.page_name, route: String(evening.route_index) };

  return (
    <Screen gap={Spacing.four}>
      <Header sealed={!!mine} title={evening.secret_title ?? evening.title} day={evening.day} />

      {!open ? (
        <ThemedText themeColor="textSecondary" style={styles.center}>
          Le livre s&apos;ouvrira le soir venu, quand le rideau tombera sur votre soirée.
        </ThemedText>
      ) : mine ? (
        <>
          <PageView page={mine} />
          {theirs ? (
            <PageView page={theirs} />
          ) : couple?.passager ? (
            <AwaitedPage />
          ) : null}
        </>
      ) : (
        <SealForm soireeId={evening.id} onSealed={onSealed} />
      )}

      {/* Until the page is sealed, the instigateur can still look back at the route. */}
      {role === 'instigateur' && !mine ? (
        <View style={styles.centerRow}>
          <TextLink href={{ pathname: '/revelation', params }}>Revoir l&apos;itinéraire →</TextLink>
        </View>
      ) : null}
    </Screen>
  );
}

function Header({ sealed, title, day }: { sealed: boolean; title: string; day: string | null }) {
  const theme = useTheme();
  return (
    <View style={[styles.header, { borderColor: theme.accentHair }]}>
      <ThemedText type="eyebrow" style={[styles.center, styles.kicker]}>
        {sealed ? 'Scellé à jamais' : "L'intrigue s'achève"}
      </ThemedText>
      <ThemedText style={[styles.title, { color: theme.accent }]}>Le Livre des Secrets</ThemedText>
      <ThemedText type="small" style={[styles.center, { color: theme.creamSoft }]}>
        « {title} »{day ? ` · ${longDay(day)}` : ''}
      </ThemedText>
      {sealed ? null : (
        <ThemedText type="small" style={[styles.center, styles.intro, { color: theme.creamSoft }]}>
          Le rideau tombe sur votre soirée parisienne. Déposez vos éclats de souvenirs dans votre grimoire avant
          qu&apos;ils ne s&apos;évaporent.
        </ThemedText>
      )}
    </View>
  );
}

function SealForm({ soireeId, onSealed }: { soireeId: string; onSealed: () => void }) {
  const theme = useTheme();
  const [fragment, setFragment] = useState<Fragment | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function pick() {
    const picked = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    const asset = picked.canceled ? null : picked.assets[0];
    if (asset) setFragment({ uri: asset.uri, mimeType: asset.mimeType });
  }

  async function seal() {
    setBusy(true);
    setError('');
    try {
      await sealPage(soireeId, note, fragment);
      onSealed();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  const empty = !fragment && !note.trim();
  return (
    <>
      <View style={styles.field}>
        <ThemedText type="eyebrow" style={styles.label}>Fragments visuels</ThemedText>
        <Pressable
          onPress={pick}
          style={[styles.drop, { backgroundColor: theme.velvet, borderColor: fragment ? theme.accentSoft : theme.accentFaint }]}>
          {fragment ? (
            <Image source={{ uri: fragment.uri }} style={[styles.preview, { borderColor: theme.accentSoft }]} />
          ) : (
            <View style={styles.dropInside}>
              <Svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke={theme.accent} strokeWidth={1.5} opacity={0.7}>
                <Path d="M21 19V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2z" />
                <Circle cx={9.5} cy={9.5} r={1.5} />
                <Path d="M21 15l-5-5L5 21" />
              </Svg>
              <ThemedText type="smallBold" style={[styles.center, { color: theme.cream, opacity: 0.8 }]}>
                Déposer une preuve de votre complicité
              </ThemedText>
              <ThemedText style={[styles.whisper, { color: theme.creamFaint }]}>Selfie, polaroïd ou cliché volé</ThemedText>
            </View>
          )}
        </Pressable>
        {fragment ? (
          <ThemedText style={[styles.whisper, styles.center, { color: theme.creamFaint }]}>Touchez la photo pour en choisir une autre</ThemedText>
        ) : null}
      </View>

      <View style={styles.field}>
        <ThemedText type="eyebrow" style={styles.label}>La note confidentielle</ThemedText>
        <TextField
          multiline
          value={note}
          onChangeText={setNote}
          maxLength={1200}
          placeholder="Écrivez un mot, une impression, un souvenir partagé à voix basse sous les voûtes…"
          placeholderTextColor={theme.creamFaint}
          style={[styles.note, { backgroundColor: theme.velvet, color: theme.cream }]}
        />
      </View>

      <View style={styles.field}>
        <Pressable
          disabled={busy || empty}
          onPress={seal}
          style={[styles.seal, { backgroundColor: theme.satin }, (busy || empty) && styles.dim]}>
          <ThemedText style={[styles.sealLabel, { color: theme.onAccent }]}>
            {busy ? 'Chiffrement du secret…' : 'Sceller dans le Grimoire'}
          </ThemedText>
        </Pressable>
        <ThemedText style={[styles.whisper, styles.center, styles.italic, { color: theme.accent, opacity: 0.5 }]}>
          Une fois scellé, l&apos;itinéraire s&apos;efface. Seul ce souvenir subsistera.
        </ThemedText>
        {error ? <ThemedText type="small" themeColor="danger" style={styles.center}>{error}</ThemedText> : null}
      </View>
    </>
  );
}

function PageView({ page }: { page: Page }) {
  const theme = useTheme();
  const sealedOn = new Date(page.sealed_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
  return (
    <View style={[styles.page, { backgroundColor: theme.velvet, borderColor: page.mine ? theme.accentHair : theme.accentSoft }]}>
      <ThemedText type="eyebrow" style={styles.label}>{page.mine ? 'Votre page' : 'La page de votre complice'}</ThemedText>
      {page.photoUrl ? <Image source={{ uri: page.photoUrl }} style={[styles.photo, { borderColor: theme.accentSoft }]} /> : null}
      {page.note ? <ThemedText type="clue" style={{ color: theme.cream }}>« {page.note} »</ThemedText> : null}
      <ThemedText style={[styles.whisper, { color: theme.creamFaint }]}>Scellée le {sealedOn}</ThemedText>
    </View>
  );
}

// The other's page, not sealed yet: a blank leaf.
function AwaitedPage() {
  const theme = useTheme();
  return (
    <View style={[styles.page, { backgroundColor: theme.velvet, borderColor: theme.accentHair }]}>
      <ThemedText type="eyebrow" style={styles.label}>La page de votre complice</ThemedText>
      <Veil widths={['92%', '70%', '45%']} />
      <ThemedText type="small" style={{ color: theme.creamSoft }}>
        Pas encore scellée : elle apparaîtra ici dès que votre complice aura déposé la sienne.
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { textAlign: 'center' },
  centerRow: { alignItems: 'center' },
  italic: { fontFamily: Fonts.headingItalic },
  header: { alignItems: 'center', gap: Spacing.two, paddingBottom: Spacing.four, borderBottomWidth: 1 },
  kicker: { fontSize: 10, letterSpacing: 3 },
  title: { fontFamily: Fonts.heading, fontSize: 26, lineHeight: 34, textAlign: 'center', letterSpacing: 0.5 },
  intro: { paddingHorizontal: Spacing.three, marginTop: Spacing.one, lineHeight: 21 },
  field: { gap: Spacing.two },
  label: { fontSize: 10, letterSpacing: 2.5 },
  drop: { aspectRatio: 4 / 3, borderRadius: 16, borderWidth: 1.5, borderStyle: 'dashed', overflow: 'hidden', justifyContent: 'center' },
  dropInside: { alignItems: 'center', gap: Spacing.two, padding: Spacing.three },
  preview: { flex: 1, margin: Spacing.two, borderRadius: 12, borderWidth: 1 },
  whisper: { fontFamily: Fonts.sans, fontSize: 11, lineHeight: 16 },
  note: {
    fontFamily: Fonts.headingItalic, fontSize: 15, lineHeight: 22, minHeight: 96, padding: Spacing.three,
    borderRadius: 16, textAlignVertical: 'top',
  },
  seal: { borderRadius: 12, paddingVertical: Spacing.three, alignItems: 'center', boxShadow: '0 4px 20px rgba(212, 175, 55, 0.15)' },
  sealLabel: { fontFamily: Fonts.headingBold, fontSize: 16, lineHeight: 22, letterSpacing: 0.4 },
  dim: { opacity: 0.45 },
  page: { gap: Spacing.three, padding: Spacing.three, borderRadius: 18, borderWidth: 1 },
  photo: { width: '100%', aspectRatio: 4 / 3, borderRadius: 12, borderWidth: 1 },
});
