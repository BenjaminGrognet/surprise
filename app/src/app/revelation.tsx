import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Linking, StyleSheet, View } from 'react-native';

import { PrimaryLink, TextButton, TextLink } from '@/components/buttons';
import { Countdown, IntrigueCard } from '@/components/intrigue-card';
import { Organiser } from '@/components/organiser';
import { imageUri, place } from '@/components/route-result';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Veil } from '@/components/veil';
import { Spacing } from '@/constants/theme';
import { useCouple } from '@/hooks/use-couple';
import { keptSecretTitle } from '@/lib/account';
import { useNow } from '@/hooks/use-now';
import { useTheme } from '@/hooks/use-theme';
import { getSoireeState, type SoireeRoute, type SoireeStep } from '@/lib/api';
import { cluesFor, inTime, nextClue, shownClues, stepRevealed } from '@/lib/clues';
import { formatTime, longDay } from '@/lib/dates';
import { curtainFalls } from '@/lib/souvenirs';

// "La Révélation": the kept evening seen from each account of the couple. The instigateur has the whole timed
// roadmap; the passager only gets riddles, and a veiled programme that lifts step by step.
export default function RevelationScreen() {
  const { soiree, route: index } = useLocalSearchParams<{ soiree?: string; route?: string }>();
  const [route, setRoute] = useState<SoireeRoute | null | 'missing'>(null);
  const [kept, setKept] = useState<string | null>(null);
  const { role } = useCouple();

  const lost = !soiree || index === undefined;

  useEffect(() => {
    if (!soiree || index === undefined) return;
    getSoireeState(soiree)
      .then((s) => setRoute(s.routes.find((r) => String(r.index) === index) ?? 'missing'))
      .catch(() => setRoute('missing'));
    // The name fixed when it was kept; the one the server would give its steps today, for older evenings.
    keptSecretTitle(soiree, Number(index)).then(setKept).catch(() => {});
  }, [soiree, index]);

  if (!lost && route === null) {
    return (
      <Screen>
        <ThemedText themeColor="textSecondary">On décachette l&apos;enveloppe…</ThemedText>
      </Screen>
    );
  }
  if (lost || route === null || route === 'missing') {
    return (
      <Screen>
        <ThemedText type="title">Intrigue introuvable</ThemedText>
        <ThemedText themeColor="textSecondary">Cette soirée n&apos;existe plus sur le serveur.</ThemedText>
        <PrimaryLink href="/">Retour au tableau</PrimaryLink>
      </Screen>
    );
  }

  const secretTitle = kept ?? route.secret_title;
  return (
    <Screen gap={Spacing.four}>
      {role === 'instigateur' ? (
        <Organiser route={route} pageName={soiree!} secretTitle={secretTitle} />
      ) : (
        <Surprised route={route} secretTitle={secretTitle} />
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

function Surprised({ route, secretTitle }: { route: SoireeRoute; secretTitle: string }) {
  const now = useNow();
  const start = Date.parse(route.start);
  const clues = cluesFor(route);
  const steps = [...route.steps, ...(route.night ? [route.night] : [])];
  return (
    <>
      <IntrigueCard>
        <ThemedText type="eyebrow" style={styles.center}>La révélation · {longDay(route.day)}</ThemedText>
        <ThemedText type="title" style={styles.center}>{secretTitle}</ThemedText>
        {now < start ? <Countdown to={start} now={now} /> : null}
      </IntrigueCard>

      <Clues clues={clues} now={now} title="Vos indices" />

      <View style={styles.block}>
        <ThemedText type="eyebrow">Le programme</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">Chaque étape se dévoile un quart d&apos;heure avant son heure.</ThemedText>
        {steps.map((step, i) => (
          <VeiledStep key={i} step={step} number={i + 1} now={now} />
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
          <ThemedText type="clue" themeColor="accentInk">✦</ThemedText>
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

function VeiledStep({ step, number, now }: { step: SoireeStep; number: number; now: number }) {
  const theme = useTheme();
  const open = stepRevealed(step, now);
  const maps = `https://www.google.com/maps/search/?api=1&query=${step.lat},${step.lon}`;
  return (
    <View style={[styles.step, { borderColor: open ? theme.accentSoft : theme.line }]}>
      <View style={[styles.thumb, { backgroundColor: theme.backgroundSelected }]}>
        {step.image_url ? <Image source={{ uri: imageUri(step.image_url) }} blurRadius={open ? 0 : 28} style={styles.thumbImg} /> : null}
        {open ? null : <ThemedText style={[styles.seal, { color: theme.cream }]}>?</ThemedText>}
      </View>
      <View style={styles.stepBody}>
        <ThemedText type="eyebrow" themeColor={open ? 'accentInk' : 'textSecondary'}>
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
            <ThemedText type="small" themeColor="textSecondary">Dévoilée {inTime(Date.parse(step.start) - 15 * 60_000, now)}</ThemedText>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { textAlign: 'center' },
  bookLink: { alignItems: 'center' },
  block: { gap: Spacing.three },
  clues: { gap: Spacing.three, padding: Spacing.four, borderRadius: 22, borderWidth: 1 },
  clue: { flexDirection: 'row', gap: Spacing.three, alignItems: 'flex-start' },
  clueText: { flex: 1, gap: Spacing.two },
  step: { flexDirection: 'row', gap: Spacing.three, padding: Spacing.two + 2, borderRadius: 18, borderWidth: 1 },
  thumb: { width: 84, height: 84, borderRadius: 12, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  thumbImg: { ...StyleSheet.absoluteFill },
  seal: { fontSize: 28, lineHeight: 34, opacity: 0.8 },
  stepBody: { flex: 1, gap: Spacing.one, justifyContent: 'center' },
});
