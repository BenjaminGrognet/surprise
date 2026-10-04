import { router } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Image, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

import { PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { PageCard } from '@/components/intrigue-card';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useTheme } from '@/hooks/use-theme';
import { deleteEvening, eveningsHistory, type EveningHistoryRow } from '@/lib/account';
import { eveningRole } from '@/lib/couple';
import { isoDay, longDay } from '@/lib/dates';
import { photoUrls } from '@/lib/souvenirs';
import { supabaseConfigured } from '@/lib/supabase';

const monthYear = (iso: string) => new Date(`${iso}T12:00`).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' }).toUpperCase();

type State = 'loading' | 'error' | EveningHistoryRow[];

// "Mes soirées": the couple's evenings along a gold thread, newest first. A sealed evening is a relic — only its
// Photo Témoin and Note Confidentielle remain, the route has faded — and the older it is, the more it fades too.
// An evening still to come, or one whose book is still open, is a plain anchor on the thread.
export default function ArchivesScreen() {
  const theme = useTheme();
  const [state, setState] = useState<State>(supabaseConfigured ? 'loading' : 'error');
  const [photos, setPhotos] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    if (!supabaseConfigured) return;
    eveningsHistory()
      .then(async (rows) => {
        setState([...rows].sort((a, b) => (b.day ?? '').localeCompare(a.day ?? '')));
        setPhotos(await photoUrls(rows.flatMap((r) => r.souvenirs?.map((p) => p.photo) ?? [])));
      })
      .catch(() => setState('error'));
  }, []);
  useEffect(load, [load]);

  const rows = Array.isArray(state) ? state : [];
  const relics = rows.filter((r) => r.souvenirs?.length);
  return (
    <Screen gap={Spacing.four}>
      <PageCard
        badge={Array.isArray(state) ? `${relics.length} secret${relics.length > 1 ? 's' : ''}` : undefined}
        title="Mes soirées"
        text="Le grimoire de vos échappées clandestines."
      />

      {state === 'loading' ? <ThemedText themeColor="textSecondary">On rouvre le grimoire…</ThemedText> : null}
      {state === 'error' ? (
        <ThemedText themeColor={supabaseConfigured ? 'danger' : 'textSecondary'}>
          {supabaseConfigured ? "Vos soirées n'ont pas pu être ouvertes." : 'Les comptes ne sont pas encore configurés sur ce serveur.'}
        </ThemedText>
      ) : null}
      {Array.isArray(state) && !rows.length ? <Empty /> : null}

      {rows.length ? (
        <View style={styles.thread}>
          <View style={styles.line} />
          {rows.map((row) =>
            row.souvenirs?.length ? (
              <Relic key={row.id} row={row} age={relics.indexOf(row)} photos={photos} onDeleted={load} />
            ) : (
              <Anchor key={row.id} row={row} onDeleted={load} />
            ),
          )}
        </View>
      ) : null}

      <View style={[styles.footer, { borderColor: theme.accentHair }]}>
        <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))}>
          <ThemedText type="small" style={{ color: theme.creamSoft }}>← Le tableau</ThemedText>
        </Pressable>
      </View>
    </Screen>
  );
}

function Empty() {
  const { role } = useCouple();
  return (
    <>
      <ThemedText themeColor="textSecondary">
        {role === 'passager'
          ? 'Pas encore de secret : votre instigateur trame le premier. À moins que vous ne le preniez de vitesse…'
          : 'Pas encore de secret : lancez une intrigue, vivez-la, et scellez-en le souvenir.'}
      </ThemedText>
      <PrimaryLink href="/soiree">{role === 'passager' ? 'À votre tour de surprendre' : 'Lancer une intrigue'}</PrimaryLink>
    </>
  );
}

// The patina of time: the newest relic shines, each older one a little dimmer and greyer, down to a floor.
function patina(age: number) {
  const t = Math.min(age, 3) / 3;
  return {
    photo: `grayscale(${20 + 80 * t}%) sepia(${10 - 10 * t}%) brightness(${85 - 10 * t}%)`,
    photoOpacity: 1 - 0.4 * t,
    text: 0.75 - 0.25 * t,
    card: 1 - 0.4 * t,
    border: 0.18 - 0.08 * t,
  };
}

function Relic({ row, age, photos, onDeleted }: { row: EveningHistoryRow; age: number; photos: Record<string, string>; onDeleted: () => void }) {
  const theme = useTheme();
  const p = patina(age);
  const pages = row.souvenirs ?? [];
  const photo = pages.map((s) => s.photo && photos[s.photo]).find(Boolean);
  const notes = pages.map((s) => s.note).filter(Boolean);
  const open = () => router.push({ pathname: '/livre', params: { soiree: row.page_name } });
  return (
    <Pressable onPress={open} style={styles.entry}>
      <View style={[styles.dot, age === 0 ? { backgroundColor: theme.gold, boxShadow: `0 0 8px ${theme.gold}` } : styles.dimDot]} />
      <ThemedText style={[styles.date, { color: theme.gold, opacity: age === 0 ? 1 : 0.6 }]}>
        INTRIGUE SCELLÉE • {row.day ? monthYear(row.day) : 'DATE LIBRE'}
      </ThemedText>
      <ThemedText style={[styles.name, { color: theme.cream, opacity: age === 0 ? 1 : 0.8 }]}>{row.secret_title ?? row.title}</ThemedText>
      <View style={[styles.card, { backgroundColor: `rgba(8, 26, 19, ${p.card})`, borderColor: `rgba(219, 193, 140, ${p.border})` }]}>
        {photo ? (
          <View style={[styles.photo, { opacity: p.photoOpacity }]}>
            <View style={[StyleSheet.absoluteFill, { filter: p.photo }]}>
              <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} />
            </View>
            {/* A veil rising from the card's velvet, so no photo breaks the night. */}
            <Svg style={StyleSheet.absoluteFill} preserveAspectRatio="none" viewBox="0 0 1 1">
              <Defs>
                <LinearGradient id={`fade-${row.id}`} x1="0" y1="1" x2="0" y2="0">
                  <Stop offset="0" stopColor={theme.velvet} stopOpacity={0.8} />
                  <Stop offset="0.5" stopColor={theme.velvet} stopOpacity={0} />
                </LinearGradient>
              </Defs>
              <Rect width="1" height="1" fill={`url(#fade-${row.id})`} />
            </Svg>
          </View>
        ) : null}
        {notes.map((n, i) => (
          <ThemedText key={i} style={[styles.note, { color: theme.cream, opacity: p.text }]}>« {n} »</ThemedText>
        ))}
      </View>
      <DeleteEvening row={row} onDeleted={onDeleted} />
    </Pressable>
  );
}

