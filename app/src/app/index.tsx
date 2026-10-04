import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

import { PrimaryLink, TextButton } from '@/components/buttons';
import { CardHead, countdownLabel, IntrigueCard, PageCard } from '@/components/intrigue-card';
import { imageUri, place } from '@/components/route-result';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Icon } from '@/components/ui-icons';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { useNow } from '@/hooks/use-now';
import { useTheme } from '@/hooks/use-theme';
import { accountProfile, eveningsHistory, upcomingEvening, type EveningHistoryRow } from '@/lib/account';
import { getSoireeState, type Profile, type SoireeRoute } from '@/lib/api';
import { cluesFor, dayHint, inTime, nextClue, revealAt, revealMode, stepRevealed } from '@/lib/clues';
import { complicity, type Complicity } from '@/lib/complicity';
import type { AccountRole } from '@/lib/couple';
import { formatTime, isoDay, longDay, shortDay } from '@/lib/dates';
import { forgetProfile, rememberedProfile } from '@/lib/local-store';
import { curtainFalls } from '@/lib/souvenirs';
import { supabaseConfigured } from '@/lib/supabase';

const capitalised = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

// "Le Tableau des Complots", cut like a membership: no bar above, the page opens on the next mystery evening as the
// couple's card — its countdown in gold —, then a status line, the evening's first step, and the complicity gauge.
// The passager gets the card, the status, the step veiled and the gauge: the instigateur makes the profile and
// orders the evenings.
export default function AccueilScreen() {
  const { role } = useCouple();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [upcoming, setUpcoming] = useState<{ row: EveningHistoryRow; route: SoireeRoute | null } | null>(null);
  const [gauge, setGauge] = useState<Complicity | null>(null);
  const [toSeal, setToSeal] = useState<EveningHistoryRow | null>(null);

  useEffect(() => {
    (async () => {
      // Signed in, only the account's own profile counts: never one left on this device by someone else.
      const known = supabaseConfigured
        ? (await accountProfile().catch(() => null))?.profile ?? null
        : (await rememberedProfile())?.profile ?? null;
      setProfile(known);
      if (supabaseConfigured) {
        const today = isoDay(new Date());
        const [row, history] = await Promise.all([
          upcomingEvening(today).catch(() => null),
          eveningsHistory().catch(() => []),
        ]);
        setGauge(complicity(history, today));
        // An evening of the past week whose book the account hasn't sealed yet.
        const weekAgo = new Date();
        weekAgo.setDate(weekAgo.getDate() - 7);
        setToSeal(history.find((r) => !!r.day && r.day < today && r.day >= isoDay(weekAgo) && !r.souvenirs?.length) ?? null);
        if (row) {
          const state = await getSoireeState(row.page_name).catch(() => null);
          setUpcoming({ row, route: state?.routes[0] ?? null });
        }
      }
      setLoaded(true);
    })();
  }, []);

  return (
    <Screen gap={Spacing.four}>
      {toSeal ? <BookCall row={toSeal} /> : null}

      <View style={styles.cardBlock}>
        {loaded ? (
          upcoming ? <NextIntrigue {...upcoming} role={role} /> : role === 'passager' ? <AwaitingIntrigue /> : <NoIntrigue />
        ) : (
          <IntrigueCard><View style={styles.placeholder} /></IntrigueCard>
        )}
        {upcoming ? <Status row={upcoming.row} route={upcoming.route} role={role} /> : null}
        {loaded && !upcoming && role === 'instigateur' ? <PrimaryLink wide href="/soiree">Lancer une nouvelle intrigue</PrimaryLink> : null}
      </View>

      {role === 'instigateur' && loaded && !profile ? <ProfileCall /> : null}
      {upcoming?.route ? <FirstStep row={upcoming.row} route={upcoming.route} role={role} /> : null}
      {gauge ? <Gauge gauge={gauge} /> : null}

      {role === 'instigateur' && profile ? (
        <View style={styles.links}>
          <TextButton onPress={() => forgetProfile().then(() => setProfile(null))}>Oublier ce profil</TextButton>
        </View>
      ) : null}
    </Screen>
  );
}

