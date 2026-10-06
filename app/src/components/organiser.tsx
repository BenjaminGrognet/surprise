import { useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import { TextButton } from '@/components/buttons';
import { CompassGuide } from '@/components/compass-guide';
import { Countdown, PageCard } from '@/components/intrigue-card';
import { NotifyAsk } from '@/components/notify-ask';
import { PassagerWeek } from '@/components/passager-week';
import { formatPrice, routePrice } from '@/lib/prices';
import { StepImage } from '@/components/step-image';
import { TasteVote } from '@/components/taste-vote';
import { ThemedText } from '@/components/themed-text';
import { busyStyle } from '@/components/spinner';
import { Veil } from '@/components/veil';
import { Fonts, Spacing } from '@/constants/theme';
import { useNow } from '@/hooks/use-now';
import { useTastes } from '@/hooks/use-tastes';
import { useTheme } from '@/hooks/use-theme';
import { bookedSteps, saveBookedSteps, type Vote } from '@/lib/account';
import { place, redoPart, refusal, type SoireeRoute, type SoireeStep } from '@/lib/api';
import { cluesFor, inTime, nextClue, shownClues, type RevealMode } from '@/lib/clues';
import { formatTime, longDay } from '@/lib/dates';
import { syncPhone } from '@/lib/phone';

const ROLE_LABELS: Record<SoireeStep['role'], string> = { repas: 'Dîner', verre: 'Un verre', sortie: 'Sortie', nuit: 'La nuit' };

type Tab = 'aventure' | 'coulisses';

// The organiser's side of a kept evening: a quiet header (the countdown, the whole budget once), the compass on the
// day itself, then two tabs — the evening itself (L'Aventure) apart from the bookings and what the partner sees
// (Les Coulisses).
export function Organiser({
  route, pageName, secretTitle, mode, onRoute,
}: { route: SoireeRoute; pageName: string; secretTitle: string; mode: RevealMode; onRoute: (route: SoireeRoute) => void }) {
  const now = useNow();
  const [tab, setTab] = useState<Tab>('aventure');
  const [booked, setBooked] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [swapping, setSwapping] = useState<string | null>(null);
  const [swapNotice, setSwapNotice] = useState('');
  const tastes = useTastes();
  const start = Date.parse(route.start);
  const steps = [...route.steps, ...(route.night ? [route.night] : [])];
  const toBook = steps.filter((s) => s.booking_action === 'reserver' && s.booking_url);
  const left = toBook.filter((s) => !booked.includes(s.id)).length;

  useEffect(() => {
    bookedSteps(pageName).then(setBooked).catch(() => {});
  }, [pageName]);

  // The instigateur's reminders, the passager's week and the widget, told again on this phone as the evening changes: kept, a plan
  // B, another reveal mode; a booking ticked, once saved (toggle).
  useEffect(() => {
    syncPhone();
  }, [route, mode]);

  // Plan B: another activity in place of an upcoming step, the rest of the evening kept. What was booked for the old one goes.
  async function swap(step: SoireeStep) {
    if (!step.redo) return;
    setSwapping(step.id);
    setSwapNotice('');
    try {
      const next = (await redoPart(pageName, step.redo)).routes[0];
      if (!next) throw new Error('Cette soirée a changé : rouvrez-la.');
      if (booked.includes(step.id)) {
        const rest = booked.filter((b) => b !== step.id);
        setBooked(rest);
        saveBookedSteps(pageName, rest).catch(() => {});
      }
      onRoute(next);
      setSwapNotice('Plan B en place. Pensez à refaire la réservation si besoin.');
    } catch (error) {
      setSwapNotice(refusal(error) ?? 'Pas de plan B pour le moment : réessayez dans un instant.');
    } finally {
      setSwapping(null);
    }
  }

  function toggle(id: string) {
    const before = booked;
    const next = booked.includes(id) ? booked.filter((b) => b !== id) : [...booked, id];
    setBooked(next);
    setError('');
    saveBookedSteps(pageName, next).then(() => syncPhone()).catch((e: Error) => {
      setBooked(before);
      setError(e.message);
    });
  }

  return (
    <>
      <PageCard back badge={routePrice(route)} title={secretTitle}>
        <ThemedText type="eyebrow">Feuille de route · {longDay(route.day)}</ThemedText>
        {now < start ? <Countdown to={start} now={now} /> : <ThemedText type="subtitle">Le rideau est levé</ThemedText>}
      </PageCard>

      <CompassGuide route={route} />

      {now < start ? (
        <NotifyAsk text={`Soyez prévenu(e) : les réservations encore à faire, l'heure du départ le jour J, et chaque indice que reçoit ${route.formule === 'squad' ? 'la bande' : 'votre passager'}.`} />
      ) : null}

      <Tabs tab={tab} onTab={setTab} pending={left} />

      {tab === 'aventure' ? (
        <Aventure route={route} steps={steps} now={now} swapping={swapping} notice={swapNotice || tastes.error} onSwap={swap} votes={tastes.votes} onVote={tastes.vote} />
      ) : (
        <Coulisses route={route} pageName={pageName} secretTitle={secretTitle} toBook={toBook} booked={booked} onToggle={toggle} error={error} now={now} mode={mode} />
      )}
    </>
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

// The instigateur's votes on the steps (hooks/use-tastes.ts), for the evenings to come.
type Votes = { votes: Record<string, Vote>; onVote: (step: SoireeStep, vote: Vote) => void };

// L'Aventure: the evening as a silk thread, a fine gold line with each step hung on a glowing anchor.
function Aventure({
  route, steps, now, swapping, notice, onSwap, votes, onVote,
}: { route: SoireeRoute; steps: SoireeStep[]; now: number; swapping: string | null; notice: string; onSwap: (step: SoireeStep) => void } & Votes) {
  return (
    <View style={styles.section}>
      {/* The title alone: the pitch would repeat the steps and the price shown below. */}
      <ThemedText type="subtitle">{route.title}</ThemedText>
      {notice ? <ThemedText type="small" themeColor="accentInk">{notice}</ThemedText> : null}
      <SilkThread steps={steps} personnes={route.personnes} now={now} swapping={swapping} onSwap={onSwap} votes={votes} onVote={onVote} />
    </View>
  );
}

function SilkThread({
  steps, personnes, now, swapping, onSwap, votes, onVote,
}: { steps: SoireeStep[]; personnes?: number; now: number; swapping: string | null; onSwap: (step: SoireeStep) => void } & Votes) {
  const theme = useTheme();
  return (
    <View style={styles.thread}>
      <View style={[styles.threadLine, { backgroundColor: theme.accentSoft }]} />
      {steps.map((step, i) => (
        <View key={step.id + i}>
          {i > 0 ? <Hop previous={steps[i - 1]} step={step} /> : null}
          <ThreadStep
            step={step}
            personnes={personnes}
            busy={swapping === step.id}
            onSwap={step.redo && Date.parse(step.start) > now && swapping === null ? () => onSwap(step) : null}
            vote={votes[step.id]}
            onVote={step.role === 'nuit' ? null : (v) => onVote(step, v)}
          />
        </View>
      ))}
    </View>
  );
}

function ThreadStep({
  step, personnes, busy, onSwap, vote, onVote,
}: { step: SoireeStep; personnes?: number; busy: boolean; onSwap: (() => void) | null; vote?: Vote; onVote: ((vote: Vote) => void) | null }) {
  const theme = useTheme();
  const [more, setMore] = useState(false);
  const [photo, setPhoto] = useState(false);
  const maps = `https://www.google.com/maps/search/?api=1&query=${step.lat},${step.lon}`;
  // ponytail: length stands for "cut at three lines"; measure the text layout if it misfires.
  const long = (step.text?.length ?? 0) > 160;
  return (
    <View style={[styles.anchorRow, busyStyle(busy)]}>
      <View style={[styles.anchor, { borderColor: theme.accent, backgroundColor: theme.background, boxShadow: `0 0 10px ${theme.glow}` }]}>
        <View style={[styles.anchorCore, { backgroundColor: theme.accent }]} />
      </View>
      <View style={styles.anchorBody}>
        <View style={styles.stepHead}>
          <View style={styles.stepHeadText}>
            <ThemedText type="eyebrow" themeColor="gold">
              {formatTime(step.start)} → {formatTime(step.end)} · {ROLE_LABELS[step.role]}
            </ThemedText>
            <ThemedText style={styles.stepTitle}>{step.title}</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">{place(step)}</ThemedText>
          </View>
          {/* The instigateur sees each place at a glance; a touch opens it wide. */}
          <Pressable onPress={() => setPhoto(!photo)} accessibilityLabel={photo ? "Réduire l'image" : "Agrandir l'image"}>
            <StepImage step={step} style={[styles.thumb, { borderColor: theme.accentFaint }]} />
          </Pressable>
        </View>
        {photo ? (
          <Pressable onPress={() => setPhoto(false)} accessibilityLabel="Réduire l'image">
            <StepImage step={step} style={styles.photo} />
          </Pressable>
        ) : null}
        {step.text ? (
          <ThemedText type="small" numberOfLines={more ? undefined : 3} style={styles.stepText}>{step.text}</ThemedText>
        ) : null}
        {long ? <TextButton onPress={() => setMore(!more)}>{more ? '− Réduire' : '+ Lire la suite'}</TextButton> : null}
        <View style={styles.stepFoot}>
          <ThemedText type="small" themeColor="textSecondary">{formatPrice(step, personnes)}</ThemedText>
          <View style={styles.links}>
            {step.booking_url && step.booking_action !== 'reserver' ? (
              <TextLinkOut url={step.booking_url}>Le lieu →</TextLinkOut>
            ) : null}
            <TextLinkOut url={maps}>S&apos;y rendre →</TextLinkOut>
            {onSwap || busy ? <TextButton busy={busy} onPress={onSwap ?? (() => {})}>{busy ? 'On cherche un plan B…' : '↻ Plan B'}</TextButton> : null}
          </View>
        </View>
        {/* For the evenings to come: whether this kind of outing is theirs. */}
        {onVote ? <TasteVote vote={vote} onVote={onVote} said /> : null}
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

// Les Coulisses: the bookings to make, ticked off as they're done (kept on the account), the partner's screen as they
// see it right now, and their week as their phone tells it.
function Coulisses({
  route, pageName, secretTitle, toBook, booked, onToggle, error, now, mode,
}: {
  route: SoireeRoute;
  pageName: string;
  secretTitle: string;
  toBook: SoireeStep[];
  booked: string[];
  onToggle: (id: string) => void;
  error: string;
  now: number;
  mode: RevealMode;
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
                    {isBooked ? 'Réservé' : `${formatPrice(s, route.personnes)} · ${place(s)}`}
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

      <PartnerScreen route={route} secretTitle={secretTitle} now={now} mode={mode} />

      <PassagerWeek route={route} mode={mode} secretTitle={secretTitle} pageName={pageName} now={now} />
    </View>
  );
}

// A facsimile of the surprised partner's screen, framed in brushed gold: the clues they hold, as quotes.
function PartnerScreen({ route, secretTitle, now, mode }: { route: SoireeRoute; secretTitle: string; now: number; mode: RevealMode }) {
  const theme = useTheme();
  const band = route.formule === 'squad';
  const clues = cluesFor(route, mode);
  const shown = shownClues(clues, now);
  const next = nextClue(clues, now);
  return (
    <View style={[styles.frameOuter, { borderColor: theme.goldSoft }]}>
      <View style={[styles.frameInner, { borderColor: theme.line, backgroundColor: theme.backgroundElement }]}>
        <ThemedText style={[styles.shadowTitle, { color: theme.gold }]}>{band ? 'Dans l’ombre de la bande…' : 'Dans l’ombre du Passager…'}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
          {band ? 'Ce que lit la bande en ce moment. Vous et vos complices voyez le reste.' : 'Ce que votre partenaire lit en ce moment. Vous seul voyez le reste.'}
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
  tabs: { flexDirection: 'row', borderBottomWidth: 1, marginTop: -Spacing.two },
  tab: { flex: 1, alignItems: 'center', paddingVertical: Spacing.two, borderBottomWidth: 1, marginBottom: -1, gap: 2 },
  tabTitle: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  tabLabel: { fontFamily: Fonts.headingItalic, fontSize: 21, lineHeight: 26 },
  tabDot: { width: 5, height: 5, borderRadius: 3 },
  tabSub: { fontSize: 11, lineHeight: 14, letterSpacing: 0.5 },
  section: { gap: Spacing.four },
  thread: { position: 'relative' },
  threadLine: { position: 'absolute', left: ANCHOR / 2 - 0.5, top: ANCHOR / 2, bottom: Spacing.four, width: 1 },
  anchorRow: { flexDirection: 'row', gap: Spacing.three, paddingBottom: Spacing.two },
  anchor: {
    width: ANCHOR, height: ANCHOR, borderRadius: ANCHOR / 2, borderWidth: 1, marginTop: 2,
    alignItems: 'center', justifyContent: 'center',
  },
  anchorCore: { width: 5, height: 5, borderRadius: 3 },
  anchorBody: { flex: 1, gap: Spacing.one },
  stepTitle: { fontFamily: Fonts.heading, fontSize: 23, lineHeight: 28 },
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
  hopText: { fontFamily: Fonts.headingItalic, fontSize: 16 },
  block: { gap: Spacing.three },
  blockHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  booking: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, paddingBottom: Spacing.three, borderBottomWidth: 1 },
  bookingBody: { flex: 1, gap: 2 },
  box: { width: 22, height: 22, borderRadius: 5, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  boxMark: { fontSize: 13, lineHeight: 16 },
  frameOuter: { borderWidth: 1, borderRadius: 30, padding: 5 },
  frameInner: { borderWidth: 1, borderRadius: 25, padding: Spacing.four, gap: Spacing.three },
  shadowTitle: { fontFamily: Fonts.headingItalic, fontSize: 27, lineHeight: 32, textAlign: 'center' },
  quote: { borderLeftWidth: 1, paddingLeft: Spacing.three, gap: Spacing.one },
});
