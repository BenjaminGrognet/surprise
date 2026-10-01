import { useEffect, useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, View } from 'react-native';

import { TextButton } from '@/components/buttons';
import { Countdown, IntrigueCard } from '@/components/intrigue-card';
import { formatPrice, imageUri, place } from '@/components/route-result';
import { ThemedText } from '@/components/themed-text';
import { Veil } from '@/components/veil';
import { Fonts, Spacing } from '@/constants/theme';
import { useNow } from '@/hooks/use-now';
import { useTheme } from '@/hooks/use-theme';
import { bookedSteps, saveBookedSteps } from '@/lib/account';
import type { SoireeRoute, SoireeStep } from '@/lib/api';
import { cluesFor, inTime, nextClue, shownClues } from '@/lib/clues';
import { formatTime, longDay } from '@/lib/dates';

const ROLE_LABELS: Record<SoireeStep['role'], string> = { repas: 'Dîner', verre: 'Un verre', sortie: 'Sortie', nuit: 'La nuit' };

type Tab = 'aventure' | 'coulisses';

// The organiser's side of a kept evening: a quiet header (the countdown, the whole budget once), then
// two tabs — the evening itself (L'Aventure) apart from the bookings and what the partner sees (Les Coulisses).
export function Organiser({ route, pageName, secretTitle }: { route: SoireeRoute; pageName: string; secretTitle: string }) {
  const now = useNow();
  const [tab, setTab] = useState<Tab>('aventure');
  const [booked, setBooked] = useState<string[]>([]);
  const [error, setError] = useState('');
  const start = Date.parse(route.start);
  const steps = [...route.steps, ...(route.night ? [route.night] : [])];
  const toBook = steps.filter((s) => s.booking_action === 'reserver' && s.booking_url);
  const left = toBook.filter((s) => !booked.includes(s.id)).length;

  useEffect(() => {
    bookedSteps(pageName, route.index).then(setBooked).catch(() => {});
  }, [pageName, route.index]);

  function toggle(id: string) {
    const before = booked;
    const next = booked.includes(id) ? booked.filter((b) => b !== id) : [...booked, id];
    setBooked(next);
    setError('');
    saveBookedSteps(pageName, route.index, next).catch((e: Error) => {
      setBooked(before);
      setError(e.message);
    });
  }

  return (
    <>
      <IntrigueCard>
        <ThemedText type="eyebrow" style={styles.center}>Feuille de route · {longDay(route.day)}</ThemedText>
        <ThemedText type="title" style={styles.center}>{secretTitle}</ThemedText>
        {now < start ? <Countdown to={start} now={now} /> : <ThemedText type="subtitle">Le rideau est levé</ThemedText>}
        <Badge>{`${route.price_estimated ? '≈ ' : ''}${route.price.toFixed(0)} € à deux`}</Badge>
      </IntrigueCard>

      <Tabs tab={tab} onTab={setTab} pending={left} />

      {tab === 'aventure' ? (
        <Aventure route={route} steps={steps} />
      ) : (
        <Coulisses route={route} secretTitle={secretTitle} toBook={toBook} booked={booked} onToggle={toggle} error={error} now={now} />
      )}
    </>
  );
}

function Badge({ children }: { children: string }) {
  const theme = useTheme();
  return (
    <View style={[styles.badge, { borderColor: theme.accentSoft }]}>
      <ThemedText type="small" themeColor="accentInk">{children}</ThemedText>
    </View>
  );
}

function Tabs({ tab, onTab, pending }: { tab: Tab; onTab: (tab: Tab) => void; pending: number }) {
  const theme = useTheme();
  const item = (key: Tab, title: string, sub: string, dot?: boolean) => {
    const active = tab === key;
    return (
      <Pressable
        key={key}
        onPress={() => onTab(key)}
        accessibilityRole="tab"
        accessibilityState={{ selected: active }}
        style={[styles.tab, { borderBottomColor: active ? theme.accent : 'transparent' }]}>
        <View style={styles.tabTitle}>
          <ThemedText style={[styles.tabLabel, { color: active ? theme.accentInk : theme.textSecondary }]}>{title}</ThemedText>
          {dot ? <View style={[styles.tabDot, { backgroundColor: theme.accent }]} /> : null}
        </View>
        <ThemedText type="small" themeColor="textSecondary" style={styles.tabSub}>{sub}</ThemedText>
      </Pressable>
    );
  };
  return (
    <View style={[styles.tabs, { borderBottomColor: theme.line }]} accessibilityRole="tablist">
      {item('aventure', "L'Aventure", 'Jour J')}
      {item('coulisses', 'Les Coulisses', pending ? `${pending} à réserver` : 'Logistique & résas', pending > 0)}
    </View>
  );
}