// The next evening as the couple's card: its secret name in italics and the account's tier, the clue of the
// day, then the day on the left and, in gold on the right, the time left.
function NextIntrigue({ row, route, role }: { row: EveningHistoryRow; route: SoireeRoute | null; role: AccountRole }) {
  const theme = useTheme();
  const now = useNow();
  // Its last step begun, the evening calls for its book.
  if (route && curtainFalls(route, now) && !row.souvenirs?.length) return <BookCall row={row} />;
  const start = route ? Date.parse(route.start) : null;
  const under = start != null && !!route && now >= start && now < Date.parse(route.end);
  const open = () => router.push({ pathname: '/revelation', params: { soiree: row.page_name } });
  return (
    <IntrigueCard onPress={open} align="start" label="Ouvrir la révélation">
      <View style={styles.member}>
        <CardHead badge={role === 'passager' ? 'Passager' : 'Instigateur'} title={row.secret_title ?? route?.secret_title ?? 'L’Inattendu vous attend…'} />
        {route ? (
          <ThemedText type="clue" style={[styles.cardClue, { color: theme.creamSoft }]} numberOfLines={3}>
            <ThemedText type="clue" style={{ color: theme.gold }}>✦ </ThemedText>
            {dayHint(route, now, revealMode(row.reveal_mode))}
          </ThemedText>
        ) : null}
        <View style={styles.cardFoot}>
          <View style={styles.cardColumn}>
            <ThemedText type="eyebrow">{under ? "L'intrigue a commencé" : 'Le jour J'}</ThemedText>
            <ThemedText style={styles.cardDay}>{row.day ? capitalised(longDay(row.day)) : 'Date à fixer'}</ThemedText>
          </View>
          {start != null && route ? (
            <View style={[styles.cardColumn, styles.cardRight]}>
              <ThemedText type="eyebrow">{under ? 'Depuis' : 'Dans'}</ThemedText>
              <ThemedText style={[styles.cardFigure, { color: theme.gold }]}>{under ? formatTime(route.start) : countdownLabel(start, now)}</ThemedText>
            </View>
          ) : null}
        </View>
      </View>
    </IntrigueCard>
  );
}

// The line under the card, a dot that breathes: who is in on the secret, or when the next clue comes.
function Status({ row, route, role }: { row: EveningHistoryRow; route: SoireeRoute | null; role: AccountRole }) {
  const theme = useTheme();
  const now = useNow();
  const invite = role === 'instigateur' && !row.passager;
  const next = role === 'passager' && route ? nextClue(cluesFor(route, revealMode(row.reveal_mode)), now) : null;
  const text = role === 'passager'
    ? next ? `Votre prochain indice arrive ${inTime(next.at, now)}` : 'Tous vos indices sont dévoilés'
    : row.passager ? 'Complices connectés : votre passager ne voit que les indices' : 'Votre passager n’a pas encore rejoint l’intrigue';
  const dot = invite ? theme.gold : theme.accent;
  const open = () => router.push({ pathname: '/revelation', params: { soiree: row.page_name } });
  return (
    <View style={styles.status}>
      <View style={[styles.statusDot, { backgroundColor: dot, boxShadow: `0 0 8px ${dot}` }]} />
      <ThemedText type="small" themeColor="textSecondary" style={styles.statusText}>{text}</ThemedText>
      {invite ? (
        <Pressable onPress={open} hitSlop={8}>
          <ThemedText type="smallBold" themeColor="accentInk">Inviter</ThemedText>
        </Pressable>
      ) : null}
    </View>
  );
}

// Le Livre des Secrets, at the end of the evening or the days after: a photo, a note, sealed.
function BookCall({ row }: { row: EveningHistoryRow }) {
  const open = () => router.push({ pathname: '/livre', params: { soiree: row.page_name } });
  return (
    <PageCard
      onPress={open}
      label="Ouvrir le Livre des Secrets"
      badge="À sceller"
      title="Le Livre des Secrets"
      text={`Le rideau tombe sur « ${row.secret_title ?? row.title} ». Déposez une photo et un mot avant qu'ils ne s'évaporent.`}>
      <ThemedText type="smallBold" themeColor="accentInk">Ouvrir le grimoire →</ThemedText>
    </PageCard>
  );
}

