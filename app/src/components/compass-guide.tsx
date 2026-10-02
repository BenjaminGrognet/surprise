import { Linking, StyleSheet, View } from 'react-native';

import { PrimaryButton } from '@/components/buttons';
import { place } from '@/components/route-result';
import { ThemedText } from '@/components/themed-text';
import { Icon } from '@/components/ui-icons';
import { Fonts, Radius, Spacing } from '@/constants/theme';
import { useNow } from '@/hooks/use-now';
import { useTheme } from '@/hooks/use-theme';
import type { SoireeRoute, SoireeStep } from '@/lib/api';
import { inTime } from '@/lib/clues';
import { formatTime, isoDay } from '@/lib/dates';

// On foot up to this hop, as the evening was composed (surprise.parcours WALK_KM) and as the roadmap's hops say.
const WALK_KM = 1.3;

// Google Maps from where the phone is: on foot or by metro as the evening was planned; to the first step, its own pick.
function directions(step: SoireeStep, first: boolean) {
  const mode = first ? '' : `&travelmode=${step.distance_km <= WALK_KM ? 'walking' : 'transit'}`;
  return `https://www.google.com/maps/dir/?api=1&destination=${step.lat},${step.lon}${mode}`;
}

// When to set off for a step: its hop from the one before, or, for the first, only the time left.
function departure(step: SoireeStep, first: boolean, now: number) {
  if (first) return `Rendez-vous ${inTime(Date.parse(step.start), now)}`;
  const way = `${step.distance_km <= WALK_KM ? 'À pied' : 'En métro'} · ${step.travel_minutes} min`;
  const leave = Date.parse(step.start) - step.travel_minutes * 60_000;
  return now < leave ? `${way} · partez à ${formatTime(new Date(leave).toISOString())}` : `${way} · c'est l'heure de partir`;
}

// The compass on the day itself: the step under way, the next one and when to leave for it, and the way there in one
// touch. From the morning of the day until the last step is over, past midnight too.
export function CompassGuide({ route }: { route: SoireeRoute }) {
  const theme = useTheme();
  const now = useNow();
  const steps = [...route.steps, ...(route.night ? [route.night] : [])];
  if (steps.every((s) => Date.parse(s.end) <= now)) return null;
  if (route.day !== isoDay(new Date(now)) && now < Date.parse(route.start)) return null;
  const current = steps.find((s) => Date.parse(s.start) <= now && now < Date.parse(s.end));
  const next = steps.find((s) => Date.parse(s.start) > now);
  const first = !!next && next === steps[0];
  return (
    <View style={[styles.card, { backgroundColor: theme.backgroundElement, borderColor: theme.accentSoft }]}>
      <View style={styles.head}>
        <Icon name="boussole" size={18} color={theme.accent} />
        <ThemedText type="eyebrow">La boussole · jour J</ThemedText>
      </View>
      {current ? <Leg kicker={`En ce moment · jusqu'à ${formatTime(current.end)}`} step={current} /> : null}
      {next ? (
        <>
          {current ? <View style={[styles.rule, { backgroundColor: theme.line }]} /> : null}
          <Leg kicker={`${current ? 'Ensuite' : first ? 'Premier rendez-vous' : 'Prochain rendez-vous'} · ${formatTime(next.start)}`} step={next} />
          <ThemedText type="small" themeColor="textSecondary">{departure(next, first, now)}</ThemedText>
          <PrimaryButton wide onPress={() => Linking.openURL(directions(next, first))}>Itinéraire ↗</PrimaryButton>
        </>
      ) : (
        <ThemedText type="small" themeColor="textSecondary">Dernière étape de la soirée : rien ne presse.</ThemedText>
      )}
    </View>
  );
}

function Leg({ kicker, step }: { kicker: string; step: SoireeStep }) {
  return (
    <View style={styles.leg}>
      <ThemedText type="eyebrow" themeColor="gold">{kicker}</ThemedText>
      <ThemedText style={styles.title}>{step.title}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">{place(step)}</ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 1, borderRadius: Radius.card, padding: Spacing.four - 2, gap: Spacing.three },
  head: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  leg: { gap: Spacing.one },
  title: { fontFamily: Fonts.heading, fontSize: 23, lineHeight: 28 },
  rule: { height: 1 },
});
