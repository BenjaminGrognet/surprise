import * as ImagePicker from 'expo-image-picker';
import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Image, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';

import { PrimaryLink, TextLink } from '@/components/buttons';
import { PageCard } from '@/components/intrigue-card';
import { Screen } from '@/components/screen';
import { TextField } from '@/components/text-field';
import { ThemedText } from '@/components/themed-text';
import { Veil } from '@/components/veil';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { eveningRole, guests, isSquad } from '@/lib/couple';
import { PaletteProvider, useTheme } from '@/hooks/use-theme';
import { isoDay, longDay } from '@/lib/dates';
import { book, bookOpen, sealPage, type Book, type Fragment, type Page } from '@/lib/souvenirs';

// "Le Livre des Secrets", at the end of the evening or the day after: each of the couple — each of the band, for a
// Secret Squad — seals one page, a photo, a note. Once sealed, the route fades from the history and only the memory
// stays; the others' pages show once one's own is sealed.
export default function LivreScreen() {
  const { soiree } = useLocalSearchParams<{ soiree?: string }>();
  const [state, setState] = useState<Book | null | 'loading' | 'error'>('loading');

  const load = useCallback(
    () => (soiree ? book(soiree) : Promise.resolve(null)).then(setState, () => setState('error')),
    [soiree],
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
        <PageCard
          back
          title="Livre introuvable"
          text={state === 'error' ? "Le livre n'a pas pu être ouvert." : "Cette soirée n'est pas gardée sur votre compte."}
        />
        <PrimaryLink href="/">Retour au tableau</PrimaryLink>
      </Screen>
    );
  }
  return (
    <PaletteProvider name={isSquad(state.evening) ? 'squad' : 'date'}>
      <Grimoire book={state} onSealed={load} />
    </PaletteProvider>
  );
}