// The instigateur's welcome before any evening: three short paragraphs, set tight.
const PITCH = [
  'Bonjour, cher instigateur.\nConfiez-nous vos envies, votre humeur. Nous imaginons pour vous une soirée parisienne qui ne ressemble à aucune autre.',
  'Jusqu’au jour J, l’invité·e ne recevra que quelques indices, juste assez pour éveiller la curiosité sans dévoiler la destination.',
  'À vous le mystère, à nous la surprise.',
];

function NoIntrigue() {
  const theme = useTheme();
  return (
    <PageCard badge="Instigateur" title="Le prochain secret reste encore à écrire…">
      <View style={styles.pitch}>
        {PITCH.map((stanza) => (
          <ThemedText key={stanza} type="small" style={{ color: theme.creamSoft }}>{stanza}</ThemedText>
        ))}
      </View>
    </PageCard>
  );
}

// The passager, before any evening is kept: nothing to see yet, and that's the point.
function AwaitingIntrigue() {
  const theme = useTheme();
  return (
    <IntrigueCard align="start">
      <View style={styles.member}>
        <CardHead badge="Passager" title="Quelque chose se trame…" />
        <ThemedText style={{ color: theme.creamSoft }}>
          Dès que votre instigateur aura scellé une soirée, son compte à rebours et ses indices apparaîtront ici.
        </ThemedText>
      </View>
    </IntrigueCard>
  );
}

// No profile yet: the quiz first, two minutes, so the evenings fit the couple.
function ProfileCall() {
  const theme = useTheme();
  return (
    <Pressable
      onPress={() => router.push('/profil')}
      style={({ pressed }) => [styles.call, { backgroundColor: theme.backgroundElement, borderColor: theme.line }, pressed && styles.pressed]}>
      <View style={[styles.callIcon, { backgroundColor: theme.backgroundSelected }]}>
        <Icon name="coeur" size={20} color={theme.accent} />
      </View>
      <View style={styles.callText}>
        <ThemedText type="smallBold">D&apos;abord, faire notre profil</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">Deux minutes, pour des soirées à votre image</ThemedText>
      </View>
      <Icon name="suite" size={18} color={theme.textSecondary} />
    </Pressable>
  );
}

// The evening's step to come, in a photo: its hour in gold. The passager sees it veiled until it is revealed.
function FirstStep({ row, route, role }: { row: EveningHistoryRow; route: SoireeRoute; role: AccountRole }) {
  const theme = useTheme();
  const now = useNow();
  const steps = [...route.steps, ...(route.night ? [route.night] : [])];
  const step = steps.find((s) => Date.parse(s.end) > now) ?? steps[0];
  if (!step) return null;
  const mode = revealMode(row.reveal_mode);
  const veiled = role === 'passager' && !stepRevealed(route, step, now, mode);
  const tonight = route.day === isoDay(new Date(now));
  const open = () => router.push({ pathname: '/revelation', params: { soiree: row.page_name } });
  return (
    <View style={styles.section}>
      <View style={styles.sectionHead}>
        <ThemedText type="eyebrow">{tonight ? 'Ce soir' : steps.indexOf(step) === 0 ? 'Première étape' : 'Prochaine étape'}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{capitalised(shortDay(route.day))}</ThemedText>
      </View>
      <Pressable
        onPress={open}
        accessibilityLabel={veiled ? 'Une étape encore voilée' : step.title}
        style={({ pressed }) => [styles.photoCard, { backgroundColor: theme.backgroundElement, borderColor: theme.line }, pressed && styles.pressed]}>
        {step.image_url ? (
          <Image source={{ uri: imageUri(step.image_url) }} blurRadius={veiled ? 30 : 0} style={StyleSheet.absoluteFill} />
        ) : null}
        <View style={StyleSheet.absoluteFill} pointerEvents="none">
          <Svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 1 1">
            <Defs>
              <LinearGradient id="step-shade" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={theme.background} stopOpacity={0.35} />
                <Stop offset="0.45" stopColor={theme.background} stopOpacity={0.05} />
                <Stop offset="1" stopColor={theme.background} stopOpacity={0.92} />
              </LinearGradient>
            </Defs>
            <Rect width="1" height="1" fill="url(#step-shade)" />
          </Svg>
        </View>
        <ThemedText style={[styles.photoTime, { color: theme.gold }]}>{veiled ? '✦' : formatTime(step.start)}</ThemedText>
        <View style={styles.photoFoot}>
          {veiled ? (
            <>
              <ThemedText style={styles.photoTitle}>Une étape encore voilée</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">Dévoilée {inTime(Math.max(revealAt(route, step, mode), now), now)}</ThemedText>
            </>
          ) : (
            <>
              <ThemedText style={styles.photoTitle} numberOfLines={2}>{step.title}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>{place(step)}</ThemedText>
            </>
          )}
        </View>
      </Pressable>
    </View>
  );
}

