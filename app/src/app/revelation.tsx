import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, View } from 'react-native';

import { PrimaryLink, TextButton } from '@/components/buttons';
import { Countdown, IntrigueCard } from '@/components/intrigue-card';
import { imageUri, place, RouteResult } from '@/components/route-result';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useNow } from '@/hooks/use-now';
import { useTheme } from '@/hooks/use-theme';
import { getSoireeState, type SoireeRoute, type SoireeStep } from '@/lib/api';
import { cluesFor, inTime, nextClue, shownClues, stepRevealed } from '@/lib/clues';
import { formatTime, longDay } from '@/lib/dates';
import { rememberedRole, rememberRole, type Role } from '@/lib/local-store';

// "La Révélation": the kept evening seen from each side. Whoever organises it has the whole timed
// roadmap; whoever is surprised only gets riddles, and a veiled programme that lifts step by step.
export default function RevelationScreen() {
  const { soiree, route: index } = useLocalSearchParams<{ soiree?: string; route?: string }>();
  const [route, setRoute] = useState<SoireeRoute | null | 'missing'>(null);
  const [role, setRole] = useState<Role | null | 'loading'>('loading');

  const lost = !soiree || index === undefined;

  useEffect(() => {
    if (!soiree || index === undefined) return;
    getSoireeState(soiree)
      .then((s) => setRoute(s.routes.find((r) => String(r.index) === index) ?? 'missing'))
      .catch(() => setRoute('missing'));
    rememberedRole(soiree, Number(index)).then(setRole);
  }, [soiree, index]);

  if (!lost && (route === null || role === 'loading')) {
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

  const pick = (r: Role) => {
    setRole(r);
    rememberRole(soiree!, route.index, r);
  };

  if (!role || role === 'loading') return <ChooseRole route={route} onPick={pick} />;
  return (
    <Screen gap={Spacing.four}>
      {role === 'organisateur' ? <Organiser route={route} /> : <Surprised route={route} />}
      <TextButton onPress={() => setRole(null)}>Changer de rôle sur ce téléphone</TextButton>
    </Screen>
  );
}

function ChooseRole({ route, onPick }: { route: SoireeRoute; onPick: (role: Role) => void }) {
  return (
    <Screen gap={Spacing.four}>
      <IntrigueCard>
        <ThemedText type="eyebrow" style={styles.center}>{longDay(route.day)}</ThemedText>
        <ThemedText type="title" style={styles.center}>Qui tient ce téléphone ?</ThemedText>
        <ThemedText themeColor="textSecondary" style={styles.center}>
          Chacun choisit sur son propre téléphone. Le choix reste sur cet appareil.
        </ThemedText>
      </IntrigueCard>
      <RoleOption
        emoji="🗝️"
        title="J'organise"
        text="Je vois toute la feuille de route, minute par minute, avec les réservations à faire."
        onPress={() => onPick('organisateur')}
      />
      <RoleOption
        emoji="✦"
        title="Je me laisse surprendre"
        text="Je ne reçois que des indices, dévoilés peu à peu jusqu'au jour J."
        onPress={() => onPick('surpris')}
      />
      <TextButton onPress={() => router.back()}>← Retour</TextButton>
    </Screen>
  );
}

function RoleOption({ emoji, title, text, onPress }: { emoji: string; title: string; text: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} style={[styles.role, { borderColor: theme.accentSoft, backgroundColor: theme.backgroundElement }]}>
      <ThemedText style={[styles.roleEmoji, { color: theme.accent }]}>{emoji}</ThemedText>
      <View style={styles.roleBody}>
        <ThemedText type="subtitle">{title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{text}</ThemedText>
      </View>
    </Pressable>
  );
}

function Surprised({ route }: { route: SoireeRoute }) {
  const now = useNow();
  const start = Date.parse(route.start);
  const clues = cluesFor(route);
  const steps = [...route.steps, ...(route.night ? [route.night] : [])];
  return (
    <>
      <IntrigueCard>
        <ThemedText type="eyebrow" style={styles.center}>La révélation · {longDay(route.day)}</ThemedText>
        <ThemedText type="title" style={styles.center}>L&apos;Inattendu vous attend…</ThemedText>
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

// The blurred lines that stand for hidden text: nothing of it is sent to the screen.
function Veil({ widths }: { widths: `${number}%`[] }) {
  const theme = useTheme();
  return (
    <View style={styles.veil}>
      {widths.map((w, i) => (
        <View key={i} style={[styles.veilLine, { width: w, backgroundColor: theme.backgroundSelected }]} />
      ))}
    </View>
  );
}

function Organiser({ route }: { route: SoireeRoute }) {
  const theme = useTheme();
  const now = useNow();
  const start = Date.parse(route.start);
  const toBook = [...route.steps, ...(route.night ? [route.night] : [])].filter((s) => s.booking_action === 'reserver' && s.booking_url);
  return (
    <>
      <IntrigueCard>
        <ThemedText type="eyebrow" style={styles.center}>Feuille de route · {longDay(route.day)}</ThemedText>
        <ThemedText type="title" style={styles.center}>{route.title}</ThemedText>
        {now < start ? <Countdown to={start} now={now} /> : null}
        <ThemedText type="small" themeColor="textSecondary" style={styles.center}>
          Vous seul voyez ceci. Votre partenaire ne reçoit que les indices ci-dessous.
        </ThemedText>
      </IntrigueCard>

      {toBook.length ? (
        <View style={[styles.clues, { borderColor: theme.accentSoft, backgroundColor: theme.backgroundElement }]}>
          <ThemedText type="eyebrow">À réserver avant le jour J</ThemedText>
          {toBook.map((s) => (
            <Pressable key={s.title} onPress={() => Linking.openURL(s.booking_url!)} style={styles.bookLine}>
              <ThemedText type="smallBold" themeColor="accentInk">{formatTime(s.start)}</ThemedText>
              <ThemedText type="small" style={styles.clueText}>{s.title}</ThemedText>
              <ThemedText type="smallBold" themeColor="accentInk">Réserver ↗</ThemedText>
            </Pressable>
          ))}
        </View>
      ) : null}

      <Clues clues={cluesFor(route)} now={now} title="Ce que voit votre partenaire" />

      <RouteResult route={route} readOnly />
    </>
  );
}

const styles = StyleSheet.create({
  center: { textAlign: 'center' },
  block: { gap: Spacing.three },
  role: { flexDirection: 'row', gap: Spacing.three, alignItems: 'center', padding: Spacing.four, borderRadius: 22, borderWidth: 1 },
  roleEmoji: { fontSize: 28, lineHeight: 36, width: 36, textAlign: 'center' },
  roleBody: { flex: 1, gap: Spacing.one },
  clues: { gap: Spacing.three, padding: Spacing.four, borderRadius: 22, borderWidth: 1 },
  clue: { flexDirection: 'row', gap: Spacing.three, alignItems: 'flex-start' },
  clueText: { flex: 1, gap: Spacing.two },
  step: { flexDirection: 'row', gap: Spacing.three, padding: Spacing.two + 2, borderRadius: 18, borderWidth: 1 },
  thumb: { width: 84, height: 84, borderRadius: 12, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  thumbImg: { ...StyleSheet.absoluteFill },
  seal: { fontSize: 28, lineHeight: 34, opacity: 0.8 },
  stepBody: { flex: 1, gap: Spacing.one, justifyContent: 'center' },
  veil: { gap: Spacing.two, paddingVertical: Spacing.one },
  veilLine: { height: 10, borderRadius: 5 },
  bookLine: { flexDirection: 'row', gap: Spacing.three, alignItems: 'center' },
});
