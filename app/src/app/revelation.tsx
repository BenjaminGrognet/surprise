import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Image, Linking, StyleSheet, View } from 'react-native';

import { GhostButton, PrimaryButton, PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { EveningsNav } from '@/components/evenings-nav';
import { Countdown, PageCard } from '@/components/intrigue-card';
import { Organiser } from '@/components/organiser';
import { imageUri, place } from '@/components/route-result';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Veil } from '@/components/veil';
import { Radius, Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { keptEvening, keptSecretTitle, type EveningHistoryRow } from '@/lib/account';
import { PassagerInvite } from '@/components/passager-invite';
import { RevealModePicker } from '@/components/reveal-mode';
import { useNow } from '@/hooks/use-now';
import { useTheme } from '@/hooks/use-theme';
import { getSoireeState, type SoireeRoute, type SoireeStep } from '@/lib/api';
import { cluesFor, inTime, nextClue, revealAt, revealMode, shownClues, stepRevealed, type RevealMode } from '@/lib/clues';
import { nearStep } from '@/lib/arrival';
import { arrivedSteps, markArrived } from '@/lib/local-store';
import { askNotify, notifyState, scheduleReveals, type NotifyState } from '@/lib/notifications';
import { formatTime, isoDay, longDay } from '@/lib/dates';
import { curtainFalls } from '@/lib/souvenirs';

// "La Révélation": the kept evening seen from each account of the couple. The instigateur has the whole timed
// roadmap; the passager only gets riddles, and a veiled programme that lifts step by step.
export default function RevelationScreen() {
  const { soiree, route: index } = useLocalSearchParams<{ soiree?: string; route?: string }>();
  const [route, setRoute] = useState<SoireeRoute | null | 'missing' | 'offline'>(null);
  const [attempt, setAttempt] = useState(0);
  const [kept, setKept] = useState<string | null>(null);
  const { role } = useCouple();
  const [evening, setEvening] = useState<EveningHistoryRow | null>(null);
  const loadEvening = useCallback(() => {
    if (soiree && index !== undefined) keptEvening(soiree, Number(index)).then(setEvening).catch(() => {});
  }, [soiree, index]);

  const lost = !soiree || index === undefined;

  useEffect(() => {
    if (!soiree || index === undefined) return;
    // Leafing to another evening: the previous one's roadmap goes before the next is unsealed.
    setRoute(null);
    setKept(null);
    setEvening(null);
    getSoireeState(soiree)
      .then((s) => setRoute(s.routes.find((r) => String(r.index) === index) ?? 'missing'))
      // Only a 404 means the evening is gone; anything else is the server not answering, worth another try.
      .catch((e: Error) => setRoute(e.message.endsWith(': 404') ? 'missing' : 'offline'));
    // The name fixed when it was kept; the one the server would give its steps today, for older evenings.
    keptSecretTitle(soiree, Number(index)).then(setKept).catch(() => {});
    loadEvening();
  }, [soiree, index, loadEvening, attempt]);

  if (!lost && route === null) {
    return (
      <Screen>
        <ThemedText themeColor="textSecondary">On décachette l&apos;enveloppe…</ThemedText>
      </Screen>
    );
  }
  if (route === 'offline') {
    return (
      <Screen>
        <PageCard back title="L'enveloppe reste close" text="Le serveur ne répond pas pour l'instant. Votre soirée est bien gardée." />
        <PrimaryButton wide onPress={() => { setRoute(null); setAttempt((n) => n + 1); }}>Réessayer</PrimaryButton>
      </Screen>
    );
  }
  if (lost || route === null || route === 'missing') {
    return (
      <Screen>
        <PageCard back title="Intrigue introuvable" text="Cette soirée n'existe plus sur le serveur." />
        <PrimaryLink href="/">Retour au tableau</PrimaryLink>
      </Screen>
    );
  }

  const secretTitle = kept ?? route.secret_title;
  const mode = revealMode(evening?.reveal_mode);
  return (
    <Screen gap={Spacing.four}>
      <EveningsNav soiree={soiree!} route={route.index} />
      {role === 'instigateur' ? (
        <>
          <Organiser route={route} pageName={soiree!} secretTitle={secretTitle} mode={mode} onRoute={setRoute} />
          {evening && (!evening.day || evening.day >= isoDay(new Date())) ? (
            <>
              <PassagerInvite evening={evening} onChange={loadEvening} />
              <RevealModePicker key={evening.reveal_mode} evening={evening} onChange={loadEvening} />
            </>
          ) : null}
        </>
      ) : (
        <Surprised route={route} secretTitle={secretTitle} mode={mode} evening={`${soiree}:${route.index}`} />
      )}
      <BookLink route={route} soiree={soiree!} />
    </Screen>
  );
}

// The evening's last step begun, its Livre des Secrets opens, for both.
function BookLink({ route, soiree }: { route: SoireeRoute; soiree: string }) {
  const now = useNow();
  if (!curtainFalls(route, now)) return null;
  return (
    <View style={styles.bookLink}>
      <TextLink href={{ pathname: '/livre', params: { soiree, route: String(route.index) } }}>
        Le rideau tombe : ouvrir le Livre des Secrets →
      </TextLink>
    </View>
  );
}

function Surprised({ route, secretTitle, mode, evening }: { route: SoireeRoute; secretTitle: string; mode: RevealMode; evening: string }) {
  const now = useNow();
  const start = Date.parse(route.start);
  const clues = cluesFor(route, mode);
  const steps = [...route.steps, ...(route.night ? [route.night] : [])];
  const [arrived, setArrived] = useState<string[]>([]);
  const [notify, setNotify] = useState<NotifyState>('unsupported');

  useEffect(() => {
    arrivedSteps(evening).then(setArrived);
  }, [evening]);

  // The clues and veils still to come become notifications on this phone, once allowed; redone when the mode changes.
  useEffect(() => {
    notifyState().then(setNotify).catch(() => {});
  }, []);
  useEffect(() => {
    if (notify === 'granted') scheduleReveals(evening, route, mode, secretTitle).catch(() => {});
  }, [notify, evening, route, mode, secretTitle]);

  function arrive(step: SoireeStep) {
    setArrived((a) => [...a, step.id]);
    markArrived(evening, step.id);
  }

  return (
    <>
      <PageCard back badge="Passager" title={secretTitle}>
        <ThemedText type="eyebrow">La révélation · {longDay(route.day)}</ThemedText>
        {now < start ? <Countdown to={start} now={now} /> : null}
      </PageCard>

      <Clues clues={clues} now={now} title="Vos indices" />

      {notify === 'ask' ? (
        <View style={styles.block}>
          <ThemedText type="small" themeColor="textSecondary">Soyez prévenu(e) à chaque indice, sans rouvrir l&apos;application.</ThemedText>
          <GhostButton onPress={() => askNotify().then(setNotify)}>Activer les rappels</GhostButton>
        </View>
      ) : null}

      <View style={styles.block}>
        <ThemedText type="eyebrow">Le programme</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {mode === 'veille'
            ? 'Le programme se dévoile la veille.'
            : mode === 'arrivee'
              ? 'Chaque étape se dévoile quand vous y êtes.'
              : 'Chaque étape se dévoile un quart d’heure avant son heure.'}
        </ThemedText>
        {steps.map((step, i) => (
          <VeiledStep
            key={i}
            route={route}
            step={step}
            number={i + 1}
            now={now}
            mode={mode}
            open={stepRevealed(route, step, now, mode, arrived)}
            onArrive={() => arrive(step)}
          />
        ))}
      </View>
    </>
  );
}

function Clues({ clues, now, title }: { clues: ReturnType<typeof cluesFor>; now: number; title: string }) {
  const theme = useTheme();
  const shown = shownClues(clues, now);
  const next = nextClue(clues, now);
  return (
    <View style={[styles.clues, { borderColor: theme.line, backgroundColor: theme.backgroundElement }]}>
      <ThemedText type="eyebrow">{title}</ThemedText>
      {shown.map((c) => (
        <View key={c.text} style={styles.clue}>
          <ThemedText type="clue" themeColor="gold">✦</ThemedText>
          <ThemedText type="clue" style={styles.clueText}>{c.text}</ThemedText>
        </View>
      ))}
      {next ? (
        <View style={styles.clue}>
          <ThemedText type="clue" themeColor="textSecondary">✦</ThemedText>
          <View style={styles.clueText}>
            <Veil widths={['85%', '55%']} />
            <ThemedText type="small" themeColor="textSecondary">Prochain indice {inTime(next.at, now)}</ThemedText>
          </View>
        </View>
      ) : null}
    </View>
  );
}

function VeiledStep({
  route, step, number, now, mode, open, onArrive,
}: { route: SoireeRoute; step: SoireeStep; number: number; now: number; mode: RevealMode; open: boolean; onArrive: () => void }) {
  const theme = useTheme();
  const [checking, setChecking] = useState(false);
  const [far, setFar] = useState(false);
  const maps = `https://www.google.com/maps/search/?api=1&query=${step.lat},${step.lon}`;
  const at = Math.max(revealAt(route, step, mode), 0);

  async function arrive() {
    setChecking(true);
    setFar(false);
    const near = await nearStep(step);
    setChecking(false);
    if (near === false) setFar(true);
    else onArrive();
  }

  return (
    <View style={[styles.step, { borderColor: open ? theme.accentSoft : theme.line }]}>
      <View style={[styles.thumb, { backgroundColor: theme.backgroundSelected }]}>
        {step.image_url ? <Image source={{ uri: imageUri(step.image_url) }} blurRadius={open ? 0 : 28} style={styles.thumbImg} /> : null}
        {open ? null : <ThemedText style={[styles.seal, { color: theme.cream }]}>?</ThemedText>}
      </View>
      <View style={styles.stepBody}>
        <ThemedText type="eyebrow" themeColor={open ? 'gold' : 'textSecondary'}>
          {step.role === 'nuit' ? 'La nuit' : `Étape ${number}`}{open ? ` · ${formatTime(step.start)}` : ''}
        </ThemedText>
        {open ? (
          <>
            <ThemedText type="smallBold">{step.title}</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">{place(step)}</ThemedText>
            <TextButton onPress={() => Linking.openURL(maps)}>Voir sur la carte ↗</TextButton>
          </>
        ) : (
          <>
            <Veil widths={['90%', '60%']} />
            <ThemedText type="small" themeColor="textSecondary">
              {mode === 'arrivee' ? `Scellée jusqu'à votre arrivée (ou ${formatTime(step.start)})` : `Dévoilée ${inTime(at, now)}`}
            </ThemedText>
            {mode === 'arrivee' ? (
              <TextButton onPress={arrive}>{checking ? 'Vérification…' : 'Je suis arrivé(e) →'}</TextButton>
            ) : null}
            {far ? <ThemedText type="small" themeColor="danger">Vous semblez encore loin : rapprochez-vous du lieu.</ThemedText> : null}
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bookLink: { alignItems: 'center' },
  block: { gap: Spacing.three },
  clues: { gap: Spacing.three, padding: Spacing.four, borderRadius: Radius.card, borderWidth: 1 },
  clue: { flexDirection: 'row', gap: Spacing.three, alignItems: 'flex-start' },
  clueText: { flex: 1, gap: Spacing.two },
  step: { flexDirection: 'row', gap: Spacing.three, padding: Spacing.two + 2, borderRadius: Radius.tile, borderWidth: 1 },
  thumb: { width: 84, height: 84, borderRadius: 16, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  thumbImg: { ...StyleSheet.absoluteFill },
  seal: { fontSize: 28, lineHeight: 34, opacity: 0.8 },
  stepBody: { flex: 1, gap: Spacing.one, justifyContent: 'center' },
});