function Gauge({ gauge }: { gauge: Complicity }) {
  const theme = useTheme();
  return (
    <View style={[styles.gauge, { backgroundColor: theme.backgroundElement, borderColor: theme.line }]}>
      <View style={styles.sectionHead}>
        <ThemedText type="eyebrow">Niveau de complicité</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {gauge.lived} soirée{gauge.lived > 1 ? 's' : ''} vécue{gauge.lived > 1 ? 's' : ''}
        </ThemedText>
      </View>
      <ThemedText style={[styles.level, { color: theme.gold }]}>{gauge.name}</ThemedText>
      <View style={[styles.track, { backgroundColor: theme.line }]}>
        <View style={[styles.fill, { width: `${Math.max(gauge.progress, 0.03) * 100}%`, backgroundColor: theme.accent }]} />
      </View>
      <ThemedText type="small" themeColor="textSecondary">
        {gauge.next ? `Encore ${gauge.next.left} soirée${gauge.next.left > 1 ? 's' : ''} à deux pour « ${gauge.next.name} »` : 'Vous avez atteint le sommet de la complicité.'}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  placeholder: { height: 196 },
  cardBlock: { gap: Spacing.three },
  member: { minHeight: 196, justifyContent: 'space-between', gap: Spacing.three },
  pitch: { gap: Spacing.two },
  cardClue: { fontSize: 17, lineHeight: 23 },
  cardFoot: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: Spacing.three },
  cardColumn: { flexShrink: 1, gap: Spacing.one },
  cardRight: { alignItems: 'flex-end' },
  cardDay: { fontFamily: Fonts.heading, fontSize: 21, lineHeight: 26 },
  cardFigure: { fontFamily: Fonts.sansBold, fontSize: 14, lineHeight: 26, letterSpacing: 1.6 },
  status: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two + 2, paddingHorizontal: Spacing.one },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { flex: 1 },
  section: { gap: Spacing.three },
  sectionHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: Spacing.two },
  call: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, padding: Spacing.three, borderRadius: Radius.tile, borderWidth: 1 },
  callIcon: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  callText: { flex: 1, gap: 2 },
  photoCard: { aspectRatio: 16 / 10, maxHeight: 260, borderRadius: Radius.tile, borderWidth: 1, overflow: 'hidden', justifyContent: 'space-between' },
  photoTime: { fontFamily: Fonts.sansBold, fontSize: 14, lineHeight: 18, letterSpacing: 1.2, margin: Spacing.three + 2 },
  photoFoot: { padding: Spacing.three + 2, gap: 2 },
  photoTitle: { fontFamily: Fonts.heading, fontSize: 22, lineHeight: 27 },
  gauge: { gap: Spacing.two, padding: Spacing.three + 2, borderRadius: Radius.tile, borderWidth: 1 },
  level: { fontFamily: Fonts.headingItalic, fontSize: 24, lineHeight: 30 },
  track: { height: 3, borderRadius: 2, overflow: 'hidden', marginVertical: Spacing.one },
  fill: { height: '100%', borderRadius: 2 },
  links: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', columnGap: Spacing.four },
  pressed: { opacity: 0.8 },
});