// L'Aventure: the evening as a silk thread, a fine gold line with each step hung on a glowing anchor.
function Aventure({ route, steps }: { route: SoireeRoute; steps: SoireeStep[] }) {
  return (
    <View style={styles.section}>
      {/* The title alone: the pitch would repeat the steps and the price shown below. */}
      <ThemedText type="subtitle">{route.title}</ThemedText>
      <SilkThread steps={steps} />
    </View>
  );
}

function SilkThread({ steps }: { steps: SoireeStep[] }) {
  const theme = useTheme();
  return (
    <View style={styles.thread}>
      <View style={[styles.threadLine, { backgroundColor: theme.accentSoft }]} />
      {steps.map((step, i) => (
        <View key={step.id + i}>
          {i > 0 ? <Hop previous={steps[i - 1]} step={step} /> : null}
          <ThreadStep step={step} />
        </View>
      ))}
    </View>
  );
}

function ThreadStep({ step }: { step: SoireeStep }) {
  const theme = useTheme();
  const [more, setMore] = useState(false);
  const [photo, setPhoto] = useState(false);
  const maps = `https://www.google.com/maps/search/?api=1&query=${step.lat},${step.lon}`;
  // ponytail: length stands for "cut at three lines"; measure the text layout if it misfires.
  const long = (step.text?.length ?? 0) > 160;
  return (
    <View style={styles.anchorRow}>
      <View style={[styles.anchor, { borderColor: theme.accent, backgroundColor: theme.background }]}>
        <View style={[styles.anchorCore, { backgroundColor: theme.accent }]} />
      </View>
      <View style={styles.anchorBody}>
        <View style={styles.stepHead}>
          <View style={styles.stepHeadText}>
            <ThemedText type="eyebrow">
              {formatTime(step.start)} → {formatTime(step.end)} · {ROLE_LABELS[step.role]}
            </ThemedText>
            <ThemedText style={styles.stepTitle}>{step.title}</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">{place(step)}</ThemedText>
          </View>
          {/* The instigateur sees each place at a glance; a touch opens it wide. */}
          {step.image_url ? (
            <Pressable onPress={() => setPhoto(!photo)} accessibilityLabel={photo ? "Réduire l'image" : "Agrandir l'image"}>
              <Image source={{ uri: imageUri(step.image_url) }} style={[styles.thumb, { borderColor: theme.accentFaint }]} />
            </Pressable>
          ) : null}
        </View>
        {photo && step.image_url ? (
          <Pressable onPress={() => setPhoto(false)} accessibilityLabel="Réduire l'image">
            <Image source={{ uri: imageUri(step.image_url) }} style={styles.photo} />
          </Pressable>
        ) : null}
        {step.text ? (
          <ThemedText type="small" numberOfLines={more ? undefined : 3} style={styles.stepText}>{step.text}</ThemedText>
        ) : null}
        {long ? <TextButton onPress={() => setMore(!more)}>{more ? '− Réduire' : '+ Lire la suite'}</TextButton> : null}
        <View style={styles.stepFoot}>
          <ThemedText type="small" themeColor="textSecondary">{formatPrice(step)}</ThemedText>
          <View style={styles.links}>
            {step.booking_url && step.booking_action !== 'reserver' ? (
              <TextLinkOut url={step.booking_url}>Le lieu →</TextLinkOut>
            ) : null}
            <TextLinkOut url={maps}>S&apos;y rendre →</TextLinkOut>
          </View>
        </View>
      </View>
    </View>
  );
}