// Not a relic yet: an evening to come (its revelation), or one whose book still waits to be sealed.
function Anchor({ row, onDeleted }: { row: EveningHistoryRow; onDeleted: () => void }) {
  const theme = useTheme();
  const role = eveningRole(row, useCouple().userId);
  const ahead = !!row.day && row.day >= isoDay(new Date());
  const href = { pathname: ahead ? '/revelation' : '/livre', params: { soiree: row.page_name } } as const;
  // To the passager, an evening to come keeps its secret here too: only its secret name, never its plain title.
  const hidden = ahead && role === 'passager';
  return (
    <Pressable onPress={() => router.push(href)} style={styles.entry}>
      <View style={[styles.dot, styles.hollow, { borderColor: theme.accent, backgroundColor: theme.background }]} />
      <ThemedText style={[styles.date, { color: theme.accent, opacity: 0.8 }]}>
        {ahead ? 'À VENIR' : 'À SCELLER'} • {row.day ? longDay(row.day).toUpperCase() : 'DATE LIBRE'}
      </ThemedText>
      <ThemedText style={[styles.name, { color: theme.cream, opacity: 0.8 }]}>{row.secret_title ?? (hidden ? 'Une intrigue en préparation' : row.title)}</ThemedText>
      <TextLink href={href}>
        {ahead ? (role === 'passager' ? 'Voir les indices →' : 'Voir la feuille de route →') : 'Ouvrir le Livre des Secrets →'}
      </TextLink>
      <DeleteEvening row={row} onDeleted={onDeleted} />
    </Pressable>
  );
}

// A past evening can be struck from the archives (its instigateur only), after a confirmation.
function DeleteEvening({ row, onDeleted }: { row: EveningHistoryRow; onDeleted: () => void }) {
  const role = eveningRole(row, useCouple().userId);
  const theme = useTheme();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (role !== 'instigateur' || (row.day && row.day >= isoDay(new Date()))) return null;
  const run = async () => {
    setBusy(true);
    setError('');
    try {
      await deleteEvening(row.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };
  return (
    <View style={styles.delete}>
      {confirm ? (
        <>
          <ThemedText type="small" style={{ color: theme.creamSoft }}>Cette soirée et son livre seront effacés pour de bon.</ThemedText>
          <View style={styles.deleteRow}>
            <TextButton onPress={() => setConfirm(false)}>Annuler</TextButton>
            <TextButton onPress={run}>{busy ? 'Suppression…' : 'Oui, supprimer'}</TextButton>
          </View>
        </>
      ) : (
        <TextButton onPress={() => setConfirm(true)}>Supprimer cette soirée</TextButton>
      )}
      {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
    </View>
  );
}

const DOT = 8;
const LINE_X = 17;

const styles = StyleSheet.create({
  thread: { gap: Spacing.five, paddingTop: Spacing.two },
  line: { position: 'absolute', left: LINE_X, top: Spacing.three, bottom: Spacing.three, width: 1, backgroundColor: 'rgba(219, 193, 140, 0.2)' },
  entry: { paddingLeft: 40 },
  dot: { position: 'absolute', left: LINE_X - DOT / 2 + 0.5, top: 5, width: DOT, height: DOT, borderRadius: DOT / 2, zIndex: 1 },
  dimDot: { backgroundColor: 'rgba(219, 193, 140, 0.4)' },
  hollow: { borderWidth: 1 },
  date: { fontFamily: Fonts.sansBold, fontSize: 10, lineHeight: 16, letterSpacing: 1.6 },
  name: { fontFamily: Fonts.heading, fontSize: 22, lineHeight: 27, marginTop: 2 },
  card: { marginTop: Spacing.three, padding: Spacing.three, borderRadius: Radius.tile, borderWidth: 1, gap: Spacing.three },
  photo: { width: '100%', aspectRatio: 16 / 10, borderRadius: 16, overflow: 'hidden', borderWidth: 1, borderColor: 'rgba(219, 193, 140, 0.08)' },
  note: { fontFamily: Fonts.headingItalic, fontSize: 17, lineHeight: 23 },
  delete: { marginTop: Spacing.two, gap: Spacing.one },
  deleteRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three },
  footer: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderTopWidth: 1, paddingTop: Spacing.three },
});