function Grimoire({ book: { evening, pages }, onSealed }: { book: Book; onSealed: () => void }) {
  const role = eveningRole(evening, useCouple().userId);
  const mine = pages.find((p) => p.mine);
  const theirs = pages.filter((p) => !p.mine);
  const squad = isSquad(evening);
  // Its instigateur and each of its guests: the pages still awaited.
  const awaited = 1 + guests(evening).length - pages.length;
  const open = bookOpen(evening, isoDay(new Date()));
  const params = { soiree: evening.page_name };

  return (
    <Screen gap={Spacing.four}>
      <Header sealed={!!mine} title={evening.secret_title ?? evening.title} day={evening.day} />

      {!open ? (
        <ThemedText themeColor="textSecondary" style={styles.center}>
          Le livre s&apos;ouvrira le soir venu, quand le rideau tombera sur votre soirée.
        </ThemedText>
      ) : mine ? (
        <>
          <PageView page={mine} squad={squad} />
          {theirs.map((page) => <PageView key={page.author} page={page} squad={squad} />)}
          {awaited > 0 ? <AwaitedPage squad={squad} count={awaited} /> : null}
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

// The book's card, as on the home: sealed or still to seal, the evening it keeps and, until sealed, what it asks for.
function Header({ sealed, title, day }: { sealed: boolean; title: string; day: string | null }) {
  const theme = useTheme();
  return (
    <PageCard back badge={sealed ? 'Scellé' : 'À sceller'} title="Le Livre des Secrets" text={`« ${title} »${day ? ` · ${longDay(day)}` : ''}`}>
      {sealed ? null : (
        <ThemedText style={{ color: theme.creamSoft }}>
          Le rideau tombe sur votre soirée parisienne. Déposez vos éclats de souvenirs dans votre grimoire avant
          qu&apos;ils ne s&apos;évaporent.
        </ThemedText>
      )}
    </PageCard>
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
          style={[styles.seal, { backgroundColor: theme.satin, boxShadow: busy || empty ? 'none' : `0 8px 22px ${theme.glow}` }, (busy || empty) && styles.dim]}>
          <ThemedText style={[styles.sealLabel, { color: theme.onAccent }]}>
            {busy ? 'Chiffrement du secret…' : 'Sceller dans le Grimoire'}
          </ThemedText>
        </Pressable>
        <ThemedText style={[styles.whisper, styles.center, styles.italic, { color: theme.gold, opacity: 0.7 }]}>
          Une fois scellé, l&apos;itinéraire s&apos;efface. Seul ce souvenir subsistera.
        </ThemedText>
        {error ? <ThemedText type="small" themeColor="danger" style={styles.center}>{error}</ThemedText> : null}
      </View>
    </>
  );
}

function PageView({ page, squad }: { page: Page; squad: boolean }) {
  const theme = useTheme();
  const sealedOn = new Date(page.sealed_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
  return (
    <View style={[styles.page, { backgroundColor: theme.velvet, borderColor: page.mine ? theme.accentHair : theme.accentSoft }]}>
      <ThemedText type="eyebrow" style={styles.label}>{page.mine ? 'Votre page' : squad ? 'Une page de la bande' : 'La page de votre complice'}</ThemedText>
      {page.photoUrl ? <Image source={{ uri: page.photoUrl }} style={[styles.photo, { borderColor: theme.accentSoft }]} /> : null}
      {page.note ? <ThemedText type="clue" style={{ color: theme.cream }}>« {page.note} »</ThemedText> : null}
      <ThemedText style={[styles.whisper, { color: theme.creamFaint }]}>Scellée le {sealedOn}</ThemedText>
    </View>
  );
}

// The other's page, not sealed yet: a blank leaf.
function AwaitedPage({ squad, count }: { squad: boolean; count: number }) {
  const theme = useTheme();
  return (
    <View style={[styles.page, { backgroundColor: theme.velvet, borderColor: theme.accentHair }]}>
      <ThemedText type="eyebrow" style={styles.label}>
        {squad ? `${count} page${count > 1 ? 's' : ''} de la bande` : 'La page de votre complice'}
      </ThemedText>
      <Veil widths={['92%', '70%', '45%']} />
      <ThemedText type="small" style={{ color: theme.creamSoft }}>
        {squad
          ? 'Pas encore scellées : elles apparaîtront ici à mesure que la bande déposera les siennes.'
          : 'Pas encore scellée : elle apparaîtra ici dès que votre complice aura déposé la sienne.'}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { textAlign: 'center' },
  centerRow: { alignItems: 'center' },
  italic: { fontFamily: Fonts.headingItalic },
  field: { gap: Spacing.two },
  label: { fontSize: 10, letterSpacing: 2.5 },
  drop: { aspectRatio: 4 / 3, borderRadius: Radius.tile, borderWidth: 1.5, borderStyle: 'dashed', overflow: 'hidden', justifyContent: 'center' },
  dropInside: { alignItems: 'center', gap: Spacing.two, padding: Spacing.three },
  preview: { flex: 1, margin: Spacing.two, borderRadius: 12, borderWidth: 1 },
  whisper: { fontFamily: Fonts.sans, fontSize: 12, lineHeight: 17 },
  note: {
    fontFamily: Fonts.headingItalic, fontSize: 18, lineHeight: 24, minHeight: 104, padding: Spacing.three,
    borderRadius: Radius.field, textAlignVertical: 'top',
  },
  seal: { borderRadius: Radius.pill, paddingVertical: Spacing.three - 2, alignItems: 'center' },
  sealLabel: { fontFamily: Fonts.headingBold, fontSize: 20, lineHeight: 24, letterSpacing: 0.3 },
  dim: { opacity: 0.45 },
  page: { gap: Spacing.three, padding: Spacing.three, borderRadius: Radius.tile, borderWidth: 1 },
  photo: { width: '100%', aspectRatio: 4 / 3, borderRadius: 16, borderWidth: 1 },
});