function Hop({ previous, step }: { previous: SoireeStep; step: SoireeStep }) {
  const walking = step.distance_km <= 1.3;
  const distance = step.distance_km < 1 ? `${(step.distance_km * 1000).toFixed(0)} m` : `${step.distance_km.toFixed(1)} km`;
  const maps = `https://www.google.com/maps/dir/?api=1&origin=${previous.lat},${previous.lon}&destination=${step.lat},${step.lon}&travelmode=${walking ? 'walking' : 'transit'}`;
  return (
    <Pressable onPress={() => Linking.openURL(maps)} style={styles.hop}>
      <ThemedText type="small" themeColor="textSecondary" style={styles.hopText}>
        {walking ? 'à pied' : 'en métro'} · {step.travel_minutes} min · {distance}
      </ThemedText>
    </Pressable>
  );
}

function TextLinkOut({ url, children }: { url: string; children: string }) {
  return (
    <Pressable onPress={() => Linking.openURL(url)} accessibilityRole="link">
      <ThemedText type="smallBold" themeColor="accentInk">{children}</ThemedText>
    </Pressable>
  );
}

// Les Coulisses: the bookings to make, ticked off as they're done (kept on the account), and the
// partner's screen as they see it right now.
function Coulisses({
  route, secretTitle, toBook, booked, onToggle, error, now,
}: {
  route: SoireeRoute;
  secretTitle: string;
  toBook: SoireeStep[];
  booked: string[];
  onToggle: (id: string) => void;
  error: string;
  now: number;
}) {
  const theme = useTheme();
  const done = toBook.filter((s) => booked.includes(s.id)).length;
  return (
    <View style={styles.section}>
      <View style={styles.block}>
        <View style={styles.blockHead}>
          <ThemedText type="eyebrow">À réserver avant le jour J</ThemedText>
          {toBook.length ? (
            <ThemedText type="small" themeColor={done === toBook.length ? 'ok' : 'textSecondary'}>
              {done === toBook.length ? 'Tout est réservé' : `${done} sur ${toBook.length}`}
            </ThemedText>
          ) : null}
        </View>
        {toBook.length ? (
          toBook.map((s) => {
            const isBooked = booked.includes(s.id);
            return (
              <View key={s.id} style={[styles.booking, { borderBottomColor: theme.line }]}>
                <Pressable
                  onPress={() => onToggle(s.id)}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: isBooked }}
                  accessibilityLabel={`${s.title} réservé`}
                  hitSlop={8}
                  style={[styles.box, { borderColor: isBooked ? theme.accent : theme.textSecondary, backgroundColor: isBooked ? theme.accent : 'transparent' }]}>
                  {isBooked ? <ThemedText style={[styles.boxMark, { color: theme.onAccent }]}>✓</ThemedText> : null}
                </Pressable>
                <View style={styles.bookingBody}>
                  <ThemedText type="smallBold" themeColor={isBooked ? 'accentInk' : undefined}>
                    {formatTime(s.start)} · {s.title}
                  </ThemedText>
                  <ThemedText type="small" themeColor="textSecondary">
                    {isBooked ? 'Réservé' : `${formatPrice(s)} · ${place(s)}`}
                  </ThemedText>
                </View>
                {isBooked ? null : <TextLinkOut url={s.booking_url!}>{s.role === 'repas' ? 'Valider la table →' : 'Réserver →'}</TextLinkOut>}
              </View>
            );
          })
        ) : (
          <ThemedText type="small" themeColor="textSecondary">Rien à réserver : tout se joue sur place.</ThemedText>
        )}
        {error ? <ThemedText type="small" themeColor="danger">{error}</ThemedText> : null}
      </View>

      <PartnerScreen route={route} secretTitle={secretTitle} now={now} />
    </View>
  );
}

// A facsimile of the surprised partner's screen, framed in brushed gold: the clues they hold, as quotes.
function PartnerScreen({ route, secretTitle, now }: { route: SoireeRoute; secretTitle: string; now: number }) {
  const theme = useTheme();
  const clues = cluesFor(route);
  const shown = shownClues(clues, now);
  const next = nextClue(clues, now);
  return (
    <View style={[styles.frameOuter, { borderColor: theme.accent }]}>
      <View style={[styles.frameInner, { borderColor: theme.accentFaint, backgroundColor: theme.backgroundElement }]}>
        <ThemedText style={[styles.shadowTitle, { color: theme.accentInk }]}>Dans l&apos;ombre du Passager…</ThemedText>
        <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
          Ce que votre partenaire lit en ce moment. Vous seul voyez le reste.
        </ThemedText>
        <ThemedText type="subtitle" style={styles.center}>{secretTitle}</ThemedText>
        {shown.map((c) => (
          <View key={c.text} style={[styles.quote, { borderLeftColor: theme.accentSoft }]}>
            <ThemedText type="clue">« {c.text} »</ThemedText>
          </View>
        ))}
        {next ? (
          <View style={[styles.quote, { borderLeftColor: theme.line }]}>
            <Veil widths={['85%', '55%']} />
            <ThemedText type="small" themeColor="textSecondary">Prochain indice {inTime(next.at, now)}</ThemedText>
          </View>
        ) : null}
      </View>
    </View>
  );
}

const ANCHOR = 15;

const styles = StyleSheet.create({
  center: { textAlign: 'center' },
  badge: { borderWidth: 1, borderRadius: 999, paddingVertical: 4, paddingHorizontal: Spacing.three },
  tabs: { flexDirection: 'row', borderBottomWidth: 1, marginTop: -Spacing.two },
  tab: { flex: 1, alignItems: 'center', paddingVertical: Spacing.two, borderBottomWidth: 1, marginBottom: -1, gap: 2 },
  tabTitle: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  tabLabel: { fontFamily: Fonts.headingItalic, fontSize: 17, lineHeight: 22 },
  tabDot: { width: 5, height: 5, borderRadius: 3 },
  tabSub: { fontSize: 11, lineHeight: 14, letterSpacing: 0.5 },
  section: { gap: Spacing.four },
  thread: { position: 'relative' },
  threadLine: { position: 'absolute', left: ANCHOR / 2 - 0.5, top: ANCHOR / 2, bottom: Spacing.four, width: 1 },
  anchorRow: { flexDirection: 'row', gap: Spacing.three, paddingBottom: Spacing.two },
  anchor: {
    width: ANCHOR, height: ANCHOR, borderRadius: ANCHOR / 2, borderWidth: 1, marginTop: 2,
    alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 10px rgba(212, 175, 55, 0.55)',
  },
  anchorCore: { width: 5, height: 5, borderRadius: 3 },
  anchorBody: { flex: 1, gap: Spacing.one },
  stepTitle: { fontFamily: Fonts.heading, fontSize: 19, lineHeight: 25 },
  stepText: { marginTop: Spacing.one },
  stepHead: { flexDirection: 'row', gap: Spacing.three, alignItems: 'flex-start' },
  stepHeadText: { flex: 1, gap: Spacing.one },
  thumb: { width: 84, height: 84, borderWidth: 1, borderTopLeftRadius: 20, borderBottomRightRadius: 20, borderTopRightRadius: 4, borderBottomLeftRadius: 4 },
  photo: {
    width: '100%', aspectRatio: 16 / 9, marginTop: Spacing.one,
    borderTopLeftRadius: 28, borderBottomRightRadius: 28, borderTopRightRadius: 4, borderBottomLeftRadius: 4,
  },
  stepFoot: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: Spacing.two, marginTop: Spacing.one },
  links: { flexDirection: 'row', gap: Spacing.three },
  hop: { paddingLeft: ANCHOR + Spacing.three, paddingTop: Spacing.one, paddingBottom: Spacing.three },
  hopText: { fontFamily: Fonts.headingItalic, fontSize: 13 },
  block: { gap: Spacing.three },
  blockHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  booking: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, paddingBottom: Spacing.three, borderBottomWidth: 1 },
  bookingBody: { flex: 1, gap: 2 },
  box: { width: 22, height: 22, borderRadius: 5, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  boxMark: { fontSize: 13, lineHeight: 16 },
  frameOuter: { borderWidth: 1, borderRadius: 26, padding: 5 },
  frameInner: { borderWidth: 1, borderRadius: 21, padding: Spacing.four, gap: Spacing.three },
  shadowTitle: { fontFamily: Fonts.headingItalic, fontSize: 22, lineHeight: 30, textAlign: 'center' },
  quote: { borderLeftWidth: 1, paddingLeft: Spacing.three, gap: Spacing.one },
});
